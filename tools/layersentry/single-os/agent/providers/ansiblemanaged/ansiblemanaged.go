package ansiblemanaged

import (
	"context"
	"errors"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/ansiblerunner"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
)

type Spec struct {
	StandaloneOnly bool
	PackageOnly    bool
}

type Provider struct {
	Base    provider.Provider
	Ansible *ansiblerunner.Runner
	Spec    Spec
}

func New(base provider.Provider, runner *ansiblerunner.Runner, spec Spec) *Provider {
	return &Provider{Base: base, Ansible: runner, Spec: spec}
}
func (p *Provider) ID() string                 { return p.Base.ID() }
func (p *Provider) Category() model.Category   { return p.Base.Category() }
func (p *Provider) ManagesGuestPlatform() bool { return true }
func (p *Provider) Validate(ctx context.Context, req model.ServiceRequest) error {
	if p.Spec.StandaloneOnly && req.Topology != "standalone" {
		return errors.New("this Ansible provider slice is qualified for standalone topology only")
	}
	return p.Base.Validate(ctx, req)
}
func (p *Provider) ResolveVersion(ctx context.Context, req model.ServiceRequest) (string, error) {
	return p.Base.ResolveVersion(ctx, req)
}
func (p *Provider) Plan(ctx context.Context, req model.ServiceRequest, resolved string) (model.Plan, error) {
	plan, err := p.Base.Plan(ctx, req, resolved)
	if err != nil {
		return plan, err
	}
	plan.Steps = append([]model.PlanStep{{Name: "ansible-execution-boundary", Action: "execute confirmed guest mutation through the allowlisted LayerSentry Ansible project; Go retains immutable plan/idempotency/journal/evidence authority"}}, plan.Steps...)
	return plan, nil
}
func (p *Provider) Apply(ctx context.Context, op model.Operation, plan model.Plan) error {
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunPlan(ctx, "apply", op, plan)
}
func (p *Provider) Install(context.Context, model.Operation, model.Plan) error {
	return errors.New("install is owned by transactional Ansible Apply")
}
func (p *Provider) Configure(context.Context, model.Operation, model.Plan) error {
	return errors.New("configure is owned by transactional Ansible Apply")
}
func (p *Provider) Initialize(context.Context, model.Operation, model.Plan) error {
	return errors.New("initialize is owned by transactional Ansible Apply")
}
func (p *Provider) Join(context.Context, model.Operation, model.Plan) error {
	return errors.New("cluster join is not enabled by this migrated Ansible slice")
}
func (p *Provider) Health(ctx context.Context, st model.ServiceState) (model.HealthResult, error) {
	return p.Base.Health(ctx, st)
}
func (p *Provider) Backup(ctx context.Context, op model.Operation, st model.ServiceState) (model.BackupRecord, error) {
	return p.Base.Backup(ctx, op, st)
}
func (p *Provider) Restore(ctx context.Context, op model.Operation, st model.ServiceState, b model.BackupRecord) error {
	return p.Base.Restore(ctx, op, st, b)
}
func (p *Provider) ResidueAudit(ctx context.Context, st model.ServiceState) (map[string]string, error) {
	return p.Base.ResidueAudit(ctx, st)
}
func (p *Provider) Start(ctx context.Context, op model.Operation, st model.ServiceState) error {
	if p.Spec.PackageOnly {
		return nil
	}
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunState(ctx, "start", op, st, false)
}
func (p *Provider) Stop(ctx context.Context, op model.Operation, st model.ServiceState) error {
	if p.Spec.PackageOnly {
		return nil
	}
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunState(ctx, "stop", op, st, false)
}
func (p *Provider) Restart(ctx context.Context, op model.Operation, st model.ServiceState) error {
	if p.Spec.PackageOnly {
		return nil
	}
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunState(ctx, "restart", op, st, false)
}
func (p *Provider) Upgrade(ctx context.Context, op model.Operation, plan model.Plan) error {
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunPlan(ctx, "upgrade", op, plan)
}
func (p *Provider) Repair(ctx context.Context, op model.Operation, plan model.Plan) error {
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunPlan(ctx, "repair", op, plan)
}
func (p *Provider) Uninstall(ctx context.Context, op model.Operation, st model.ServiceState, destroy bool) error {
	if destroy {
		return errors.New("destructive data removal requires a separately reviewed provider operation")
	}
	if p.Ansible == nil {
		return errors.New("Ansible runner unavailable")
	}
	return p.Ansible.RunState(ctx, "uninstall", op, st, false)
}
