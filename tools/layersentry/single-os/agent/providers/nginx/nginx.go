package nginx

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "net"
 "net/http"
 "os"
 "path/filepath"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

const repoID="appstream"
type Provider struct{Runner executor.Runner;DNF packageutil.DNF}
func New(r executor.Runner)*Provider{return &Provider{Runner:r,DNF:packageutil.DNF{Runner:r}}}
func(p *Provider)ID()string{return "nginx"}
func(p *Provider)Category()model.Category{return model.CategoryApplication}
func(p *Provider)Validate(_ context.Context,r model.ServiceRequest)error{if r.Category!=model.CategoryApplication{return errors.New("nginx category must be application")};if r.Topology!="standalone"{return errors.New("nginx provider currently supports standalone topology")};if net.ParseIP(r.Network.ListenAddress)==nil{return errors.New("nginx requires an explicit guest listen IP")};if r.Network.Port==0{return errors.New("nginx listener port required")};if r.ReleaseLine!="stable"&&r.ReleaseLine!="rocky9"{return errors.New("nginx release_line must be stable or rocky9")};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,_ model.ServiceRequest)(string,error){if err:=p.DNF.ValidateRepositories(ctx,repoID);err!=nil{return "",err};return p.DNF.ResolveLatestFromRepos(ctx,"nginx",[]string{repoID})}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){repoDigest,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return model.Plan{},err};steps:=[]model.PlanStep{{Name:"repository",Action:"use Rocky AppStream with GPG/TLS verification"},{Name:"packages",Action:"install exact Rocky-supported nginx package "+resolved},{Name:"configure",Action:fmt.Sprintf("configure listener %s:%d",r.Network.ListenAddress,r.Network.Port)},{Name:"firewall",Action:"allow only requested CIDRs"},{Name:"service",Action:"enable and start nginx"},{Name:"health",Action:"validate systemd, nginx syntax and local HTTP health response"}};sum:=sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%s|%s|%v",r.ServiceID,resolved,repoID,repoDigest,steps)));return model.Plan{ID:r.OperationID,ServiceID:r.ServiceID,Provider:p.ID(),ResolvedVersion:resolved,RepositoryID:repoID,RepositoryDigest:repoDigest,Digest:hex.EncodeToString(sum[:]),CreatedAt:time.Now().UTC(),Request:r,Steps:steps},nil}
func(p *Provider)Install(ctx context.Context,_ model.Operation,plan model.Plan)error{if plan.RepositoryID!=repoID||plan.RepositoryDigest==""{return errors.New("nginx plan repository provenance missing")};current,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return err};if current!=plan.RepositoryDigest{return errors.New("nginx repository configuration drifted after plan confirmation")};return p.DNF.InstallExactFromRepos(ctx,[]string{repoID},plan.ResolvedVersion)}
func(p *Provider)Configure(ctx context.Context,_ model.Operation,plan model.Plan)error{r:=plan.Request;root:=filepath.Join("/var/lib/layersentryd/apps",r.ServiceID,"www");if err:=os.MkdirAll(root,0750);err!=nil{return err};index:=[]byte("LayerSentry managed Nginx application service\n");if err:=filesystem.AtomicWrite(filepath.Join(root,"index.html"),index,0640,root);err!=nil{return err};sum:=sha256.Sum256([]byte(r.ServiceID));name:="layersentry-"+hex.EncodeToString(sum[:6])+".conf";conf:=fmt.Sprintf("server {\n    listen %s:%d;\n    server_name _;\n    root %s;\n    location = /__layersentry_health { access_log off; return 204; }\n    location / { try_files $uri $uri/ =404; }\n}\n",r.Network.ListenAddress,r.Network.Port,root);if err:=filesystem.AtomicWrite(filepath.Join("/etc/nginx/conf.d",name),[]byte(conf),0644,"/etc/nginx/conf.d");err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/sbin/nginx","-t");return err}
func(p *Provider)Initialize(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Join(context.Context,model.Operation,model.Plan)error{return errors.New("nginx join not supported")}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){checks:=map[string]string{};r,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active","nginx.service");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["systemd"]=strings.TrimSpace(r.Stdout);if _,err=p.Runner.Run(ctx,"/usr/sbin/nginx","-t");err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["config"]="ok";client:=&http.Client{Timeout:3*time.Second,Transport:&http.Transport{DialContext:(&net.Dialer{Timeout:2*time.Second}).DialContext,DisableKeepAlives:true,Proxy:nil}};url:=fmt.Sprintf("http://%s:%d/__layersentry_health",st.Network.ListenAddress,st.Network.Port);resp,err:=client.Get(url);if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};_ = resp.Body.Close();if resp.StatusCode!=http.StatusNoContent{return model.HealthResult{Healthy:false,Checks:checks,Error:"unexpected HTTP health status"},nil};checks["http"]="204";r,err=p.Runner.Run(ctx,"/usr/sbin/nginx","-v");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["version"]=strings.TrimSpace(r.Stderr);return model.HealthResult{Healthy:true,Version:strings.TrimSpace(r.Stderr),Checks:checks},nil}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Install(ctx,op,plan);err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","nginx.service");return err}
func(p *Provider)Repair(ctx context.Context,_ model.Operation,_ model.Plan)error{if _,err:=p.Runner.Run(ctx,"/usr/sbin/nginx","-t");err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","nginx.service");return err}
func(p *Provider)Backup(context.Context,model.Operation,model.ServiceState)(model.BackupRecord,error){return model.BackupRecord{},errors.New("nginx provider does not own customer application-data backup")}
func(p *Provider)Restore(context.Context,model.Operation,model.ServiceState,model.BackupRecord)error{return errors.New("nginx provider does not own customer application-data restore")}
func(p *Provider)Uninstall(ctx context.Context,_ model.Operation,st model.ServiceState,destroyData bool)error{if destroyData{return errors.New("data destruction is not part of normal nginx uninstall")};_,_=p.Runner.Run(ctx,"/usr/bin/systemctl","disable","--now","nginx.service");sum:=sha256.Sum256([]byte(st.ID));_ = os.Remove(filepath.Join("/etc/nginx/conf.d","layersentry-"+hex.EncodeToString(sum[:6])+".conf"));return p.DNF.Remove(ctx,"nginx")}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){out:=map[string]string{};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q","nginx");if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};r,_=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active","nginx.service");if r.ExitCode==0{out["service"]="active"}else{out["service"]="inactive"};sum:=sha256.Sum256([]byte(st.ID));if _,err:=os.Stat(filepath.Join("/etc/nginx/conf.d","layersentry-"+hex.EncodeToString(sum[:6])+".conf"));err==nil{out["managed_config"]="present"}else{out["managed_config"]="absent"};out["customer_data"]="preserved";return out,nil}
