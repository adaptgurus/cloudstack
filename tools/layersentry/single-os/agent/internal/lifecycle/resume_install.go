package lifecycle

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"reflect"
	"strings"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lock"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
)

const resumeInstallStage = "guest-apply"

type ResumeInstallRequest struct {
	OperationID         string `json:"operation_id"`
	IdempotencyKey      string `json:"idempotency_key"`
	FailedOperationID   string `json:"failed_operation_id"`
	ConfirmedPlanDigest string `json:"confirmed_plan_digest"`
}

type resumeInstallState struct {
	service   model.ServiceState
	failed    model.Operation
	original  model.Operation
	plan      model.Plan
	provider  provider.Provider
	tx        provider.TransactionalGuestProvider
	ownership provider.GuestOwnershipVerifier
}

func (e *Engine) ResumeInstall(ctx context.Context, serviceID string, r ResumeInstallRequest) (model.Operation, error) {
	if strings.TrimSpace(r.OperationID) == "" || strings.TrimSpace(r.IdempotencyKey) == "" || strings.TrimSpace(r.FailedOperationID) == "" || strings.TrimSpace(r.ConfirmedPlanDigest) == "" {
		return model.Operation{}, errors.New("operation_id, idempotency_key, failed_operation_id and confirmed_plan_digest are required")
	}
	if len(r.IdempotencyKey) > 256 || strings.ContainsAny(r.IdempotencyKey, "\x00\r\n") {
		return model.Operation{}, errors.New("idempotency_key is invalid")
	}
	initial, err := e.loadResumeInstallState(serviceID, r.FailedOperationID, r.ConfirmedPlanDigest)
	if err != nil {
		return model.Operation{}, err
	}
	requestDigest := resumeInstallDigest(serviceID, r)
	proposed := model.Operation{
		ID:                    r.OperationID,
		ServiceID:             serviceID,
		IdempotencyKey:        r.IdempotencyKey,
		RequestDigest:         requestDigest,
		PlanDigest:            initial.plan.Digest,
		RecoveryOfOperationID: initial.original.ID,
		Status:                model.OpRequested,
		Stage:                 "resume-install",
	}
	op, err := e.Store.Begin(proposed)
	if err != nil {
		return op, err
	}
	if op.ID != proposed.ID || op.ServiceID != proposed.ServiceID || op.RequestDigest != proposed.RequestDigest || op.IdempotencyKey != proposed.IdempotencyKey || op.PlanDigest != proposed.PlanDigest || op.RecoveryOfOperationID != proposed.RecoveryOfOperationID {
		return op, errors.New("resume operation identity changed or collided")
	}
	if op.Status == model.OpSucceeded {
		return op, nil
	}
	if op.Status == model.OpUnknown {
		return op, errors.New("UNKNOWN resume operation requires authoritative reconciliation before retry")
	}
	if op.Status != model.OpRequested {
		return op, fmt.Errorf("resume operation state %s cannot be replayed; allocate a new operation UUID", op.Status)
	}

	lk, err := lock.Acquire(e.LockPath)
	if err != nil {
		return op, err
	}
	defer lk.Release()

	current, err := e.Store.GetOperation(op.ID)
	if err != nil {
		return op, err
	}
	if current.Status != model.OpRequested || current.ServiceID != serviceID || current.RequestDigest != requestDigest || current.IdempotencyKey != r.IdempotencyKey || current.PlanDigest != initial.plan.Digest || current.RecoveryOfOperationID != initial.original.ID {
		return current, errors.New("resume operation changed before mutation lock acquisition")
	}
	state, err := e.loadResumeInstallState(serviceID, r.FailedOperationID, r.ConfirmedPlanDigest)
	if err != nil {
		return current, err
	}
	if state.original.ID != current.RecoveryOfOperationID || state.plan.Digest != current.PlanDigest {
		return current, errors.New("recovery root or immutable plan changed before mutation")
	}

	current.Status = model.OpRunning
	current.Stage = "provenance-revalidation"
	current.Error = ""
	if err = e.Store.SaveOperation(current); err != nil {
		return current, err
	}
	if err = verifyTransactionalProvenance(ctx, e.Runner, state.plan); err != nil {
		return e.failSafeResume(current, err)
	}
	current.Stage = "ownership-revalidation"
	if err = e.Store.SaveOperation(current); err != nil {
		return current, err
	}
	if err = state.ownership.VerifyGuestOwnership(state.plan.Request); err != nil {
		return e.failSafeResume(current, err)
	}

	st := state.service
	st.Status = "recovering-install"
	st.RecoveryRequired = true
	st.FailureStage = resumeInstallStage
	st.LastOperationID = current.ID
	if err = e.Store.SaveService(st); err != nil {
		return current, err
	}
	current.Stage = resumeInstallStage
	if err = e.Store.SaveOperation(current); err != nil {
		return current, err
	}

	if err = state.tx.Apply(ctx, current, state.plan); err != nil {
		return e.failResumeMutation(current, st, resumeInstallStage, err)
	}

	current.Status = model.OpVerifying
	current.Stage = "health"
	if err = e.Store.SaveOperation(current); err != nil {
		return current, err
	}
	health, healthErr := state.provider.Health(ctx, st)
	if healthErr != nil {
		return e.failResumeMutation(current, st, "health", healthErr)
	}
	if !health.Healthy {
		msg := strings.TrimSpace(health.Error)
		if msg == "" {
			msg = "provider health verification failed"
		}
		return e.failResumeMutation(current, st, "health", errors.New(msg))
	}

	st.Status = "installed"
	st.RecoveryRequired = false
	st.FailureStage = ""
	st.LastOperationID = current.ID
	if err = e.Store.SaveService(st); err != nil {
		return current, err
	}
	current.Status = model.OpSucceeded
	current.Stage = "complete"
	current.Error = ""
	if err = e.Store.SaveOperation(current); err != nil {
		return current, err
	}
	return current, nil
}

func (e *Engine) loadResumeInstallState(serviceID, failedOperationID, confirmedPlanDigest string) (resumeInstallState, error) {
	var out resumeInstallState
	st, err := e.Store.GetService(serviceID)
	if err != nil {
		return out, err
	}
	if st.ID != serviceID {
		return out, errors.New("service identity mismatch")
	}
	if !st.RecoveryRequired || st.FailureStage != resumeInstallStage {
		return out, errors.New("service is not eligible for guest-apply install recovery")
	}
	if st.LastOperationID != failedOperationID {
		return out, errors.New("failed operation is not the service recovery head")
	}
	failed, err := e.Store.GetOperation(failedOperationID)
	if err != nil {
		return out, err
	}
	if failed.ID != failedOperationID || failed.ServiceID != serviceID || failed.Status != model.OpFailedNeedsRecovery || failed.Stage != resumeInstallStage {
		return out, errors.New("failed operation is not an eligible guest-apply recovery source")
	}
	originalID := failed.ID
	if failed.RecoveryOfOperationID != "" {
		originalID = failed.RecoveryOfOperationID
	}
	original, err := e.Store.GetOperation(originalID)
	if err != nil {
		return out, err
	}
	if original.ID != originalID || original.ServiceID != serviceID || original.RecoveryOfOperationID != "" || original.Status != model.OpFailedNeedsRecovery || original.Stage != resumeInstallStage {
		return out, errors.New("original install operation is not an eligible immutable recovery root")
	}
	if failed.ID != original.ID && failed.RecoveryOfOperationID != original.ID {
		return out, errors.New("failed recovery operation does not reference the original install operation")
	}
	plan, err := e.Store.GetPlan(original.ID)
	if err != nil {
		return out, err
	}
	requestDigest, err := config.CanonicalDigest(plan.Request)
	if err != nil {
		return out, err
	}
	if err = validateStoredPlan(plan, original, requestDigest); err != nil {
		return out, err
	}
	if plan.Request.IdempotencyKey != original.IdempotencyKey {
		return out, errors.New("stored plan idempotency identity mismatch")
	}
	if confirmedPlanDigest == "" || confirmedPlanDigest != plan.Digest || confirmedPlanDigest != original.PlanDigest || confirmedPlanDigest != failed.PlanDigest || confirmedPlanDigest != st.PlanDigest {
		return out, errors.New("resume plan confirmation digest mismatch")
	}
	if st.Provider != plan.Provider || st.Provider != plan.Request.Provider || st.Category != plan.Request.Category || st.ResolvedVersion != plan.ResolvedVersion || st.RepositoryID != plan.RepositoryID || st.RepositoryDigest != plan.RepositoryDigest || !reflect.DeepEqual(st.PlatformPackages, plan.PlatformPackages) {
		return out, errors.New("service state no longer matches the immutable install plan")
	}
	if st.ConfigDigest != requestDigest || st.ConfigDigest != original.RequestDigest {
		return out, errors.New("service request digest no longer matches the original install intent")
	}
	stateRequest := requestFromRecoveryState(plan.Request, st)
	stateDigest, err := config.CanonicalDigest(stateRequest)
	if err != nil {
		return out, err
	}
	if stateDigest != requestDigest {
		return out, errors.New("service configuration changed since the failed install plan")
	}
	p, ok := e.Registry.Get(plan.Provider)
	if !ok {
		return out, errors.New("provider unavailable")
	}
	tx, ok := p.(provider.TransactionalGuestProvider)
	if !ok || !tx.ManagesGuestPlatform() {
		return out, errors.New("provider does not support transactional guest install recovery")
	}
	ownership, ok := p.(provider.GuestOwnershipVerifier)
	if !ok {
		return out, errors.New("provider cannot prove guest-global ownership for recovery")
	}
	out.service = st
	out.failed = failed
	out.original = original
	out.plan = plan
	out.provider = p
	out.tx = tx
	out.ownership = ownership
	return out, nil
}

func requestFromRecoveryState(original model.ServiceRequest, st model.ServiceState) model.ServiceRequest {
	out := original
	out.Category = st.Category
	out.Provider = st.Provider
	out.ReleaseLine = st.ReleaseLine
	out.Topology = st.Topology
	out.Storage = st.Storage
	out.LVM = st.LVM
	out.Network = st.Network
	out.Maintenance = st.Maintenance
	out.Backup = st.Backup
	out.Cluster = st.Cluster
	out.SecretRefs = st.SecretRefs
	return out
}

func resumeInstallDigest(serviceID string, r ResumeInstallRequest) string {
	sum := sha256.Sum256([]byte(serviceID + "|resume-install|" + r.FailedOperationID + "|" + r.ConfirmedPlanDigest))
	return hex.EncodeToString(sum[:])
}

func (e *Engine) failSafeResume(op model.Operation, cause error) (model.Operation, error) {
	op.Status = model.OpFailedSafe
	op.Error = redact(cause.Error())
	_ = e.Store.SaveOperation(op)
	return op, cause
}

func (e *Engine) failResumeMutation(op model.Operation, st model.ServiceState, stage string, cause error) (model.Operation, error) {
	if isAmbiguous(cause) {
		op.Status = model.OpUnknown
		st.Status = "unknown-recovery"
	} else {
		op.Status = model.OpFailedNeedsRecovery
		st.Status = "failed-needs-recovery"
	}
	op.Stage = stage
	op.Error = redact(cause.Error())
	st.RecoveryRequired = true
	st.FailureStage = stage
	st.LastOperationID = op.ID
	_ = e.Store.SaveService(st)
	_ = e.Store.SaveOperation(op)
	return op, cause
}
