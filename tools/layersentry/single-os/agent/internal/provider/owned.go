package provider

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

var ownerScopeRE = regexp.MustCompile(`^[a-z0-9][a-z0-9_.-]{0,95}$`)

// OwnershipSpec describes one guest-global resource that must not be represented
// by multiple independent LayerSentry ServiceState objects. PostgreSQL uses a
// release-scoped owner because vendor units/data roots are major-version scoped;
// package-only runtimes use one owner per provider/package.
type OwnershipSpec struct {
	ScopeForRequest func(model.ServiceRequest) string
	ScopeForState   func(model.ServiceState) string
	PackageForRequest func(model.ServiceRequest) string
	PackageForState   func(model.ServiceState) string
	PreexistingPaths func(model.ServiceRequest) []string
}

type Owned struct {
	Inner  Provider
	Runner executor.Runner
	Spec   OwnershipSpec
	Root   string
}

func NewOwned(inner Provider, runner executor.Runner, spec OwnershipSpec) *Owned {
	return &Owned{Inner: inner, Runner: runner, Spec: spec, Root: "/var/lib/layersentryd/state/provider-owners"}
}

func (p *Owned) ID() string { return p.Inner.ID() }
func (p *Owned) Category() model.Category { return p.Inner.Category() }
func (p *Owned) Validate(ctx context.Context, r model.ServiceRequest) error {
	if err := p.Inner.Validate(ctx, r); err != nil { return err }
	scope, err := p.requestScope(r); if err != nil { return err }
	owner, exists, err := p.readOwner(scope); if err != nil { return err }
	if exists {
		if owner != r.ServiceID { return fmt.Errorf("guest-global %s resource is already owned by another LayerSentry service", scope) }
		return nil
	}
	if p.Runner == nil { return errors.New("ownership preflight executor unavailable") }
	pkg := p.Spec.PackageForRequest(r)
	if pkg == "" { return errors.New("ownership package identity unavailable") }
	res, runErr := p.Runner.Run(ctx, "/usr/bin/rpm", "-q", pkg)
	if runErr == nil && res.ExitCode == 0 { return fmt.Errorf("refusing to adopt unmanaged pre-existing package %s", pkg) }
	if p.Spec.PreexistingPaths != nil {
		for _, path := range p.Spec.PreexistingPaths(r) {
			if path == "" || !filepath.IsAbs(path) { return errors.New("ownership preexisting path is invalid") }
			if _, statErr := os.Lstat(path); statErr == nil { return fmt.Errorf("refusing to adopt unmanaged pre-existing path %s", path) } else if !errors.Is(statErr, os.ErrNotExist) { return statErr }
		}
	}
	return nil
}
func (p *Owned) ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.Inner.ResolveVersion(ctx,r)}
func (p *Owned) Plan(ctx context.Context,r model.ServiceRequest,v string)(model.Plan,error){return p.Inner.Plan(ctx,r,v)}
func (p *Owned) Install(ctx context.Context,op model.Operation,plan model.Plan)error{scope,err:=p.requestScope(plan.Request);if err!=nil{return err};if err=p.ensureOwner(scope,plan.ServiceID,false);err!=nil{return err};return p.Inner.Install(ctx,op,plan)}
func (p *Owned) Configure(ctx context.Context,op model.Operation,plan model.Plan)error{scope,err:=p.requestScope(plan.Request);if err!=nil{return err};if err=p.ensureOwner(scope,plan.ServiceID,true);err!=nil{return err};return p.Inner.Configure(ctx,op,plan)}
func (p *Owned) Initialize(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Inner.Initialize(ctx,op,plan)}
func (p *Owned) Join(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Inner.Join(ctx,op,plan)}
func (p *Owned) Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){return p.Inner.Health(ctx,st)}
func (p *Owned) Start(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Inner.Start(ctx,op,st)}
func (p *Owned) Stop(ctx context.Context,op model.Operation,st model.ServiceState)error{if err:=p.verifyStateOwner(st);err!=nil{return err};return p.Inner.Stop(ctx,op,st)}
func (p *Owned) Restart(ctx context.Context,op model.Operation,st model.ServiceState)error{if err:=p.verifyStateOwner(st);err!=nil{return err};return p.Inner.Restart(ctx,op,st)}
func (p *Owned) Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{scope,err:=p.requestScope(plan.Request);if err!=nil{return err};if err=p.ensureOwner(scope,plan.ServiceID,false);err!=nil{return err};return p.Inner.Upgrade(ctx,op,plan)}
func (p *Owned) Repair(ctx context.Context,op model.Operation,plan model.Plan)error{scope,err:=p.requestScope(plan.Request);if err!=nil{return err};if err=p.ensureOwner(scope,plan.ServiceID,false);err!=nil{return err};return p.Inner.Repair(ctx,op,plan)}
func (p *Owned) Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){if err:=p.verifyStateOwner(st);err!=nil{return model.BackupRecord{},err};return p.Inner.Backup(ctx,op,st)}
func (p *Owned) Restore(ctx context.Context,op model.Operation,st model.ServiceState,b model.BackupRecord)error{if err:=p.verifyStateOwner(st);err!=nil{return err};return p.Inner.Restore(ctx,op,st,b)}
func (p *Owned) Uninstall(ctx context.Context,op model.Operation,st model.ServiceState,destroy bool)error{scope,err:=p.stateScope(st);if err!=nil{return err};if err=p.ensureOwner(scope,st.ID,false);err!=nil{return err};if err=p.Inner.Uninstall(ctx,op,st,destroy);err!=nil{return err};return p.removeOwner(scope,st.ID)}
func (p *Owned) ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){out,err:=p.Inner.ResidueAudit(ctx,st);if err!=nil{return nil,err};scope,scopeErr:=p.stateScope(st);if scopeErr!=nil{return nil,scopeErr};_,exists,readErr:=p.readOwner(scope);if readErr!=nil{return nil,readErr};if exists{out["provider_owner"]="present"}else{out["provider_owner"]="absent"};return out,nil}

func (p *Owned) requestScope(r model.ServiceRequest)(string,error){if p.Spec.ScopeForRequest==nil{return "",errors.New("ownership request scope unavailable")};return validateOwnerScope(p.Spec.ScopeForRequest(r))}
func (p *Owned) stateScope(st model.ServiceState)(string,error){if p.Spec.ScopeForState==nil{return "",errors.New("ownership state scope unavailable")};return validateOwnerScope(p.Spec.ScopeForState(st))}
func validateOwnerScope(scope string)(string,error){if !ownerScopeRE.MatchString(scope){return "",errors.New("ownership scope is invalid")};return scope,nil}
func (p *Owned) ownerPath(scope string)string{return filepath.Join(p.Root,scope+".owner")}
func (p *Owned) readOwner(scope string)(string,bool,error){path:=p.ownerPath(scope);fi,err:=os.Lstat(path);if errors.Is(err,os.ErrNotExist){return "",false,nil};if err!=nil{return "",false,err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()||fi.Size()<2||fi.Size()>128{return "",false,errors.New("unsafe provider owner record")};raw,err:=os.ReadFile(path);if err!=nil{return "",false,err};owner:=strings.TrimSpace(string(raw));if owner==""{return "",false,errors.New("empty provider owner record")};return owner,true,nil}
func (p *Owned) ensureOwner(scope,serviceID string,claim bool)error{owner,exists,err:=p.readOwner(scope);if err!=nil{return err};if exists{if owner!=serviceID{return fmt.Errorf("guest-global %s resource ownership mismatch",scope)};return nil};if !claim{return nil};if err=os.MkdirAll(p.Root,0700);err!=nil{return err};return filesystem.AtomicWrite(p.ownerPath(scope),[]byte(serviceID+"\n"),0600,p.Root)}
func (p *Owned) verifyStateOwner(st model.ServiceState)error{scope,err:=p.stateScope(st);if err!=nil{return err};owner,exists,err:=p.readOwner(scope);if err!=nil{return err};if !exists||owner!=st.ID{return fmt.Errorf("guest-global %s resource ownership missing or changed",scope)};return nil}
func (p *Owned) removeOwner(scope,serviceID string)error{owner,exists,err:=p.readOwner(scope);if err!=nil{return err};if !exists{return errors.New("provider owner record missing during uninstall")};if owner!=serviceID{return errors.New("provider owner record changed during uninstall")};return os.Remove(p.ownerPath(scope))}
