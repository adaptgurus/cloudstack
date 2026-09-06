package journal

import (
    "errors"
    "os"
    "path/filepath"
    "strings"
)

func (s *Store) PruneBackups(serviceID string,retention int)error{if err:=safeID(serviceID);err!=nil{return err};if retention<1{return errors.New("backup retention must be >=1")};items,err:=s.ListBackups(serviceID);if err!=nil{return err};if len(items)<=retention{return nil};root:=filepath.Join(s.root,"backups",serviceID);for _,b:=range items[retention:]{clean:=filepath.Clean(b.Path);rel,err:=filepath.Rel(root,clean);if err!=nil||rel==".."||strings.HasPrefix(rel,".."+string(filepath.Separator)){return errors.New("backup catalog path escaped service backup root")};fi,err:=os.Lstat(clean);if err==nil{if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("refusing to prune unsafe backup object")};if err=os.Remove(clean);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};sidecar:=clean+".sha256";if fi,err:=os.Lstat(sidecar);err==nil{if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("refusing unsafe backup checksum object")};if err=os.Remove(sidecar);err!=nil{return err}}else if !errors.Is(err,os.ErrNotExist){return err};catalog,err:=s.backupPath(b.ID);if err!=nil{return err};if err=os.Remove(catalog);err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};return nil}
