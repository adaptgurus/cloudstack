package providerexec

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
	"time"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

const DefaultSocket = "/run/layersentryd/provider-exec.sock"
const maxMessage = 2 << 20

var uuidPart = `[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}`
var sqlStageRE = regexp.MustCompile(`^/run/layersentryd/sql-staging/` + uuidPart + `/` + uuidPart + `-(bootstrap|db-dump|db-restore)\.sql$`)
var redisStageRE = regexp.MustCompile(`^/run/layersentryd/(redis-staging|backup-staging)/` + uuidPart + `/([0-9a-fA-F-]+-redis(-restore)?\.rdb|redis\.conf)$`)
var redisDataRE = regexp.MustCompile(`^/var/lib/redis/layersentry-` + uuidPart + `(/dump\.rdb)?$`)
var redisConfRE = regexp.MustCompile(`^/etc/redis/layersentry-` + uuidPart + `\.conf$`)
var mysqlTLSRE = regexp.MustCompile(`^/var/lib/mysql/layersentry-` + uuidPart + `(/(server\.crt|server\.key))?$`)
var mysqlConfRE = regexp.MustCompile(`^/etc/my\.cnf\.d/99-layersentry-(mysql|mariadb)\.cnf$`)

// Router keeps the generic core privileged helper separate from the small set
// of provider-native commands that need root identity (for example local
// socket database bootstrap). Unknown paths always stay on the core helper,
// which fails closed on its own allowlist.
type Router struct {
	Core     executor.Runner
	Provider executor.Runner
}

func (r Router) Run(ctx context.Context, path string, args ...string) (executor.Result, error) {
	if isProviderPath(path) {
		if r.Provider == nil {
			return executor.Result{}, errors.New("provider execution helper unavailable")
		}
		return r.Provider.Run(ctx, path, args...)
	}
	if r.Core == nil {
		return executor.Result{}, errors.New("core privileged helper unavailable")
	}
	return r.Core.Run(ctx, path, args...)
}

type request struct {
	Path string   `json:"path"`
	Args []string `json:"args"`
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
	return Client{Socket: socket, Timeout: 3 * time.Minute}
}

func (c Client) Run(ctx context.Context, path string, args ...string) (executor.Result, error) {
	if err := validate(path, args); err != nil {
		return executor.Result{}, err
	}
	if c.Timeout <= 0 {
		c.Timeout = 3 * time.Minute
	}
	cctx, cancel := context.WithTimeout(ctx, c.Timeout)
	defer cancel()
	conn, err := (&net.Dialer{Timeout: 5 * time.Second}).DialContext(cctx, "unix", c.Socket)
	if err != nil {
		return executor.Result{}, fmt.Errorf("provider execution helper unavailable: %w", err)
	}
	defer conn.Close()
	if deadline, ok := cctx.Deadline(); ok {
		_ = conn.SetDeadline(deadline)
	}
	if err = json.NewEncoder(conn).Encode(request{Path: path, Args: args}); err != nil {
		return executor.Result{}, err
	}
	var out response
	dec := json.NewDecoder(io.LimitReader(conn, maxMessage))
	if err = dec.Decode(&out); err != nil {
		return executor.Result{}, err
	}
	res := executor.Result{Stdout: out.Stdout, Stderr: out.Stderr, ExitCode: out.ExitCode}
	if out.Error != "" {
		return res, errors.New(out.Error)
	}
	return res, nil
}

func Serve(ctx context.Context, socketPath, groupName string, runner executor.Runner) error {
	if socketPath == "" {
		socketPath = DefaultSocket
	}
	if groupName == "" {
		groupName = "layersentry"
	}
	if runner == nil {
		return errors.New("provider helper runner is nil")
	}
	dir := filepath.Dir(socketPath)
	fi, err := os.Lstat(dir)
	if err != nil {
		return err
	}
	if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 || fi.Mode().Perm()&01000 == 0 {
		return errors.New("unsafe provider helper socket directory")
	}
	if old, err := os.Lstat(socketPath); err == nil {
		if old.Mode()&os.ModeSocket == 0 {
			return errors.New("refusing to replace non-socket provider helper path")
		}
		if err = os.Remove(socketPath); err != nil {
			return err
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
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
	g, err := user.LookupGroup(groupName)
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
	sem := make(chan struct{}, 4)
	for {
		_ = ln.SetDeadline(time.Now().Add(time.Second))
		conn, err := ln.AcceptUnix()
		if err != nil {
			if ne, ok := err.(net.Error); ok && ne.Timeout() {
				select {
				case <-ctx.Done():
					return ctx.Err()
				default:
					continue
				}
			}
			return err
		}
		select {
		case sem <- struct{}{}:
			go func(c *net.UnixConn) {
				defer func() { <-sem; _ = c.Close() }()
				handle(c, runner)
			}(conn)
		default:
			_ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "provider helper busy"})
			_ = conn.Close()
		}
	}
}

func handle(conn *net.UnixConn, runner executor.Runner) {
	_ = conn.SetDeadline(time.Now().Add(5 * time.Minute))
	dec := json.NewDecoder(io.LimitReader(conn, maxMessage))
	dec.DisallowUnknownFields()
	var req request
	if err := dec.Decode(&req); err != nil {
		_ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: "invalid provider helper request"})
		return
	}
	if err := validate(req.Path, req.Args); err != nil {
		_ = json.NewEncoder(conn).Encode(response{ExitCode: -1, Error: err.Error()})
		return
	}
	res, runErr := runner.Run(context.Background(), req.Path, req.Args...)
	out := response{Stdout: res.Stdout, Stderr: res.Stderr, ExitCode: res.ExitCode}
	if runErr != nil {
		out.Error = runErr.Error()
	}
	_ = json.NewEncoder(conn).Encode(out)
}

func isProviderPath(path string) bool {
	switch path {
	case "/usr/sbin/httpd", "/usr/sbin/restorecon", "/usr/bin/install", "/usr/bin/mysql", "/usr/bin/mysqldump", "/usr/bin/mariadb", "/usr/bin/mariadb-dump":
		return true
	default:
		return false
	}
}

func validate(path string, args []string) error {
	if !isProviderPath(path) {
		return fmt.Errorf("provider executable is not allowlisted: %s", path)
	}
	if len(args) > 24 {
		return errors.New("too many provider-helper arguments")
	}
	for _, a := range args {
		if len(a) > 4096 || strings.ContainsAny(a, "\x00\r\n") {
			return errors.New("unsafe provider-helper argument")
		}
	}
	switch path {
	case "/usr/sbin/httpd":
		if len(args) == 1 && (args[0] == "-t" || args[0] == "-v") {
			return nil
		}
		return errors.New("httpd action rejected")
	case "/usr/sbin/restorecon":
		return validateRestorecon(args)
	case "/usr/bin/install":
		return validateInstall(args)
	case "/usr/bin/mysql", "/usr/bin/mariadb":
		return validateSQLClient(args)
	case "/usr/bin/mysqldump", "/usr/bin/mariadb-dump":
		return validateSQLDump(args)
	default:
		return errors.New("provider action rejected")
	}
}

func validateSQLClient(args []string) error {
	if len(args) == 5 && args[0] == "--protocol=socket" && args[1] == "--user=root" && args[2] == "--batch" && args[3] == "--skip-column-names" && args[4] == "--execute=SELECT VERSION()" {
		return nil
	}
	if len(args) == 3 && args[0] == "--protocol=socket" && args[1] == "--user=root" && strings.HasPrefix(args[2], "--execute=source ") {
		path := strings.TrimPrefix(args[2], "--execute=source ")
		if filepath.Clean(path) != path || !sqlStageRE.MatchString(path) || strings.HasSuffix(path, "-db-dump.sql") {
			return errors.New("database source path rejected")
		}
		fi, err := os.Lstat(path)
		if err != nil {
			return err
		}
		if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Mode().Perm()&0002 != 0 {
			return errors.New("database source file is unsafe")
		}
		return nil
	}
	return errors.New("database client grammar rejected")
}

func validateSQLDump(args []string) error {
	want := []string{"--protocol=socket", "--user=root", "--all-databases", "--single-transaction", "--routines", "--events", "--hex-blob"}
	if len(args) != len(want)+1 {
		return errors.New("database dump grammar rejected")
	}
	for i := range want {
		if args[i] != want[i] {
			return errors.New("database dump argument rejected")
		}
	}
	if !strings.HasPrefix(args[len(args)-1], "--result-file=") {
		return errors.New("database dump result path missing")
	}
	path := strings.TrimPrefix(args[len(args)-1], "--result-file=")
	if filepath.Clean(path) != path || !sqlStageRE.MatchString(path) || !strings.HasSuffix(path, "-db-dump.sql") {
		return errors.New("database dump result path rejected")
	}
	if err := safeParent(filepath.Dir(path)); err != nil {
		return err
	}
	if _, err := os.Lstat(path); err == nil {
		return errors.New("database dump result already exists")
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}

func validateRestorecon(args []string) error {
	if len(args) < 2 || len(args) > 3 || (args[0] != "-F" && args[0] != "-RF") {
		return errors.New("restorecon grammar rejected")
	}
	if args[0] == "-RF" && len(args) != 2 {
		return errors.New("recursive restorecon accepts one provider root")
	}
	for _, path := range args[1:] {
		if !allowedRestoreconPath(path, args[0] == "-RF") {
			return errors.New("restorecon path rejected")
		}
	}
	return nil
}

func allowedRestoreconPath(path string, recursive bool) bool {
	if filepath.Clean(path) != path || !filepath.IsAbs(path) {
		return false
	}
	if mysqlConfRE.MatchString(path) || redisConfRE.MatchString(path) || path == "/etc/redis/redis.conf" {
		return !recursive
	}
	if mysqlTLSRE.MatchString(path) || redisDataRE.MatchString(path) {
		if recursive {
			return !strings.HasSuffix(path, "/server.crt") && !strings.HasSuffix(path, "/server.key") && !strings.HasSuffix(path, "/dump.rdb")
		}
		return strings.HasSuffix(path, "/dump.rdb")
	}
	return false
}

func validateInstall(args []string) error {
	if len(args) == 5 && args[0] == "--directory" && args[1] == "--mode=0750" && args[2] == "--owner=redis" && args[3] == "--group=redis" && redisDataRE.MatchString(args[4]) && !strings.HasSuffix(args[4], "/dump.rdb") {
		return nil
	}
	if len(args) != 5 {
		return errors.New("install grammar rejected")
	}
	mode, owner, group, src, dst := args[0], args[1], args[2], args[3], args[4]
	switch {
	case mode == "--mode=0640" && owner == "--owner=root" && group == "--group=redis" && strings.HasSuffix(src, "/redis.conf") && redisStageRE.MatchString(src) && redisConfRE.MatchString(dst):
		return safeExistingFile(src)
	case mode == "--mode=0600" && owner == "--owner=layersentry" && group == "--group=layersentry" && redisDataRE.MatchString(src) && strings.HasSuffix(src, "/dump.rdb") && redisStageRE.MatchString(dst) && strings.HasSuffix(dst, "-redis.rdb"):
		return safeNewFile(dst)
	case mode == "--mode=0600" && owner == "--owner=redis" && group == "--group=redis" && redisStageRE.MatchString(src) && strings.HasSuffix(src, "-redis-restore.rdb") && redisDataRE.MatchString(dst) && strings.HasSuffix(dst, "/dump.rdb"):
		return safeExistingFile(src)
	default:
		return errors.New("install provider path/ownership rejected")
	}
}

func safeParent(path string) error {
	fi, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 || fi.Mode().Perm()&0002 != 0 {
		return errors.New("unsafe provider staging directory")
	}
	return nil
}

func safeExistingFile(path string) error {
	if err := safeParent(filepath.Dir(path)); err != nil {
		return err
	}
	fi, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Mode().Perm()&0002 != 0 {
		return errors.New("unsafe provider source file")
	}
	return nil
}

func safeNewFile(path string) error {
	if err := safeParent(filepath.Dir(path)); err != nil {
		return err
	}
	if _, err := os.Lstat(path); err == nil {
		return errors.New("provider destination already exists")
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}