package bootstrap

import (
    "net"
    "os"
    "path/filepath"
    "testing"
)

func testPaths(root string) Paths { identity:=filepath.Join(root,"identity");return Paths{Root:root,NodeID:filepath.Join(identity,"node-id"),BootstrapToken:filepath.Join(identity,"bootstrap-token"),TLSCert:filepath.Join(identity,"tls.crt"),TLSKey:filepath.Join(identity,"tls.key")} }
func TestEnsureCreatesUniqueCloneIdentity(t *testing.T){a:=testPaths(filepath.Join(t.TempDir(),"a"));b:=testPaths(filepath.Join(t.TempDir(),"b"));if err:=Ensure(a,[]net.IP{net.ParseIP("127.0.0.1")});err!=nil{t.Fatal(err)};if err:=Ensure(b,[]net.IP{net.ParseIP("127.0.0.1")});err!=nil{t.Fatal(err)};aid,_:=os.ReadFile(a.NodeID);bid,_:=os.ReadFile(b.NodeID);if string(aid)==string(bid){t.Fatal("clones received identical node identity")};at,_:=os.ReadFile(a.BootstrapToken);bt,_:=os.ReadFile(b.BootstrapToken);if string(at)==string(bt){t.Fatal("clones received identical bootstrap token")}}
func TestEnsureIsIdempotentForSameNode(t *testing.T){p:=testPaths(t.TempDir());if err:=Ensure(p,nil);err!=nil{t.Fatal(err)};before,_:=os.ReadFile(p.NodeID);if err:=Ensure(p,nil);err!=nil{t.Fatal(err)};after,_:=os.ReadFile(p.NodeID);if string(before)!=string(after){t.Fatal("firstboot identity changed on rerun")}}
func TestEnsureRejectsSymlinkIdentity(t *testing.T){p:=testPaths(t.TempDir());if err:=os.MkdirAll(filepath.Dir(p.NodeID),0700);err!=nil{t.Fatal(err)};victim:=filepath.Join(t.TempDir(),"victim");_ = os.WriteFile(victim,[]byte("safe"),0600);if err:=os.Symlink(victim,p.NodeID);err!=nil{t.Fatal(err)};if err:=Ensure(p,nil);err==nil{t.Fatal("expected symlink identity rejection")}}
func TestSealRefusesCustomerState(t *testing.T){p:=testPaths(t.TempDir());if err:=Ensure(p,nil);err!=nil{t.Fatal(err)};svc:=filepath.Join(p.Root,"state","services");if err:=os.MkdirAll(svc,0700);err!=nil{t.Fatal(err)};if err:=os.WriteFile(filepath.Join(svc,"service.json"),[]byte("{}"),0600);err!=nil{t.Fatal(err)};if err:=Seal(p);err==nil{t.Fatal("seal should refuse customer lifecycle state")}}
func TestSealRemovesCloneIdentityWhenClean(t *testing.T){p:=testPaths(t.TempDir());if err:=Ensure(p,nil);err!=nil{t.Fatal(err)};if err:=Seal(p);err!=nil{t.Fatal(err)};for _,path:=range []string{p.NodeID,p.BootstrapToken,p.TLSCert,p.TLSKey}{if _,err:=os.Lstat(path);!os.IsNotExist(err){t.Fatalf("identity survived seal: %s",path)}}}
