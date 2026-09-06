package journal

import (
 "encoding/json"
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "regexp"
 "sort"
 "sync"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

var objectIDRE=regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)
type Store struct { root string; mu sync.Mutex }
func New(root string) (*Store,error) { if !filepath.IsAbs(root) { return nil,errors.New("journal root must be absolute") }; if err:=secureDir(root);err!=nil{return nil,err}; return &Store{root:root},nil }
func secureDir(path string) error { if fi,err:=os.Lstat(path);err==nil{if fi.Mode()&os.ModeSymlink!=0{return errors.New("journal directory may not be a symlink")};if !fi.IsDir(){return errors.New("journal path is not a directory")};if fi.Mode().Perm()&0022!=0{return errors.New("journal directory is group/world writable")};return nil}else if !errors.Is(err,os.ErrNotExist){return err};return os.MkdirAll(path,0700) }
func safeID(id string)error{if !objectIDRE.MatchString(id){return errors.New("journal object id must be a UUID")};return nil}
func (s *Store) objectPath(kind,id string)(string,error){if err:=safeID(id);err!=nil{return "",err};switch kind{case "operation":return filepath.Join(s.root,"operations",id+".json"),nil;case "service":return filepath.Join(s.root,"state","services",id+".json"),nil;case "plan":return filepath.Join(s.root,"plans",id+".json"),nil;default:return "",errors.New("unknown journal object kind")}}
func atomicJSON(path string, value any) error { dir:=filepath.Dir(path); if err:=secureDir(dir);err!=nil{return err};if fi,err:=os.Lstat(path);err==nil&&fi.Mode()&os.ModeSymlink!=0{return errors.New("refusing symlink target")};f,err:=os.CreateTemp(dir,".layersentry-*");if err!=nil{return err};tmp:=f.Name();defer os.Remove(tmp);if err=f.Chmod(0600);err!=nil{f.Close();return err};enc:=json.NewEncoder(f);enc.SetIndent("","  ");if err=enc.Encode(value);err!=nil{f.Close();return err};if err=f.Sync();err!=nil{f.Close();return err};if err=f.Close();err!=nil{return err};if err=os.Rename(tmp,path);err!=nil{return err};if d,err:=os.Open(dir);err==nil{_ = d.Sync();_ = d.Close()};return nil }
func readJSON[T any](path string)(T,error){var out T;fi,err:=os.Lstat(path);if err!=nil{return out,err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return out,errors.New("refusing unsafe journal object")};if fi.Size()>4<<20{return out,errors.New("journal object too large")};b,err:=os.ReadFile(path);if err!=nil{return out,err};if err=json.Unmarshal(b,&out);err!=nil{return out,err};return out,nil}
func (s *Store) Begin(op model.Operation)(model.Operation,error){s.mu.Lock();defer s.mu.Unlock();p,err:=s.objectPath("operation",op.ID);if err!=nil{return op,err};existing,err:=readJSON[model.Operation](p);if err==nil{if existing.RequestDigest!=op.RequestDigest||existing.IdempotencyKey!=op.IdempotencyKey{return existing,errors.New("operation UUID/idempotency collision")};return existing,nil};if !errors.Is(err,os.ErrNotExist){return op,err};now:=time.Now().UTC();op.CreatedAt=now;op.UpdatedAt=now;if op.Status==""{op.Status=model.OpRequested};return op,atomicJSON(p,op)}
func (s *Store) GetOperation(id string)(model.Operation,error){p,err:=s.objectPath("operation",id);if err!=nil{return model.Operation{},err};return readJSON[model.Operation](p)}
func (s *Store) SaveOperation(op model.Operation) error {s.mu.Lock();defer s.mu.Unlock();p,err:=s.objectPath("operation",op.ID);if err!=nil{return err};op.UpdatedAt=time.Now().UTC();return atomicJSON(p,op)}
func (s *Store) ListOperations()([]model.Operation,error){dir:=filepath.Join(s.root,"operations");entries,err:=os.ReadDir(dir);if errors.Is(err,os.ErrNotExist){return []model.Operation{},nil};if err!=nil{return nil,err};out:=make([]model.Operation,0,len(entries));for _,e:=range entries{if e.IsDir()||filepath.Ext(e.Name())!=".json"{continue};id:=e.Name()[:len(e.Name())-len(".json")];if safeID(id)!=nil{continue};op,err:=readJSON[model.Operation](filepath.Join(dir,e.Name()));if err!=nil{return nil,fmt.Errorf("read operation %s: %w",e.Name(),err)};out=append(out,op)};sort.Slice(out,func(i,j int)bool{return out[i].UpdatedAt.After(out[j].UpdatedAt)});return out,nil}
func (s *Store) SavePlan(p model.Plan) error {s.mu.Lock();defer s.mu.Unlock();path,err:=s.objectPath("plan",p.ID);if err!=nil{return err};return atomicJSON(path,p)}
func (s *Store) GetPlan(id string)(model.Plan,error){p,err:=s.objectPath("plan",id);if err!=nil{return model.Plan{},err};return readJSON[model.Plan](p)}
func (s *Store) SaveService(st model.ServiceState) error {s.mu.Lock();defer s.mu.Unlock();p,err:=s.objectPath("service",st.ID);if err!=nil{return err};st.UpdatedAt=time.Now().UTC();return atomicJSON(p,st)}
func (s *Store) GetService(id string)(model.ServiceState,error){p,err:=s.objectPath("service",id);if err!=nil{return model.ServiceState{},err};return readJSON[model.ServiceState](p)}
func (s *Store) ListServices()([]model.ServiceState,error){dir:=filepath.Join(s.root,"state","services");entries,err:=os.ReadDir(dir);if errors.Is(err,os.ErrNotExist){return []model.ServiceState{},nil};if err!=nil{return nil,err};out:=make([]model.ServiceState,0,len(entries));for _,e:=range entries{if e.IsDir()||filepath.Ext(e.Name())!=".json"{continue};id:=e.Name()[:len(e.Name())-len(".json")];if safeID(id)!=nil{continue};st,err:=readJSON[model.ServiceState](filepath.Join(dir,e.Name()));if err!=nil{return nil,fmt.Errorf("read service %s: %w",e.Name(),err)};out=append(out,st)};sort.Slice(out,func(i,j int)bool{return out[i].UpdatedAt.After(out[j].UpdatedAt)});return out,nil}
