package nodeexec

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

const DefaultSocket="/run/layersentryd/nodejs-exec.sock"
const maxMessage=2<<20
var nodeNEVRA=regexp.MustCompile(`^nodejs-[A-Za-z0-9._+~:-]+$`)
type request struct{Path string `json:"path"`;Args []string `json:"args"`}
type response struct{Stdout string `json:"stdout,omitempty"`;Stderr string `json:"stderr,omitempty"`;ExitCode int `json:"exit_code"`;Error string `json:"error,omitempty"`}
type Client struct{Socket string;Timeout time.Duration}
func NewClient(socket string)Client{if socket==""{socket=DefaultSocket};return Client{Socket:socket,Timeout:3*time.Minute}}
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};if c.Timeout<=0{c.Timeout=3*time.Minute};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("Node.js module helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}
func Serve(ctx context.Context,socketPath,groupName string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if groupName==""{groupName="layersentry"};if runner==nil{return errors.New("Node.js helper runner is nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe Node.js helper socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket Node.js helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(groupName);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(5*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid Node.js helper request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};res,runErr:=runner.Run(context.Background(),req.Path,req.Args...);out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}
func validate(path string,args []string)error{if len(args)>32{return errors.New("too many Node.js helper arguments")};for _,a:=range args{if len(a)>4096||strings.ContainsAny(a,"\x00\r\n"){return errors.New("unsafe Node.js helper argument")}};switch path{case "/usr/bin/dnf":return validateDNF(args);case "/usr/bin/rpm":if len(args)==2&&args[0]=="-q"&&args[1]=="nodejs"{return nil}};return errors.New("Node.js privileged action rejected")}
func validateDNF(args []string)error{if len(args)==4&&args[0]=="-q"&&args[1]=="config-manager"&&args[2]=="--dump"&&args[3]=="appstream"{return nil};if len(args)==5&&args[0]=="-q"&&args[1]=="module"&&args[2]=="repoquery"&&args[3]=="--available"&&args[4]=="nodejs:20"{return nil};if len(args)==5&&args[0]=="-q"&&args[1]=="module"&&args[2]=="list"&&args[3]=="--enabled"&&args[4]=="nodejs"{return nil};if len(args)==4&&args[0]=="-y"&&args[1]=="module"&&args[2]=="enable"&&args[3]=="nodejs:20"{return nil};if len(args)==4&&args[0]=="-y"&&args[1]=="module"&&args[2]=="reset"&&args[3]=="nodejs"{return nil};if len(args)==6&&args[0]=="-y"&&args[1]=="--setopt=install_weak_deps=False"&&args[2]=="--disablerepo=*"&&args[3]=="--enablerepo=appstream"&&args[4]=="install"&&nodeNEVRA.MatchString(args[5]){return nil};if len(args)==3&&args[0]=="-y"&&args[1]=="remove"&&args[2]=="nodejs"{return nil};return errors.New("Node.js DNF grammar rejected")}
