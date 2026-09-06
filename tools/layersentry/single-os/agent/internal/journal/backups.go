package journal

import (
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "sort"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func (s *Store) backupPath(id string)(string,error){if err:=safeID(id);err!=nil{return "",err};return filepath.Join(s.root,"backups","catalog",id+".json"),nil}
func (s *Store) SaveBackup(b model.BackupRecord)error{s.mu.Lock();defer s.mu.Unlock();if err:=safeID(b.ID);err!=nil{return err};if err:=safeID(b.ServiceID);err!=nil{return errors.New("backup service id must be a UUID")};if !b.Verified||b.SHA256==""||b.SizeBytes<1{return errors.New("only verified non-empty backups may enter catalog")};p,err:=s.backupPath(b.ID);if err!=nil{return err};if _,err:=os.Lstat(p);err==nil{return errors.New("backup record already exists") }else if !errors.Is(err,os.ErrNotExist){return err};return atomicJSON(p,b)}
func (s *Store) GetBackup(id string)(model.BackupRecord,error){p,err:=s.backupPath(id);if err!=nil{return model.BackupRecord{},err};return readJSON[model.BackupRecord](p)}
func (s *Store) ListBackups(serviceID string)([]model.BackupRecord,error){if serviceID!=""{if err:=safeID(serviceID);err!=nil{return nil,err}};dir:=filepath.Join(s.root,"backups","catalog");entries,err:=os.ReadDir(dir);if errors.Is(err,os.ErrNotExist){return []model.BackupRecord{},nil};if err!=nil{return nil,err};out:=make([]model.BackupRecord,0,len(entries));for _,e:=range entries{if e.IsDir()||filepath.Ext(e.Name())!=".json"{continue};id:=e.Name()[:len(e.Name())-len(".json")];if safeID(id)!=nil{continue};b,err:=readJSON[model.BackupRecord](filepath.Join(dir,e.Name()));if err!=nil{return nil,fmt.Errorf("read backup %s: %w",e.Name(),err)};if serviceID==""||b.ServiceID==serviceID{out=append(out,b)}};sort.Slice(out,func(i,j int)bool{return out[i].CreatedAt.After(out[j].CreatedAt)});return out,nil}
