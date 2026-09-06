package providerexec

import (
	"context"
	"testing"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type markerRunner struct{ stdout string }

func (r markerRunner) Run(context.Context, string, ...string) (executor.Result, error) {
	return executor.Result{Stdout: r.stdout}, nil
}

func TestHTTPDAllowsOnlyConfigAndVersionChecks(t *testing.T) {
	for _, arg := range []string{"-t", "-v"} {
		if err := validate("/usr/sbin/httpd", []string{arg}); err != nil {
			t.Fatalf("expected httpd %s to be allowed: %v", arg, err)
		}
	}
	if err := validate("/usr/sbin/httpd", []string{"-f", "/tmp/attacker.conf"}); err == nil {
		t.Fatal("expected arbitrary httpd config path to be rejected")
	}
}

func TestDatabaseClientRejectsArbitrarySQL(t *testing.T) {
	if err := validate("/usr/bin/mysql", []string{"--protocol=socket", "--user=root", "--execute=DROP DATABASE customer"}); err == nil {
		t.Fatal("expected arbitrary SQL to be rejected")
	}
	if err := validate("/usr/bin/mariadb", []string{"--protocol=socket", "--user=root", "--batch", "--skip-column-names", "--execute=SELECT VERSION()"}); err != nil {
		t.Fatalf("expected fixed health query to be accepted: %v", err)
	}
}

func TestRestoreconRejectsForeignPath(t *testing.T) {
	if err := validate("/usr/sbin/restorecon", []string{"-RF", "/root"}); err == nil {
		t.Fatal("expected foreign restorecon root to be rejected")
	}
}

func TestInstallRejectsArbitraryCopy(t *testing.T) {
	if err := validate("/usr/bin/install", []string{"--mode=04755", "--owner=root", "--group=root", "/bin/sh", "/tmp/rootsh"}); err == nil {
		t.Fatal("expected arbitrary privileged file copy to be rejected")
	}
}

func TestProviderHelperRejectsShell(t *testing.T) {
	if err := validate("/bin/sh", []string{"-c", "id"}); err == nil {
		t.Fatal("expected shell execution to be rejected")
	}
}

func TestRouterSeparatesCoreAndProviderPaths(t *testing.T) {
	r := Router{Core: markerRunner{stdout: "core"}, Provider: markerRunner{stdout: "provider"}}
	got, err := r.Run(context.Background(), "/usr/sbin/httpd", "-t")
	if err != nil || got.Stdout != "provider" {
		t.Fatalf("provider path not routed to provider helper: %+v %v", got, err)
	}
	got, err = r.Run(context.Background(), "/usr/bin/rpm", "-q", "nginx")
	if err != nil || got.Stdout != "core" {
		t.Fatalf("core path not routed to core helper: %+v %v", got, err)
	}
}
