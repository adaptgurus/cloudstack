package main

import (
 "crypto/tls"
 "fmt"
 "log"
 "net"
 "net/http"
 "os"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/api"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/auth"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/bootstrap"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lifecycle"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/maintenance"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/secrets"
 nginxprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/nginx"
 pgprovider "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/postgresql"
)

const root="/var/lib/layersentryd"
type runtimeState struct{runner executor.OSRunner;reg *provider.Registry;store *journal.Store;eng *lifecycle.Engine}
func main(){mode:="serve";if len(os.Args)>1{mode=os.Args[1]};switch mode{case "firstboot":must(firstBoot());case "seal":must(bootstrap.Seal(bootstrap.DefaultPaths()));case "maintenance-run":must(maintenanceRun());case "serve":must(serve());default:log.Fatalf("unknown mode %q",mode)}}
func firstBoot()error{return bootstrap.Ensure(bootstrap.DefaultPaths(),localIPs())}
func buildRuntime()(*runtimeState,error){runner:=executor.OSRunner{Timeout:3*time.Minute,MaxOutput:1<<20};reg:=provider.NewRegistry();if err:=reg.Register(pgprovider.New(runner));err!=nil{return nil,err};if err:=reg.Register(nginxprovider.New(runner));err!=nil{return nil,err};st,err:=journal.New(root);if err!=nil{return nil,err};eng:=&lifecycle.Engine{Registry:reg,Store:st,Runner:runner,LockPath:root+"/state/mutation.lock"};return &runtimeState{runner:runner,reg:reg,store:st,eng:eng},nil}
func serve()error{if err:=firstBoot();err!=nil{return err};rt,err:=buildRuntime();if err!=nil{return err};sec,err:=secrets.Open(root+"/secrets",root+"/identity/secret.key");if err!=nil{return err};authm:=auth.New(root+"/identity/admin.json");srv:=&api.Server{Engine:rt.eng,Auth:authm,Secrets:sec,Journal:rt.store,Registry:rt.reg,BootstrapFile:root+"/identity/bootstrap-token",AllowedOrigin:os.Getenv("LAYERSENTRY_ALLOWED_ORIGIN")};handler,err:=srv.Handler();if err!=nil{return err};hs:=&http.Server{Addr:":9443",Handler:handler,ReadHeaderTimeout:10*time.Second,ReadTimeout:30*time.Second,WriteTimeout:5*time.Minute,IdleTimeout:60*time.Second,MaxHeaderBytes:1<<20,TLSConfig:&tls.Config{MinVersion:tls.VersionTLS12}};log.Printf("layersentryd starting HTTPS management endpoint on %s",hs.Addr);return hs.ListenAndServeTLS(root+"/identity/tls.crt",root+"/identity/tls.key")}
func maintenanceRun()error{rt,err:=buildRuntime();if err!=nil{return err};return (maintenance.Runner{Store:rt.store,Engine:rt.eng}).Run(contextBackground())}
func contextBackground() interface{ Done() <-chan struct{} } { return nil }
func localIPs()[]net.IP{ifs,_:=net.Interfaces();var out []net.IP;for _,i:=range ifs{addrs,_:=i.Addrs();for _,a:=range addrs{ip,_,err:=net.ParseCIDR(a.String());if err==nil&&ip!=nil&&!ip.IsUnspecified(){out=append(out,ip)}}};return out}
func must(err error){if err!=nil{fmt.Fprintln(os.Stderr,"layersentryd:",err);os.Exit(1)}}
