package packageutil

import (
    "context"
    "errors"
    "reflect"
    "testing"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type call struct{path string;args []string}
type fakeRunner struct{calls []call;results []executor.Result;errs []error}
func(f *fakeRunner)Run(_ context.Context,path string,args ...string)(executor.Result,error){f.calls=append(f.calls,call{path:path,args:append([]string(nil),args...)});i:=len(f.calls)-1;if i<len(f.results){var err error;if i<len(f.errs){err=f.errs[i]};return f.results[i],err};return executor.Result{},errors.New("unexpected call")}
func goodRepo()string{return "enabled = 1\ngpgcheck = 1\nsslverify = 1\nbaseurl = https://mirror.example.invalid/repo\ngpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-test\n"}
func TestValidateRepoConfigAcceptsSignedHTTPSRepo(t *testing.T){if err:=validateRepoConfig("appstream",normalizeRepo(goodRepo()));err!=nil{t.Fatalf("valid repo rejected: %v",err)}}
func TestValidateRepoConfigRejectsNoGPG(t *testing.T){cfg:="enabled=1\ngpgcheck=0\nsslverify=1\nbaseurl=https://repo\ngpgkey=file:///key\n";if err:=validateRepoConfig("bad",normalizeRepo(cfg));err==nil{t.Fatal("expected gpgcheck rejection")}}
func TestValidateRepoConfigRejectsHTTP(t *testing.T){cfg:="enabled=1\ngpgcheck=1\nsslverify=1\nbaseurl=http://repo\ngpgkey=file:///key\n";if err:=validateRepoConfig("bad",normalizeRepo(cfg));err==nil{t.Fatal("expected insecure HTTP rejection")}}
func TestRepositoryDigestStableAcrossLineOrder(t *testing.T){a:=normalizeRepo("gpgcheck=1\nenabled=1\nsslverify=1\ngpgkey=file:///key\nbaseurl=https://repo\n");b:=normalizeRepo("baseurl=https://repo\nsslverify=1\ngpgkey=file:///key\nenabled=1\ngpgcheck=1\n");if a!=b{t.Fatal("normalized repository config is order-sensitive")}}
func TestResolveLatestFromReposUsesPinnedRepo(t *testing.T){f:=&fakeRunner{results:[]executor.Result{{Stdout:"nginx-1:1.24.0-1.el9.x86_64\n"}}};d:=DNF{Runner:f};got,err:=d.ResolveLatestFromRepos(context.Background(),"nginx",[]string{"appstream"});if err!=nil{t.Fatal(err)};if got!="nginx-1:1.24.0-1.el9.x86_64"{t.Fatalf("unexpected NEVRA %q",got)};want:=[]string{"-q","repoquery","--latest-limit","1","--qf","%{name}-%{epoch}:%{version}-%{release}.%{arch}","--repoid=appstream","nginx"};if !reflect.DeepEqual(f.calls[0].args,want){t.Fatalf("unexpected argv %#v",f.calls[0].args)}}
func TestInstallExactFromReposDisablesOtherRepos(t *testing.T){f:=&fakeRunner{results:[]executor.Result{{}}};d:=DNF{Runner:f};if err:=d.InstallExactFromRepos(context.Background(),[]string{"pgdg17"},"postgresql17-server-0:17.6-1PGDG.rhel9.x86_64");err!=nil{t.Fatal(err)};want:=[]string{"-y","--setopt=install_weak_deps=False","--disablerepo=*","--enablerepo=pgdg17","install","postgresql17-server-0:17.6-1PGDG.rhel9.x86_64"};if !reflect.DeepEqual(f.calls[0].args,want){t.Fatalf("unexpected argv %#v",f.calls[0].args)}}
func TestInstallRejectsUnsafeNEVRA(t *testing.T){d:=DNF{Runner:&fakeRunner{}};if err:=d.InstallExactFromRepos(context.Background(),[]string{"appstream"},"nginx;id");err==nil{t.Fatal("unsafe NEVRA accepted")}}
