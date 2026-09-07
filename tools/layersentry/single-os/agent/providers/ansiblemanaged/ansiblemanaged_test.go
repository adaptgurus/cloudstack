package ansiblemanaged

import (
    "context"
    "errors"
    "testing"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type fakeProvider struct{}
func (fakeProvider) ID() string { return "fake" }
func (fakeProvider) Category() model.Category { return model.CategoryApplication }
func (fakeProvider) Validate(context.Context, model.ServiceRequest) error { return nil }
func (fakeProvider) ResolveVersion(context.Context, model.ServiceRequest) (string,error) { return "fake-1.0-1.x86_64",nil }
func (fakeProvider) Plan(context.Context, model.ServiceRequest,string)(model.Plan,error){return model.Plan{},nil}
func (fakeProvider) Install(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Configure(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Initialize(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Join(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Health(context.Context,model.ServiceState)(model.HealthResult,error){return model.HealthResult{Healthy:true},nil}
func (fakeProvider) Start(context.Context,model.Operation,model.ServiceState)error{return nil}
func (fakeProvider) Stop(context.Context,model.Operation,model.ServiceState)error{return nil}
func (fakeProvider) Restart(context.Context,model.Operation,model.ServiceState)error{return nil}
func (fakeProvider) Upgrade(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Repair(context.Context,model.Operation,model.Plan)error{return nil}
func (fakeProvider) Backup(context.Context,model.Operation,model.ServiceState)(model.BackupRecord,error){return model.BackupRecord{},errors.New("unsupported")}
func (fakeProvider) Restore(context.Context,model.Operation,model.ServiceState,model.BackupRecord)error{return errors.New("unsupported")}
func (fakeProvider) Uninstall(context.Context,model.Operation,model.ServiceState,bool)error{return nil}
func (fakeProvider) ResidueAudit(context.Context,model.ServiceState)(map[string]string,error){return map[string]string{},nil}

func TestStandaloneOnlyRejectsCluster(t *testing.T){p:=New(fakeProvider{},nil,Spec{StandaloneOnly:true});req:=model.ServiceRequest{Topology:"cluster"};if err:=p.Validate(context.Background(),req);err==nil{t.Fatal("expected cluster rejection")}}
func TestPackageOnlyServiceActionsAreNoopWithoutRunner(t *testing.T){p:=New(fakeProvider{},nil,Spec{StandaloneOnly:true,PackageOnly:true});st:=model.ServiceState{ID:"22222222-2222-4222-8222-222222222222"};op:=model.Operation{ServiceID:st.ID};if err:=p.Start(context.Background(),op,st);err!=nil{t.Fatalf("package-only start: %v",err)};if err:=p.Stop(context.Background(),op,st);err!=nil{t.Fatalf("package-only stop: %v",err)};if err:=p.Restart(context.Background(),op,st);err!=nil{t.Fatalf("package-only restart: %v",err)}}
func TestServiceProviderRequiresRunnerForServiceMutation(t *testing.T){p:=New(fakeProvider{},nil,Spec{StandaloneOnly:true});st:=model.ServiceState{ID:"22222222-2222-4222-8222-222222222222"};op:=model.Operation{ServiceID:st.ID};if err:=p.Start(context.Background(),op,st);err==nil{t.Fatal("expected missing Ansible runner error")}}
func TestLegacyMutationMethodsFailClosed(t *testing.T){p:=New(fakeProvider{},nil,Spec{});if err:=p.Install(context.Background(),model.Operation{},model.Plan{});err==nil{t.Fatal("legacy install must fail closed")};if err:=p.Configure(context.Background(),model.Operation{},model.Plan{});err==nil{t.Fatal("legacy configure must fail closed")};if err:=p.Initialize(context.Background(),model.Operation{},model.Plan{});err==nil{t.Fatal("legacy initialize must fail closed")}}
