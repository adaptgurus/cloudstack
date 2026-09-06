package journal

import (
    "errors"
    "os"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

// ReferencedSecretRefs returns the secret references that are still required by
// installed service state or by an in-flight/recoverable operation. Terminal
// plans are deliberately not treated as live references: a completed service
// has its own durable state, and cancelled/rolled-back plans must not pin
// abandoned secret objects forever.
func (s *Store) ReferencedSecretRefs() (map[string]struct{}, error) {
    refs := make(map[string]struct{})

    services, err := s.ListServices()
    if err != nil {
        return nil, err
    }
    for _, st := range services {
        if strings.HasPrefix(st.Status, "uninstalled") {
            continue
        }
        addSecretRefs(refs, st.SecretRefs, st.Cluster.JoinTokenRef)
    }

    operations, err := s.ListOperations()
    if err != nil {
        return nil, err
    }
    for _, op := range operations {
        if !operationNeedsPlanSecrets(op.Status) || op.PlanDigest == "" {
            continue
        }
        plan, err := s.GetPlan(op.ID)
        if errors.Is(err, os.ErrNotExist) {
            continue
        }
        if err != nil {
            return nil, err
        }
        addSecretRefs(refs, plan.Request.SecretRefs, plan.Request.Cluster.JoinTokenRef)
    }
    return refs, nil
}

// ExpireUnconfirmedPlans converts stale, never-confirmed plans to a terminal
// CANCELLED state. The immutable plan remains as audit evidence, but it no
// longer keeps its transient secret references live for garbage collection.
func (s *Store) ExpireUnconfirmedPlans(before time.Time) (int, error) {
    operations, err := s.ListOperations()
    if err != nil {
        return 0, err
    }
    expired := 0
    for _, op := range operations {
        if op.Status != model.OpWaitingConfirmation || !op.UpdatedAt.Before(before) {
            continue
        }
        op.Status = model.OpCancelled
        op.Stage = "plan-expired"
        op.Error = ""
        if err := s.SaveOperation(op); err != nil {
            return expired, err
        }
        expired++
    }
    return expired, nil
}

func operationNeedsPlanSecrets(status model.OperationStatus) bool {
    switch status {
    case model.OpPlanned,
        model.OpWaitingConfirmation,
        model.OpRunning,
        model.OpVerifying,
        model.OpUnknown,
        model.OpFailedNeedsRecovery,
        model.OpRollingBack:
        return true
    default:
        return false
    }
}

func addSecretRefs(dst map[string]struct{}, refs map[string]string, joinTokenRef string) {
    for _, ref := range refs {
        if strings.HasPrefix(ref, "secret://") {
            dst[ref] = struct{}{}
        }
    }
    if strings.HasPrefix(joinTokenRef, "secret://") {
        dst[joinTokenRef] = struct{}{}
    }
}
