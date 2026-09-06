package secrets

import (
    "os"
    "path/filepath"
    "strings"
    "testing"
)

func openTestStore(t *testing.T)*Store{t.Helper();root:=filepath.Join(t.TempDir(),"secrets");key:=filepath.Join(t.TempDir(),"identity","secret.key");s,err:=Open(root,key);if err!=nil{t.Fatal(err)};return s}
func TestPutGetRoundTrip(t *testing.T){s:=openTestStore(t);ref,err:=s.Put([]byte("super-secret-value"));if err!=nil{t.Fatal(err)};if !strings.HasPrefix(ref,"secret://")||len(strings.TrimPrefix(ref,"secret://"))!=32{t.Fatalf("bad ref %q",ref)};got,err:=s.Get(ref);if err!=nil{t.Fatal(err)};if string(got)!="super-secret-value"{t.Fatal("secret round trip mismatch")}}
func TestCiphertextDoesNotContainPlaintext(t *testing.T){s:=openTestStore(t);plain:=[]byte("do-not-persist-me");ref,err:=s.Put(plain);if err!=nil{t.Fatal(err)};id:=strings.TrimPrefix(ref,"secret://");b,err:=os.ReadFile(filepath.Join(s.root,id+".bin"));if err!=nil{t.Fatal(err)};if strings.Contains(string(b),string(plain)){t.Fatal("plaintext found in ciphertext file")}}
func TestGetRejectsMalformedReference(t *testing.T){s:=openTestStore(t);if _,err:=s.Get("secret://../../etc/passwd");err==nil{t.Fatal("expected malformed reference rejection")}}
func TestOpenRejectsSymlinkKey(t *testing.T){base:=t.TempDir();root:=filepath.Join(base,"secrets");identity:=filepath.Join(base,"identity");if err:=os.MkdirAll(identity,0700);err!=nil{t.Fatal(err)};victim:=filepath.Join(base,"victim");if err:=os.WriteFile(victim,make([]byte,32),0600);err!=nil{t.Fatal(err)};key:=filepath.Join(identity,"secret.key");if err:=os.Symlink(victim,key);err!=nil{t.Fatal(err)};if _,err:=Open(root,key);err==nil{t.Fatal("expected symlink key rejection")}}
func TestPutRejectsEmptyAndOversized(t *testing.T){s:=openTestStore(t);if _,err:=s.Put(nil);err==nil{t.Fatal("empty secret accepted")};if _,err:=s.Put(make([]byte,(1<<20)+1));err==nil{t.Fatal("oversized secret accepted")}}
