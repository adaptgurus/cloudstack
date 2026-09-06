package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/api"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/auth"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/backupcrypto"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/bootstrap"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/cluster"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lifecycle"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/maintenance"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/privileged"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/providerexec"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/secrets"
	apacheprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/apache"
	mysqlprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/mysqlfamily"
	nginxprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/nginx"
	pgprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/postgresql"
	redisprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/redis"
	runtimeprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/runtime"
	tomcatprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/tomcat"
)

const root = "/var/lib/layersentryd"

type runtimeState struct {
	runner     executor.Runner
	reg        *provider.Registry
	store      *journal.Store
	secrets    *secrets.Store
	backupKeys *backupcrypto.Keyring
	enrollment *cluster.Manager
	eng        *lifecycle.Engine
}

func main() {
	mode := "serve"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}
	switch mode {
	case "firstboot":
		must(firstBoot())
	case "seal":
		must(bootstrap.Seal(bootstrap.DefaultPaths()))
	case "maintenance-run":
		must(maintenanceRun())
	case "privileged-helper":
		must(privilegedHelper())
	case "serve":
		must(serve())
	default:
		log.Fatalf("unknown mode %q", mode)
	}
}

func firstBoot() error { return bootstrap.Ensure(bootstrap.DefaultPaths(), localIPs()) }

func buildRuntime() (*runtimeState, error) {
	coreRunner := privileged.NewClient(privileged.DefaultSocket)
	providerRunner := providerexec.NewClient(providerexec.DefaultSocket)
	runner := providerexec.Router{Core: coreRunner, Provider: providerRunner}
	st, err := journal.New(root)
	if err != nil {
		return nil, err
	}
	sec, err := secrets.Open(root+"/secrets", root+"/identity/secret.key")
	if err != nil {
		return nil, err
	}
	backupKeys, err := backupcrypto.Open(root + "/identity/backup.agekeys")
	if err != nil {
		return nil, err
	}
	enrollment, err := cluster.Open(root + "/enrollment/tokens")
	if err != nil {
		return nil, err
	}
	reg := provider.NewRegistry()
	providers := []provider.Provider{
		pgprovider.New(runner, sec, backupKeys),
		mysqlprovider.MySQL(runner, sec, backupKeys),
		mysqlprovider.MariaDB(runner, sec, backupKeys),
		redisprovider.New(runner, sec, backupKeys),
		nginxprovider.New(runner),
		apacheprovider.New(runner),
		tomcatprovider.New(runner),
		runtimeprovider.New(runner, runtimeprovider.Spec{ID: "nodejs-runtime", Package: "nodejs", RepoID: "appstream", AllowedReleaseLines: map[string]string{"22": "22"}, Description: "Rocky AppStream Node.js runtime"}),
		runtimeprovider.New(runner, runtimeprovider.Spec{ID: "python-runtime", Package: "python3.12", RepoID: "appstream", AllowedReleaseLines: map[string]string{"3.12": "3.12"}, Description: "Rocky AppStream Python 3.12 runtime"}),
		runtimeprovider.New(runner, runtimeprovider.Spec{ID: "podman-runtime", Package: "podman", RepoID: "appstream", AllowedReleaseLines: map[string]string{"rocky9": ""}, Description: "Rocky AppStream Podman runtime; no OCI workload is started by this package-only provider"}),
	}
	for _, p := range providers {
		if err = reg.Register(p); err != nil {
			return nil, err
		}
	}
	clusterClient := &cluster.Client{Secrets: sec}
	eng := &lifecycle.Engine{Registry: reg, Store: st, Runner: runner, Cluster: clusterClient, LockPath: root + "/state/mutation.lock"}
	return &runtimeState{runner: runner, reg: reg, store: st, secrets: sec, backupKeys: backupKeys, enrollment: enrollment, eng: eng}, nil
}

func serve() error {
	if err := firstBoot(); err != nil {
		return err
	}
	rt, err := buildRuntime()
	if err != nil {
		return err
	}
	authm := auth.New(root + "/identity/admin.json")
	srv := &api.Server{
		Engine:        rt.eng,
		Auth:          authm,
		Secrets:       rt.secrets,
		Journal:       rt.store,
		Registry:      rt.reg,
		Enrollment:    rt.enrollment,
		BootstrapFile: root + "/identity/bootstrap-token",
		TLSCertFile:   root + "/identity/tls.crt",
		AllowedOrigin: os.Getenv("LAYERSENTRY_ALLOWED_ORIGIN"),
	}
	handler, err := srv.Handler()
	if err != nil {
		return err
	}
	hs := &http.Server{
		Addr:              ":9443",
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      5 * time.Minute,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
		TLSConfig:         &tls.Config{MinVersion: tls.VersionTLS12},
	}
	log.Printf("layersentryd starting HTTPS management endpoint on %s", hs.Addr)
	return hs.ListenAndServeTLS(root+"/identity/tls.crt", root+"/identity/tls.key")
}

func maintenanceRun() error {
	rt, err := buildRuntime()
	if err != nil {
		return err
	}
	return (maintenance.Runner{Store: rt.store, Engine: rt.eng, Secrets: rt.secrets, Enrollment: rt.enrollment}).Run(context.Background())
}

func privilegedHelper() error {
	if os.Geteuid() != 0 {
		return errors.New("privileged-helper requires root")
	}
	runner := executor.OSRunner{Timeout: 5 * time.Minute, MaxOutput: 1 << 20}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	errCh := make(chan error, 2)
	go func() { errCh <- privileged.Serve(ctx, privileged.DefaultSocket, "layersentry", runner) }()
	go func() { errCh <- providerexec.Serve(ctx, providerexec.DefaultSocket, "layersentry", runner) }()
	first := <-errCh
	cancel()
	second := <-errCh
	if first != nil && !errors.Is(first, context.Canceled) {
		return first
	}
	if second != nil && !errors.Is(second, context.Canceled) {
		return second
	}
	return nil
}

func localIPs() []net.IP {
	ifs, _ := net.Interfaces()
	var out []net.IP
	for _, i := range ifs {
		addrs, _ := i.Addrs()
		for _, a := range addrs {
			ip, _, err := net.ParseCIDR(a.String())
			if err == nil && ip != nil && !ip.IsUnspecified() {
				out = append(out, ip)
			}
		}
	}
	return out
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "layersentryd:", err)
		os.Exit(1)
	}
}