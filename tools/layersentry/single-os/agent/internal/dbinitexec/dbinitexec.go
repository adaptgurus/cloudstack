package dbinitexec

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

const DefaultSocket="/run/layersentryd/dbinit-exec.sock"
const maxMessage=2<<20
var safeDataRE=regexp.MustCompile(`^/(data|srv|opt/layersentry-data|var/lib/mysql)(/[A-Za-z0-9_.-]+)+$`)
type request struct{Path string `json:"path"`;Args []string `json:"args"`}
type response struct{Stdout string `json:"stdout,omitempty"`;Stderr string `json:"stderr,omitempty"`;ExitCode int `json:"exit_code"`;Error string `json:"error,omitempty"`}
type Client struct{Socket string;Timeout time.Duration}
func NewClient(socket string)Client{if socket==""{socket=DefaultSocket};return Client{Socket:socket,Timeout:5*time.Minute}}
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("database init helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}
func Serve(ctx context.Context,socketPath,group string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if group==""{group="layersentry"};if runner==nil{return errors.New("database init helper runner is nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe database init socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket database init helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(group);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(8*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid database init request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};res,runErr:=runner.Run(context.Background(),req.Path,req.Args...);out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}
func validate(path string,args []string)error{if len(args)>16{return errors.New("too many database init arguments")};for _,a:=range args{if len(a)>4096||strings.ContainsAny(a,"\x00\r\n"){return errors.New("unsafe database init argument")}};switch path{case "/usr/libexec/mysqld","/usr/sbin/mysqld":return validateMySQLInit(args);case "/usr/bin/mariadb-install-db":return validateMariaInit(args);case "/usr/sbin/semanage":return validateSemanage(args);case "/usr/sbin/restorecon":return validateRestorecon(args)};return errors.New("database initialization executable rejected")}
func validateMySQLInit(args []string)error{if len(args)!=3||args[0]!="--initialize-insecure"||args[1]!="--user=mysql"||!strings.HasPrefix(args[2],"--datadir="){return errors.New("mysqld initialization grammar rejected")};return validateDataPath(strings.TrimPrefix(args[2],"--datadir="))}
func validateMariaInit(args []string)error{if len(args)!=4||args[0]!="--user=mysql"||!strings.HasPrefix(args[1],"--datadir=")||args[2]!="--auth-root-authentication-method=socket"||args[3]!="--skip-test-db"{return errors.New("mariadb-install-db grammar rejected")};return validateDataPath(strings.TrimPrefix(args[1],"--datadir="))}
func validateSemanage(args []string)error{if len(args)==5&&args[0]=="fcontext"&&(args[1]=="-a"||args[1]=="-m")&&args[2]=="-e"&&args[3]=="/var/lib/mysql"{return validateDataRoot(args[4])};if len(args)==5&&args[0]=="fcontext"&&(args[1]=="-a"||args[1]=="-m")&&args[2]=="-t"&&args[3]=="mysqld_log_t"{pattern:=args[4];if !strings.HasSuffix(pattern,"(/.*)?"){return errors.New("database log SELinux pattern rejected")};return validateDataRoot(strings.TrimSuffix(pattern,"(/.*)?"))};return errors.New("SELinux database fcontext grammar rejected")}
func validateRestorecon(args []string)error{if len(args)!=2||args[0]!="-RF"{return errors.New("database restorecon grammar rejected")};return validateDataRoot(args[1])}
func validateDataPath(path string)error{if err:=validateDataRoot(filepath.Dir(path));err!=nil{return err};if filepath.Base(path)!="data"{return errors.New("database datadir must be a data child directory")};return nil}
func validateDataRoot(path string)error{if !filepath.IsAbs(path)||filepath.Clean(path)!=path||!safeDataRE.MatchString(path){return errors.New("custom database storage root rejected")};for _,bad:=range []string{"/","/boot","/etc","/usr","/var","/var/lib"}{if path==bad{return errors.New("unsafe database storage root")}};return nil}
