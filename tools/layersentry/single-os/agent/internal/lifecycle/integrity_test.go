package lifecycle

import (
    "testing"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func integrityRequest()model.ServiceRequest{return model.ServiceRequest{SchemaVersion:1,RequestID:"11111111-1111-4111-8111-111111111111",ServiceID:"22222222-2222-4222-8222-222222222222",OperationID:"33333333-3333-4333-8333-333333333333",IdempotencyKey:"idem",Category:model.CategoryApplication,Provider:"nginx",ReleaseLine:"rocky9",Topology:"standalone",Network:model.NetworkSpec{ListenAddress:"127.0.0.1",Port:8080,AllowedCIDRs:[]string{"127.0.0.0/8"}},Maintenance:model.MaintenancePolicy{Mode:"manual",ReleaseLineLocked:true},Backup:model.BackupPolicy{Enabled:false}}}
func integrityPlan(t *testing.T)(model.Plan,model.Operation,string){t.Helper();req:=integrityRequest();rd,err:=config.CanonicalDigest(req);if err!=nil{t.Fatal(err)};plan:=model.Plan{ID:req.OperationID,ServiceID:req.ServiceID,Provider:req.Provider,ResolvedVersion:"nginx-1:1.24.0-1.el9.x86_64",RepositoryID:"appstream",RepositoryDigest:"repo-digest",Request:req};pd,err:=config.PlanDigest(plan);if err!=nil{t.Fatal(err)};plan.Digest=pd;op:=model.Operation{ID:req.OperationID,ServiceID:req.ServiceID,IdempotencyKey:req.IdempotencyKey,RequestDigest:rd,PlanDigest:pd,Status:model.OpWaitingConfirmation};return plan,op,rd}
func TestValidateStoredPlanAcceptsCanonicalPlan(t *testing.T){plan,op,rd:=integrityPlan(t);if err:=validateStoredPlan(plan,op,rd);err!=nil{t.Fatalf("canonical plan rejected: %v",err)}}
func TestValidateStoredPlanRejectsResolvedVersionTamper(t *testing.T){plan,op,rd:=integrityPlan(t);plan.ResolvedVersion="nginx-evil";if err:=validateStoredPlan(plan,op,rd);err==nil{t.Fatal("tampered resolved version accepted")}}
func TestValidateStoredPlanRejectsRepositoryTamper(t *testing.T){plan,op,rd:=integrityPlan(t);plan.RepositoryDigest="different";if err:=validateStoredPlan(plan,op,rd);err==nil{t.Fatal("tampered repository provenance accepted")}}
func TestValidateStoredPlanRejectsRequestTamper(t *testing.T){plan,op,rd:=integrityPlan(t);plan.Request.Network.Port=9090;if err:=validateStoredPlan(plan,op,rd);err==nil{t.Fatal("tampered request accepted")}}
func TestValidateStoredPlanRejectsOperationDigestMismatch(t *testing.T){plan,op,rd:=integrityPlan(t);op.PlanDigest="wrong";if err:=validateStoredPlan(plan,op,rd);err==nil{t.Fatal("operation/plan digest mismatch accepted")}}
