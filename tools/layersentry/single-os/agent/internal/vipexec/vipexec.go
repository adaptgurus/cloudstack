package vipexec

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
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

const DefaultSocket="/run/layersentryd/vip-exec.sock"
const maxMessage=2<<20
const SecondaryAdd="/usr/libexec/layersentry-vip-secondary-add"
const SecondaryRemove="/usr/libexec/layersentry-vip-secondary-remove"
const VRRPFirewallAdd="/usr/libexec/layersentry-vrrp-firewall-add"
const VRRPFirewallRemove="/usr/libexec/layersentry-vrrp-firewall-remove"
var uuidRE=regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)
var ifaceRE=regexp.MustCompile(`^[A-Za-z0-9_.:-]{1,32}$`)
var nevraRE=regexp.MustCompile(`^keepalived-[A-Za-z0-9._+~:-]+$`)
type request struct{Path string `json:"path"`;Args []string `json:"args"`}
type response struct{Stdout string `json:"stdout,omitempty"`;Stderr string `json:"stderr,omitempty"`;ExitCode int `json:"exit_code"`;Error string `json:"error,omitempty"`}
type Client struct{Socket string;Timeout time.Duration}
func NewClient(socket string)Client{if socket==""{socket=DefaultSocket};return Client{Socket:socket,Timeout:3*time.Minute}}
func(c Client)Run(ctx context.Context,path string,args ...string)(executor.Result,error){if err:=validate(path,args);err!=nil{return executor.Result{},err};cctx,cancel:=context.WithTimeout(ctx,c.Timeout);defer cancel();conn,err:=(&net.Dialer{Timeout:5*time.Second}).DialContext(cctx,"unix",c.Socket);if err!=nil{return executor.Result{},fmt.Errorf("VIP helper unavailable: %w",err)};defer conn.Close();if d,ok:=cctx.Deadline();ok{_ = conn.SetDeadline(d)};if err=json.NewEncoder(conn).Encode(request{Path:path,Args:args});err!=nil{return executor.Result{},err};var out response;if err=json.NewDecoder(io.LimitReader(conn,maxMessage)).Decode(&out);err!=nil{return executor.Result{},err};res:=executor.Result{Stdout:out.Stdout,Stderr:out.Stderr,ExitCode:out.ExitCode};if out.Error!=""{return res,errors.New(out.Error)};return res,nil}
func Serve(ctx context.Context,socketPath,group string,runner executor.Runner)error{if socketPath==""{socketPath=DefaultSocket};if group==""{group="layersentry"};if runner==nil{return errors.New("VIP helper runner nil")};dir:=filepath.Dir(socketPath);fi,err:=os.Lstat(dir);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&01000==0{return errors.New("unsafe VIP helper socket directory")};if old,err:=os.Lstat(socketPath);err==nil{if old.Mode()&os.ModeSocket==0{return errors.New("refusing non-socket VIP helper path")};if err=os.Remove(socketPath);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};addr,err:=net.ResolveUnixAddr("unix",socketPath);if err!=nil{return err};ln,err:=net.ListenUnix("unix",addr);if err!=nil{return err};defer ln.Close();defer os.Remove(socketPath);g,err:=user.LookupGroup(group);if err!=nil{return err};gid,err:=strconv.Atoi(g.Gid);if err!=nil{return err};if err=os.Chown(socketPath,0,gid);err!=nil{return err};if err=os.Chmod(socketPath,0660);err!=nil{return err};for{_ = ln.SetDeadline(time.Now().Add(time.Second));conn,err:=ln.AcceptUnix();if err!=nil{if ne,ok:=err.(net.Error);ok&&ne.Timeout(){select{case<-ctx.Done():return ctx.Err();default:continue}};return err};go handle(conn,runner)}}
func handle(conn *net.UnixConn,runner executor.Runner){defer conn.Close();_ = conn.SetDeadline(time.Now().Add(5*time.Minute));dec:=json.NewDecoder(io.LimitReader(conn,maxMessage));dec.DisallowUnknownFields();var req request;if err:=dec.Decode(&req);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:"invalid VIP request"});return};if err:=validate(req.Path,req.Args);err!=nil{_ = json.NewEncoder(conn).Encode(response{ExitCode:-1,Error:err.Error()});return};var res executor.Result;var runErr error;switch req.Path{case SecondaryAdd:res,runErr=secondary(runner,true,req.Args);case SecondaryRemove:res,runErr=secondary(runner,false,req.Args);case VRRPFirewallAdd:res,runErr=vrrpFirewall(runner,true,req.Args);case VRRPFirewallRemove:res,runErr=vrrpFirewall(runner,false,req.Args);default:res,runErr=runner.Run(context.Background(),req.Path,req.Args...)};out:=response{Stdout:res.Stdout,Stderr:res.Stderr,ExitCode:res.ExitCode};if runErr!=nil{out.Error=runErr.Error()};_ = json.NewEncoder(conn).Encode(out)}
func validate(path string,args []string)error{for _,a:=range args{if len(a)>4096||strings.ContainsAny(a,"\x00\r\n"){return errors.New("unsafe VIP argument")}};switch path{case SecondaryAdd,SecondaryRemove:return validateSecondary(args);case VRRPFirewallAdd,VRRPFirewallRemove:return validateVRRP(args);case "/usr/bin/dnf":return validateDNF(args);case "/usr/bin/rpm":if len(args)==2&&args[0]=="-q"&&args[1]=="keepalived"{return nil};case "/usr/bin/systemctl":return validateSystemctl(args);case "/usr/bin/install":return validateInstall(args);case "/usr/bin/rm":if len(args)==2&&args[0]=="-f"&&args[1]=="/etc/keepalived/keepalived.conf"{return nil}};return errors.New("VIP privileged action rejected")}
func validateSecondary(args []string)error{if len(args)!=2||!ifaceRE.MatchString(args[0]){return errors.New("secondary VIP grammar rejected")};ip,nw,err:=net.ParseCIDR(args[1]);if err!=nil||ip.To4()==nil||nw.String()!=args[1]{return errors.New("secondary VIP must be canonical IPv4 CIDR")};return nil}
func validateVRRP(args []string)error{if len(args)<2||!uuidRE.MatchString(args[0])||len(args)>18{return errors.New("VRRP firewall grammar rejected")};for _,peer:=range args[1:]{ip:=net.ParseIP(peer);if ip==nil||ip.To4()==nil||ip.String()!=peer{return errors.New("VRRP peer rejected")}};return nil}
func validateDNF(args []string)error{if len(args)==4&&args[0]=="-q"&&args[1]=="config-manager"&&args[2]=="--dump"&&args[3]=="appstream"{return nil};if len(args)>=8&&args[0]=="-q"&&args[1]=="repoquery"&&args[2]=="--latest-limit"&&args[3]=="1"&&args[4]=="--qf"&&args[len(args)-2]=="--repoid=appstream"&&args[len(args)-1]=="keepalived"{return nil};if len(args)==6&&args[0]=="-y"&&args[1]=="--setopt=install_weak_deps=False"&&args[2]=="--disablerepo=*"&&args[3]=="--enablerepo=appstream"&&args[4]=="install"&&nevraRE.MatchString(args[5]){return nil};if len(args)==3&&args[0]=="-y"&&args[1]=="remove"&&args[2]=="keepalived"{return nil};return errors.New("Keepalived DNF grammar rejected")}
func validateSystemctl(args []string)error{if len(args)==2&&args[0]=="is-active"&&args[1]=="nm-cloud-setup.service"{return nil};if len(args)>=2{allowed:=map[string]bool{"enable":true,"disable":true,"start":true,"stop":true,"restart":true,"is-active":true};if !allowed[args[0]]{return errors.New("Keepalived systemctl action rejected")};for _,a:=range args[1:]{if a=="--now"{continue};if a!="keepalived.service"{return errors.New("systemctl unit rejected")}};return nil};return errors.New("systemctl grammar rejected")}
func validateInstall(args []string)error{if len(args)!=5||args[0]!="--mode=0600"||args[1]!="--owner=root"||args[2]!="--group=root"||!strings.HasPrefix(args[3],"/run/layersentryd/vip/")||filepath.Ext(args[3])!=".conf"||args[4]!="/etc/keepalived/keepalived.conf"{return errors.New("Keepalived config install rejected")};return nil}
func secondary(r executor.Runner,add bool,args []string)(executor.Result,error){ctx:=context.Background();iface,cidr:=args[0],args[1];if state,err:=r.Run(ctx,"/usr/bin/systemctl","is-active","nm-cloud-setup.service");err==nil&&strings.TrimSpace(state.Stdout)=="active"{return executor.Result{},errors.New("nm-cloud-setup.service is active; refusing persistent manual VIP that may be reconciled away")};q,err:=r.Run(ctx,"/usr/bin/nmcli","-g","GENERAL.CONNECTION","device","show",iface);if err!=nil{return q,err};conn:=strings.TrimSpace(q.Stdout);if conn==""||conn=="--"||len(conn)>256||strings.ContainsAny(conn,"\x00\r\n"){return executor.Result{},errors.New("active NetworkManager connection cannot be resolved")};op:="+ipv4.addresses";if !add{op="-ipv4.addresses"};res,err:=r.Run(ctx,"/usr/bin/nmcli","connection","modify",conn,op,cidr);if err!=nil{return res,err};return r.Run(ctx,"/usr/bin/nmcli","device","reapply",iface)}
func vrrpFirewall(r executor.Runner,add bool,args []string)(executor.Result,error){ctx:=context.Background();sum:=sha256.Sum256([]byte(args[0]));zone:="ls-vip-"+hex.EncodeToString(sum[:6]);if add{_,_ = r.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--new-zone="+zone);if _,err:=r.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--set-target=DROP");err!=nil{return executor.Result{},err};for _,peer:=range args[1:]{if _,err:=r.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-source="+peer+"/32");err!=nil{return executor.Result{},err}};if _,err:=r.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-protocol=vrrp");err!=nil{return executor.Result{},err};return r.Run(ctx,"/usr/bin/firewall-cmd","--reload")};_,err:=r.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--delete-zone="+zone);if err!=nil{return executor.Result{},err};return r.Run(ctx,"/usr/bin/firewall-cmd","--reload")}
