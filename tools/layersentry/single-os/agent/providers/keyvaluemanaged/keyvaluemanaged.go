package keyvaluemanaged

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
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/keyvalue"
)

type Provider struct{Base *keyvalue.Provider;Label executor.Runner}
func New(base *keyvalue.Provider,label executor.Runner)*Provider{return &Provider{Base:base,Label:label}}
func(p *Provider)ID()string{return p.Base.ID()}
func(p *Provider)Category()model.Category{return p.Base.Category()}
func(p *Provider)Validate(ctx context.Context,r model.ServiceRequest)error{copy:=r;copy.Storage=nil;copy.LVM=nil;if err:=p.Base.Validate(ctx,copy);err!=nil{return err};root,err:=storageplan.PathForPurpose(r,"database-data");if err!=nil{return err};if root!=""&&filepath.Base(root)=="data"{return errors.New("database-data mount must be a filesystem/LV root; LayerSentry creates its data child")};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.Base.ResolveVersion(ctx,r)}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){plan,err:=p.Base.Plan(ctx,r,resolved);if err!=nil{return plan,err};if root,_:=storageplan.PathForPurpose(r,"database-data");root!=""{plan.Steps=append([]model.PlanStep{{Name:"data-bind",Action:fmt.Sprintf("mount external %s data root at %s using a provider-owned bind mount",filepath.Join(root,"data"),p.vendorData(r.ServiceID))},{Name:"selinux",Action:"persist SELinux equivalence from "+p.Base.Spec.DataRoot+" to "+root+" and restore contexts"}},plan.Steps...)};return plan,nil}
func(p *Provider)Install(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Install(ctx,op,plan)}
func(p *Provider)Configure(ctx context.Context,op model.Operation,plan model.Plan)error{if root,_:=storageplan.PathForPurpose(plan.Request,"database-data");root!=""{source:=filepath.Join(root,"data");if err:=prepareOwned(source,p.Base.Spec.OSUser,0750);err!=nil{return err};if p.Label==nil{return errors.New("data SELinux helper unavailable")};if _,err:=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-e",p.Base.Spec.DataRoot,root);err!=nil{if _,err=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-e",p.Base.Spec.DataRoot,root);err!=nil{return err}};if _,err:=p.Label.Run(ctx,"/usr/sbin/restorecon","-RF",root);err!=nil{return err};if err:=(mounts.Manager{Runner:p.Base.Runner}).EnsureBind(ctx,source,p.vendorData(plan.ServiceID));err!=nil{return err}};return p.Base.Configure(ctx,op,plan)}
func(p *Provider)Initialize(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Initialize(ctx,op,plan)}
func(p *Provider)Join(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Join(ctx,op,plan)}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){h,err:=p.Base.Health(ctx,st);if h.Checks==nil{h.Checks=map[string]string{}};if root,_:=storageplan.StatePathForPurpose(st,"database-data");root!=""{h.Checks["data_mount"]=root};return h,err}
func(p *Provider)Start(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Start(ctx,op,st)}
func(p *Provider)Stop(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Stop(ctx,op,st)}
func(p *Provider)Restart(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Restart(ctx,op,st)}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Upgrade(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Configure(ctx,op,plan);err!=nil{return err};return p.Base.Repair(ctx,op,plan)}
func(p *Provider)Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){return p.Base.Backup(ctx,op,st)}
func(p *Provider)Restore(ctx context.Context,op model.Operation,st model.ServiceState,b model.BackupRecord)error{return p.Base.Restore(ctx,op,st,b)}
func(p *Provider)Uninstall(ctx context.Context,op model.Operation,st model.ServiceState,destroy bool)error{return p.Base.Uninstall(ctx,op,st,destroy)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){return p.Base.ResidueAudit(ctx,st)}
func(p *Provider)vendorData(id string)string{return filepath.Join(p.Base.Spec.DataRoot,"layersentry-"+id)}
func prepareOwned(path,name string,mode os.FileMode)error{if err:=os.MkdirAll(path,mode);err!=nil{return err};if err:=os.Chmod(path,mode);err!=nil{return err};u,err:=user.Lookup(name);if err!=nil{return err};uid,err:=strconv.Atoi(u.Uid);if err!=nil{return err};gid,err:=strconv.Atoi(u.Gid);if err!=nil{return err};return os.Chown(path,uid,gid)}
