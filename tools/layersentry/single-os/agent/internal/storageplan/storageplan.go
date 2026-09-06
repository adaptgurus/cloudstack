package storageplan

import (
    "errors"
    "fmt"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

// PathForPurpose resolves one service data purpose regardless of whether the
// backing filesystem was supplied directly or created as a LayerSentry LV.
// Configuration validation guarantees cross-model mount/device uniqueness;
// this resolver additionally refuses multiple paths for the same semantic role.
func PathForPurpose(r model.ServiceRequest,purpose string)(string,error){var path string;set:=func(candidate string)error{if candidate==""{return nil};if path!=""&&path!=candidate{return fmt.Errorf("multiple storage paths configured for purpose %s",purpose)};path=candidate;return nil};for _,s:=range r.Storage{if s.Purpose==purpose{if err:=set(s.MountPoint);err!=nil{return "",err}}};for _,g:=range r.LVM{for _,lv:=range g.LogicalVolumes{if lv.Purpose==purpose{if err:=set(lv.MountPoint);err!=nil{return "",err}}}};return path,nil}
func StatePathForPurpose(st model.ServiceState,purpose string)(string,error){r:=model.ServiceRequest{Storage:st.Storage,LVM:st.LVM};return PathForPurpose(r,purpose)}
func RequireSingle(r model.ServiceRequest,purpose string)(string,error){p,err:=PathForPurpose(r,purpose);if err!=nil{return "",err};if p==""{return "",errors.New("storage purpose "+purpose+" is required")};return p,nil}
func HasAny(r model.ServiceRequest)bool{return len(r.Storage)>0||len(r.LVM)>0}
