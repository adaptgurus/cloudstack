package lvmexec

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net"
    "os"
    "os/exec"
    "os/user"
    "path/filepath"
    "regexp"
    "strconv"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket="/run/layersentryd/lvm-exec.sock"
const maxMessage=2<<20
var lvmNameRE=regexp.MustCompile(`^ls_[a-z0-9_]{1,48}$`)
var sizeRE=regexp.MustCompile(`^[1-9][0-9]*[MGT]$`)
var lvPathRE=regexp.MustCompile(`^/dev/ls_[a-z0-9_]{1,48}/ls_[a-z0-9_]{1,48}$`)
type request struct{Path string `json:"path"`;Args []string `json:"args"`}
type response struct{Stdout string `json:"stdout,omitempty"`;Stderr string `json:"stderr,omitempty"`;ExitCode int `json:"exit_code"`;Error string `json:"error,omitempty"`}
type Client struct{Socket string;Timeout time.Duration}
func NewClient(socket string)Client{if socket==""{socket=DefaultSocket};return Client{Socket:socket,Timeout:3*time.Minute}}
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};if c.Timeout<=0{c.Timeout=3*time.Minute};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("LVM helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}
func Serve(ctx context.Context,socketPath,group string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if group==""{group="layersentry"};if runner==nil{return errors.New("LVM helper runner is nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe LVM socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket LVM helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(group);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(5*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid LVM helper request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};res,runErr:=runner.Run(context.Background(),req.Path,req.Args...);out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}
func validate(path string,args []string)error{if len(args)>64{return errors.New("too many LVM helper arguments")};for _,a:=range args{if len(a)>4096||strings.ContainsAny(a,"\x00\r\n"){return errors.New("unsafe LVM helper argument")}};switch path{case "/usr/sbin/pvs":return validateObserve(args,"pv");case "/usr/sbin/vgs":return validateObserve(args,"vg");case "/usr/sbin/lvs":return validateObserve(args,"lv");case "/usr/sbin/pvcreate":return validatePVCreate(args);case "/usr/sbin/vgcreate":return validateVGMutation(args);case "/usr/sbin/vgextend":return validateVGMutation(args);case "/usr/sbin/lvcreate":return validateLVCreate(args);case "/usr/sbin/mkfs.xfs":return validateMkfs(args,"-f");case "/usr/sbin/mkfs.ext4":return validateMkfs(args,"-F");case "/usr/sbin/blkid":return validateBlkid(args);case "/usr/bin/findmnt":return validateFindmnt(args);case "/usr/bin/mount":return validateMount(args)};return errors.New("LVM privileged executable rejected")}
func validateObserve(args []string,kind string)error{if len(args)!=4||args[0]!="--noheadings"||args[1]!="-o"{return errors.New("LVM observation grammar rejected")};switch kind{case "pv":if args[2]!="vg_name"||!stableDevice(args[3]){return errors.New("pvs request rejected")};case "vg":if args[2]!="vg_name"||!lvmNameRE.MatchString(args[3]){return errors.New("vgs request rejected")};case "lv":if args[2]!="lv_name"||!lvPathRE.MatchString(args[3]){return errors.New("lvs request rejected")}};return nil}
func validatePVCreate(args []string)error{if len(args)!=2||args[0]!="-y"||!stableDevice(args[1]){return errors.New("pvcreate request rejected")};return requireNonRootDevice(args[1])}
func validateVGMutation(args []string)error{if len(args)<2||!lvmNameRE.MatchString(args[0]){return errors.New("VG mutation request rejected")};for _,d:=range args[1:]{if !stableDevice(d){return errors.New("VG device must use /dev/disk/by-* identity")};if err:=requireNonRootDevice(d);err!=nil{return err}};return nil}
func validateLVCreate(args []string)error{if len(args)!=6||args[0]!="-y"||args[1]!="-n"||!lvmNameRE.MatchString(args[2]){return errors.New("lvcreate grammar rejected")};if args[3]=="-L"{if !sizeRE.MatchString(args[4]){return errors.New("lvcreate size rejected")}}else if args[3]=="-l"{if args[4]!="100%FREE"{return errors.New("lvcreate extent request rejected")}}else{return errors.New("lvcreate allocation mode rejected")};if !lvmNameRE.MatchString(args[5]){return errors.New("lvcreate VG rejected")};return nil}
func validateMkfs(args []string,flag string)error{if len(args)!=2||args[0]!=flag||!lvPathRE.MatchString(args[1]){return errors.New("LVM mkfs request rejected")};return nil}
func validateBlkid(args []string)error{if len(args)!=5||args[0]!="-s"||(args[1]!="TYPE"&&args[1]!="UUID")||args[2]!="-o"||args[3]!="value"||!lvPathRE.MatchString(args[4]){return errors.New("LVM blkid request rejected")};return nil}
func validateFindmnt(args []string)error{if len(args)==4&&args[0]=="-nro"&&args[1]=="UUID"&&args[2]=="--target"&&safeMount(args[3]){return nil};if len(args)==3&&args[0]=="--verify"&&args[1]=="--target"&&safeMount(args[2]){return nil};return errors.New("LVM findmnt request rejected")}
func validateMount(args []string)error{if len(args)!=1||!safeMount(args[0]){return errors.New("LVM mount request rejected")};return nil}
func stableDevice(p string)bool{return strings.HasPrefix(p,"/dev/disk/by-")&&filepath.Clean(p)==p}
func safeMount(p string)bool{if !filepath.IsAbs(p)||filepath.Clean(p)!=p{return false};for _,root:=range []string{"/var/lib/pgsql","/var/lib/mysql","/var/lib/redis","/var/lib/valkey","/var/lib/layersentryd/apps","/var/lib/tomcat","/var/www/html","/srv","/data","/opt/layersentry-data","/var/log/layersentry-services"}{if p==root||strings.HasPrefix(p,root+"/"){return true}};return false}
func requireNonRootDevice(candidate string)error{real,err:=filepath.EvalSymlinks(candidate);if err!=nil{return err};fi,err:=os.Stat(real);if err!=nil{return err};if fi.Mode()&os.ModeDevice==0{return errors.New("LVM PV candidate is not a block device")};rootRaw,err:=exec.Command("/usr/bin/findmnt","-nro","SOURCE","/").Output();if err!=nil{return err};root:=strings.TrimSpace(string(rootRaw));if root==""{return errors.New("root source is empty")};chainRaw,err:=exec.Command("/usr/bin/lsblk","-s","-nrpo","PATH",root).Output();if err!=nil{return err};for _,line:=range strings.Fields(string(chainRaw)){p,_:=filepath.EvalSymlinks(line);if p==""{p=line};if p==real{return errors.New("refusing OS/root/root-parent disk for LVM")}};return nil}
