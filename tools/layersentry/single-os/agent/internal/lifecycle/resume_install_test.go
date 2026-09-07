package lifecycle

import (
	"context"
	"errors"
	"path/filepath"
	"testing"
	"time"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
)

const (
	resumeServiceID   = "11111111-1111-4111-8111-111111111111"
	resumeOriginalID  = "22222222-2222-4222-8222-222222222222"
	resumeRequestID   = "33333333-3333-4333-8333-333333333333"
	resumeRecoveryID  = "44444444-4444-4444-8444-444444444444"
	resumeRecoveryID2 = "55555555-5555-4555-8555-555555555555"
	resumeOtherID     = "66666666-6666-4666-8666-666666666666"
)

type resumeRepoRunner struct{}

func (resumeRepoRunner) Run(_ context.Context, path string, args ...string) (executor.Result, error) {
	if path == "/usr/bin/dnf" && len(args) == 4 && args[0] == "-q" && args[1] == "config-manager" && args[2] == "--dump" && args[3] == "pgdg17" {
		return executor.Result{Stdout: "[pgdg17]\nenabled=1\ngpgcheck=1\nsslverify=1\nbaseurl=https://download.postgresql.org/pub/repos/yum/17/redhat/rhel-9-x86_64\ngpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-PGDG\n", ExitCode: 0}, nil
	}
	return executor.Result{ExitCode: 127}, errors.New("unexpected runner command")
}

type resumeBaseProvider struct{}

func (*resumeBaseProvider) ID() string                                           { return "postgresql" }
func (*resumeBaseProvider) Category() model.Category                             { return model.CategoryDatabase }
func (*resumeBaseProvider) Validate(context.Context, model.ServiceRequest) error { return nil }
func (*resumeBaseProvider) ResolveVersion(context.Context, model.ServiceRequest) (string, error) {
	return "postgresql17-server-0:17.11-1PGDG.rhel9.8.x86_64", nil
}
func (*resumeBaseProvider) Plan(context.Context, model.ServiceRequest, string) (model.Plan, error) {
	return model.Plan{}, nil
}
func (*resumeBaseProvider) Install(context.Context, model.Operation, model.Plan) error    { return nil }
func (*resumeBaseProvider) Configure(context.Context, model.Operation, model.Plan) error  { return nil }
func (*resumeBaseProvider) Initialize(context.Context, model.Operation, model.Plan) error { return nil }
func (*resumeBaseProvider) Join(context.Context, model.Operation, model.Plan) error       { return nil }
func (*resumeBaseProvider) Health(context.Context, model.ServiceState) (model.HealthResult, error) {
	return model.HealthResult{Healthy: true, Version: "17.11"}, nil
}
func (*resumeBaseProvider) Start(context.Context, model.Operation, model.ServiceState) error {
	return nil
}
func (*resumeBaseProvider) Stop(context.Context, model.Operation, model.ServiceState) error {
	return nil
}
func (*resumeBaseProvider) Restart(context.Context, model.Operation, model.ServiceState) error {
	return nil
}
func (*resumeBaseProvider) Upgrade(context.Context, model.Operation, model.Plan) error { return nil }
func (*resumeBaseProvider) Repair(context.Context, model.Operation, model.Plan) error  { return nil }
func (*resumeBaseProvider) Backup(context.Context, model.Operation, model.ServiceState) (model.BackupRecord, error) {
	return model.BackupRecord{}, nil
}
func (*resumeBaseProvider) Restore(context.Context, model.Operation, model.ServiceState, model.BackupRecord) error {
	return nil
}
func (*resumeBaseProvider) Uninstall(context.Context, model.Operation, model.ServiceState, bool) error {
	return nil
}
func (*resumeBaseProvider) ResidueAudit(context.Context, model.ServiceState) (map[string]string, error) {
	return map[string]string{}, nil
}

type resumeTxProvider struct {
	*resumeBaseProvider
	applyErr   error
	ownerErr   error
	applyCalls int
}

func (p *resumeTxProvider) Apply(_ context.Context, op model.Operation, plan model.Plan) error {
	p.applyCalls++
	if op.RecoveryOfOperationID != plan.ID {
		return errors.New("test provider observed recovery/original mismatch")
	}
	return p.applyErr
}
func (*resumeTxProvider) ManagesGuestPlatform() bool                        { return true }
func (p *resumeTxProvider) VerifyGuestOwnership(model.ServiceRequest) error { return p.ownerErr }

type resumeFixture struct {
	engine   *Engine
	store    *journal.Store
	plan     model.Plan
	original model.Operation
	service  model.ServiceState
	request  ResumeInstallRequest
}

func newResumeFixture(t *testing.T, p provider.Provider) *resumeFixture {
	t.Helper()
	root := filepath.Join(t.TempDir(), "journal")
	store, err := journal.New(root)
	if err != nil {
		t.Fatal(err)
	}
	registry := provider.NewRegistry()
	if err = registry.Register(p); err != nil {
		t.Fatal(err)
	}
	runner := resumeRepoRunner{}
	repoDigest, err := (packageutil.DNF{Runner: runner}).RepositoryDigest(context.Background(), "pgdg17")
	if err != nil {
		t.Fatal(err)
	}
	req := model.ServiceRequest{
		SchemaVersion:  1,
		RequestID:      resumeRequestID,
		ServiceID:      resumeServiceID,
		OperationID:    resumeOriginalID,
		IdempotencyKey: "original-install-key",
		Category:       model.CategoryDatabase,
		Provider:       "postgresql",
		ReleaseLine:    "17",
		Topology:       "standalone",
		LVM: []model.LVMVolumeGroup{{
			Name: "ls_pg", Devices: []string{"/dev/disk/by-id/test-disk"}, InitializePVs: true, ConfirmPVInitialize: true,
			LogicalVolumes: []model.LVMLogicalVolume{{Name: "ls_pgdata", Size: "8G", MountPoint: "/data/postgresql", Purpose: "database-data", Filesystem: "xfs", Format: true, ConfirmFormat: true}},
		}},
		Network:     model.NetworkSpec{ListenAddress: "10.10.10.16", Port: 5432, AllowedCIDRs: []string{"10.10.10.0/24"}},
		Maintenance: model.MaintenancePolicy{Mode: "manual", ReleaseLineLocked: true},
		Backup:      model.BackupPolicy{},
	}
	requestDigest, err := config.CanonicalDigest(req)
	if err != nil {
		t.Fatal(err)
	}
	plan := model.Plan{
		ID:               resumeOriginalID,
		ServiceID:        resumeServiceID,
		Provider:         "postgresql",
		ResolvedVersion:  "postgresql17-server-0:17.11-1PGDG.rhel9.8.x86_64",
		RepositoryID:     "pgdg17",
		RepositoryDigest: repoDigest,
		CreatedAt:        time.Unix(1700000000, 0).UTC(),
		Request:          req,
		Steps:            []model.PlanStep{{Name: "apply", Action: "transactional guest apply"}},
	}
	plan.Digest, err = config.PlanDigest(plan)
	if err != nil {
		t.Fatal(err)
	}
	original := model.Operation{
		ID:             resumeOriginalID,
		ServiceID:      resumeServiceID,
		IdempotencyKey: req.IdempotencyKey,
		RequestDigest:  requestDigest,
		PlanDigest:     plan.Digest,
		Status:         model.OpFailedNeedsRecovery,
		Stage:          resumeInstallStage,
		Error:          "original guest apply failure",
	}
	if _, err = store.Begin(original); err != nil {
		t.Fatal(err)
	}
	if err = store.SaveOperation(original); err != nil {
		t.Fatal(err)
	}
	if err = store.SavePlan(plan); err != nil {
		t.Fatal(err)
	}
	service := model.ServiceState{
		ID:               req.ServiceID,
		Provider:         req.Provider,
		Category:         req.Category,
		ReleaseLine:      req.ReleaseLine,
		ResolvedVersion:  plan.ResolvedVersion,
		RepositoryID:     plan.RepositoryID,
		RepositoryDigest: plan.RepositoryDigest,
		Topology:         req.Topology,
		Storage:          req.Storage,
		LVM:              req.LVM,
		Network:          req.Network,
		Maintenance:      req.Maintenance,
		Backup:           req.Backup,
		Cluster:          req.Cluster,
		SecretRefs:       req.SecretRefs,
		PlatformPackages: plan.PlatformPackages,
		ConfigDigest:     requestDigest,
		PlanDigest:       plan.Digest,
		Status:           "failed-needs-recovery",
		RecoveryRequired: true,
		FailureStage:     resumeInstallStage,
		LastOperationID:  resumeOriginalID,
	}
	if err = store.SaveService(service); err != nil {
		t.Fatal(err)
	}
	engine := &Engine{Registry: registry, Store: store, Runner: runner, LockPath: filepath.Join(t.TempDir(), "mutation.lock")}
	return &resumeFixture{
		engine: engine, store: store, plan: plan, original: original, service: service,
		request: ResumeInstallRequest{OperationID: resumeRecoveryID, IdempotencyKey: "resume-key", FailedOperationID: resumeOriginalID, ConfirmedPlanDigest: plan.Digest},
	}
}

func TestResumeInstallSuccessPreservesOriginalFailureAudit(t *testing.T) {
	tx := &resumeTxProvider{resumeBaseProvider: &resumeBaseProvider{}}
	f := newResumeFixture(t, tx)
	op, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, f.request)
	if err != nil {
		t.Fatalf("resume failed: %v", err)
	}
	if op.Status != model.OpSucceeded || op.RecoveryOfOperationID != resumeOriginalID || op.PlanDigest != f.plan.Digest {
		t.Fatalf("unexpected recovery op: %+v", op)
	}
	if tx.applyCalls != 1 {
		t.Fatalf("apply calls=%d want 1", tx.applyCalls)
	}
	original, err := f.store.GetOperation(resumeOriginalID)
	if err != nil {
		t.Fatal(err)
	}
	if original.Status != model.OpFailedNeedsRecovery || original.Stage != resumeInstallStage || original.Error != "original guest apply failure" {
		t.Fatalf("original failure was rewritten: %+v", original)
	}
	st, err := f.store.GetService(resumeServiceID)
	if err != nil {
		t.Fatal(err)
	}
	if st.Status != "installed" || st.RecoveryRequired || st.FailureStage != "" || st.LastOperationID != resumeRecoveryID {
		t.Fatalf("unexpected recovered service state: %+v", st)
	}
}

func TestResumeInstallRejectsGuardViolations(t *testing.T) {
	tests := []struct {
		name   string
		setup  func(*testing.T, *resumeFixture)
		invoke func(*resumeFixture) error
	}{
		{name: "wrong operation status", setup: func(t *testing.T, f *resumeFixture) {
			op := f.original
			op.Status = model.OpFailedSafe
			if err := f.store.SaveOperation(op); err != nil {
				t.Fatal(err)
			}
		}},
		{name: "wrong failure stage", setup: func(t *testing.T, f *resumeFixture) {
			op := f.original
			op.Stage = "health"
			if err := f.store.SaveOperation(op); err != nil {
				t.Fatal(err)
			}
		}},
		{name: "wrong plan digest", invoke: func(f *resumeFixture) error {
			r := f.request
			r.ConfirmedPlanDigest = "wrong-digest"
			_, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, r)
			return err
		}},
		{name: "changed service id", setup: func(t *testing.T, f *resumeFixture) {
			op := f.original
			op.ServiceID = resumeOtherID
			if err := f.store.SaveOperation(op); err != nil {
				t.Fatal(err)
			}
		}},
		{name: "changed service request", setup: func(t *testing.T, f *resumeFixture) {
			st := f.service
			st.Network.Port = 5433
			if err := f.store.SaveService(st); err != nil {
				t.Fatal(err)
			}
		}},
		{name: "corrupted stored plan", setup: func(t *testing.T, f *resumeFixture) {
			plan := f.plan
			plan.Steps = append(plan.Steps, model.PlanStep{Name: "corrupt", Action: "changed without digest"})
			if err := f.store.SavePlan(plan); err != nil {
				t.Fatal(err)
			}
		}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tx := &resumeTxProvider{resumeBaseProvider: &resumeBaseProvider{}}
			f := newResumeFixture(t, tx)
			if tt.setup != nil {
				tt.setup(t, f)
			}
			var err error
			if tt.invoke != nil {
				err = tt.invoke(f)
			} else {
				_, err = f.engine.ResumeInstall(context.Background(), resumeServiceID, f.request)
			}
			if err == nil {
				t.Fatal("expected guarded resume rejection")
			}
			if tx.applyCalls != 0 {
				t.Fatalf("guard failure reached guest Apply %d time(s)", tx.applyCalls)
			}
		})
	}
}

func TestResumeInstallRejectsNonTransactionalProvider(t *testing.T) {
	f := newResumeFixture(t, &resumeBaseProvider{})
	if _, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, f.request); err == nil {
		t.Fatal("expected non-transactional provider rejection")
	}
}

func TestResumeInstallRejectsOwnershipMismatchBeforeApply(t *testing.T) {
	tx := &resumeTxProvider{resumeBaseProvider: &resumeBaseProvider{}, ownerErr: errors.New("ownership mismatch")}
	f := newResumeFixture(t, tx)
	op, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, f.request)
	if err == nil {
		t.Fatal("expected ownership mismatch rejection")
	}
	if op.Status != model.OpFailedSafe || op.Stage != "ownership-revalidation" {
		t.Fatalf("ownership pre-mutation failure should be safe: %+v", op)
	}
	if tx.applyCalls != 0 {
		t.Fatal("ownership mismatch reached guest Apply")
	}
	st, err := f.store.GetService(resumeServiceID)
	if err != nil {
		t.Fatal(err)
	}
	if st.LastOperationID != resumeOriginalID || !st.RecoveryRequired || st.FailureStage != resumeInstallStage {
		t.Fatalf("pre-mutation failure rewrote original recovery head: %+v", st)
	}
}

func TestResumeInstallApplyFailureCreatesAuditableRecoveryHead(t *testing.T) {
	tx := &resumeTxProvider{resumeBaseProvider: &resumeBaseProvider{}, applyErr: errors.New("sanitized storage apply failure")}
	f := newResumeFixture(t, tx)
	op, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, f.request)
	if err == nil {
		t.Fatal("expected Apply failure")
	}
	if op.Status != model.OpFailedNeedsRecovery || op.Stage != resumeInstallStage || op.RecoveryOfOperationID != resumeOriginalID {
		t.Fatalf("unexpected failed recovery operation: %+v", op)
	}
	st, err := f.store.GetService(resumeServiceID)
	if err != nil {
		t.Fatal(err)
	}
	if st.Status != "failed-needs-recovery" || !st.RecoveryRequired || st.FailureStage != resumeInstallStage || st.LastOperationID != resumeRecoveryID {
		t.Fatalf("failed recovery was not durable: %+v", st)
	}

	tx.applyErr = nil
	r2 := f.request
	r2.OperationID = resumeRecoveryID2
	r2.IdempotencyKey = "resume-key-2"
	r2.FailedOperationID = resumeRecoveryID
	op2, err := f.engine.ResumeInstall(context.Background(), resumeServiceID, r2)
	if err != nil {
		t.Fatalf("second guarded recovery failed: %v", err)
	}
	if op2.Status != model.OpSucceeded || op2.RecoveryOfOperationID != resumeOriginalID {
		t.Fatalf("second recovery did not preserve original root: %+v", op2)
	}
}
