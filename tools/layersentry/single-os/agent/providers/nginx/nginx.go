package nginx

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

type Provider struct{Runner executor.Runner;DNF packageutil.DNF}
func New(r executor.Runner)*Provider{return &Provider{Runner:r,DNF:packageutil.DNF{Runner:r}}}
func(p *Provider)ID()string{return "nginx"}
func(p *Provider)Category()model.Category{return model.CategoryApplication}
func(p *Provider)Validate(_ context.Context,r model.ServiceRequest)error{if r.Category!=model.CategoryApplication{return errors.New("nginx category must be application")};if r.Topology!="standalone"{return errors.New("nginx provider currently supports standalone topology")};if r.Network.Port==0{return errors.New("nginx listener port required")};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,_ model.ServiceRequest)(string,error){return p.DNF.ResolveLatest(ctx,"nginx")}
func(p *Provider)Plan(_ context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){steps:=[]model.PlanStep{{Name:"packages",Action:"install exact Rocky-supported nginx package "+resolved},{Name:"configure",Action:fmt.Sprintf("configure listener %s:%d",r.Network.ListenAddress,r.Network.Port)},{Name:"firewall",Action:"allow only requested CIDRs"},{Name:"service",Action:"enable and start nginx"},{Name:"health",Action:"validate systemd/listener/local HTTP response"}};sum:=sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%v",r.ServiceID,resolved,steps)));return model.Plan{ID:r.OperationID,ServiceID:r.ServiceID,Provider:p.ID(),ResolvedVersion:resolved,Digest:hex.EncodeToString(sum[:]),CreatedAt:time.Now().UTC(),Steps:steps},nil}
func(p *Provider)Install(ctx context.Context,_ model.Operation,plan model.Plan)error{return p.DNF.InstallExact(ctx,plan.ResolvedVersion)}
func(p *Provider)Configure(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Initialize(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Join(context.Context,model.Operation,model.Plan)error{return errors.New("nginx join not supported")}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){checks:=map[string]string{};r,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active","nginx.service");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["systemd"]=strings.TrimSpace(r.Stdout);r,err=p.Runner.Run(ctx,"/usr/sbin/nginx","-v");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["version"]=strings.TrimSpace(r.Stderr);return model.HealthResult{Healthy:true,Version:strings.TrimSpace(r.Stderr),Checks:checks},nil}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Install(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,_ model.Operation,_ model.Plan)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","nginx.service");return err}
func(p *Provider)Backup(context.Context,model.Operation,model.ServiceState)error{return errors.New("nginx provider has no application-data backup semantics")}
func(p *Provider)Restore(context.Context,model.Operation,model.ServiceState)error{return errors.New("nginx provider has no application-data restore semantics")}
func(p *Provider)Uninstall(ctx context.Context,_ model.Operation,_ model.ServiceState,destroyData bool)error{if destroyData{return errors.New("data destruction is not part of nginx uninstall")};_,_=p.Runner.Run(ctx,"/usr/bin/systemctl","disable","--now","nginx.service");return p.DNF.Remove(ctx,"nginx")}
func(p *Provider)ResidueAudit(ctx context.Context,_ model.ServiceState)(map[string]string,error){out:=map[string]string{};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q","nginx");if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};r,_=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active","nginx.service");if r.ExitCode==0{out["service"]="active"}else{out["service"]="inactive"};return out,nil}
