package privileged

import "testing"

func TestDNFRejectsNoGPGCheck(t *testing.T){if err:=validateDNF([]string{"-y","--nogpgcheck","install","nginx"});err==nil{t.Fatal("expected --nogpgcheck rejection")}}
func TestDNFRejectsRuntimeRepositoryURL(t *testing.T){if err:=validateDNF([]string{"-y","--repofrompath=x,https://example.invalid/repo","install","nginx"});err==nil{t.Fatal("expected runtime repository rejection")}}
func TestDNFRejectsInstallWithoutExplicitRepo(t *testing.T){if err:=validateDNF([]string{"-y","--setopt=install_weak_deps=False","install","nginx-1:1.24.0-1.el9.x86_64"});err==nil{t.Fatal("expected implicit repository rejection")}}
func TestDNFAcceptsPinnedInstallShape(t *testing.T){if err:=validateDNF([]string{"-y","--setopt=install_weak_deps=False","--disablerepo=*","--enablerepo=appstream","install","nginx-1:1.24.0-1.el9.x86_64"});err!=nil{t.Fatalf("safe install rejected: %v",err)}}
func TestDNFRejectsPackageRepoMismatch(t *testing.T){if err:=validateDNF([]string{"-y","--setopt=install_weak_deps=False","--disablerepo=*","--enablerepo=appstream","install","postgresql17-server-0:17.6-1PGDG.rhel9.x86_64"});err==nil{t.Fatal("expected package/repository mismatch rejection")}}
func TestSystemctlRejectsForeignUnit(t *testing.T){if err:=validateSystemctl([]string{"restart","sshd.service"});err==nil{t.Fatal("expected foreign unit rejection")}}
func TestSystemctlAllowsProviderUnit(t *testing.T){if err:=validateSystemctl([]string{"enable","--now","nginx.service"});err!=nil{t.Fatalf("provider unit rejected: %v",err)}}
func TestFirewallRejectsGlobalSource(t *testing.T){if err:=validateFirewall([]string{"--permanent","--zone=ls-0123456789ab","--add-source=not-a-cidr"});err==nil{t.Fatal("expected invalid CIDR rejection")}}
func TestFirewallAcceptsOwnedZone(t *testing.T){if err:=validateFirewall([]string{"--permanent","--zone=ls-0123456789ab","--add-source=10.0.0.0/24","--add-port=5432/tcp"});err!=nil{t.Fatalf("owned firewall rule rejected: %v",err)}}
func TestMkfsRequiresStableDevice(t *testing.T){if err:=validateMkfs([]string{"-f","/dev/sdb"},"-f");err==nil{t.Fatal("expected unstable disk rejection")}}
func TestMountRejectsEtc(t *testing.T){if err:=validateMount([]string{"/etc"});err==nil{t.Fatal("expected unsafe mount rejection")}}
func TestRunuserRejectsArbitraryExecutable(t *testing.T){if err:=validateRunuserPostgres([]string{"-u","postgres","--","/bin/sh","-c","id"});err==nil{t.Fatal("expected arbitrary runuser rejection")}}
func TestPostgresPSQLRejectsArbitrarySQL(t *testing.T){if err:=validatePostgresArgs("/usr/pgsql-17/bin/psql",[]string{"-c","DROP DATABASE customer"});err==nil{t.Fatal("expected arbitrary SQL rejection")}}
func TestPostgresRestoreRequiresExactCatalogPath(t *testing.T){args:=[]string{"-X","-v","ON_ERROR_STOP=1","-p","5432","-d","postgres","--file=/tmp/backup.sql"};if err:=validatePostgresArgs("/usr/pgsql-17/bin/psql",args);err==nil{t.Fatal("expected non-catalog restore path rejection")}}
func TestActionForRejectsShell(t *testing.T){if _,err:=actionFor("/bin/sh",[]string{"-c","id"});err==nil{t.Fatal("expected shell rejection")}}
