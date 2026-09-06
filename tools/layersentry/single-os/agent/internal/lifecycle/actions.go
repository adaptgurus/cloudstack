package lifecycle

import (
 "context"
 "crypto/sha256"
 "encoding/hex"
 "errors"
 "fmt"
 "strconv"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/firewall"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lock"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type ActionRequest struct{OperationID string `json:"operation_id"`;IdempotencyKey string `json:"idempotency_key"`;Action string `json:"action"`;DestroyData bool `json:"destroy_data,omitempty"`;BackupID string `json:"backup_id,omitempty"`;ConfirmedBackupSHA256 string `json:"confirmed_backup_sha256,omitempty"`}

func(e *Engine)Action(ctx context.Context,serviceID string,r ActionRequest)(model.Operation,error){
 if r.OperationID==""||r.IdempotencyKey==""{return model.Operation{},errors.New("operation_id and idempotency_key required")}
 switch r.Action{case "start","stop","restart","upgrade","repair","backup","restore","uninstall":default:return model.Operation{},errors.New("unsupported lifecycle action")}
 if r.Action!="restore"&&(r.BackupID!=""||r.ConfirmedBackupSHA256!=""){return model.Operation{},errors.New("backup selection fields are only allowed for restore")}
 if r.Action=="restore"&&(r.BackupID==""||r.ConfirmedBackupSHA256==""){return model.Operation{},errors.New("restore requires backup_id and confirmed_backup_sha256")}
 st,err:=e.Store.GetService(serviceID);if err!=nil{return model.Operation{},err};if st.Status=="uninstalled-data-preserved"&&r.Action!="restore"{return model.Operation{},errors.New("service is uninstalled; create a new install plan before lifecycle actions")}
 p,ok:=e.Registry.Get(st.Provider);if !ok{return model.Operation{},errors.New("provider unavailable")}
 sum:=sha256.Sum256([]byte(serviceID+"|"+r.Action+"|"+r.BackupID+"|"+r.ConfirmedBackupSHA256+"|"+strconv.FormatBool(r.DestroyData)))
 proposed:=model.Operation{ID:r.OperationID,ServiceID:serviceID,IdempotencyKey:r.IdempotencyKey,RequestDigest:hex.EncodeToString(sum[:]),Status:model.OpRequested,Stage:r.Action}
 op,err:=e.Store.Begin(proposed);if err!=nil{return op,err}
 if op.Status==model.OpSucceeded{return op,nil}
 if op.Status==model.OpUnknown{return op,errors.New("UNKNOWN operation requires authoritative observation before retry")}
 if op.Status!=model.OpRequested{return op,fmt.Errorf("operation state %s cannot be replayed",op.Status)}
 lk,err:=lock.Acquire(e.LockPath);if err!=nil{return op,err};defer lk.Release()
 current,err:=e.Store.GetOperation(op.ID);if err!=nil{return op,err};if current.Status!=model.OpRequested||current.RequestDigest!=op.RequestDigest||current.IdempotencyKey!=op.IdempotencyKey{return current,errors.New("operation changed before mutation lock acquisition")};op=current
 op.Status=model.OpRunning;op.Stage=r.Action;op.Error="";_ = e.Store.SaveOperation(op)
 fail:=func(cause error,ambiguous bool)(model.Operation,error){op.Error=redact(cause.Error());if ambiguous{op.Status=model.OpUnknown}else{op.Status=model.OpFailedNeedsRecovery};_ = e.Store.SaveOperation(op);return op,cause}
 switch r.Action{
 case "start":err=p.Start(ctx,op,st)
 case "stop":err=p.Stop(ctx,op,st)
 case "restart":err=p.Restart(ctx,op,st)
 case "repair":
  plan:=planFromState(op,st);plan.Digest="";if plan.Digest,err=config.PlanDigest(plan);err!=nil{return fail(err,false)};if err=e.Store.SavePlan(plan);err!=nil{return fail(err,false)};op.PlanDigest=plan.Digest;_ = e.Store.SaveOperation(op);err=p.Repair(ctx,op,plan)
 case "backup":
  var rec model.BackupRecord;rec,err=p.Backup(ctx,op,st);if err==nil{if rec.ID==""{rec.ID=op.ID};if rec.ServiceID==""{rec.ServiceID=st.ID};if rec.Provider==""{rec.Provider=st.Provider};if rec.CreatedAt.IsZero(){rec.CreatedAt=time.Now().UTC()};err=e.Store.SaveBackup(rec)}
 case "restore":
  var rec model.BackupRecord;rec,err=e.Store.GetBackup(r.BackupID);if err==nil{if rec.ServiceID!=st.ID||rec.Provider!=st.Provider||!rec.Verified{return fail(errors.New("backup does not belong to this verified service/provider"),false)};if rec.SHA256!=r.ConfirmedBackupSHA256{return fail(errors.New("confirmed backup checksum mismatch"),false)};err=p.Restore(ctx,op,st,rec)}
 case "upgrade":
  req:=requestFromState(op,st,r.IdempotencyKey);resolved,e2:=p.ResolveVersion(ctx,req);if e2!=nil{return fail(e2,false)};if resolved==st.ResolvedVersion{op.Status=model.OpSucceeded;op.Stage="already-current";op.Error="";_ = e.Store.SaveOperation(op);return op,nil};plan,e2:=p.Plan(ctx,req,resolved);if e2!=nil{return fail(e2,false)};plan.Request=req;plan.Digest="";if plan.Digest,e2=config.PlanDigest(plan);e2!=nil{return fail(e2,false)};if e2=e.Store.SavePlan(plan);e2!=nil{return fail(e2,false)};op.PlanDigest=plan.Digest;_ = e.Store.SaveOperation(op);err=p.Upgrade(ctx,op,plan);if err==nil{st.ResolvedVersion=resolved;st.PlanDigest=plan.Digest;st.UpdatedAt=time.Now().UTC();_ = e.Store.SaveService(st)}
 case "uninstall":return e.uninstallLocked(ctx,st,p,op,r.DestroyData)
 }
 if err!=nil{return fail(err,isAmbiguous(err))}
 if r.Action!="stop"&&r.Action!="backup"{h,herr:=p.Health(ctx,st);if herr!=nil{return fail(herr,false)};if !h.Healthy{return fail(fmt.Errorf("post-%s health failed: %s",r.Action,h.Error),false)}}
 switch r.Action{case "stop":st.Status="stopped";_ = e.Store.SaveService(st);case "start","restart","repair","restore":st.Status="installed";_ = e.Store.SaveService(st)}
 op.Status=model.OpSucceeded;op.Stage="complete";op.Error="";_ = e.Store.SaveOperation(op);return op,nil
}
func requestFromState(op model.Operation,st model.ServiceState,idempotency string)model.ServiceRequest{return model.ServiceRequest{SchemaVersion:1,RequestID:op.ID,ServiceID:st.ID,OperationID:op.ID,IdempotencyKey:idempotency,Category:st.Category,Provider:st.Provider,ReleaseLine:st.ReleaseLine,Topology:st.Topology,Storage:st.Storage,Network:st.Network,Maintenance:st.Maintenance,Backup:st.Backup,Cluster:st.Cluster,SecretRefs:st.SecretRefs}}
func planFromState(op model.Operation,st model.ServiceState)model.Plan{req:=requestFromState(op,st,op.IdempotencyKey);return model.Plan{ID:op.ID,ServiceID:st.ID,Provider:st.Provider,ResolvedVersion:st.ResolvedVersion,CreatedAt:time.Now().UTC(),Request:req}}
func(e *Engine)uninstallLocked(ctx context.Context,st model.ServiceState,p interface{Uninstall(context.Context,model.Operation,model.ServiceState,bool)error;ResidueAudit(context.Context,model.ServiceState)(map[string]string,error)},op model.Operation,destroy bool)(model.Operation,error){if err:=p.Uninstall(ctx,op,st,destroy);err!=nil{op.Status=model.OpFailedNeedsRecovery;op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return op,err};if e.Runner!=nil{if err:=(firewall.Manager{Runner:e.Runner}).Remove(ctx,st.ID);err!=nil{op.Status=model.OpFailedNeedsRecovery;op.Stage="firewall-cleanup";op.Error=redact(err.Error());_ = e.Store.SaveOperation(op);return op,err}};res,err:=p.ResidueAudit(ctx,st);if err!=nil{return op,err};for _,v:=range res{if v=="present"||v=="active"{op.Status=model.OpFailedNeedsRecovery;op.Stage="residue-audit";op.Error="managed residue remains";_ = e.Store.SaveOperation(op);return op,errors.New("managed residue remains")}};st.Status="uninstalled-data-preserved";_ = e.Store.SaveService(st);op.Status=model.OpSucceeded;op.Stage="complete";op.Error="";_ = e.Store.SaveOperation(op);return op,nil}
