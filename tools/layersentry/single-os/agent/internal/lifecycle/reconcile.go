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
// timed out. A terminal state is selected only when provider-native evidence is
// strong enough to prove success or prove that recovery is required.
func(e *Engine)ReconcileUnknown(ctx context.Context,operationID string)(ReconcileResult,error){op,err:=e.Store.GetOperation(operationID);if err!=nil{return ReconcileResult{},err};if op.Status!=model.OpUnknown{return ReconcileResult{},errors.New("operation is not UNKNOWN")};lk,err:=lock.Acquire(e.LockPath);if err!=nil{return ReconcileResult{},err};defer lk.Release();observed:=map[string]string{"previous_stage":op.Stage};st,stErr:=e.Store.GetService(op.ServiceID);var pProvider string;if stErr==nil{pProvider=st.Provider}else{plan,planErr:=e.Store.GetPlan(op.ID);if planErr==nil{req:=plan.Request;st=model.ServiceState{ID:req.ServiceID,Provider:req.Provider,Category:req.Category,ReleaseLine:req.ReleaseLine,ResolvedVersion:plan.ResolvedVersion,Topology:req.Topology,Storage:req.Storage,Network:req.Network,Maintenance:req.Maintenance,Backup:req.Backup,Cluster:req.Cluster,SecretRefs:req.SecretRefs,PlanDigest:plan.Digest,Status:"observed-after-unknown",UpdatedAt:time.Now().UTC()};pProvider=plan.Provider}else if !errors.Is(stErr,os.ErrNotExist){return ReconcileResult{},stErr}}
 if pProvider==""{op.Stage="observation-inconclusive";op.Error="no durable service or plan state available for authoritative observation";_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil};p,ok:=e.Registry.Get(pProvider);if !ok{return ReconcileResult{},errors.New("provider unavailable for UNKNOWN observation")}
 switch op.Stage{
 case "backup":b,bErr:=e.Store.GetBackup(op.ID);if bErr==nil&&b.Verified&&b.ServiceID==op.ServiceID{observed["backup"]="verified-catalog-entry";op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error=""}else{observed["backup"]="no-verified-catalog-entry";op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="timed-out backup has no verified catalog record; do not reuse the operation UUID"};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 case "uninstall":res,rErr:=p.ResidueAudit(ctx,st);if rErr!=nil{return ReconcileResult{},rErr};for k,v:=range res{observed[k]=v};if noManagedResidue(res){op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";st.Status="uninstalled-data-preserved";_ = e.Store.SaveService(st)}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="managed residue remains after ambiguous uninstall"};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 case "stop":res,rErr:=p.ResidueAudit(ctx,st);if rErr!=nil{return ReconcileResult{},rErr};for k,v:=range res{observed[k]=v};if res["service"]=="inactive"{op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error=""}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="service remains active after ambiguous stop"};_ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil
 }
 h,hErr:=p.Health(ctx,st);if hErr!=nil{observed["health_error"]=hErr.Error()}else{observed["healthy"]=fmt.Sprintf("%t",h.Healthy);observed["version"]=h.Version}
 switch op.Stage{
 case "install","service-start","firewall","health","start","restart","repair":if hErr==nil&&h.Healthy{op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";if stErr!=nil{st.Status="installed";if err=e.Store.SaveService(st);err!=nil{return ReconcileResult{},err}}}else{op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="provider health does not prove successful completion after timeout"}
 case "upgrade":plan,pErr:=e.Store.GetPlan(op.ID);if pErr==nil&&hErr==nil&&h.Healthy&&versionMatches(plan.ResolvedVersion,h.Version){observed["target_version"]="matched";op.Status=model.OpSucceeded;op.Stage="reconciled-success";op.Error="";st.ResolvedVersion=plan.ResolvedVersion;st.PlanDigest=plan.Digest;_ = e.Store.SaveService(st)}else{observed["target_version"]="not-proven";op.Status=model.OpFailedNeedsRecovery;op.Stage="reconciled-needs-recovery";op.Error="healthy service does not prove the requested upgrade target"}
 case "restore":op.Stage="observation-inconclusive";op.Error="service health cannot prove restored data contents; restore remains UNKNOWN pending explicit data validation"
 default:op.Stage="observation-inconclusive";op.Error="no authoritative reconciliation rule for previous mutation stage"
 }
 _ = e.Store.SaveOperation(op);return ReconcileResult{Operation:op,Observed:observed},nil}
func noManagedResidue(res map[string]string)bool{for _,v:=range res{if v=="present"||v=="active"{return false}};return true}
func versionMatches(target,observed string)bool{v:=observedVersionRE.FindString(observed);return v!=""&&strings.Contains(target,v)}
