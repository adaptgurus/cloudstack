package lvm

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "regexp"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/mounts"
)

var uuidRE=regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)

type Manager struct{Runner executor.Runner;StateRoot string}
type ownership struct{ServiceID string `json:"service_id"`;VG string `json:"vg"`;Devices []string `json:"devices"`;CreatedAt time.Time `json:"created_at"`}

func(m Manager)Prepare(ctx context.Context,serviceID string,groups []model.LVMVolumeGroup)error{
    if len(groups)==0{return nil};if m.Runner==nil{return errors.New("LVM executor unavailable")};if !uuidRE.MatchString(serviceID){return errors.New("invalid service id for LVM ownership")};if m.StateRoot==""{m.StateRoot="/var/lib/layersentryd/state/lvm"};if err:=os.MkdirAll(m.StateRoot,0700);err!=nil{return err}
    for _,g:=range groups{if err:=m.prepareGroup(ctx,serviceID,g);err!=nil{return fmt.Errorf("LVM group %s: %w",g.Name,err)}};return nil
}
func(m Manager)prepareGroup(ctx context.Context,serviceID string,g model.LVMVolumeGroup)error{
    marker:=filepath.Join(m.StateRoot,g.Name+".json");rec,exists,err:=readOwnership(marker);if err!=nil{return err};vgExists,err:=m.vgExists(ctx,g.Name);if err!=nil{return err}
    if exists{if rec.ServiceID!=serviceID||rec.VG!=g.Name||!sameStrings(rec.Devices,g.Devices){return errors.New("existing LayerSentry LVM ownership does not match requested service/devices")}}
    if vgExists&&!exists{return errors.New("refusing to adopt pre-existing unowned volume group")}
    if !exists{raw,_:=json.MarshalIndent(ownership{ServiceID:serviceID,VG:g.Name,Devices:append([]string{},g.Devices...),CreatedAt:time.Now().UTC()},"","  ");if err=filesystem.AtomicWrite(marker,append(raw,'\n'),0600,m.StateRoot);err!=nil{return err}}
    for _,dev:=range g.Devices{vg,known,err:=m.pvVG(ctx,dev);if err!=nil{return err};if !known{if !g.InitializePVs||!g.ConfirmPVInitialize{return fmt.Errorf("device %s is not an LVM PV and PV initialization was not explicitly confirmed",dev)};if _,err=m.Runner.Run(ctx,"/usr/sbin/pvcreate","-y",dev);err!=nil{return err};vg=""}else if vg!=""&&vg!=g.Name{return fmt.Errorf("device %s belongs to foreign volume group %s",dev,vg)}}
    if !vgExists{args:=append([]string{g.Name},g.Devices...);if _,err=m.Runner.Run(ctx,"/usr/sbin/vgcreate",args...);err!=nil{return err}}else{for _,dev:=range g.Devices{vg,_,err:=m.pvVG(ctx,dev);if err!=nil{return err};if vg==""{if _,err=m.Runner.Run(ctx,"/usr/sbin/vgextend",g.Name,dev);err!=nil{return err}}}}
    for _,lv:=range g.LogicalVolumes{if err=m.prepareLV(ctx,g.Name,lv);err!=nil{return err}}
    return nil
}
func(m Manager)prepareLV(ctx,vg string,lv model.LVMLogicalVolume)error{
    dev:=filepath.Join("/dev",vg,lv.Name);exists,err:=m.lvExists(ctx,dev);if err!=nil{return err};if !exists{var args []string;if lv.Size=="100%FREE"{args=[]string{"-y","-n",lv.Name,"-l","100%FREE",vg}}else{args=[]string{"-y","-n",lv.Name,"-L",lv.Size,vg}};if _,err=m.Runner.Run(ctx,"/usr/sbin/lvcreate",args...);err!=nil{return err}}
    fs,err:=m.fstype(ctx,dev);if err!=nil{return err};if fs==""{if !lv.Format||!lv.ConfirmFormat{return errors.New("logical volume has no filesystem and format was not explicitly confirmed")};switch lv.Filesystem{case "xfs":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.xfs","-f",dev);case "ext4":_,err=m.Runner.Run(ctx,"/usr/sbin/mkfs.ext4","-F",dev);default:return errors.New("LVM filesystem must be xfs or ext4")};if err!=nil{return err}}else if lv.Filesystem!=""&&fs!=lv.Filesystem{return fmt.Errorf("logical volume filesystem mismatch: expected %s observed %s",lv.Filesystem,fs)}
    assignment:=model.StorageAssignment{Device:dev,MountPoint:lv.MountPoint,Purpose:lv.Purpose,Filesystem:lv.Filesystem,Format:false,ConfirmFormat:false};return (mounts.Manager{Runner:m.Runner}).Prepare(ctx,[]model.StorageAssignment{assignment})
}
func(m Manager)vgExists(ctx context.Context,name string)(bool,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/vgs","--noheadings","-o","vg_name",name);if err!=nil{if r.ExitCode==5{return false,nil};return false,err};return strings.TrimSpace(r.Stdout)==name,nil}
func(m Manager)lvExists(ctx context.Context,path string)(bool,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/lvs","--noheadings","-o","lv_name",path);if err!=nil{if r.ExitCode==5{return false,nil};return false,err};return strings.TrimSpace(r.Stdout)!="",nil}
func(m Manager)pvVG(ctx context.Context,dev string)(string,bool,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/pvs","--noheadings","-o","vg_name",dev);if err!=nil{if r.ExitCode==5{return "",false,nil};return "",false,err};return strings.TrimSpace(r.Stdout),true,nil}
func(m Manager)fstype(ctx context.Context,dev string)(string,error){r,err:=m.Runner.Run(ctx,"/usr/sbin/blkid","-s","TYPE","-o","value",dev);if err!=nil{if r.ExitCode==2{return "",nil};return "",err};return strings.TrimSpace(r.Stdout),nil}
func readOwnership(path string)(ownership,bool,error){fi,err:=os.Lstat(path);if errors.Is(err,os.ErrNotExist){return ownership{},false,nil};if err!=nil{return ownership{},false,err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()||fi.Size()>64<<10{return ownership{},false,errors.New("unsafe LVM ownership record")};b,err:=os.ReadFile(path);if err!=nil{return ownership{},false,err};var r ownership;if err=json.Unmarshal(b,&r);err!=nil{return ownership{},false,err};return r,true,nil}
func sameStrings(a,b []string)bool{if len(a)!=len(b){return false};for i:=range a{if a[i]!=b[i]{return false}};return true}
