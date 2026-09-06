package apache

import (
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "fmt"
    "io"
    "net"
    "net/http"
    "os"
    "path/filepath"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

const (
    repoID       = "appstream"
    packageName  = "httpd"
    serviceUnit  = "httpd.service"
    mainConf     = "/etc/httpd/conf/httpd.conf"
    ownerPath    = "/var/lib/layersentryd/state/apache-httpd-owner"
    listenBackup = "/var/lib/layersentryd/state/apache-httpd-original-listen"
)

const listenMarker = "# LayerSentry managed primary Listen"

type Provider struct {
    Runner executor.Runner
    DNF    packageutil.DNF
}

func New(r executor.Runner) *Provider { return &Provider{Runner: r, DNF: packageutil.DNF{Runner: r}} }
func (p *Provider) ID() string { return "apache-httpd" }
func (p *Provider) Category() model.Category { return model.CategoryApplication }

func (p *Provider) Validate(_ context.Context, r model.ServiceRequest) error {
    if r.Category != model.CategoryApplication {
        return errors.New("apache-httpd category must be application")
    }
    if r.Topology != "standalone" {
        return errors.New("apache-httpd supports standalone topology only")
    }
    if r.ReleaseLine != "rocky9" && r.ReleaseLine != "stable" {
        return errors.New("apache-httpd release_line must be rocky9 or stable")
    }
    if net.ParseIP(r.Network.ListenAddress) == nil || r.Network.Port == 0 {
        return errors.New("apache-httpd requires an explicit guest listen IP and TCP port")
    }
    if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
        return errors.New("apache-httpd does not own customer application-data backup; backup policy must be disabled")
    }
    if len(r.Storage) != 0 {
        return errors.New("apache-httpd managed static-root provider does not consume attached storage; omit storage assignments")
    }
    if owner, err := os.ReadFile(ownerPath); err == nil && strings.TrimSpace(string(owner)) != r.ServiceID {
        return errors.New("apache-httpd is single-instance on a guest and is already owned by another service")
    } else if err != nil && !errors.Is(err, os.ErrNotExist) {
        return err
    }
    return nil
}

func (p *Provider) ResolveVersion(ctx context.Context, _ model.ServiceRequest) (string, error) {
    if err := p.DNF.ValidateRepositories(ctx, repoID); err != nil {
        return "", err
    }
    return p.DNF.ResolveLatestFromRepos(ctx, packageName, []string{repoID})
}

func (p *Provider) Plan(ctx context.Context, r model.ServiceRequest, resolved string) (model.Plan, error) {
    repoDigest, err := p.DNF.RepositoryDigest(ctx, repoID)
    if err != nil {
        return model.Plan{}, err
    }
    steps := []model.PlanStep{
        {Name: "repository", Action: "use Rocky AppStream with GPG/TLS verification"},
        {Name: "packages", Action: "install exact Rocky-supported httpd package " + resolved},
        {Name: "listener", Action: fmt.Sprintf("replace only the vendor primary Listen directive with %s:%d and retain the original directive for reversible uninstall", r.Network.ListenAddress, r.Network.Port)},
        {Name: "configure", Action: "create a LayerSentry-owned virtual host with indexes/CGI disabled and a deterministic local health object"},
        {Name: "config-test", Action: "run httpd -t before service start"},
        {Name: "firewall", Action: "allow only requested CIDRs to the requested TCP port"},
        {Name: "service", Action: "enable and start httpd.service"},
        {Name: "health", Action: "validate systemd state, config syntax and local HTTP health response"},
    }
    sum := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%s|%s|%v", r.ServiceID, resolved, repoID, repoDigest, steps)))
    return model.Plan{ID: r.OperationID, ServiceID: r.ServiceID, Provider: p.ID(), ResolvedVersion: resolved, RepositoryID: repoID, RepositoryDigest: repoDigest, Digest: hex.EncodeToString(sum[:]), CreatedAt: time.Now().UTC(), Request: r, Steps: steps}, nil
}

func (p *Provider) Install(ctx context.Context, _ model.Operation, plan model.Plan) error {
    if err := p.ensureOwnerAvailable(plan.ServiceID); err != nil {
        return err
    }
    if plan.RepositoryID != repoID || plan.RepositoryDigest == "" {
        return errors.New("apache-httpd plan repository provenance missing")
    }
    current, err := p.DNF.RepositoryDigest(ctx, repoID)
    if err != nil {
        return err
    }
    if current != plan.RepositoryDigest {
        return errors.New("apache-httpd repository configuration drifted after plan confirmation")
    }
    return p.DNF.InstallExactFromRepos(ctx, []string{repoID}, plan.ResolvedVersion)
}

func (p *Provider) Configure(ctx context.Context, _ model.Operation, plan model.Plan) error {
    if err := p.claimOwner(plan.ServiceID); err != nil {
        return err
    }
    if err := rewritePrimaryListen(plan.Request.Network.ListenAddress, plan.Request.Network.Port); err != nil {
        return err
    }
    root := documentRoot(plan.ServiceID)
    if err := os.MkdirAll(root, 0755); err != nil {
        return err
    }
    if err := filesystem.AtomicWrite(filepath.Join(root, "index.html"), []byte("LayerSentry managed Apache HTTP service\n"), 0644, root); err != nil {
        return err
    }
    if err := filesystem.AtomicWrite(filepath.Join(root, ".layersentry-health"), []byte("layersentry-ok\n"), 0644, root); err != nil {
        return err
    }
    conf := fmt.Sprintf(`<VirtualHost %s:%d>
    ServerName localhost
    DocumentRoot "%s"
    ServerTokens Prod
    ServerSignature Off
    TraceEnable Off
    <Directory "%s">
        Options -Indexes -ExecCGI
        AllowOverride None
        Require all granted
    </Directory>
</VirtualHost>
`, plan.Request.Network.ListenAddress, plan.Request.Network.Port, root, root)
    confPath := managedConf(plan.ServiceID)
    if err := filesystem.AtomicWrite(confPath, []byte(conf), 0644, "/etc/httpd/conf.d"); err != nil {
        return err
    }
    if _, err := p.Runner.Run(ctx, "/usr/sbin/httpd", "-t"); err != nil {
        return err
    }
    return nil
}

func (p *Provider) Initialize(context.Context, model.Operation, model.Plan) error { return nil }
func (p *Provider) Join(context.Context, model.Operation, model.Plan) error { return errors.New("apache-httpd cluster join is not supported") }

func (p *Provider) Start(ctx context.Context, _ model.Operation, _ model.ServiceState) error {
    _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "enable", "--now", serviceUnit)
    return err
}
func (p *Provider) Stop(ctx context.Context, _ model.Operation, _ model.ServiceState) error {
    _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "stop", serviceUnit)
    return err
}
func (p *Provider) Restart(ctx context.Context, _ model.Operation, _ model.ServiceState) error {
    _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "restart", serviceUnit)
    return err
}

func (p *Provider) Health(ctx context.Context, st model.ServiceState) (model.HealthResult, error) {
    checks := map[string]string{}
    res, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "is-active", serviceUnit)
    if err != nil {
        return model.HealthResult{Healthy: false, Checks: checks, Error: "httpd.service is not active"}, nil
    }
    checks["systemd"] = strings.TrimSpace(res.Stdout)
    if _, err = p.Runner.Run(ctx, "/usr/sbin/httpd", "-t"); err != nil {
        return model.HealthResult{Healthy: false, Checks: checks, Error: "httpd configuration test failed"}, nil
    }
    checks["config"] = "ok"
    transport := &http.Transport{Proxy: nil, DisableKeepAlives: true, DialContext: (&net.Dialer{Timeout: 2 * time.Second}).DialContext}
    client := &http.Client{Timeout: 3 * time.Second, Transport: transport, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return errors.New("redirect rejected") }}
    resp, err := client.Get(fmt.Sprintf("http://%s:%d/.layersentry-health", st.Network.ListenAddress, st.Network.Port))
    if err != nil {
        return model.HealthResult{Healthy: false, Checks: checks, Error: "local Apache HTTP health request failed"}, nil
    }
    defer resp.Body.Close()
    body, err := io.ReadAll(io.LimitReader(resp.Body, 128))
    if err != nil || resp.StatusCode != http.StatusOK || !bytes.Equal(body, []byte("layersentry-ok\n")) {
        return model.HealthResult{Healthy: false, Checks: checks, Error: "unexpected Apache HTTP health response"}, nil
    }
    checks["http"] = "200"
    ver, err := p.Runner.Run(ctx, "/usr/sbin/httpd", "-v")
    if err != nil {
        return model.HealthResult{Healthy: false, Checks: checks, Error: "httpd version check failed"}, nil
    }
    version := strings.TrimSpace(ver.Stdout)
    checks["version"] = version
    return model.HealthResult{Healthy: true, Version: version, Checks: checks}, nil
}

func (p *Provider) Upgrade(ctx context.Context, op model.Operation, plan model.Plan) error {
    if err := p.Install(ctx, op, plan); err != nil {
        return err
    }
    _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "restart", serviceUnit)
    return err
}
func (p *Provider) Repair(ctx context.Context, _ model.Operation, _ model.Plan) error {
    if _, err := p.Runner.Run(ctx, "/usr/sbin/httpd", "-t"); err != nil {
        return err
    }
    _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "restart", serviceUnit)
    return err
}
func (p *Provider) Backup(context.Context, model.Operation, model.ServiceState) (model.BackupRecord, error) { return model.BackupRecord{}, errors.New("apache-httpd does not own customer application-data backup") }
func (p *Provider) Restore(context.Context, model.Operation, model.ServiceState, model.BackupRecord) error { return errors.New("apache-httpd does not own customer application-data restore") }

func (p *Provider) Uninstall(ctx context.Context, _ model.Operation, st model.ServiceState, destroyData bool) error {
    if destroyData {
        return errors.New("apache-httpd uninstall never destroys customer application data")
    }
    if _, err := p.Runner.Run(ctx, "/usr/bin/systemctl", "disable", "--now", serviceUnit); err != nil {
        return err
    }
    if err := restorePrimaryListen(); err != nil {
        return err
    }
    if err := os.Remove(managedConf(st.ID)); err != nil && !errors.Is(err, os.ErrNotExist) {
        return err
    }
    if err := os.Remove(ownerPath); err != nil && !errors.Is(err, os.ErrNotExist) {
        return err
    }
    return p.DNF.Remove(ctx, packageName)
}

func (p *Provider) ResidueAudit(ctx context.Context, st model.ServiceState) (map[string]string, error) {
    out := map[string]string{"customer_data": "preserved"}
    r, _ := p.Runner.Run(ctx, "/usr/bin/rpm", "-q", packageName)
    if r.ExitCode == 0 { out["rpm"] = "present" } else { out["rpm"] = "absent" }
    r, _ = p.Runner.Run(ctx, "/usr/bin/systemctl", "is-active", serviceUnit)
    if r.ExitCode == 0 { out["service"] = "active" } else { out["service"] = "inactive" }
    if _, err := os.Lstat(managedConf(st.ID)); err == nil { out["managed_config"] = "present" } else { out["managed_config"] = "absent" }
    if _, err := os.Lstat(ownerPath); err == nil { out["owner"] = "present" } else { out["owner"] = "absent" }
    return out, nil
}

func (p *Provider) ensureOwnerAvailable(serviceID string) error {
    raw, err := os.ReadFile(ownerPath)
    if errors.Is(err, os.ErrNotExist) { return nil }
    if err != nil { return err }
    if strings.TrimSpace(string(raw)) != serviceID { return errors.New("apache-httpd is already owned by another service") }
    return nil
}

func (p *Provider) claimOwner(serviceID string) error {
    if err := p.ensureOwnerAvailable(serviceID); err != nil { return err }
    return filesystem.AtomicWrite(ownerPath, []byte(serviceID+"\n"), 0600, "/var/lib/layersentryd/state")
}

func rewritePrimaryListen(ip string, port int) error {
    raw, err := os.ReadFile(mainConf)
    if err != nil { return err }
    lines := strings.Split(string(raw), "\n")
    managed := -1
    active := []int{}
    for i, line := range lines {
        trimmed := strings.TrimSpace(line)
        if strings.Contains(line, listenMarker) {
            if managed >= 0 { return errors.New("multiple LayerSentry-managed Apache Listen directives found") }
            managed = i
            continue
        }
        if strings.HasPrefix(trimmed, "Listen ") && !strings.HasPrefix(trimmed, "#") { active = append(active, i) }
    }
    if managed >= 0 {
        lines[managed] = fmt.Sprintf("Listen %s:%d %s", ip, port, listenMarker)
    } else {
        if len(active) != 1 || strings.TrimSpace(lines[active[0]]) != "Listen 80" {
            return errors.New("apache-httpd requires the unmodified Rocky primary 'Listen 80' directive; custom listener state is not rewritten implicitly")
        }
        if _, err = os.Lstat(listenBackup); errors.Is(err, os.ErrNotExist) {
            if err = filesystem.AtomicWrite(listenBackup, []byte("Listen 80\n"), 0600, "/var/lib/layersentryd/state"); err != nil { return err }
        } else if err != nil { return err }
        lines[active[0]] = fmt.Sprintf("Listen %s:%d %s", ip, port, listenMarker)
    }
    return filesystem.AtomicWrite(mainConf, []byte(strings.Join(lines, "\n")), 0644, "/etc/httpd/conf")
}

func restorePrimaryListen() error {
    backup, err := os.ReadFile(listenBackup)
    if err != nil { return err }
    original := strings.TrimSpace(string(backup))
    if original != "Listen 80" { return errors.New("stored Apache original Listen directive is invalid") }
    raw, err := os.ReadFile(mainConf)
    if err != nil { return err }
    lines := strings.Split(string(raw), "\n")
    found := -1
    for i, line := range lines {
        if strings.Contains(line, listenMarker) {
            if found >= 0 { return errors.New("multiple LayerSentry-managed Apache Listen directives found") }
            found = i
        }
    }
    if found < 0 { return errors.New("LayerSentry-managed Apache Listen directive is missing; refusing blind restore") }
    lines[found] = original
    if err = filesystem.AtomicWrite(mainConf, []byte(strings.Join(lines, "\n")), 0644, "/etc/httpd/conf"); err != nil { return err }
    if err = os.Remove(listenBackup); err != nil && !errors.Is(err, os.ErrNotExist) { return err }
    return nil
}

func managedConf(serviceID string) string {
    sum := sha256.Sum256([]byte(serviceID))
    return filepath.Join("/etc/httpd/conf.d", "layersentry-"+hex.EncodeToString(sum[:6])+".conf")
}
func documentRoot(serviceID string) string {
    sum := sha256.Sum256([]byte(serviceID))
    return filepath.Join("/var/www/html", "layersentry-"+hex.EncodeToString(sum[:6]))
}
