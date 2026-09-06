package maintenance

import (
 "context"
 "crypto/rand"
 "encoding/hex"
 "fmt"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lifecycle"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Runner struct{Store *journal.Store;Engine *lifecycle.Engine;Now func()time.Time}
func(r Runner)Run(ctx context.Context)error{now:=time.Now().UTC();if r.Now!=nil{now=r.Now().UTC()};items,err:=r.Store.ListServices();if err!=nil{return err};for _,st:=range items{if st.Status!="installed"||!due(st,now){continue};p:=st.Maintenance;if p.Mode=="notify"||p.Mode=="notify-only"||!p.AutoPatch{continue};if !p.ReleaseLineLocked{return fmt.Errorf("service %s auto-patch requires release_line_locked",st.ID)};op:=newUUID();_,err=r.Engine.Action(ctx,st.ID,lifecycle.ActionRequest{OperationID:op,IdempotencyKey:"maintenance:"+st.ID+":"+now.Format("2006-01-02T15"),Action:"upgrade"});if err!=nil{return fmt.Errorf("maintenance service %s: %w",st.ID,err)}};return nil}
func due(st model.ServiceState,now time.Time)bool{p:=st.Maintenance;switch p.Mode{case "manual","","notify","notify-only":return false;case "daily":if now.Sub(st.UpdatedAt)<23*time.Hour{return false};case "weekly":if now.Sub(st.UpdatedAt)<6*24*time.Hour{return false};if p.Day!=""&&!strings.EqualFold(now.Weekday().String(),p.Day){return false};case "monthly":if now.Sub(st.UpdatedAt)<27*24*time.Hour{return false};default:return false};return inWindow(p.Window,now)}
func inWindow(w string,now time.Time)bool{if w==""{return true};parts:=strings.Split(w,"-");if len(parts)!=2{return false};parse:=func(s string)(int,bool){var h,m int;if _,err:=fmt.Sscanf(s,"%d:%d",&h,&m);err!=nil||h<0||h>23||m<0||m>59{return 0,false};return h*60+m,true};a,ok:=parse(parts[0]);if !ok{return false};b,ok:=parse(parts[1]);if !ok{return false};n:=now.Hour()*60+now.Minute();if a<=b{return n>=a&&n<=b};return n>=a||n<=b}
func newUUID()string{b:=make([]byte,16);_,_=rand.Read(b);b[6]=(b[6]&0x0f)|0x40;b[8]=(b[8]&0x3f)|0x80;h:=hex.EncodeToString(b);return h[0:8]+"-"+h[8:12]+"-"+h[12:16]+"-"+h[16:20]+"-"+h[20:32]}
