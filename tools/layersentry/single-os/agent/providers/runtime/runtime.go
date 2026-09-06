package runtime

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "fmt"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

type Spec struct {
    ID                   string
    Package              string
    RepoID               string
    AllowedReleaseLines  map[string]string
    Description          string
}

type Provider struct {
    Runner executor.Runner
    DNF    packageutil.DNF
    Spec   Spec
}

func New(r executor.Runner, spec Spec) *Provider {
    return &Provider{Runner: r, DNF: packageutil.DNF{Runner: r}, Spec: spec}
}

func (p *Provider) ID() string { return p.Spec.ID }
func (p *Provider) Category() model.Category { return model.CategoryApplication }

func (p *Provider) Validate(_ context.Context, r model.ServiceRequest) error {
    if r.Category != model.CategoryApplication {
        return errors.New("runtime provider category must be application")
    }
    if r.Topology != "standalone" {
        return errors.New("runtime package providers support standalone topology only")
    }
    if _, ok := p.Spec.AllowedReleaseLines[r.ReleaseLine]; !ok {
        return fmt.Errorf("unsupported %s release line %q", p.Spec.ID, r.ReleaseLine)
    }
    if r.Network.Port != 0 || r.Network.ListenAddress != "" || len(r.Network.AllowedCIDRs) != 0 {
        return errors.New("runtime package providers do not own a network listener; network port/address/CIDRs must be empty")
    }
    if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
        return errors.New("runtime package providers do not own customer application-data backup; backup policy must be disabled")
    }
    return nil
}

func (p *Provider) ResolveVersion(ctx context.Context, r model.ServiceRequest) (string, error) {
    if err := p.DNF.ValidateRepositories(ctx, p.Spec.RepoID); err != nil {
        return "", err
    }
    resolved, err := p.DNF.ResolveLatestFromRepos(ctx, p.Spec.Package, []string{p.Spec.RepoID})
    if err != nil {
        return "", err
    }
    prefix := p.Spec.AllowedReleaseLines[r.ReleaseLine]
    if prefix != "" && !resolvedVersionMatches(p.Spec.Package, resolved, prefix) {
        return "", fmt.Errorf("repository default for %s resolved to %q, outside requested release line %q", p.Spec.Package, resolved, r.ReleaseLine)
    }
    return resolved, nil
}

func (p *Provider) Plan(ctx context.Context, r model.ServiceRequest, resolved string) (model.Plan, error) {
    repoDigest, err := p.DNF.RepositoryDigest(ctx, p.Spec.RepoID)
    if err != nil {
        return model.Plan{}, err
    }
    steps := []model.PlanStep{
        {Name: "repository", Action: "use approved " + p.Spec.RepoID + " repository with GPG/TLS verification"},
        {Name: "packages", Action: "install exact runtime package " + resolved},
        {Name: "runtime-health", Action: "verify installed RPM identity/version without starting an unmanaged workload"},
    }
    raw := fmt.Sprintf("%s|%s|%s|%s|%s|%v", r.ServiceID, p.Spec.ID, resolved, p.Spec.RepoID, repoDigest, steps)
    sum := sha256.Sum256([]byte(raw))
    return model.Plan{ID: r.OperationID, ServiceID: r.ServiceID, Provider: p.ID(), ResolvedVersion: resolved, RepositoryID: p.Spec.RepoID, RepositoryDigest: repoDigest, Digest: hex.EncodeToString(sum[:]), CreatedAt: time.Now().UTC(), Request: r, Steps: steps}, nil
}

func (p *Provider) Install(ctx context.Context, _ model.Operation, plan model.Plan) error {
    if plan.RepositoryID != p.Spec.RepoID || plan.RepositoryDigest == "" {
        return errors.New("runtime plan repository provenance missing")
    }
    current, err := p.DNF.RepositoryDigest(ctx, p.Spec.RepoID)
    if err != nil {
        return err
    }
    if current != plan.RepositoryDigest {
        return errors.New("runtime repository configuration drifted after plan confirmation")
    }
    return p.DNF.InstallExactFromRepos(ctx, []string{p.Spec.RepoID}, plan.ResolvedVersion)
}

func (p *Provider) Configure(context.Context, model.Operation, model.Plan) error { return nil }
func (p *Provider) Initialize(context.Context, model.Operation, model.Plan) error { return nil }
func (p *Provider) Join(context.Context, model.Operation, model.Plan) error { return errors.New("runtime cluster join is not supported") }

func (p *Provider) Health(ctx context.Context, _ model.ServiceState) (model.HealthResult, error) {
    res, err := p.Runner.Run(ctx, "/usr/bin/rpm", "-q", p.Spec.Package)
    if err != nil {
        return model.HealthResult{Healthy: false, Checks: map[string]string{"rpm": "missing"}, Error: "runtime package is not installed"}, nil
    }
    version := strings.TrimSpace(res.Stdout)
    if version == "" {
        return model.HealthResult{Healthy: false, Checks: map[string]string{"rpm": "invalid"}, Error: "runtime package identity unavailable"}, nil
    }
    return model.HealthResult{Healthy: true, Version: version, Checks: map[string]string{"rpm": "installed", "workload": "not-managed-by-runtime-provider"}}, nil
}

func (p *Provider) Start(context.Context, model.Operation, model.ServiceState) error { return nil }
func (p *Provider) Stop(context.Context, model.Operation, model.ServiceState) error { return nil }
func (p *Provider) Restart(context.Context, model.Operation, model.ServiceState) error { return nil }
func (p *Provider) Upgrade(ctx context.Context, op model.Operation, plan model.Plan) error { return p.Install(ctx, op, plan) }
func (p *Provider) Repair(ctx context.Context, _ model.Operation, _ model.Plan) error {
    _, err := p.Runner.Run(ctx, "/usr/bin/rpm", "-q", p.Spec.Package)
    return err
}
func (p *Provider) Backup(context.Context, model.Operation, model.ServiceState) (model.BackupRecord, error) { return model.BackupRecord{}, errors.New("runtime provider does not own customer application-data backup") }
func (p *Provider) Restore(context.Context, model.Operation, model.ServiceState, model.BackupRecord) error { return errors.New("runtime provider does not own customer application-data restore") }
func (p *Provider) Uninstall(ctx context.Context, _ model.Operation, _ model.ServiceState, destroyData bool) error {
    if destroyData {
        return errors.New("runtime package uninstall never destroys customer application data")
    }
    return p.DNF.Remove(ctx, p.Spec.Package)
}
func (p *Provider) ResidueAudit(ctx context.Context, _ model.ServiceState) (map[string]string, error) {
    res, _ := p.Runner.Run(ctx, "/usr/bin/rpm", "-q", p.Spec.Package)
    if res.ExitCode == 0 {
        return map[string]string{"rpm": "present", "customer_data": "preserved"}, nil
    }
    return map[string]string{"rpm": "absent", "customer_data": "preserved"}, nil
}

func resolvedVersionMatches(pkg, nevra, releasePrefix string) bool {
    rest := strings.TrimPrefix(nevra, pkg+"-")
    if rest == nevra {
        return false
    }
    if idx := strings.IndexByte(rest, ':'); idx >= 0 {
        rest = rest[idx+1:]
    }
    return rest == releasePrefix || strings.HasPrefix(rest, releasePrefix+".")
}
