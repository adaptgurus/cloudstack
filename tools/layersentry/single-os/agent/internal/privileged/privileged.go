package privileged

import (
    "bufio"
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net"
    "os"
    "os/user"
    "path/filepath"
    "regexp"
    "strconv"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket = "/run/layersentryd/privileged.sock"

const maxMessage = 2 << 20

var (
    unitRE      = regexp.MustCompile(`^[A-Za-z0-9_.@-]+$`)
    zoneRE      = regexp.MustCompile(`^ls-[0-9a-f]{12}$`)
    safeTokenRE = regexp.MustCompile(`^[A-Za-z0-9_./:+@=,%~-]+$`)
    pgPathRE    = regexp.MustCompile(`^/usr/pgsql-(16|17)/bin/(initdb|psql|pg_isready|pg_dumpall|postgres)$`)
)

type request struct {
    Action string   `json:"action"`
    Args   []string `json:"args"`
}

type response struct {
    Stdout   string `json:"stdout,omitempty"`
    Stderr   string `json:"stderr,omitempty"`
    ExitCode int    `json:"exit_code"`
    Error    string `json:"error,omitempty"`
}

// Client implements executor.Runner without giving the API process a shell or a
// generic command socket. Each executable maps to a named helper action and is
// revalidated by the root helper before execution.
type Client struct {
    Socket string
    Timeout time.Duration
}

func NewClient(socket string) Client {
    if socket == "" {
        socket = DefaultSocket
    }
    return Client{Socket: socket, Timeout: 3 * time.Minute}
}

func (c Client) Run(ctx context.Context, path string, args ...string) (executor.Result, error) {
    action, err := actionFor(path, args)
    if err != nil {
        return executor.Result{}, err
    }
    if c.Timeout <= 0 {
        c.Timeout = 3 * time.Minute
    }
    cctx, cancel := context.WithTimeout(ctx, c.Timeout)
    defer cancel()
    d := net.Dialer{Timeout: 5 * time.Second}
    conn, err := d.DialContext(cctx, "unix", c.Socket)
    if err != nil {
        return executor.Result{}, fmt.Errorf("privileged helper unavailable: %w", err)
    }
    defer conn.Close()
    if deadline, ok := cctx.Deadline(); ok {
        _ = conn.SetDeadline(deadline)
    }
    if err = json.NewEncoder(conn).Encode(request{Action: action, Args: args}); err != nil {
        return executor.Result{}, err
    }
    var resp response
    dec := json.NewDecoder(io.LimitReader(conn, maxMessage))
    if err = dec.Decode(&resp); err != nil {
        return executor.Result{}, err
    }
    result := executor.Result{Stdout: resp.Stdout, Stderr: resp.Stderr, ExitCode: resp.ExitCode}
    if resp.Error != "" {
        return result, errors.New(resp.Error)
    }
    return result, nil
}

func actionFor(path string, args []string) (string, error) {
    switch path {
    case "/usr/bin/dnf":
        return "dnf", validateDNF(args)
    case "/usr/bin/systemctl":
        return "systemctl", validateSystemctl(args)
    case "/usr/bin/firewall-cmd":
        return "firewall", validateFirewall(args)
    case "/usr/sbin/mkfs.xfs":
        return "mkfs-xfs", validateMkfs(args, "-f")
    case "/usr/sbin/mkfs.ext4":
        return "mkfs-ext4", validateMkfs(args, "-F")
    case "/usr/bin/mount":
        return "mount", validateMount(args)
    case "/usr/bin/findmnt":
        return "findmnt", validateReadOnlyArgs(args)
    case "/usr/sbin/blkid":
        return "blkid", validateReadOnlyArgs(args)
    case "/usr/bin/lsblk":
        return "lsblk", validateReadOnlyArgs(args)
    case "/usr/sbin/getenforce":
        if len(args) != 0 { return "", errors.New("getenforce accepts no arguments") }
        return "getenforce", nil
    case "/usr/sbin/ss":
        return "ss", validateReadOnlyArgs(args)
    case "/usr/bin/rpm":
        return "rpm", validateRPM(args)
    case "/usr/sbin/nginx":
        return "nginx", validateNginx(args)
    case "/usr/sbin/runuser":
        return "runuser-postgres", validateRunuserPostgres(args)
    default:
        if pgPathRE.MatchString(path) {
            return "postgres-bin:" + path, validatePostgresArgs(path, args)
        }
        return "", fmt.Errorf("privileged executable is not allowlisted: %s", path)
    }
}

// Serve runs as root. Socket permissions and peer credentials restrict access to
// the dedicated LayerSentry account; action validation is still mandatory.
func Serve(ctx context.Context, socketPath, groupName string, runner executor.Runner) error {
    if socketPath == "" { socketPath = DefaultSocket }
    if groupName == "" { groupName = "layersentry" }
    if runner == nil { return errors.New("privileged helper runner is nil") }
    dir := filepath.Dir(socketPath)
    if err := os.MkdirAll(dir, 0750); err != nil { return err }
    if fi, err := os.Lstat(socketPath); err == nil {
        if fi.Mode()&os.ModeSocket == 0 { return errors.New("refusing to replace non-socket privileged path") }
        if err := os.Remove(socketPath); err != nil { return err }
    } else if !errors.Is(err, os.ErrNotExist) { return err }

    addr, err := net.ResolveUnixAddr("unix", socketPath)
    if err != nil { return err }
    ln, err := net.ListenUnix("unix", addr)
    if err != nil { return err }
    defer ln.Close()
    defer os.Remove(socketPath)
    if err = os.Chmod(socketPath, 0660); err != nil { return err }
    if g, lookupErr := user.LookupGroup(groupName); lookupErr == nil {
        gid, convErr := strconv.Atoi(g.Gid)
        if convErr != nil { return convErr }
        if err = os.Chown(socketPath, 0, gid); err != nil { return err }
    } else {
        return fmt.Errorf("lookup helper group: %w", lookupErr)
    }

    sem := make(chan struct{}, 4)
    for {
        if err := ln.SetDeadline(time.Now().Add(time.Second)); err != nil { return err }
        conn, err := ln.AcceptUnix()
        if err != nil {
            if ne, ok := err.(net.Error); ok && ne.Timeout() {
                select {
                case <-ctx.Done(): return ctx.Err()
                default: continue
                }
            }
            return err
        }
        select {
        case sem <- struct{}{}:
            go func(c *net.UnixConn) {
                defer func(){ <-sem; c.Close() }()
                handle(c, runner)
            }(conn)
        default:
            _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "privileged helper busy"})
            _ = conn.Close()
        }
    }
}

func handle(conn *net.UnixConn, runner executor.Runner) {
    _ = conn.SetDeadline(time.Now().Add(5 * time.Minute))
    dec := json.NewDecoder(io.LimitReader(bufio.NewReader(conn), maxMessage))
    dec.DisallowUnknownFields()
    var req request
    if err := dec.Decode(&req); err != nil {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "invalid privileged request"})
        return
    }
    exe, err := executableFor(req.Action)
    if err == nil { err = validateAction(req.Action, req.Args) }
    if err != nil {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: err.Error()})
        return
    }
    res, runErr := runner.Run(context.Background(), exe, req.Args...)
    out := response{Stdout: res.Stdout, Stderr: res.Stderr, ExitCode: res.ExitCode}
    if runErr != nil { out.Error = runErr.Error() }
    _ = json.NewEncoder(conn).Encode(out)
}

func executableFor(action string) (string, error) {
    fixed := map[string]string{
        "dnf":"/usr/bin/dnf", "systemctl":"/usr/bin/systemctl", "firewall":"/usr/bin/firewall-cmd",
        "mkfs-xfs":"/usr/sbin/mkfs.xfs", "mkfs-ext4":"/usr/sbin/mkfs.ext4", "mount":"/usr/bin/mount",
        "findmnt":"/usr/bin/findmnt", "blkid":"/usr/sbin/blkid", "lsblk":"/usr/bin/lsblk",
        "getenforce":"/usr/sbin/getenforce", "ss":"/usr/sbin/ss", "rpm":"/usr/bin/rpm",
        "nginx":"/usr/sbin/nginx", "runuser-postgres":"/usr/sbin/runuser",
    }
    if p, ok := fixed[action]; ok { return p, nil }
    if strings.HasPrefix(action, "postgres-bin:") {
        p := strings.TrimPrefix(action, "postgres-bin:")
        if pgPathRE.MatchString(p) { return p, nil }
    }
    return "", errors.New("unknown privileged action")
}

func validateAction(action string, args []string) error {
    if err := validateBasic(args); err != nil { return err }
    switch {
    case action == "dnf": return validateDNF(args)
    case action == "systemctl": return validateSystemctl(args)
    case action == "firewall": return validateFirewall(args)
    case action == "mkfs-xfs": return validateMkfs(args, "-f")
    case action == "mkfs-ext4": return validateMkfs(args, "-F")
    case action == "mount": return validateMount(args)
    case action == "findmnt", action == "blkid", action == "lsblk", action == "ss": return validateReadOnlyArgs(args)
    case action == "getenforce": if len(args) != 0 { return errors.New("getenforce accepts no arguments") }; return nil
    case action == "rpm": return validateRPM(args)
    case action == "nginx": return validateNginx(args)
    case action == "runuser-postgres": return validateRunuserPostgres(args)
    case strings.HasPrefix(action, "postgres-bin:"): return validatePostgresArgs(strings.TrimPrefix(action, "postgres-bin:"), args)
    default: return errors.New("unknown privileged action")
    }
}

func validateBasic(args []string) error {
    if len(args) > 64 { return errors.New("too many privileged arguments") }
    for _, a := range args {
        if len(a) > 4096 || strings.ContainsAny(a, "\x00\r\n") { return errors.New("unsafe privileged argument") }
    }
    return nil
}

func validateDNF(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    joined := strings.ToLower(strings.Join(args, " "))
    for _, forbidden := range []string{"--nogpgcheck", "gpgcheck=0", "repo_gpgcheck=0", "sslverify=false", "http://", "https://", "file://"} {
        if strings.Contains(joined, forbidden) { return errors.New("unsafe dnf option rejected") }
    }
    if len(args) == 0 { return errors.New("dnf action missing") }
    for _, a := range args {
        if strings.HasPrefix(a, "--disablerepo=") || strings.HasPrefix(a, "--enablerepo=") || strings.HasPrefix(a, "--repofrompath=") {
            return errors.New("runtime repository override rejected")
        }
    }
    has := func(v string) bool { for _, a := range args { if a == v { return true } }; return false }
    if has("repoquery") || has("install") || has("remove") { return nil }
    if len(args) == 2 && args[0] == "clean" && args[1] == "packages" { return nil }
    return errors.New("dnf action is not allowlisted")
}

func validateSystemctl(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    if len(args) < 2 { return errors.New("systemctl action/unit required") }
    allowed := map[string]bool{"start":true,"stop":true,"restart":true,"enable":true,"disable":true,"is-active":true,"is-enabled":true}
    action := args[0]
    if !allowed[action] { return errors.New("systemctl action rejected") }
    for _, a := range args[1:] {
        if a == "--now" { continue }
        if !unitRE.MatchString(a) { return errors.New("systemctl unit rejected") }
        if !(a == "nginx.service" || strings.HasPrefix(a, "postgresql-")) { return errors.New("systemctl unit outside provider allowlist") }
    }
    return nil
}

func validateFirewall(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    for _, a := range args {
        switch {
        case a == "--permanent", a == "--reload":
        case strings.HasPrefix(a, "--new-zone=") || strings.HasPrefix(a, "--delete-zone=") || strings.HasPrefix(a, "--zone="):
            z := a[strings.IndexByte(a, '=')+1:]
            if !zoneRE.MatchString(z) { return errors.New("firewall zone rejected") }
        case a == "--set-target=DROP":
        case strings.HasPrefix(a, "--add-source="):
            if _, _, err := net.ParseCIDR(strings.TrimPrefix(a, "--add-source=")); err != nil { return errors.New("firewall CIDR rejected") }
        case strings.HasPrefix(a, "--add-port="):
            v := strings.TrimSuffix(strings.TrimPrefix(a, "--add-port="), "/tcp")
            p, err := strconv.Atoi(v); if err != nil || p < 1 || p > 65535 { return errors.New("firewall port rejected") }
        default:
            return errors.New("firewall argument rejected")
        }
    }
    return nil
}

func validateMkfs(args []string, flag string) error {
    if len(args) != 2 || args[0] != flag || !strings.HasPrefix(args[1], "/dev/disk/by-") { return errors.New("mkfs request rejected") }
    return validateBasic(args)
}

func validateMount(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    if len(args) != 1 || !safeMountPoint(args[0]) { return errors.New("mount target rejected") }
    return nil
}

func safeMountPoint(p string) bool {
    if !filepath.IsAbs(p) || filepath.Clean(p) != p { return false }
    for _, root := range []string{"/var/lib/pgsql", "/var/lib/mysql", "/var/lib/redis", "/var/lib/valkey", "/srv", "/data", "/opt/layersentry-data", "/var/log/layersentry-services"} {
        if p == root || strings.HasPrefix(p, root+"/") { return true }
    }
    return false
}

func validateReadOnlyArgs(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    for _, a := range args {
        if strings.HasPrefix(a, "--output") || strings.HasPrefix(a, "--target") || strings.HasPrefix(a, "--paths") || strings.HasPrefix(a, "--bytes") || strings.HasPrefix(a, "--json") || a == "-H" || a == "-lnt" || a == "-q" || a == "-s" || a == "-o" || a == "value" || safeTokenRE.MatchString(a) {
            continue
        }
        return errors.New("read-only helper argument rejected")
    }
    return nil
}

func validateRPM(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    if len(args) != 2 || args[0] != "-q" || !safeTokenRE.MatchString(args[1]) { return errors.New("rpm action rejected") }
    return nil
}

func validateNginx(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    if len(args) == 1 && (args[0] == "-t" || args[0] == "-v") { return nil }
    return errors.New("nginx action rejected")
}

func validateRunuserPostgres(args []string) error {
    if err := validateBasic(args); err != nil { return err }
    if len(args) < 4 || args[0] != "-u" || args[1] != "postgres" || args[2] != "--" { return errors.New("runuser request rejected") }
    if !pgPathRE.MatchString(args[3]) { return errors.New("runuser PostgreSQL executable rejected") }
    return validatePostgresArgs(args[3], args[4:])
}

func validatePostgresArgs(path string, args []string) error {
    if !pgPathRE.MatchString(path) { return errors.New("PostgreSQL executable rejected") }
    if err := validateBasic(args); err != nil { return err }
    base := filepath.Base(path)
    switch base {
    case "postgres":
        if len(args) == 1 && args[0] == "--version" { return nil }
    case "pg_isready":
        return nil
    case "psql":
        joined := strings.Join(args, " ")
        if strings.Contains(joined, "SELECT current_setting('server_version')") { return nil }
        return errors.New("psql statement rejected")
    case "pg_dumpall":
        for _, a := range args { if strings.HasPrefix(a, "--file=/var/lib/layersentryd/backups/") { return nil } }
    case "initdb":
        for _, a := range args { if strings.HasPrefix(a, "--pwfile=/run/layersentryd/pgpw-") { return nil } }
    }
    return errors.New("PostgreSQL helper arguments rejected")
}
