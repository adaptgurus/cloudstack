package journal

import (
 "encoding/json"
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "sync"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Store struct { root string; mu sync.Mutex }

func New(root string) (*Store,error) {
 if !filepath.IsAbs(root) { return nil,errors.New("journal root must be absolute") }
 if err:=os.MkdirAll(root,0700); err!=nil{return nil,err}
 return &Store{root:root},nil
}

func (s *Store) operationPath(id string) string { return filepath.Join(s.root,"operations",id+".json") }
func (s *Store) servicePath(id string) string { return filepath.Join(s.root,"state","services",id+".json") }
func (s *Store) planPath(id string) string { return filepath.Join(s.root,"plans",id+".json") }

func atomicJSON(path string, value any) error {
 dir:=filepath.Dir(path); if err:=os.MkdirAll(dir,0700);err!=nil{return err}
 if fi,err:=os.Lstat(path); err==nil && fi.Mode()&os.ModeSymlink!=0 { return errors.New("refusing symlink target") }
 f,err:=os.CreateTemp(dir,".layersentry-*"); if err!=nil{return err}
 tmp:=f.Name(); defer os.Remove(tmp)
 if err=f.Chmod(0600);err!=nil{f.Close();return err}
 enc:=json.NewEncoder(f); enc.SetIndent("","  ")
 if err=enc.Encode(value);err!=nil{f.Close();return err}
 if err=f.Sync();err!=nil{f.Close();return err}
 if err=f.Close();err!=nil{return err}
 if err=os.Rename(tmp,path);err!=nil{return err}
 if d,err:=os.Open(dir);err==nil{_ = d.Sync(); _ = d.Close()}
 return nil
}

func readJSON[T any](path string)(T,error){
 var out T
 fi,err:=os.Lstat(path); if err!=nil{return out,err}; if fi.Mode()&os.ModeSymlink!=0{return out,errors.New("refusing symlink")}; if fi.Size()>4<<20{return out,errors.New("journal object too large")}
 b,err:=os.ReadFile(path); if err!=nil{return out,err}; if err=json.Unmarshal(b,&out);err!=nil{return out,err}; return out,nil
}

func (s *Store) Begin(op model.Operation)(model.Operation,error){
 s.mu.Lock(); defer s.mu.Unlock(); p:=s.operationPath(op.ID)
 existing,err:=readJSON[model.Operation](p)
 if err==nil { if existing.RequestDigest!=op.RequestDigest || existing.IdempotencyKey!=op.IdempotencyKey{return existing,errors.New("operation UUID/idempotency collision")}; return existing,nil }
 if !errors.Is(err,os.ErrNotExist){return op,err}
 now:=time.Now().UTC(); op.CreatedAt=now;op.UpdatedAt=now; if op.Status==""{op.Status=model.OpRequested}
 return op,atomicJSON(p,op)
}

func (s *Store) GetOperation(id string)(model.Operation,error){return readJSON[model.Operation](s.operationPath(id))}
func (s *Store) SaveOperation(op model.Operation) error { s.mu.Lock();defer s.mu.Unlock();op.UpdatedAt=time.Now().UTC();return atomicJSON(s.operationPath(op.ID),op) }
func (s *Store) SavePlan(p model.Plan) error {s.mu.Lock();defer s.mu.Unlock();return atomicJSON(s.planPath(p.ID),p)}
func (s *Store) GetPlan(id string)(model.Plan,error){return readJSON[model.Plan](s.planPath(id))}
func (s *Store) SaveService(st model.ServiceState) error {s.mu.Lock();defer s.mu.Unlock();st.UpdatedAt=time.Now().UTC();return atomicJSON(s.servicePath(st.ID),st)}
func (s *Store) GetService(id string)(model.ServiceState,error){return readJSON[model.ServiceState](s.servicePath(id))}
func (s *Store) ListServices()([]model.ServiceState,error){
 dir:=filepath.Join(s.root,"state","services"); entries,err:=os.ReadDir(dir);if errors.Is(err,os.ErrNotExist){return []model.ServiceState{},nil};if err!=nil{return nil,err}
 out:=make([]model.ServiceState,0,len(entries));for _,e:=range entries{if e.IsDir()||filepath.Ext(e.Name())!=".json"{continue};st,err:=readJSON[model.ServiceState](filepath.Join(dir,e.Name()));if err!=nil{return nil,fmt.Errorf("read service %s: %w",e.Name(),err)};out=append(out,st)};return out,nil
}
