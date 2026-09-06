package main

import (
    "context"
    "encoding/json"
    "errors"
    "os"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func planFile(path string) error {
    req,err:=readIntentFile(path);if err!=nil{return err}
    if err=firstBoot();err!=nil{return err}
    rt,err:=buildRuntime();if err!=nil{return err}
    plan,op,err:=rt.eng.Plan(context.Background(),req);if err!=nil{return err}
    enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ")
    return enc.Encode(map[string]any{"plan":plan,"operation":op,"confirmation_digest":plan.Digest,"mutation_started":false})
}
func applyFile(path,digest string) error {
    if digest==""{return errors.New("confirmed plan digest is required")}
    req,err:=readIntentFile(path);if err!=nil{return err}
    if err=firstBoot();err!=nil{return err}
    rt,err:=buildRuntime();if err!=nil{return err}
    op,err:=rt.eng.Install(context.Background(),req,digest);if err!=nil{return err}
    enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ")
    return enc.Encode(map[string]any{"operation":op,"confirmed_plan_digest":digest})
}
func readIntentFile(path string)(model.ServiceRequest,error){
    fi,err:=os.Lstat(path);if err!=nil{return model.ServiceRequest{},err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return model.ServiceRequest{},errors.New("intent file must be a regular non-symlink file")};if fi.Size()<2||fi.Size()>1<<20{return model.ServiceRequest{},errors.New("intent file size outside 2..1048576 bytes")}
    b,err:=os.ReadFile(path);if err!=nil{return model.ServiceRequest{},err};return config.DecodeStrict(b)
}
