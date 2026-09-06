package preflight

import (
 "bufio"
 "context"
 "errors"
 "fmt"
 "net"
 "os"
 "path/filepath"
 "strconv"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Result struct{MemoryMiB int;CPUs int;Checks map[string]string}
func System(ctx context.Context,req model.ServiceRequest,_ executor.Runner)(Result,error){r:=Result{Checks:map[string]string{}};b,err:=os.ReadFile("/etc/os-release");if err!=nil{return r,err};s:=string(b);if !strings.Contains(s,"ID=\"rocky\"")&&!strings.Contains(s,"ID=rocky"){return r,errors.New("Rocky Linux required")};if !strings.Contains(s,"VERSION_ID=\"9")&&!strings.Contains(s,"VERSION_ID=9"){return r,errors.New("Rocky Linux 9 required")};r.Checks["os"]="rocky9";readRunner:=executor.OSRunner{Timeout:30*time.Second,MaxOutput:1<<20};if out,err:=readRunner.Run(ctx,"/usr/sbin/getenforce");err!=nil||strings.TrimSpace(out.Stdout)!="Enforcing"{return r,errors.New("SELinux must be Enforcing")};r.Checks["selinux"]="Enforcing";if _,err:=readRunner.Run(ctx,"/usr/bin/systemctl","is-active","--quiet","firewalld.service");err!=nil{return r,errors.New("firewalld must be active")};if _,err:=readRunner.Run(ctx,"/usr/bin/systemctl","is-enabled","--quiet","firewalld.service");err!=nil{return r,errors.New("firewalld must be enabled")};r.Checks["firewalld"]="active-enabled";if b,err:=os.ReadFile("/proc/meminfo");err==nil{sc:=bufio.NewScanner(strings.NewReader(string(b)));for sc.Scan(){f:=strings.Fields(sc.Text());if len(f)>=2&&f[0]=="MemTotal:"{kb,_:=strconv.Atoi(f[1]);r.MemoryMiB=kb/1024;break}}};r.CPUs=runtimeCPUs();if r.CPUs<1{return r,errors.New("no CPU detected")};if err:=validateNetwork(req.Network);err!=nil{return r,err};if err:=validateStorage(ctx,readRunner,req.Storage);err!=nil{return r,err};return r,nil}
func runtimeCPUs()int{b,err:=os.ReadFile("/proc/cpuinfo");if err!=nil{return 0};n:=0;sc:=bufio.NewScanner(strings.NewReader(string(b)));for sc.Scan(){if strings.HasPrefix(sc.Text(),"processor"){n++}};return n}
func validateNetwork(n model.NetworkSpec)error{if n.ListenAddress!=""{ip:=net.ParseIP(n.ListenAddress);if ip==nil{return errors.New("invalid listen IP")};found:=false;ifs,_:=net.Interfaces();for _,i:=range ifs{addrs,_:=i.Addrs();for _,a:=range addrs{host,_,_:=net.ParseCIDR(a.String());if host!=nil&&host.Equal(ip){found=true}}};if !found{return fmt.Errorf("listen IP %s is not assigned to this guest",n.ListenAddress)}};ln,err:=net.Listen("tcp",fmt.Sprintf("%s:%d",n.ListenAddress,n.Port));if err!=nil{return fmt.Errorf("requested port unavailable: %w",err)};return ln.Close()}
func validateStorage(ctx context.Context,runner executor.Runner,items []model.StorageAssignment)error{root,err:=runner.Run(ctx,"/usr/bin/findmnt","-nro","SOURCE","/");if err!=nil{return fmt.Errorf("discover root source: %w",err)};rootReal,_:=filepath.EvalSymlinks(strings.TrimSpace(root.Stdout));rootAnc:=ancestry(ctx,runner,rootReal);for _,s:=range items{real,err:=filepath.EvalSymlinks(s.Device);if err!=nil{return fmt.Errorf("resolve device %s: %w",s.Device,err)};fi,err:=os.Stat(real);if err!=nil{return err};if fi.Mode()&os.ModeDevice==0{return fmt.Errorf("%s is not a device",s.Device)};candidate:=ancestry(ctx,runner,real);for dev:=range candidate{if rootAnc[dev]{return fmt.Errorf("refusing root/root-parent device %s",s.Device)}}};return nil}
func ancestry(ctx context.Context,runner executor.Runner,dev string)map[string]bool{out:=map[string]bool{};cur:=dev;for i:=0;i<16&&cur!="";i++{real,_:=filepath.EvalSymlinks(cur);if real==""{real=cur};if out[real]{break};out[real]=true;r,err:=runner.Run(ctx,"/usr/bin/lsblk","-nro","PKNAME",real);if err!=nil{break};parent:=strings.TrimSpace(r.Stdout);if parent==""{break};if !strings.HasPrefix(parent,"/"){parent="/dev/"+parent};cur=parent};return out}
