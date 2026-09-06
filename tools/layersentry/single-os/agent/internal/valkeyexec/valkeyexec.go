package valkeyexec

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"os/user"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket = "/run/layersentryd/valkey-exec.sock"
const maxMessage = 2 << 20

var uuidPart = `[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}`
var stageRE = regexp.MustCompile(`^/run/layersentryd/(valkey-staging|backup-staging)/` + uuidPart + `/([0-9a-fA-F-]+-valkey(-restore)?\.rdb|valkey\.conf)$`)
var dataRE = regexp.MustCompile(`^/var/lib/valkey/layersentry-` + uuidPart + `(/dump\.rdb)?$`)
var confRE = regexp.MustCompile(`^/etc/valkey/layersentry-` + uuidPart + `\.conf$`)
var nevraRE = regexp.MustCompile(`^valkey-[A-Za-z0-9._+~:-]+$`)

type request struct{ Path string `json:"path"`; Args []string `json:"args"` }
type response struct{ Stdout string `json:"stdout,omitempty"`; Stderr string `json:"stderr,omitempty"`; ExitCode int `json:"exit_code"`; Error string `json:"error,omitempty"` }

type Client struct{ Socket string; Timeout time.Duration }
func NewClient(socket string) Client { if socket==""{socket=DefaultSocket}; return Client{Socket:socket,Timeout:3*time.Minute} }
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};if c.Timeout<=0{c.Timeout=3*time.Minute};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("Valkey helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}

func Serve(ctx context.Context,socketPath,groupName string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if groupName==""{groupName="layersentry"};if runner==nil{return errors.New("Valkey helper runner is nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe Valkey helper socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket Valkey helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(groupName);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(5*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid Valkey helper request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};res,runErr:=runner.Run(context.Background(),req.Path,req.Args...);out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}

func validate(path string,args []string)error{if len(args)>32{return errors.New("too many Valkey helper arguments")};for _,a:=range args{if len(a)>4096||strings.ContainsAny(a,"\x00\r\n"){return errors.New("unsafe Valkey helper argument")}};switch path{case "/usr/bin/dnf":return validateDNF(args);case "/usr/bin/systemctl":return validateSystemctl(args);case "/usr/bin/rpm":if len(args)==2&&args[0]=="-q"&&args[1]=="valkey"{return nil};case "/usr/bin/install":return validateInstall(args);case "/usr/sbin/restorecon":return validateRestorecon(args)};return errors.New("Valkey privileged action rejected")}
func validateDNF(args []string)error{if len(args)==4&&args[0]=="-q"&&args[1]=="config-manager"&&args[2]=="--dump"&&args[3]=="appstream"{return nil};if len(args)>=8&&args[0]=="-q"&&args[1]=="repoquery"&&args[2]=="--latest-limit"&&args[3]=="1"&&args[4]=="--qf"&&args[len(args)-1]=="valkey"{for _,a:=range args[6:len(args)-1]{if a!="--repoid=appstream"{return errors.New("Valkey repoquery repository rejected")}};return nil};if len(args)==6&&args[0]=="-y"&&args[1]=="--setopt=install_weak_deps=False"&&args[2]=="--disablerepo=*"&&args[3]=="--enablerepo=appstream"&&args[4]=="install"&&nevraRE.MatchString(args[5]){return nil};if len(args)==3&&args[0]=="-y"&&args[1]=="remove"&&args[2]=="valkey"{return nil};return errors.New("Valkey DNF grammar rejected")}
func validateSystemctl(args []string)error{if len(args)<2{return errors.New("Valkey systemctl action missing")};allowed:=map[string]bool{"start":true,"stop":true,"restart":true,"enable":true,"disable":true,"is-active":true,"is-enabled":true};if !allowed[args[0]]{return errors.New("Valkey systemctl action rejected")};for _,a:=range args[1:]{if a=="--now"||a=="--quiet"{continue};if a!="valkey.service"{return errors.New("Valkey systemctl unit rejected")}};return nil}
func validateRestorecon(args []string)error{if len(args)<2||len(args)>3||(args[0]!="-F"&&args[0]!="-RF"){return errors.New("Valkey restorecon grammar rejected")};for _,p:=range args[1:]{if p=="/etc/valkey/valkey.conf"||confRE.MatchString(p){if args[0]!="-F"{return errors.New("Valkey config restorecon must be non-recursive")};continue};if dataRE.MatchString(p){continue};return errors.New("Valkey restorecon path rejected")};return nil}
func validateInstall(args []string)error{if len(args)==5&&args[0]=="--directory"&&args[1]=="--mode=0750"&&args[2]=="--owner=valkey"&&args[3]=="--group=valkey"&&dataRE.MatchString(args[4])&&!strings.HasSuffix(args[4],"/dump.rdb"){return nil};if len(args)!=5{return errors.New("Valkey install grammar rejected")};mode,owner,group,src,dst:=args[0],args[1],args[2],args[3],args[4];switch{case mode=="--mode=0640"&&owner=="--owner=root"&&group=="--group=valkey"&&strings.HasSuffix(src,"/valkey.conf")&&stageRE.MatchString(src)&&confRE.MatchString(dst):return safeExisting(src);case mode=="--mode=0600"&&owner=="--owner=layersentry"&&group=="--group=layersentry"&&dataRE.MatchString(src)&&strings.HasSuffix(src,"/dump.rdb")&&stageRE.MatchString(dst)&&strings.HasSuffix(dst,"-valkey.rdb"):return safeNew(dst);case mode=="--mode=0600"&&owner=="--owner=valkey"&&group=="--group=valkey"&&stageRE.MatchString(src)&&strings.HasSuffix(src,"-valkey-restore.rdb")&&dataRE.MatchString(dst)&&strings.HasSuffix(dst,"/dump.rdb"):return safeExisting(src)};return errors.New("Valkey install path/ownership rejected")}
func safeParent(path string)error{fi,err:=os.Lstat(path);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&0002!=0{return errors.New("unsafe Valkey staging directory")};return nil}
func safeExisting(path string)error{if err:=safeParent(filepath.Dir(path));err!=nil{return err};fi,err:=os.Lstat(path);if err!=nil{return err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()||fi.Mode().Perm()&0002!=0{return errors.New("unsafe Valkey source file")};return nil}
func safeNew(path string)error{if err:=safeParent(filepath.Dir(path));err!=nil{return err};if _,err:=os.Lstat(path);err==nil{return errors.New("Valkey destination already exists")}else if !errors.Is(err,os.ErrNotExist){return err};return nil}
