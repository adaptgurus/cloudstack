package lifecycle

import (
    "context"
    "errors"
    "fmt"
    "os"
    "regexp"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lock"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

var observedVersionRE=regexp.MustCompile(`[0-9]+\.[0-9]+(?:\.[0-9]+)?`)
type ReconcileResult struct{Operation model.Operation `json:"operation"`;Observed map[string]string `json:"observed"`}

// ReconcileUnknown performs observation only. It never repeats the mutation that
// timed out. In particular, a healthy service does not prove that later install
// stages (for example the firewall) executed, so only a timeout in the final
// health-verification stage may reconcile an install to success.
func(e *Engine)ReconcileUnknown(ctx context.Context,operationID string)(ReconcileResult,error){
 op,err:=e.Store.GetOperation(operationID);if err!=nil{return ReconcileResult{},err};if op.Status!=model.OpUnknown{return ReconcileResult{},errors.New("operation is not UNKNOWN")};lk,err:=lock.Acquire(e.LockPath);if err!=nil{return ReconcileResult{},err};defer lk.Release();observed:=map[string]string{"previous_stage":op.Stage};previousStage:=op.Stage
 st,stErr:=e.Store.GetService(op.ServiceID);var providerID string
 if stErr==nil{providerID=st.Provider}else{plan,planErr:=e.Store.GetPlan(op.ID);if planErr==nil{req:=plan.Request;st=model.ServiceState{ID:req.ServiceID,Provider:req.Provider,Category:req.Category,ReleaseLine:req.ReleaseLine,ResolvedVersion:plan.ResolvedVersion,Topology:req.Topology,Storage:req.Storage,Network:req.Network,Maintenance:req.Maintenance,Backup:req.Backup,Cluster:req.Cluster,SecretRefs:req.SecretRefs,PlanDigest:plan.Digest,Status:"unknown-recovery",RecoveryRequired:true,FailureStage:previousStage,LastOperationID:op.ID,UpdatedAt:time.Now().UTC()};providerID=plan.Provider}else if !errors.Is(stErr,os.ErrNotExist){return ReconcileResult{},stErr}}
 if providerID==""{op.Stage="observation-inconclusive";op.Error="no durable service or plan state available for authoritative observation";_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil};p,ok:=e.Registry.Get(providerID);if !ok{return ReconcileResult{},errors.New("provider unavailable for UNKNOWN observation")}
 markService:=func(success bool,status,stage string){st.LastOperationID=op.ID;if success{st.Status=status;st.RecoveryRequired=false;st.FailureStage=""}else{st.Status="failed-needs-recovery";st.RecoveryRequired=true;st.FailureStage=stage};_ = e.Store.SaveService(st)}
 switch previousStage{
 case "backup":b,bErr:=e.Store.GetBackup(op.ID);if bErr==nil&&b.Verified&&b.ServiceID==op.ServiceID{observed["backup"]="verified-catalog-entry";op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error=""}else{observed["backup"]="no-verified-catalog-entry";op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="timed-out backup has no verified catalog record; do not reuse the operation UUID"};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 case "uninstall":res,rErr:=p.ResidueAudit(ctx,st);if rErr!=nil{return ReconcileResult{},rErr};for k,v:=range res{observed[k]=v};if noManagedResidue(res){op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";markService(true,"uninstalled-data-preserved","")}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="managed residue remains after ambiguous uninstall";markService(false,"",previousStage)};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 case "stop":res,rErr:=p.ResidueAudit(ctx,st);if rErr!=nil{return ReconcileResult{},rErr};for k,v:=range res{observed[k]=v};if res["service"]=="inactive"{op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";markService(true,"stopped","")}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="service remains active after ambiguous stop";markService(false,"",previousStage)};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 }
 h,hErr:=p.Health(ctx,st);if hErr!=nil{observed["health_error"]=hErr.Error()}else{observed["healthy"]=fmt.Sprintf("%t",h.Healthy);observed["version"]=h.Version}
 switch previousStage{
 case "health":
  if hErr==nil&&h.Healthy{op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";markService(true,"installed","")}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="final install health could not be proven after timeout";markService(false,"",previousStage)}
 case "start","restart","repair":
  if hErr==nil&&h.Healthy{op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";markService(true,"installed","")}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="provider health does not prove successful lifecycle completion after timeout";markService(false,"",previousStage)}
 case "upgrade":
  plan,pErr:=e.Store.GetPlan(op.ID);if pErr==nil&&hErr==nil&&h.Healthy&&versionMatches(plan.ResolvedVersion,h.Version){observed["target_version"]="matched";op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";st.ResolvedVersion=plan.ResolvedVersion;st.PlanDigest=plan.Digest;markService(true,"installed","")}else{observed["target_version"]="not-proven";op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="healthy service does not prove the requested upgrade target";markService(false,"",previousStage)}
 case "restore":
  op.Stage="observation-inconclusive";op.Error="service health cannot prove restored data contents; restore remains UNKNOWN pending explicit data validation";st.Status="unknown-recovery";st.RecoveryRequired=true;st.FailureStage=previousStage;st.LastOperationID=op.ID;_ = e.Store.SaveService(st)
 case "install","configure","initialize","cluster-enrollment","join","service-start","firewall":
  op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="the timed-out install stage cannot prove that all subsequent confirmed-plan stages executed; mutation is not replayed";markService(false,"",previousStage)
 default:
  op.Stage="observation-inconclusive";op.Error="no authoritative reconciliation rule for previous mutation stage";st.Status="unknown-recovery";st.RecoveryRequired=true;st.FailureStage=previousStage;st.LastOperationID=op.ID;_ = e.Store.SaveService(st)
 }
 _ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
}
func noManagedResidue(res map[string]string)bool{for _,v:=range res{if v=="present"||v=="active"{return false}};return true}
func versionMatches(target,observed string)bool{v:=observedVersionRE.FindString(observed);return v!=""&&strings.Contains(target,v)}
