package pgmanaged

import (
 "context"
 "errors"
 "fmt"
 "os"
 "os/user"
 "path/filepath"
 "strconv"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/mounts"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/storageplan"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/postgresql"
)

type Provider struct{Base *postgresql.Provider;Label executor.Runner}
func New(base *postgresql.Provider,label executor.Runner)*Provider{return &Provider{Base:base,Label:label}}
func(p *Provider)ID()string{return p.Base.ID()}
func(p *Provider)Category()model.Category{return p.Base.Category()}
func(p *Provider)Validate(ctx context.Context,r model.ServiceRequest)error{for _,purpose:=range []string{"database-data","database-wal","database-logs"}{root,err:=storageplan.PathForPurpose(r,purpose);if err!=nil{return err};if root!=""&&isExternal(root){base:=filepath.Base(root);if (purpose=="database-data"&&base=="data")||(purpose=="database-wal"&&base=="wal")||(purpose=="database-logs"&&base=="logs"){return fmt.Errorf("%s mount must be a filesystem/LV root; LayerSentry creates its %s child",purpose,base)}}};return p.Base.Validate(ctx,transformRequest(r))}
func(p *Provider)ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.Base.ResolveVersion(ctx,transformRequest(r))}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){plan,err:=p.Base.Plan(ctx,transformRequest(r),resolved);if err!=nil{return plan,err};var steps []model.PlanStep;if root,_:=storageplan.PathForPurpose(r,"database-data");root!=""&&isExternal(root){steps=append(steps,model.PlanStep{Name:"pgdata-bind",Action:fmt.Sprintf("use external PostgreSQL data root %s and bind %s to /var/lib/pgsql/%s/data",root,filepath.Join(root,"data"),r.ReleaseLine)},model.PlanStep{Name:"pgdata-selinux",Action:"persist SELinux equivalence from /var/lib/pgsql to the external PostgreSQL filesystem root"})};if root,_:=storageplan.PathForPurpose(r,"database-wal");root!=""&&isExternal(root){steps=append(steps,model.PlanStep{Name:"pgwal",Action:"use external WAL directory "+filepath.Join(root,"wal")})};if root,_:=storageplan.PathForPurpose(r,"database-logs");root!=""&&isExternal(root){steps=append(steps,model.PlanStep{Name:"pglogs",Action:"use external PostgreSQL log directory "+filepath.Join(root,"logs")})};plan.Steps=append(steps,plan.Steps...);return plan,nil}
func(p *Provider)Install(ctx context.Context,op model.Operation,plan model.Plan)error{plan.Request=transformRequest(plan.Request);return p.Base.Install(ctx,op,plan)}
func(p *Provider)Configure(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Configure(ctx,op,withTransformedPlan(plan))}
func(p *Provider)Initialize(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.prepareExternal(ctx,plan.Request);err!=nil{return err};return p.Base.Initialize(ctx,op,withTransformedPlan(plan))}
func(p *Provider)Join(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Join(ctx,op,withTransformedPlan(plan))}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){return p.Base.Health(ctx,st)}
func(p *Provider)Start(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Start(ctx,op,st)}
func(p *Provider)Stop(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Stop(ctx,op,st)}
func(p *Provider)Restart(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Restart(ctx,op,st)}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Upgrade(ctx,op,withTransformedPlan(plan))}
func(p *Provider)Repair(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Repair(ctx,op,withTransformedPlan(plan))}
func(p *Provider)Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){return p.Base.Backup(ctx,op,st)}
func(p *Provider)Restore(ctx context.Context,op model.Operation,st model.ServiceState,b model.BackupRecord)error{return p.Base.Restore(ctx,op,st,b)}
func(p *Provider)Uninstall(ctx context.Context,op model.Operation,st model.ServiceState,destroy bool)error{return p.Base.Uninstall(ctx,op,st,destroy)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){return p.Base.ResidueAudit(ctx,st)}
func(p *Provider)prepareExternal(ctx context.Context,r model.ServiceRequest)error{if p.Label==nil{return errors.New("PostgreSQL external-data SELinux helper unavailable")};root,_:=storageplan.PathForPurpose(r,"database-data");if root!=""&&isExternal(root){source:=filepath.Join(root,"data");if err:=prepareOwned(source,"postgres",0700);err!=nil{return err};if err:=p.label(ctx,root);err!=nil{return err};target:=filepath.Join("/var/lib/pgsql",r.ReleaseLine,"data");if err:=(mounts.Manager{Runner:p.Base.Runner}).EnsureBind(ctx,source,target);err!=nil{return err}}
 for _,purpose:=range []string{"database-wal","database-logs"}{root,_:=storageplan.PathForPurpose(r,purpose);if root==""||!isExternal(root){continue};child:="wal";mode:=os.FileMode(0700);if purpose=="database-logs"{child="logs";mode=0750};path:=filepath.Join(root,child);if err:=prepareOwned(path,"postgres",mode);err!=nil{return err};if err:=p.label(ctx,root);err!=nil{return err}};return nil}
func(p *Provider)label(ctx context.Context,root string)error{if _,err:=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-e","/var/lib/pgsql",root);err!=nil{if _,err=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-e","/var/lib/pgsql",root);err!=nil{return err}};_,err:=p.Label.Run(ctx,"/usr/sbin/restorecon","-RF",root);return err}
func transformRequest(r model.ServiceRequest)model.ServiceRequest{out:=r;out.Storage=nil;out.LVM=nil;major:=r.ReleaseLine;for _,purpose:=range []string{"database-data","database-wal","database-logs"}{root,err:=storageplan.PathForPurpose(r,purpose);if err!=nil||root==""{continue};path:=root;if isExternal(root){switch purpose{case "database-data":path=filepath.Join("/var/lib/pgsql",major,"data");case "database-wal":path=filepath.Join(root,"wal");case "database-logs":path=filepath.Join(root,"logs")}};out.Storage=append(out.Storage,model.StorageAssignment{MountPoint:path,Purpose:purpose,Filesystem:"xfs"})};return out}
func withTransformedPlan(plan model.Plan)model.Plan{plan.Request=transformRequest(plan.Request);return plan}
func isExternal(path string)bool{for _,root:=range []string{"/data","/srv","/opt/layersentry-data"}{rel,err:=filepath.Rel(root,path);if err==nil&&rel!="."&&rel!=".."&&rel[:0]==rel[:0]&&!startsParent(rel){return true}};return false}
func startsParent(rel string)bool{return rel==".."||len(rel)>=3&&rel[:3]=="../"}
func prepareOwned(path,name string,mode os.FileMode)error{if err:=os.MkdirAll(path,mode);err!=nil{return err};if err:=os.Chmod(path,mode);err!=nil{return err};u,err:=user.Lookup(name);if err!=nil{return err};uid,err:=strconv.Atoi(u.Uid);if err!=nil{return err};gid,err:=strconv.Atoi(u.Gid);if err!=nil{return err};return os.Chown(path,uid,gid)}
