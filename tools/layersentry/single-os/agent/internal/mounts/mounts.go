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
func(m Manager)Prepare(ctx context.Context,items []model.StorageAssignment)error{for _,s:=range items{if err:=m.prepareOne(ctx,s,true);err!=nil{return err}};return nil}
// EnsureMounted is for repair/recovery only. It never formats a device. If a
// confirmed-format step did not complete far enough to create the expected
// filesystem, recovery stops and requires a new explicit destructive plan.
func(m Manager)EnsureMounted(ctx context.Context,items []model.StorageAssignment)error{for _,s:=range items{if err:=m.prepareOne(ctx,s,false);err!=nil{return err}};return nil}
func(m Manager)prepareOne(ctx context.Context,s model.StorageAssignment,allowFormat bool)error{real,err:=filepath.EvalSymlinks(s.Device);if err!=nil{return err};fi,err:=os.Stat(real);if err!=nil{return err};if fi.Mode()&os.ModeDevice==0{return errors.New("storage target is not a device")}
 if s.Format&&allowFormat{if !s.ConfirmFormat{return errors.New("format was not explicitly confirmed")};switch s.Filesystem{case "xfs":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.xfs","-f",s.Device);case "ext4":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.ext4","-F",s.Device);default:return errors.New("unsupported filesystem")};if err!=nil{return err}}
 if !allowFormat{current,fsErr:=m.fstype(ctx,s.Device);if fsErr!=nil{return fsErr};if current==""{if s.Format{return errors.New("recovery cannot prove that the confirmed format completed; refusing to format again")};return errors.New("storage device has no filesystem during recovery")};if s.Filesystem!=""&&current!=s.Filesystem{return fmt.Errorf("recovery filesystem mismatch: plan=%s observed=%s",s.Filesystem,current)}}
 if err=os.MkdirAll(s.MountPoint,0750);err!=nil{return err};uuid,err:=m.uuid(ctx,s.Device);if err!=nil{return err};if err=ensureFstab(uuid,s.MountPoint,s.Filesystem);err!=nil{return err};mounted,err:=m.mountedUUID(ctx,s.MountPoint);if err==nil&&mounted!=""{if mounted!=uuid{return fmt.Errorf("mount point %s is already mounted from a different filesystem UUID",s.MountPoint)};return m.verify(ctx,s.MountPoint)};if err!=nil&&!isNotMounted(err){return err};if _,err=m.Runner.Run(ctx,"/usr/bin/mount",s.MountPoint);err!=nil{return err};return m.verify(ctx,s.MountPoint)}
func(m Manager)uuid(ctx context.Context,dev string)(string,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/blkid","-s","UUID","-o","value",dev);if err!=nil{return "",err};v:=strings.TrimSpace(r.Stdout);if v==""||strings.ContainsAny(v," \t\n/"){return "",errors.New("invalid filesystem UUID")};return v,nil}
func(m Manager)fstype(ctx context.Context,dev string)(string,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/blkid","-s","TYPE","-o","value",dev);if err!=nil{if r.ExitCode==2{return "",nil};return "",err};v:=strings.TrimSpace(r.Stdout);if v==""{return "",nil};if v!="xfs"&&v!="ext4"{return "",fmt.Errorf("unsupported observed filesystem %q",v)};return v,nil}
func(m Manager)mountedUUID(ctx context.Context,mount string)(string,error){r,err:=m.Runner.Run(ctx,"/usr/bin/findmnt","-nro","UUID","--target",mount);if err!=nil{return "",err};v:=strings.TrimSpace(r.Stdout);if v==""||strings.ContainsAny(v," \t\n/"){return "",errors.New("invalid mounted filesystem UUID")};return v,nil}
func(m Manager)verify(ctx context.Context,mount string)error{_,err:=m.Runner.Run(ctx,"/usr/bin/findmnt","--verify","--target",mount);return err}
func isNotMounted(err error)bool{return err!=nil}
func ensureFstab(uuid,mount,fsys string)error{if fsys==""{fsys="auto"};line:=fmt.Sprintf("UUID=%s %s %s defaults,nofail 0 2",uuid,mount,fsys);fi,err:=os.Lstat("/etc/fstab");if err!=nil{return err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("refusing unsafe /etc/fstab")};if fi.Mode().Perm()&0022!=0{return errors.New("/etc/fstab may not be group/world writable")};old,err:=os.ReadFile("/etc/fstab");if err!=nil{return err};sc:=bufio.NewScanner(bytes.NewReader(old));for sc.Scan(){fields:=strings.Fields(sc.Text());if len(fields)>=2&&fields[1]==mount{if strings.TrimSpace(sc.Text())==line{return nil};return fmt.Errorf("fstab mount point %s already owned by different source",mount)}};if err=sc.Err();err!=nil{return err};next:=append(append([]byte{},old...),[]byte("\n"+line+"\n")...);return filesystem.AtomicWrite("/etc/fstab",next,0644,"/etc")}
