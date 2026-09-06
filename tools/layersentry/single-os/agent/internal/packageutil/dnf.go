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

var nevraSafe=regexp.MustCompile(`^[A-Za-z0-9._+~:-]+$`)
type DNF struct{Runner executor.Runner}
func(d DNF)ResolveLatest(ctx context.Context,pkg string)(string,error){if !nevraSafe.MatchString(pkg){return "",errors.New("invalid package name")};r,err:=d.Runner.Run(ctx,"/usr/bin/dnf","-q","repoquery","--latest-limit","1","--qf","%{name}-%{epoch}:%{version}-%{release}.%{arch}",pkg);if err!=nil{return "",err};lines:=strings.Fields(strings.TrimSpace(r.Stdout));if len(lines)==0{return "",fmt.Errorf("package not found: %s",pkg)};sort.Strings(lines);v:=lines[len(lines)-1];if !nevraSafe.MatchString(v){return "",errors.New("unsafe repoquery output")};return v,nil}
func(d DNF)InstallExact(ctx context.Context,nevras ...string)error{if len(nevras)==0{return errors.New("no packages")};args:=[]string{"-y","--setopt=install_weak_deps=False","install"};for _,n:=range nevras{if !nevraSafe.MatchString(n){return fmt.Errorf("unsafe NEVRA %q",n)};args=append(args,n)};_,err:=d.Runner.Run(ctx,"/usr/bin/dnf",args...);return err}
func(d DNF)Remove(ctx context.Context,pkgs ...string)error{args:=[]string{"-y","remove"};for _,p:=range pkgs{if !nevraSafe.MatchString(p){return errors.New("unsafe package")};args=append(args,p)};_,err:=d.Runner.Run(ctx,"/usr/bin/dnf",args...);return err}
func(d DNF)Clean(ctx context.Context)error{_,err:=d.Runner.Run(ctx,"/usr/bin/dnf","clean","packages");return err}
