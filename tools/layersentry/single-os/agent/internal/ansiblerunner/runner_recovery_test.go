package ansiblerunner

import (
	"encoding/base64"
	"testing"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func TestValidatePlanOperationIdentityAllowsExplicitRecoveryOfImmutablePlan(t *testing.T) {
	const original = "11111111-1111-4111-8111-111111111111"
	const recovery = "22222222-2222-4222-8222-222222222222"
	const service = "33333333-3333-4333-8333-333333333333"
	plan := model.Plan{ID: original, ServiceID: service, Digest: "abc123", Request: model.ServiceRequest{OperationID: original, ServiceID: service}}
	op := model.Operation{ID: recovery, ServiceID: service, PlanDigest: plan.Digest, RecoveryOfOperationID: original}
	if err := validatePlanOperationIdentity(op, plan); err != nil {
		t.Fatalf("recovery identity rejected: %v", err)
	}
}

func TestValidatePlanOperationIdentityRejectsRecoveryDigestMismatch(t *testing.T) {
	const original = "11111111-1111-4111-8111-111111111111"
	const recovery = "22222222-2222-4222-8222-222222222222"
	const service = "33333333-3333-4333-8333-333333333333"
	plan := model.Plan{ID: original, ServiceID: service, Digest: "original-digest", Request: model.ServiceRequest{OperationID: original, ServiceID: service}}
	op := model.Operation{ID: recovery, ServiceID: service, PlanDigest: "changed", RecoveryOfOperationID: original}
	if err := validatePlanOperationIdentity(op, plan); err == nil {
		t.Fatal("expected recovery digest mismatch rejection")
	}
}

func TestSafeAnsibleDiagnosticDecodesOnlyExplicitStorageToken(t *testing.T) {
	want := "command failed rc=5: lvcreate: device activation failed"
	token := base64.RawURLEncoding.EncodeToString([]byte(want))
	res := executor.Result{Stdout: `fatal: [localhost]: FAILED! => {"msg":"layersentry-storage-safe:` + token + ` visible text"}`}
	if got := safeAnsibleDiagnostic(res); got != want {
		t.Fatalf("diagnostic mismatch: got %q want %q", got, want)
	}
	if got := safeAnsibleDiagnostic(executor.Result{Stdout: "fatal: raw password=must-not-leak"}); got != "" {
		t.Fatalf("unmarked output must not be promoted into durable errors: %q", got)
	}
}
