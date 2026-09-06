package dataexec

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
 "strconv"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket="/run/layersentryd/data-exec.sock"
const maxMessage=2<<20
var labelSources=map[string]bool{"/var/lib/redis":true,"/var/lib/valkey":true,"/var/www":true,"/var/lib/tomcat":true,"/var/lib/layersentryd/apps":true}
type request struct{Path string `json:"path"`;Args []string `json:"args"`}
type response struct{Stdout string `json:"stdout,omitempty"`;Stderr string `json:"stderr,omitempty"`;ExitCode int `json:"exit_code"`;Error string `json:"error,omitempty"`}
type Client struct{Socket string;Timeout time.Duration}
func NewClient(socket string)Client{if socket==""{socket=DefaultSocket};return Client{Socket:socket,Timeout:2*time.Minute}}
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("data-label helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}
func Serve(ctx context.Context,socketPath,group string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if group==""{group="layersentry"};if runner==nil{return errors.New("data helper runner nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe data helper socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket data helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(group);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(3*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid data helper request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};res,runErr:=runner.Run(context.Background(),req.Path,req.Args...);out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}
func validate(path string,args []string)error{switch path{case "/usr/sbin/semanage":if len(args)!=5||args[0]!="fcontext"||(args[1]!="-a"&&args[1]!="-m")||args[2]!="-e"||!labelSources[args[3]]||!safeExternal(args[4]){return errors.New("data SELinux equivalence rejected")};return nil;case "/usr/sbin/restorecon":if len(args)!=2||args[0]!="-RF"||!safeExternal(args[1]){return errors.New("data restorecon rejected")};return nil};return errors.New("data helper executable rejected")}
func safeExternal(p string)bool{if !filepath.IsAbs(p)||filepath.Clean(p)!=p{return false};for _,root:=range []string{"/data","/srv","/opt/layersentry-data"}{rel,err:=filepath.Rel(root,p);if err==nil&&rel!="."&&rel!=".."&&!strings.HasPrefix(rel,".."+string(filepath.Separator)){return true}};return false}
