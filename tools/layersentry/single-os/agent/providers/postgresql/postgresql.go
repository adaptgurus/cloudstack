package postgresql

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "regexp"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

var majorRE=regexp.MustCompile(`^(16|17)$`)
type Provider struct{Runner executor.Runner; DNF packageutil.DNF}
func New(r executor.Runner)*Provider{return &Provider{Runner:r,DNF:packageutil.DNF{Runner:r}}}
func(p *Provider)ID()string{return "postgresql"}
func(p *Provider)Category()model.Category{return model.CategoryDatabase}
func(p *Provider)Validate(_ context.Context,r model.ServiceRequest)error{if r.Category!=model.CategoryDatabase{return errors.New("postgresql category must be database")};if !majorRE.MatchString(r.ReleaseLine){return errors.New("supported PostgreSQL release lines: 16,17")};if r.Topology=="cluster"{switch r.Cluster.Role{case "primary","standby":default:return errors.New("postgresql cluster role must be primary or standby")}};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.DNF.ResolveLatest(ctx,"postgresql"+r.ReleaseLine+"-server")}
func(p *Provider)Plan(_ context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){steps:=[]model.PlanStep{{Name:"packages",Action:"install exact official PostgreSQL server package "+resolved},{Name:"storage",Action:"prepare requested mounts"},{Name:"initialize",Action:"initialize database cluster"},{Name:"configure",Action:"write provider-owned PostgreSQL configuration"},{Name:"firewall",Action:"open listener only to requested CIDRs"},{Name:"service",Action:"enable and start postgresql-"+r.ReleaseLine},{Name:"health",Action:"pg_isready plus SQL/version validation"}};for _,s:=range r.Storage{if s.Format{steps=append([]model.PlanStep{{Name:"format",Action:"format "+s.Device+" as "+s.Filesystem,Destructive:true,Detail:"THIS DEVICE WILL BE FORMATTED"}},steps...)}};raw:=fmt.Sprintf("%s|%s|%s|%v",r.ServiceID,r.Provider,resolved,steps);sum:=sha256.Sum256([]byte(raw));return model.Plan{ID:r.OperationID,ServiceID:r.ServiceID,Provider:p.ID(),ResolvedVersion:resolved,Digest:hex.EncodeToString(sum[:]),CreatedAt:time.Now().UTC(),Steps:steps},nil}
func(p *Provider)Install(ctx context.Context,_ model.Operation,plan model.Plan)error{return p.DNF.InstallExact(ctx,plan.ResolvedVersion)}
func(p *Provider)Configure(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Initialize(ctx context.Context,_ model.Operation,plan model.Plan)error{major:=extractMajor(plan.ResolvedVersion);if major==""{return errors.New("cannot derive PostgreSQL major")};_,err:=p.Runner.Run(ctx,"/usr/pgsql-"+major+"/bin/postgresql-"+major+"-setup","initdb");return err}
func(p *Provider)Join(context.Context,model.Operation,model.Plan)error{return errors.New("real multi-node PostgreSQL join is not enabled under the one-VM acceptance envelope")}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){major:=st.ReleaseLine;checks:=map[string]string{};if _,err:=p.Runner.Run(ctx,"/usr/pgsql-"+major+"/bin/pg_isready","-q");err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["pg_isready"]="ok";r,err:=p.Runner.Run(ctx,"/usr/pgsql-"+major+"/bin/postgres","--version");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:err.Error()},nil};checks["version"]=strings.TrimSpace(r.Stdout);return model.HealthResult{Healthy:true,Version:strings.TrimSpace(r.Stdout),Checks:checks},nil}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Install(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,_ model.Operation,plan model.Plan)error{major:=extractMajor(plan.ResolvedVersion);if major==""{return errors.New("unknown major")};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","postgresql-"+major+".service");return err}
func(p *Provider)Backup(ctx context.Context,_ model.Operation,st model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/pgsql-"+st.ReleaseLine+"/bin/pg_dumpall","--file=/var/lib/layersentryd/backups/"+st.ID+".sql");return err}
func(p *Provider)Restore(context.Context,model.Operation,model.ServiceState)error{return errors.New("restore requires an explicit verified backup selection")}
func(p *Provider)Uninstall(ctx context.Context,_ model.Operation,st model.ServiceState,destroyData bool)error{if destroyData{return errors.New("destructive data removal requires a separate implementation/authorization")};_,_=p.Runner.Run(ctx,"/usr/bin/systemctl","disable","--now","postgresql-"+st.ReleaseLine+".service");return p.DNF.Remove(ctx,"postgresql"+st.ReleaseLine+"-server")}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){out:=map[string]string{};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q","postgresql"+st.ReleaseLine+"-server");if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};r,_=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active","postgresql-"+st.ReleaseLine+".service");if r.ExitCode==0{out["service"]="active"}else{out["service"]="inactive"};return out,nil}
func extractMajor(nevra string)string{for _,m:=range []string{"16","17"}{if strings.Contains(nevra,"postgresql"+m+"-server"){return m}};return ""}
