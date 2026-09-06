package storage

import (
 "context"
 "encoding/json"
 "errors"
 "os"
 "path/filepath"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
)

type Device struct{Path string `json:"path"`;StableIDs []string `json:"stable_ids"`;Type string `json:"type"`;Size uint64 `json:"size_bytes"`;Filesystem string `json:"filesystem,omitempty"`;Mountpoints []string `json:"mountpoints,omitempty"`;Parent string `json:"parent,omitempty"`}
type lsblk struct{Blockdevices []struct{Name string `json:"name"`;Path string `json:"path"`;Type string `json:"type"`;Size uint64 `json:"size"`;Fstype string `json:"fstype"`;Mountpoints []any `json:"mountpoints"`;Pkname *string `json:"pkname"`} `json:"blockdevices"`}
func Discover(ctx context.Context,r executor.Runner)([]Device,error){res,err:=r.Run(ctx,"/usr/bin/lsblk","--json","--bytes","--paths","--output","NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,PKNAME");if err!=nil{return nil,err};var raw lsblk;if err=json.Unmarshal([]byte(res.Stdout),&raw);err!=nil{return nil,err};ids:=stableIDs();out:=make([]Device,0,len(raw.Blockdevices));for _,d:=range raw.Blockdevices{if d.Type!="disk"&&d.Type!="part"&&d.Type!="lvm"{continue};dev:=Device{Path:d.Path,StableIDs:ids[real(d.Path)],Type:d.Type,Size:d.Size,Filesystem:d.Fstype};if d.Pkname!=nil{dev.Parent=*d.Pkname};for _,m:=range d.Mountpoints{if s,ok:=m.(string);ok&&s!=""{dev.Mountpoints=append(dev.Mountpoints,s)}};out=append(out,dev)};return out,nil}
func stableIDs()map[string][]string{out:=map[string][]string{};entries,err:=os.ReadDir("/dev/disk/by-id");if err!=nil{return out};for _,e:=range entries{if e.IsDir()||strings.HasPrefix(e.Name(),"wwn-")==false&&strings.HasPrefix(e.Name(),"scsi-")==false&&strings.HasPrefix(e.Name(),"nvme-")==false&&strings.HasPrefix(e.Name(),"virtio-")==false{continue};p:=filepath.Join("/dev/disk/by-id",e.Name());r,err:=filepath.EvalSymlinks(p);if err==nil{out[r]=append(out[r],p)}};return out}
func real(p string)string{r,err:=filepath.EvalSymlinks(p);if err!=nil{return p};return r}
func ResolveStableID(path string)(string,error){if !strings.HasPrefix(path,"/dev/disk/by-"){return "",errors.New("stable /dev/disk/by-* path required")};r,err:=filepath.EvalSymlinks(path);if err!=nil{return "",err};fi,err:=os.Stat(r);if err!=nil{return "",err};if fi.Mode()&os.ModeDevice==0{return "",errors.New("not a block device")};return r,nil}
