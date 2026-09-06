package support

import (
    "bufio"
    "context"
    "errors"
    "os"
    "regexp"
    "runtime"
    "sort"
    "strconv"
    "strings"
    "syscall"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

const (
    maxRecentOperations = 100
    maxLogBytes         = 64 << 10
)

type HealthFunc func(context.Context, string) (model.HealthResult, error)

type Collector struct {
    Store  *journal.Store
    Runner executor.Runner
    Health HealthFunc
    Now    func() time.Time
}

type Bundle struct {
    GeneratedAt      time.Time           `json:"generated_at"`
    Agent            AgentEvidence       `json:"agent"`
    Host             HostEvidence        `json:"host"`
    Services         []ServiceEvidence   `json:"services"`
    RecentOperations []OperationEvidence `json:"recent_operations"`
    VerifiedBackups  []BackupEvidence    `json:"verified_backups"`
    PackageInventory map[string]string   `json:"package_inventory"`
    Resources        ResourceEvidence    `json:"resources"`
    Logs             LogEvidence         `json:"logs"`
    SecretsIncluded  bool                `json:"secrets_included"`
}

type AgentEvidence struct {
    API        string `json:"api"`
    GoVersion  string `json:"go_version"`
    GOOS       string `json:"goos"`
    GOARCH     string `json:"goarch"`
}

type HostEvidence struct {
    OSID          string `json:"os_id,omitempty"`
    OSVersion     string `json:"os_version,omitempty"`
    OSPrettyName  string `json:"os_pretty_name,omitempty"`
    Kernel        string `json:"kernel,omitempty"`
    SELinux       string `json:"selinux"`
    Firewalld     string `json:"firewalld"`
}

type ServiceEvidence struct {
    ID              string             `json:"id"`
    Provider        string             `json:"provider"`
    Category        model.Category     `json:"category"`
    ReleaseLine     string             `json:"release_line"`
    ResolvedVersion string             `json:"resolved_version"`
    Topology        string             `json:"topology"`
    Status          string             `json:"status"`
    ListenAddress   string             `json:"listen_address,omitempty"`
    Port            int                `json:"port,omitempty"`
    StorageCount    int                `json:"storage_count"`
    ConfigDigest    string             `json:"config_digest"`
    PlanDigest      string             `json:"plan_digest"`
    Health          model.HealthResult `json:"health"`
}

type OperationEvidence struct {
    ID        string                `json:"id"`
    ServiceID string                `json:"service_id"`
    Status    model.OperationStatus `json:"status"`
    Stage     string                `json:"stage,omitempty"`
    CreatedAt time.Time             `json:"created_at"`
    UpdatedAt time.Time             `json:"updated_at"`
}

type BackupEvidence struct {
    ID        string    `json:"id"`
    ServiceID string    `json:"service_id"`
    Provider  string    `json:"provider"`
    SHA256    string    `json:"sha256"`
    SizeBytes int64     `json:"size_bytes"`
    Verified  bool      `json:"verified"`
    CreatedAt time.Time `json:"created_at"`
}

type ResourceEvidence struct {
    Goroutines       int    `json:"goroutines"`
    HeapAllocBytes   uint64 `json:"heap_alloc_bytes"`
    ProcessSysBytes  uint64 `json:"process_sys_bytes"`
    RootTotalBytes   uint64 `json:"root_total_bytes,omitempty"`
    RootFreeBytes    uint64 `json:"root_free_bytes,omitempty"`
}

type LogEvidence struct {
    Available bool   `json:"available"`
    Content   string `json:"content,omitempty"`
    Note      string `json:"note,omitempty"`
}

func (c Collector) Collect(ctx context.Context) (Bundle, error) {
    if c.Store == nil {
        return Bundle{}, errors.New("support collector journal is unavailable")
    }
    now := time.Now().UTC()
    if c.Now != nil {
        now = c.Now().UTC()
    }

    services, err := c.Store.ListServices()
    if err != nil {
        return Bundle{}, err
    }
    operations, err := c.Store.ListOperations()
    if err != nil {
        return Bundle{}, err
    }
    backups, err := c.Store.ListBackups("")
    if err != nil {
        return Bundle{}, err
    }
    if len(operations) > maxRecentOperations {
        operations = operations[:maxRecentOperations]
    }

    bundle := Bundle{
        GeneratedAt: now,
        Agent: AgentEvidence{
            API:       "v1",
            GoVersion: runtime.Version(),
            GOOS:      runtime.GOOS,
            GOARCH:    runtime.GOARCH,
        },
        Host:             hostEvidence(ctx, c.Runner),
        Services:         make([]ServiceEvidence, 0, len(services)),
        RecentOperations: make([]OperationEvidence, 0, len(operations)),
        VerifiedBackups:  make([]BackupEvidence, 0, len(backups)),
        PackageInventory: packageInventory(ctx, c.Runner, services),
        Resources:        resourceEvidence(),
        Logs:             logEvidence(ctx, c.Runner),
        SecretsIncluded:  false,
    }

    for _, st := range services {
        health := model.HealthResult{Healthy: false, Error: "health unavailable"}
        if c.Health != nil && st.Status == "installed" {
            if h, err := c.Health(ctx, st.ID); err == nil {
                health = h
            }
        }
        bundle.Services = append(bundle.Services, ServiceEvidence{
            ID:              st.ID,
            Provider:        st.Provider,
            Category:        st.Category,
            ReleaseLine:     st.ReleaseLine,
            ResolvedVersion: st.ResolvedVersion,
            Topology:        st.Topology,
            Status:          st.Status,
            ListenAddress:   st.Network.ListenAddress,
            Port:            st.Network.Port,
            StorageCount:    len(st.Storage),
            ConfigDigest:    st.ConfigDigest,
            PlanDigest:      st.PlanDigest,
            Health:          health,
        })
    }
    for _, op := range operations {
        bundle.RecentOperations = append(bundle.RecentOperations, OperationEvidence{
            ID:        op.ID,
            ServiceID: op.ServiceID,
            Status:    op.Status,
            Stage:     op.Stage,
            CreatedAt: op.CreatedAt,
            UpdatedAt: op.UpdatedAt,
        })
    }
    for _, b := range backups {
        bundle.VerifiedBackups = append(bundle.VerifiedBackups, BackupEvidence{
            ID:        b.ID,
            ServiceID: b.ServiceID,
            Provider:  b.Provider,
            SHA256:    b.SHA256,
            SizeBytes: b.SizeBytes,
            Verified:  b.Verified,
            CreatedAt: b.CreatedAt,
        })
    }
    return bundle, nil
}

func hostEvidence(ctx context.Context, runner executor.Runner) HostEvidence {
    osrel := readOSRelease()
    return HostEvidence{
        OSID:         osrel["ID"],
        OSVersion:    osrel["VERSION_ID"],
        OSPrettyName: osrel["PRETTY_NAME"],
        Kernel:       commandValue(ctx, runner, "/usr/bin/uname", "-r"),
        SELinux:      commandValue(ctx, runner, "/usr/sbin/getenforce"),
        Firewalld:    commandValue(ctx, runner, "/usr/bin/firewall-cmd", "--state"),
    }
}

func readOSRelease() map[string]string {
    out := map[string]string{}
    f, err := os.Open("/etc/os-release")
    if err != nil {
        return out
    }
    defer f.Close()
    scanner := bufio.NewScanner(f)
    scanner.Buffer(make([]byte, 4096), 64<<10)
    for scanner.Scan() {
        line := scanner.Text()
        key, value, ok := strings.Cut(line, "=")
        if !ok {
            continue
        }
        switch key {
        case "ID", "VERSION_ID", "PRETTY_NAME":
            out[key] = strings.Trim(strings.TrimSpace(value), "\"")
        }
    }
    return out
}

func commandValue(ctx context.Context, runner executor.Runner, exe string, args ...string) string {
    if runner == nil {
        return "unavailable"
    }
    res, err := runner.Run(ctx, exe, args...)
    if err != nil {
        return "unavailable"
    }
    value := strings.TrimSpace(res.Stdout)
    if value == "" {
        value = strings.TrimSpace(res.Stderr)
    }
    if value == "" {
        return "unknown"
    }
    if len(value) > 1024 {
        value = value[:1024]
    }
    return sanitizeText(value)
}

func packageInventory(ctx context.Context, runner executor.Runner, services []model.ServiceState) map[string]string {
    names := map[string]struct{}{"layersentry-single-os": {}}
    for _, st := range services {
        switch st.Provider {
        case "nginx":
            names["nginx"] = struct{}{}
        case "postgresql":
            if st.ReleaseLine == "16" || st.ReleaseLine == "17" {
                names["postgresql"+st.ReleaseLine+"-server"] = struct{}{}
            }
        }
    }
    ordered := make([]string, 0, len(names))
    for name := range names {
        ordered = append(ordered, name)
    }
    sort.Strings(ordered)
    out := make(map[string]string, len(ordered))
    for _, name := range ordered {
        if runner == nil {
            out[name] = "unavailable"
            continue
        }
        res, err := runner.Run(ctx, "/usr/bin/rpm", "-q", "--qf", "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n", name)
        if err != nil {
            out[name] = "not-installed-or-unavailable"
            continue
        }
        out[name] = strings.TrimSpace(res.Stdout)
    }
    return out
}

func resourceEvidence() ResourceEvidence {
    var ms runtime.MemStats
    runtime.ReadMemStats(&ms)
    out := ResourceEvidence{
        Goroutines:      runtime.NumGoroutine(),
        HeapAllocBytes:  ms.HeapAlloc,
        ProcessSysBytes: ms.Sys,
    }
    var st syscall.Statfs_t
    if err := syscall.Statfs("/", &st); err == nil {
        blockSize := uint64(st.Bsize)
        out.RootTotalBytes = st.Blocks * blockSize
        out.RootFreeBytes = st.Bavail * blockSize
    }
    return out
}

func logEvidence(ctx context.Context, runner executor.Runner) LogEvidence {
    if runner == nil {
        return LogEvidence{Available: false, Note: "diagnostic runner unavailable"}
    }
    res, err := runner.Run(ctx, "/usr/bin/journalctl", "--no-pager", "--output=short-iso", "-n", "200", "-u", "layersentryd.service", "-u", "layersentry-privileged.service")
    if err != nil {
        return LogEvidence{Available: false, Note: "journal access unavailable to support collector"}
    }
    text := sanitizeText(res.Stdout)
    if len(text) > maxLogBytes {
        text = text[len(text)-maxLogBytes:]
    }
    return LogEvidence{Available: true, Content: text, Note: "bounded and redacted service journal tail"}
}

var (
    secretRefRE = regexp.MustCompile(`secret://[0-9a-fA-F]{32}`)
    bearerRE    = regexp.MustCompile(`(?i)Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+`)
    sensitiveKV = regexp.MustCompile(`(?i)(password|token|authorization|cookie|csrf|secret)[A-Za-z0-9_.-]*[[:space:]]*[:=][[:space:]]*("[^"]*"|'[^']*'|[^[:space:],;]+)`)
)

func sanitizeText(in string) string {
    if len(in) > 256<<10 {
        in = in[len(in)-(256<<10):]
    }
    in = secretRefRE.ReplaceAllString(in, "secret://REDACTED")
    in = bearerRE.ReplaceAllString(in, "Bearer [REDACTED]")
    in = sensitiveKV.ReplaceAllString(in, "$1=[REDACTED]")
    lines := strings.Split(in, "\n")
    for i, line := range lines {
        lower := strings.ToLower(line)
        if strings.Contains(lower, "private key") || strings.Contains(lower, "set-cookie:") || strings.Contains(lower, "authorization:") {
            lines[i] = "[REDACTED SENSITIVE LINE]"
        }
    }
    return strings.Join(lines, "\n")
}

// ParseUintMetric is intentionally small and exported only for future bounded
// procfs metric readers without introducing a general parser surface.
func ParseUintMetric(value string) (uint64, bool) {
    fields := strings.Fields(value)
    if len(fields) == 0 {
        return 0, false
    }
    v, err := strconv.ParseUint(fields[0], 10, 64)
    return v, err == nil
}
