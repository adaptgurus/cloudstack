package network

import (
 "bufio"
 "context"
 "net"
 "strconv"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type Interface struct{Name string `json:"name"`;Index int `json:"index"`;MTU int `json:"mtu"`;Flags string `json:"flags"`;Addresses []string `json:"addresses"`}
type Listener struct{Address string `json:"address"`;Port int `json:"port"`}
type Inventory struct{Interfaces []Interface `json:"interfaces"`;Listeners []Listener `json:"listeners"`}
func Discover(ctx context.Context,r executor.Runner)(Inventory,error){var out Inventory;ifs,err:=net.Interfaces();if err!=nil{return out,err};for _,i:=range ifs{item:=Interface{Name:i.Name,Index:i.Index,MTU:i.MTU,Flags:i.Flags.String()};addrs,_:=i.Addrs();for _,a:=range addrs{item.Addresses=append(item.Addresses,a.String())};out.Interfaces=append(out.Interfaces,item)};res,err:=r.Run(ctx,"/usr/sbin/ss","-H","-lnt");if err!=nil{return out,nil};sc:=bufio.NewScanner(strings.NewReader(res.Stdout));for sc.Scan(){f:=strings.Fields(sc.Text());if len(f)<4{continue};hostport:=f[3];idx:=strings.LastIndex(hostport,":");if idx<0{continue};p,err:=strconv.Atoi(strings.TrimPrefix(hostport[idx+1:],"*"));if err!=nil{continue};out.Listeners=append(out.Listeners,Listener{Address:strings.Trim(hostport[:idx],"[]"),Port:p})};return out,nil}
