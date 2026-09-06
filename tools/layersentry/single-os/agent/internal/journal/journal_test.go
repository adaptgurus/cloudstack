package journal

import (
    "errors"
    "os"
    "path/filepath"
    "testing"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func newTestStore(t *testing.T)*Store{t.Helper();root:=t.TempDir();if err:=os.Chmod(root,0700);err!=nil{t.Fatal(err)};s,err:=New(root);if err!=nil{t.Fatal(err)};return s}
func TestBeginIsIdempotentForSameDigest(t *testing.T){s:=newTestStore(t);op:=model.Operation{ID:"11111111-1111-4111-8111-111111111111",ServiceID:"22222222-2222-4222-8222-222222222222",IdempotencyKey:"key",RequestDigest:"abc"};first,err:=s.Begin(op);if err!=nil{t.Fatal(err)};second,err:=s.Begin(op);if err!=nil{t.Fatal(err)};if first.ID!=second.ID||first.CreatedAt!=second.CreatedAt{t.Fatal("idempotent begin did not return existing operation")}}
func TestBeginRejectsOperationCollision(t *testing.T){s:=newTestStore(t);op:=model.Operation{ID:"11111111-1111-4111-8111-111111111111",ServiceID:"22222222-2222-4222-8222-222222222222",IdempotencyKey:"key",RequestDigest:"abc"};if _,err:=s.Begin(op);err!=nil{t.Fatal(err)};op.RequestDigest="changed";if _,err:=s.Begin(op);err==nil{t.Fatal("expected operation digest collision")}}
func TestAtomicJSONRejectsSymlinkTarget(t *testing.T){s:=newTestStore(t);dir:=filepath.Join(s.root,"operations");if err:=os.MkdirAll(dir,0700);err!=nil{t.Fatal(err)};target:=filepath.Join(t.TempDir(),"victim");if err:=os.WriteFile(target,[]byte("safe"),0600);err!=nil{t.Fatal(err)};link:=s.operationPath("11111111-1111-4111-8111-111111111111");if err:=os.Symlink(target,link);err!=nil{t.Fatal(err)};err:=s.SaveOperation(model.Operation{ID:"11111111-1111-4111-8111-111111111111"});if err==nil{t.Fatal("expected symlink rejection")};b,_:=os.ReadFile(target);if string(b)!="safe"{t.Fatal("symlink target was modified")}}
func TestNewRejectsWorldWritableRoot(t *testing.T){root:=t.TempDir();if err:=os.Chmod(root,0777);err!=nil{t.Fatal(err)};_,err:=New(root);if err==nil{t.Fatal("expected world-writable root rejection")};if !errors.Is(err,os.ErrPermission)&&err.Error()==""{t.Fatal("expected descriptive error")}}
func TestServiceRoundTripDoesNotRequireExternalDatabase(t *testing.T){s:=newTestStore(t);st:=model.ServiceState{ID:"22222222-2222-4222-8222-222222222222",Provider:"nginx",Category:model.CategoryApplication,ReleaseLine:"rocky9",Status:"installed"};if err:=s.SaveService(st);err!=nil{t.Fatal(err)};got,err:=s.GetService(st.ID);if err!=nil{t.Fatal(err)};if got.Provider!=st.Provider||got.Status!=st.Status{t.Fatalf("unexpected round-trip: %+v",got)}}
