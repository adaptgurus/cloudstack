package firewall

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "net"
 "strconv"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type Manager struct{Runner executor.Runner;Observer executor.Runner}
func(m Manager)zone(serviceID string)string{s:=sha256.Sum256([]byte(serviceID));return "ls-"+hex.EncodeToString(s[:6])}
func(m Manager)observer()executor.Runner{if m.Observer!=nil{return m.Observer};return executor.OSRunner{Timeout:10*time.Second,MaxOutput:1<<20}}
func(m Manager)exists(ctx context.Context,zone string)(bool,error){r,err:=m.observer().Run(ctx,"/usr/bin/firewall-cmd","--permanent","--get-zones");if err!=nil{return false,fmt.Errorf("observe firewalld zones: %w",err)};for _,z:=range strings.Fields(r.Stdout){if z==zone{return true,nil}};return false,nil}
func(m Manager)Apply(ctx context.Context,serviceID string,port int,cidrs []string)error{if m.Runner==nil{return errors.New("firewall mutation executor unavailable")};if port<1||port>65535{return errors.New("invalid port")};if len(cidrs)==0{return errors.New("at least one allowed CIDR is required")};for _,cidr:=range cidrs{if _,_,err:=net.ParseCIDR(cidr);err!=nil{return fmt.Errorf("invalid CIDR: %w",err)}};zone:=m.zone(serviceID);present,err:=m.exists(ctx,zone);if err!=nil{return err};if present{if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--delete-zone="+zone);err!=nil{return err}};if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--new-zone="+zone);err!=nil{return err};if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--set-target=DROP");err!=nil{return err};for _,cidr:=range cidrs{if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-source="+cidr);err!=nil{return err}};if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-port="+strconv.Itoa(port)+"/tcp");err!=nil{return err};_,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--reload");return err}
func(m Manager)Remove(ctx context.Context,serviceID string)error{if m.Runner==nil{return errors.New("firewall mutation executor unavailable")};zone:=m.zone(serviceID);present,err:=m.exists(ctx,zone);if err!=nil{return err};if !present{return nil};if _,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--delete-zone="+zone);err!=nil{return err};_,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--reload");return err}
