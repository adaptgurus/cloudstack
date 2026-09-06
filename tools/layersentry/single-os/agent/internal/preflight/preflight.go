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

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Result struct{MemoryMiB int; CPUs int; Checks map[string]string}
func System(ctx context.Context,req model.ServiceRequest)(Result,error){
 r:=Result{Checks:map[string]string{}}
 b,err:=os.ReadFile("/etc/os-release");if err!=nil{return r,err};s:=string(b);if !strings.Contains(s,"ID=\"rocky\"")&&!strings.Contains(s,"ID=rocky"){return r,errors.New("Rocky Linux required")};if !strings.Contains(s,"VERSION_ID=\"9")&&!strings.Contains(s,"VERSION_ID=9"){return r,errors.New("Rocky Linux 9 required")};r.Checks["os"]="rocky9"
 if b,err:=os.ReadFile("/proc/meminfo");err==nil{sc:=bufio.NewScanner(strings.NewReader(string(b)));for sc.Scan(){f:=strings.Fields(sc.Text());if len(f)>=2&&f[0]=="MemTotal:"{kb,_:=strconv.Atoi(f[1]);r.MemoryMiB=kb/1024;break}}}
 r.CPUs=runtimeCPUs();if r.CPUs<1{return r,errors.New("no CPU detected")}
 if err:=validateNetwork(req.Network);err!=nil{return r,err};if err:=validateStorage(req.Storage);err!=nil{return r,err};return r,nil
}
func runtimeCPUs()int{b,err:=os.ReadFile("/proc/cpuinfo");if err!=nil{return 0};n:=0;sc:=bufio.NewScanner(strings.NewReader(string(b)));for sc.Scan(){if strings.HasPrefix(sc.Text(),"processor") {n++}};return n}
func validateNetwork(n model.NetworkSpec)error{if n.ListenAddress!=""{ip:=net.ParseIP(n.ListenAddress);if ip==nil{return errors.New("invalid listen IP")};found:=false;ifs,_:=net.Interfaces();for _,i:=range ifs{addrs,_:=i.Addrs();for _,a:=range addrs{host,_,_:=net.ParseCIDR(a.String());if host!=nil&&host.Equal(ip){found=true}}};if !found{return fmt.Errorf("listen IP %s is not assigned to this guest",n.ListenAddress)}};ln,err:=net.Listen("tcp",fmt.Sprintf("%s:%d",n.ListenAddress,n.Port));if err!=nil{return fmt.Errorf("requested port unavailable: %w",err)};return ln.Close()}
func validateStorage(items []model.StorageAssignment)error{rootDev:=rootSource();for _,s:=range items{real,err:=filepath.EvalSymlinks(s.Device);if err!=nil{return fmt.Errorf("resolve device %s: %w",s.Device,err)};if rootDev!=""&&sameDevice(real,rootDev){return fmt.Errorf("refusing root device %s",s.Device)};fi,err:=os.Stat(real);if err!=nil{return err};if fi.Mode()&os.ModeDevice==0{return fmt.Errorf("%s is not a device",s.Device)}};return nil}
func rootSource()string{b,err:=os.ReadFile("/proc/mounts");if err!=nil{return ""};sc:=bufio.NewScanner(strings.NewReader(string(b)));for sc.Scan(){f:=strings.Fields(sc.Text());if len(f)>=2&&f[1]=="/"{return f[0]}};return ""}
func sameDevice(a,b string)bool{ra,_:=filepath.EvalSymlinks(a);rb,_:=filepath.EvalSymlinks(b);return ra!=""&&rb!=""&&ra==rb}
