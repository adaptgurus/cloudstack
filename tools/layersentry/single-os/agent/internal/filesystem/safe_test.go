package filesystem

import (
    "os"
    "path/filepath"
    "testing"
)

func TestEnsureUnderRejectsTraversal(t *testing.T){root:=t.TempDir();if _,err:=EnsureUnder(filepath.Join(root,"..","escape"),root);err==nil{t.Fatal("expected traversal rejection")}}
func TestAtomicWriteRoundTrip(t *testing.T){root:=t.TempDir();path:=filepath.Join(root,"state.json");if err:=AtomicWrite(path,[]byte("safe"),0600,root);err!=nil{t.Fatal(err)};b,err:=os.ReadFile(path);if err!=nil||string(b)!="safe"{t.Fatalf("unexpected write: %q %v",b,err)}}
func TestAtomicWriteRejectsSymlinkTarget(t *testing.T){root:=t.TempDir();victim:=filepath.Join(root,"victim");if err:=os.WriteFile(victim,[]byte("safe"),0600);err!=nil{t.Fatal(err)};link:=filepath.Join(root,"link");if err:=os.Symlink(victim,link);err!=nil{t.Fatal(err)};if err:=AtomicWrite(link,[]byte("changed"),0600,root);err==nil{t.Fatal("expected target symlink rejection")};b,_:=os.ReadFile(victim);if string(b)!="safe"{t.Fatal("victim changed")}}
func TestAtomicWriteRejectsSymlinkParent(t *testing.T){root:=t.TempDir();real:=filepath.Join(root,"real");if err:=os.Mkdir(real,0700);err!=nil{t.Fatal(err)};link:=filepath.Join(root,"link");if err:=os.Symlink(real,link);err!=nil{t.Fatal(err)};if err:=AtomicWrite(filepath.Join(link,"file"),[]byte("x"),0600,root);err==nil{t.Fatal("expected parent symlink rejection")}}
func TestAtomicWriteRejectsOutsideRoot(t *testing.T){root:=t.TempDir();outside:=filepath.Join(t.TempDir(),"file");if err:=AtomicWrite(outside,[]byte("x"),0600,root);err==nil{t.Fatal("expected outside-root rejection")}}
