package mounts

import (
 "bufio"
 "bytes"
 "context"
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Manager struct{Runner executor.Runner}
func(m Manager)Prepare(ctx context.Context,items []model.StorageAssignment)error{for _,s:=range items{if err:=m.prepareOne(ctx,s);err!=nil{return err}};return nil}
func(m Manager)prepareOne(ctx context.Context,s model.StorageAssignment)error{real,err:=filepath.EvalSymlinks(s.Device);if err!=nil{return err};fi,err:=os.Stat(real);if err!=nil{return err};if fi.Mode()&os.ModeDevice==0{return errors.New("storage target is not a device")};if s.Format{if !s.ConfirmFormat{return errors.New("format was not explicitly confirmed")};switch s.Filesystem{case "xfs":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.xfs","-f",s.Device);case "ext4":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.ext4","-F",s.Device);default:return errors.New("unsupported filesystem")};if err!=nil{return err}};if err=os.MkdirAll(s.MountPoint,0750);err!=nil{return err};uuid,err:=m.uuid(ctx,s.Device);if err!=nil{return err};if err=ensureFstab(uuid,s.MountPoint,s.Filesystem);err!=nil{return err};_,err=m.Runner.Run(ctx,"/usr/bin/mount",s.MountPoint);if err!=nil{return err};_,err=m.Runner.Run(ctx,"/usr/bin/findmnt","--verify","--target",s.MountPoint);return err}
func(m Manager)uuid(ctx context.Context,dev string)(string,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/blkid","-s","UUID","-o","value",dev);if err!=nil{return "",err};v:=strings.TrimSpace(r.Stdout);if v==""||strings.ContainsAny(v," \t\n/"){return "",errors.New("invalid filesystem UUID")};return v,nil}
func ensureFstab(uuid,mount,fsys string)error{if fsys==""{fsys="auto"};line:=fmt.Sprintf("UUID=%s %s %s defaults,nofail 0 2",uuid,mount,fsys);fi,err:=os.Lstat("/etc/fstab");if err!=nil{return err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("refusing unsafe /etc/fstab")};if fi.Mode().Perm()&0022!=0{return errors.New("/etc/fstab may not be group/world writable")};old,err:=os.ReadFile("/etc/fstab");if err!=nil{return err};sc:=bufio.NewScanner(bytes.NewReader(old));for sc.Scan(){fields:=strings.Fields(sc.Text());if len(fields)>=2&&fields[1]==mount{if strings.TrimSpace(sc.Text())==line{return nil};return fmt.Errorf("fstab mount point %s already owned by different source",mount)}};if err=sc.Err();err!=nil{return err};next:=append(append([]byte{},old...),[]byte("\n"+line+"\n")...);return filesystem.AtomicWrite("/etc/fstab",next,0644,"/etc")}
