package packageutil

import (
 "context"
 "errors"
 "fmt"
 "regexp"
 "sort"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

var tokenSafe=regexp.MustCompile(`^[A-Za-z0-9._+~:-]+$`)
type DNF struct{Runner executor.Runner}
func(d DNF)ValidateRepositories(ctx context.Context,repos ...string)error{if len(repos)==0{return errors.New("no approved repositories")};for _,repo:=range repos{if !tokenSafe.MatchString(repo){return fmt.Errorf("unsafe repository id %q",repo)};r,err:=d.Runner.Run(ctx,"/usr/bin/dnf","-q","config-manager","--dump",repo);if err!=nil{return fmt.Errorf("repository %s unavailable: %w",repo,err)};cfg:=strings.ToLower(r.Stdout);if !settingEnabled(cfg,"enabled"){return fmt.Errorf("repository %s is disabled",repo)};if !settingEnabled(cfg,"gpgcheck"){return fmt.Errorf("repository %s must enforce package GPG verification",repo)};if strings.Contains(cfg,"sslverify = 0")||strings.Contains(cfg,"sslverify=false"){return fmt.Errorf("repository %s disables TLS verification",repo)}};return nil}
func settingEnabled(cfg,key string)bool{for _,line:=range strings.Split(cfg,"\n"){f:=strings.SplitN(strings.TrimSpace(line),"=",2);if len(f)==2&&strings.TrimSpace(f[0])==key{v:=strings.TrimSpace(f[1]);return v=="1"||v=="true"}};return false}
func(d DNF)ResolveLatest(ctx context.Context,pkg string)(string,error){return d.ResolveLatestFromRepos(ctx,pkg,nil)}
func(d DNF)ResolveLatestFromRepos(ctx context.Context,pkg string,repos []string)(string,error){if !tokenSafe.MatchString(pkg){return "",errors.New("invalid package name")};args:=[]string{"-q","repoquery","--latest-limit","1","--qf","%{name}-%{epoch}:%{version}-%{release}.%{arch}"};for _,repo:=range repos{if !tokenSafe.MatchString(repo){return "",fmt.Errorf("unsafe repository id %q",repo)};args=append(args,"--repoid="+repo)};args=append(args,pkg);r,err:=d.Runner.Run(ctx,"/usr/bin/dnf",args...);if err!=nil{return "",err};lines:=strings.Fields(strings.TrimSpace(r.Stdout));if len(lines)==0{return "",fmt.Errorf("package not found: %s",pkg)};sort.Strings(lines);v:=lines[len(lines)-1];if !tokenSafe.MatchString(v){return "",errors.New("unsafe repoquery output")};return v,nil}
func(d DNF)InstallExact(ctx context.Context,nevras ...string)error{return d.InstallExactFromRepos(ctx,nil,nevras...)}
func(d DNF)InstallExactFromRepos(ctx context.Context,repos []string,nevras ...string)error{if len(nevras)==0{return errors.New("no packages")};args:=[]string{"-y","--setopt=install_weak_deps=False"};if len(repos)>0{args=append(args,"--disablerepo=*");for _,repo:=range repos{if !tokenSafe.MatchString(repo){return fmt.Errorf("unsafe repository id %q",repo)};args=append(args,"--enablerepo="+repo)}};args=append(args,"install");for _,n:=range nevras{if !tokenSafe.MatchString(n){return fmt.Errorf("unsafe NEVRA %q",n)};args=append(args,n)};_,err:=d.Runner.Run(ctx,"/usr/bin/dnf",args...);return err}
func(d DNF)Remove(ctx context.Context,pkgs ...string)error{args:=[]string{"-y","remove"};for _,p:=range pkgs{if !tokenSafe.MatchString(p){return errors.New("unsafe package")};args=append(args,p)};_,err:=d.Runner.Run(ctx,"/usr/bin/dnf",args...);return err}
func(d DNF)Clean(ctx context.Context)error{_,err:=d.Runner.Run(ctx,"/usr/bin/dnf","clean","packages");return err}
