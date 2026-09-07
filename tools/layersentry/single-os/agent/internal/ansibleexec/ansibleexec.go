package ansibleexec

import (
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
    "syscall"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket = "/run/layersentryd/ansible-exec.sock"
const runtimeRoot = "/run/layersentryd/ansible"
const projectRoot = "/usr/lib/layersentry/ansible"
const maxMessage = 2 << 20

var fileRE = regexp.MustCompile(`^[0-9a-fA-F-]{36}-(apply|upgrade|repair|uninstall|start|stop|restart)\.json$`)

var playbooks = map[string]string{
    "apply":     projectRoot + "/playbooks/single_os_apply.yml",
    "upgrade":   projectRoot + "/playbooks/single_os_upgrade.yml",
    "repair":    projectRoot + "/playbooks/single_os_repair.yml",
    "uninstall": projectRoot + "/playbooks/single_os_uninstall.yml",
    "start":     projectRoot + "/playbooks/single_os_service.yml",
    "stop":      projectRoot + "/playbooks/single_os_service.yml",
    "restart":   projectRoot + "/playbooks/single_os_service.yml",
}

type request struct {
    Action   string `json:"action"`
    VarsPath string `json:"vars_path"`
}
type response struct {
    Stdout   string `json:"stdout,omitempty"`
    Stderr   string `json:"stderr,omitempty"`
    ExitCode int    `json:"exit_code"`
    Error    string `json:"error,omitempty"`
}

type Client struct {
    Socket  string
    Timeout time.Duration
}

func NewClient(socket string) Client {
    if socket == "" {
        socket = DefaultSocket
    }
    return Client{Socket: socket, Timeout: 15 * time.Minute}
}

func (c Client) Run(ctx context.Context, action, varsPath string) (executor.Result, error) {
    if _, ok := playbooks[action]; !ok {
        return executor.Result{}, errors.New("Ansible action rejected")
    }
    if err := validateVarsPath(varsPath, -1); err != nil {
        return executor.Result{}, err
    }
    cctx, cancel := context.WithTimeout(ctx, c.Timeout)
    defer cancel()
    conn, err := (&net.Dialer{Timeout: 5 * time.Second}).DialContext(cctx, "unix", c.Socket)
    if err != nil {
        return executor.Result{}, fmt.Errorf("Ansible helper unavailable: %w", err)
    }
    defer conn.Close()
    if deadline, ok := cctx.Deadline(); ok {
        _ = conn.SetDeadline(deadline)
    }
    if err = json.NewEncoder(conn).Encode(request{Action: action, VarsPath: varsPath}); err != nil {
        return executor.Result{}, err
    }
    var out response
    if err = json.NewDecoder(io.LimitReader(conn, maxMessage)).Decode(&out); err != nil {
        return executor.Result{}, err
    }
    res := executor.Result{Stdout: out.Stdout, Stderr: out.Stderr, ExitCode: out.ExitCode}
    if out.Error != "" {
        return res, errors.New(out.Error)
    }
    return res, nil
}

func Serve(ctx context.Context, socketPath, group string, runner executor.Runner) error {
    if socketPath == "" {
        socketPath = DefaultSocket
    }
    if group == "" {
        group = "layersentry"
    }
    if runner == nil {
        return errors.New("Ansible helper runner is nil")
    }
    expectedUID, err := lookupUID("layersentry")
    if err != nil {
        return err
    }
    dir := filepath.Dir(socketPath)
    fi, err := os.Lstat(dir)
    if err != nil {
        return err
    }
    if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 || fi.Mode().Perm()&01000 == 0 {
        return errors.New("unsafe Ansible helper socket directory")
    }
    if old, statErr := os.Lstat(socketPath); statErr == nil {
        if old.Mode()&os.ModeSocket == 0 {
            return errors.New("refusing non-socket Ansible helper path")
        }
        if err = os.Remove(socketPath); err != nil {
            return err
        }
    } else if !errors.Is(statErr, os.ErrNotExist) {
        return statErr
    }
    addr, err := net.ResolveUnixAddr("unix", socketPath)
    if err != nil {
        return err
    }
    ln, err := net.ListenUnix("unix", addr)
    if err != nil {
        return err
    }
    defer ln.Close()
    defer os.Remove(socketPath)
    g, err := user.LookupGroup(group)
    if err != nil {
        return err
    }
    gid, err := strconv.Atoi(g.Gid)
    if err != nil {
        return err
    }
    if err = os.Chown(socketPath, 0, gid); err != nil {
        return err
    }
    if err = os.Chmod(socketPath, 0660); err != nil {
        return err
    }
    for {
        _ = ln.SetDeadline(time.Now().Add(time.Second))
        conn, acceptErr := ln.AcceptUnix()
        if acceptErr != nil {
            if ne, ok := acceptErr.(net.Error); ok && ne.Timeout() {
                select {
                case <-ctx.Done():
                    return ctx.Err()
                default:
                    continue
                }
            }
            return acceptErr
        }
        go handle(conn, runner, expectedUID)
    }
}

func handle(conn *net.UnixConn, runner executor.Runner, expectedUID int) {
    defer conn.Close()
    _ = conn.SetDeadline(time.Now().Add(20 * time.Minute))
    dec := json.NewDecoder(io.LimitReader(conn, maxMessage))
    dec.DisallowUnknownFields()
    var req request
    if err := dec.Decode(&req); err != nil {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "invalid Ansible request"})
        return
    }
    playbook, ok := playbooks[req.Action]
    if !ok {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "Ansible action rejected"})
        return
    }
    if err := validateVarsPath(req.VarsPath, expectedUID); err != nil {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: err.Error()})
        return
    }
    if err := validateProjectFile(playbook); err != nil {
        _ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: err.Error()})
        return
    }
    args := []string{
        "--inventory", projectRoot + "/inventory/localhost.ini",
        "--connection", "local",
        "--forks", "1",
        "--extra-vars", "@" + req.VarsPath,
        playbook,
    }
    res, runErr := runner.Run(context.Background(), "/usr/bin/ansible-playbook", args...)
    out := response{Stdout: res.Stdout, Stderr: res.Stderr, ExitCode: res.ExitCode}
    if runErr != nil {
        out.Error = runErr.Error()
    }
    _ = json.NewEncoder(conn).Encode(out)
}

func validateVarsPath(path string, expectedUID int) error {
    clean := filepath.Clean(path)
    if clean != path || !filepath.IsAbs(path) {
        return errors.New("Ansible vars path must be canonical absolute path")
    }
    rel, err := filepath.Rel(runtimeRoot, clean)
    if err != nil || rel == "." || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || strings.Contains(rel, string(filepath.Separator)) {
        return errors.New("Ansible vars path outside private runtime root")
    }
    if !fileRE.MatchString(filepath.Base(clean)) {
        return errors.New("Ansible vars filename rejected")
    }
    fi, err := os.Lstat(clean)
    if err != nil {
        return err
    }
    if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Size() < 2 || fi.Size() > 1<<20 || fi.Mode().Perm() != 0600 {
        return errors.New("unsafe Ansible vars file")
    }
    if expectedUID >= 0 {
        st, ok := fi.Sys().(*syscall.Stat_t)
        if !ok || int(st.Uid) != expectedUID {
            return errors.New("Ansible vars file owner mismatch")
        }
    }
    return nil
}

func validateProjectFile(path string) error {
    clean := filepath.Clean(path)
    if !strings.HasPrefix(clean, projectRoot+string(filepath.Separator)) {
        return errors.New("Ansible playbook outside immutable project root")
    }
    fi, err := os.Lstat(clean)
    if err != nil {
        return err
    }
    if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Mode().Perm()&0022 != 0 {
        return errors.New("unsafe Ansible playbook file")
    }
    return nil
}

func lookupUID(name string) (int, error) {
    u, err := user.Lookup(name)
    if err != nil {
        return 0, err
    }
    uid, err := strconv.Atoi(u.Uid)
    if err != nil {
        return 0, err
    }
    return uid, nil
}
