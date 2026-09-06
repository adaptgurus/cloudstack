package firewall

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "net"
 "strconv"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type Manager struct{Runner executor.Runner}
func(m Manager)zone(serviceID string)string{s:=sha256.Sum256([]byte(serviceID));return "ls-"+hex.EncodeToString(s[:6])}
func(m Manager)Apply(ctx context.Context,serviceID string,port int,cidrs []string)error{if port<1||port>65535{return errors.New("invalid port")};if len(cidrs)==0{return errors.New("at least one allowed CIDR is required")};zone:=m.zone(serviceID);_,_ = m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--new-zone="+zone);if _,err:=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--set-target=DROP");err!=nil{return err};for _,cidr:=range cidrs{if _,_,err:=net.ParseCIDR(cidr);err!=nil{return fmt.Errorf("invalid CIDR: %w",err)};if _,err:=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-source="+cidr);err!=nil{return err}};if _,err:=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--zone="+zone,"--add-port="+strconv.Itoa(port)+"/tcp");err!=nil{return err};_,err:=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--reload");return err}
func(m Manager)Remove(ctx context.Context,serviceID string)error{zone:=m.zone(serviceID);_,err:=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--permanent","--delete-zone="+zone);if err!=nil{return err};_,err=m.Runner.Run(ctx,"/usr/bin/firewall-cmd","--reload");return err}
