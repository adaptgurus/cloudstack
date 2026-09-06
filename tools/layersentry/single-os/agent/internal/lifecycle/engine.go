package lifecycle

import (
 "context"
 "errors"
 "fmt"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/firewall"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lock"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/mounts"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/preflight"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
)

type Engine struct{Registry *provider.Registry;Store *journal.Store;Runner executor.Runner;LockPath string}

func(e *Engine)Plan(ctx context.Context,req model.ServiceRequest)(model.Plan,model.Operation,error){
 if err:=config.Validate(req);err!=nil{return model.Plan{},model.Operation{},err}
 p,ok:=e.Registry.Get(req.Provider);if !ok{return model.Plan{},model.Operation{},fmt.Errorf("unknown provider %q",req.Provider)}
 if p.Category()!=req.Category{return model.Plan{},model.Operation{},errors.New("provider category mismatch")}
 if err:=p.Validate(ctx,req);err!=nil{return model.Plan{},model.Operation{},err}
 if _,err:=preflight.System(ctx,req,e.Runner);err!=nil{return model.Plan{},model.Operation{},err}
 requestDigest,err:=config.CanonicalDigest(req);if err!=nil{return model.Plan{},model.Operation{},err}
 proposed:=model.Operation{ID:req.OperationID,ServiceID:req.ServiceID,IdempotencyKey:req.IdempotencyKey,RequestDigest:requestDigest,Status:model.OpPreflight,Stage:"preflight"}
 op,err:=e.Store.Begin(proposed);if err!=nil{return model.Plan{},op,err}
 // Idempotent re-planning never re-resolves packages or repository state. Once a
 // plan is pinned, return exactly that stored plan/current operation.
 if op.PlanDigest!=""{
  plan,err:=e.Store.GetPlan(op.ID);if err!=nil{return model.Plan{},op,fmt.Errorf("load pinned plan: %w",err)}
  if err=validateStoredPlan(plan,op,requestDigest);err!=nil{return model.Plan{},op,err}
  return plan,op,nil
 }
 switch op.Status{case model.OpRunning,model.OpVerifying,model.OpUnknown,model.OpSucceeded:return model.Plan{},op,fmt.Errorf("operation state %s has no reusable pinned plan",op.Status);case model.OpFailedSafe,model.OpFailedNeedsRecovery,model.OpCancelled,model.OpRolledBack:return model.Plan{},op,fmt.Errorf("operation state %s cannot be replanned with the same operation UUID",op.Status)}
 resolved,err:=p.ResolveVersion(ctx,req);if err!=nil{op.Status=model.OpFailedSafe;op.Stage="version-resolution";op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return model.Plan{},op,err}
 plan,err:=p.Plan(ctx,req,resolved);if err!=nil{op.Status=model.OpFailedSafe;op.Stage="planning";op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return model.Plan{},op,err}
 if plan.ID!=req.OperationID||plan.ServiceID!=req.ServiceID||plan.Provider!=req.Provider||plan.ResolvedVersion==""{return model.Plan{},op,errors.New("provider returned an invalid plan identity")}
 plan.Request=req
 plan.Digest=""
 canonical,err:=config.PlanDigest(plan);if err!=nil{return model.Plan{},op,err};plan.Digest=canonical
 if err=e.Store.SavePlan(plan);err!=nil{return model.Plan{},op,err}
 op.PlanDigest=plan.Digest;op.Status=model.OpWaitingConfirmation;op.Stage="waiting-confirmation";op.Error=""
 if err=e.Store.SaveOperation(op);err!=nil{return model.Plan{},op,err}
 return plan,op,nil
}

func(e *Engine)Install(ctx context.Context,req model.ServiceRequest,confirmedPlanDigest string)(model.Operation,error){
 if err:=config.Validate(req);err!=nil{return model.Operation{},err}
 requestDigest,err:=config.CanonicalDigest(req);if err!=nil{return model.Operation{},err}
 op,err:=e.Store.GetOperation(req.OperationID);if err!=nil{return op,err}
 if op.RequestDigest!=requestDigest||op.IdempotencyKey!=req.IdempotencyKey||op.ServiceID!=req.ServiceID{return op,errors.New("operation request/idempotency mismatch")}
 if op.Status==model.OpSucceeded{return op,nil}
 if op.Status==model.OpUnknown{return op,errors.New("UNKNOWN operation requires authoritative reconciliation before retry")}
 if op.Status!=model.OpWaitingConfirmation{return op,fmt.Errorf("operation state %s is not eligible for installation",op.Status)}
 plan,err:=e.Store.GetPlan(req.OperationID);if err!=nil{return op,err}
 if err=validateStoredPlan(plan,op,requestDigest);err!=nil{return op,err}
 if confirmedPlanDigest==""||confirmedPlanDigest!=plan.Digest||confirmedPlanDigest!=op.PlanDigest{return op,errors.New("plan confirmation digest mismatch")}
 p,ok:=e.Registry.Get(req.Provider);if !ok{return op,errors.New("provider disappeared")}
 lk,err:=lock.Acquire(e.LockPath);if err!=nil{return op,err};defer lk.Release()
 // Re-read under the mutation lock so a concurrent/crashed process cannot have
 // transitioned the operation between confirmation and the first mutation.
 current,err:=e.Store.GetOperation(op.ID);if err!=nil{return op,err};if current.Status!=model.OpWaitingConfirmation||current.PlanDigest!=op.PlanDigest{return current,errors.New("operation changed before mutation lock acquisition")};op=current
 op.Status=model.OpRunning;op.Stage="preflight-revalidation";op.Error="";_ = e.Store.SaveOperation(op)
 fail:=func(stage string,cause error,ambiguous bool)(model.Operation,error){op.Stage=stage;op.Error=redact(cause.Error());if ambiguous{op.Status=model.OpUnknown}else{op.Status=model.OpFailedNeedsRecovery};_ = e.Store.SaveOperation(op);return op,cause}
 if e.Runner==nil{return fail("executor",errors.New("privileged executor unavailable"),false)}
 if _,err=preflight.System(ctx,req,e.Runner);err!=nil{return fail("preflight-revalidation",err,false)}
 if err=(mounts.Manager{Runner:e.Runner}).Prepare(ctx,req.Storage);err!=nil{return fail("storage",err,false)}
 op.Stage="install";_ = e.Store.SaveOperation(op);if err=p.Install(ctx,op,plan);err!=nil{return fail("install",err,isAmbiguous(err))}
 op.Stage="configure";_ = e.Store.SaveOperation(op);if err=p.Configure(ctx,op,plan);err!=nil{return fail("configure",err,isAmbiguous(err))}
 op.Stage="initialize";_ = e.Store.SaveOperation(op);if req.Topology=="cluster"{if err=p.Join(ctx,op,plan);err!=nil{return fail("join",err,isAmbiguous(err))}}else if err=p.Initialize(ctx,op,plan);err!=nil{return fail("initialize",err,isAmbiguous(err))}
 st:=model.ServiceState{ID:req.ServiceID,Provider:req.Provider,Category:req.Category,ReleaseLine:req.ReleaseLine,ResolvedVersion:plan.ResolvedVersion,Topology:req.Topology,Storage:req.Storage,Network:req.Network,Maintenance:req.Maintenance,Backup:req.Backup,Cluster:req.Cluster,SecretRefs:req.SecretRefs,ConfigDigest:requestDigest,PlanDigest:plan.Digest,Status:"installing",UpdatedAt:time.Now().UTC()}
 op.Stage="service-start";_ = e.Store.SaveOperation(op);if err=p.Start(ctx,op,st);err!=nil{return fail("service-start",err,isAmbiguous(err))}
 op.Stage="firewall";_ = e.Store.SaveOperation(op);if err=(firewall.Manager{Runner:e.Runner}).Apply(ctx,req.ServiceID,req.Network.Port,req.Network.AllowedCIDRs);err!=nil{return fail("firewall",err,isAmbiguous(err))}
 op.Status=model.OpVerifying;op.Stage="health";_ = e.Store.SaveOperation(op);st.Status="installed"
 h,err:=p.Health(ctx,st);if err!=nil{return fail("health",err,false)};if !h.Healthy{return fail("health",errors.New(h.Error),false)}
 if err=e.Store.SaveService(st);err!=nil{return fail("commit-state",err,false)}
 op.Status=model.OpSucceeded;op.Stage="complete";op.Error="";_ = e.Store.SaveOperation(op);return op,nil
}

func validateStoredPlan(plan model.Plan,op model.Operation,requestDigest string)error{
 if plan.ID!=op.ID||plan.ServiceID!=op.ServiceID||plan.Digest==""||op.PlanDigest==""||plan.Digest!=op.PlanDigest{return errors.New("stored plan identity/digest mismatch")}
 canonical,err:=config.PlanDigest(plan);if err!=nil{return err};if canonical!=plan.Digest{return errors.New("stored immutable plan failed integrity verification")}
 d,err:=config.CanonicalDigest(plan.Request);if err!=nil{return err};if d!=requestDigest||d!=op.RequestDigest{return errors.New("stored plan request does not match operation intent")}
 if plan.Provider!=plan.Request.Provider||plan.ServiceID!=plan.Request.ServiceID||plan.ID!=plan.Request.OperationID{return errors.New("stored plan/request identity mismatch")}
 return nil
}
func isAmbiguous(err error)bool{return errors.Is(err,context.DeadlineExceeded)||errors.Is(err,context.Canceled)}
func(e *Engine)Health(ctx context.Context,id string)(model.HealthResult,error){st,err:=e.Store.GetService(id);if err!=nil{return model.HealthResult{},err};p,ok:=e.Registry.Get(st.Provider);if !ok{return model.HealthResult{},errors.New("provider unavailable")};return p.Health(ctx,st)}
func(e *Engine)Uninstall(ctx context.Context,id string,op model.Operation,destroyData bool)(model.Operation,error){st,err:=e.Store.GetService(id);if err!=nil{return op,err};p,ok:=e.Registry.Get(st.Provider);if !ok{return op,errors.New("provider unavailable")};lk,err:=lock.Acquire(e.LockPath);if err!=nil{return op,err};defer lk.Release();op.Status=model.OpRunning;op.Stage="uninstall";_ = e.Store.SaveOperation(op);if err=p.Uninstall(ctx,op,st,destroyData);err!=nil{op.Status=model.OpFailedNeedsRecovery;op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return op,err};if e.Runner!=nil{if err=(firewall.Manager{Runner:e.Runner}).Remove(ctx,id);err!=nil{op.Status=model.OpFailedNeedsRecovery;op.Stage="firewall-cleanup";op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return op,err}};res,err:=p.ResidueAudit(ctx,st);if err!=nil{return op,err};for _,v:=range res{if v=="present"||v=="active"{op.Status=model.OpFailedNeedsRecovery;op.Stage="residue-audit";op.Error="managed residue remains";_ = e.Store.SaveOperation(op);return op,errors.New("managed residue remains")}};st.Status="uninstalled-data-preserved";_ = e.Store.SaveService(st);op.Status=model.OpSucceeded;op.Stage="complete";op.Error="";_ = e.Store.SaveOperation(op);return op,nil}
func redact(s string)string{if len(s)>1024{s=s[:1024]};return s}
