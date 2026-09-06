package main

import (
    "encoding/json"
    "errors"
    "fmt"
    "os"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
)

func planFile(path string) error {
    req,err:=readIntentFile(path);if err!=nil{return err}
    if err=firstBoot();err!=nil{return err}
    rt,err:=buildRuntime();if err!=nil{return err}
    plan,op,err:=rt.eng.Plan(background(),req);if err!=nil{return err}
    enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ")
    return enc.Encode(map[string]any{"plan":plan,"operation":op,"confirmation_digest":plan.Digest,"mutation_started":false})
}
func applyFile(path,digest string) error {
    if digest==""{return errors.New("confirmed plan digest is required")}
    req,err:=readIntentFile(path);if err!=nil{return err}
    if err=firstBoot();err!=nil{return err}
    rt,err:=buildRuntime();if err!=nil{return err}
    op,err:=rt.eng.Install(background(),req,digest);if err!=nil{return err}
    enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ")
    return enc.Encode(map[string]any{"operation":op,"confirmed_plan_digest":digest})
}
func readIntentFile(path string)(anyRequest,error){
    fi,err:=os.Lstat(path);if err!=nil{return anyRequest{},err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return anyRequest{},errors.New("intent file must be a regular non-symlink file")};if fi.Size()<2||fi.Size()>1<<20{return anyRequest{},errors.New("intent file size outside 2..1048576 bytes")}
    b,err:=os.ReadFile(path);if err!=nil{return anyRequest{},err};req,err:=config.DecodeStrict(b);if err!=nil{return anyRequest{},err};return anyRequest{ServiceRequest:req},nil
}

// tiny wrapper keeps the file-mode implementation explicit while allowing the
// concrete model type to remain hidden from shell-facing code.
type anyRequest struct{ServiceRequest interface{} }

func background() contextContext { return contextBackground() }

// compile-time aliases are implemented in file_mode_types.go to keep imports
// here focused on the file boundary.
var _ = fmt.Sprintf
