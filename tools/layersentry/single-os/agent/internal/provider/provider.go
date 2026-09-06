package provider

import (
 "context"
 "errors"
 "sort"
 "sync"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

type Provider interface {
 ID() string
 Category() model.Category
 Validate(context.Context,model.ServiceRequest) error
 ResolveVersion(context.Context,model.ServiceRequest)(string,error)
 Plan(context.Context,model.ServiceRequest,string)(model.Plan,error)
 Install(context.Context,model.Operation,model.Plan) error
 Configure(context.Context,model.Operation,model.Plan) error
 Initialize(context.Context,model.Operation,model.Plan) error
 Join(context.Context,model.Operation,model.Plan) error
 Health(context.Context,model.ServiceState)(model.HealthResult,error)
 Start(context.Context,model.Operation,model.ServiceState) error
 Stop(context.Context,model.Operation,model.ServiceState) error
 Restart(context.Context,model.Operation,model.ServiceState) error
 Upgrade(context.Context,model.Operation,model.Plan) error
 Repair(context.Context,model.Operation,model.Plan) error
 Backup(context.Context,model.Operation,model.ServiceState) (model.BackupRecord,error)
 Restore(context.Context,model.Operation,model.ServiceState,model.BackupRecord) error
 Uninstall(context.Context,model.Operation,model.ServiceState,bool) error
 ResidueAudit(context.Context,model.ServiceState)(map[string]string,error)
}

type Registry struct{mu sync.RWMutex;items map[string]Provider}
func NewRegistry()*Registry{return &Registry{items:map[string]Provider{}}}
func(r *Registry)Register(p Provider)error{if p==nil||p.ID()==""{return errors.New("invalid provider")};r.mu.Lock();defer r.mu.Unlock();if _,ok:=r.items[p.ID()];ok{return errors.New("duplicate provider")};r.items[p.ID()]=p;return nil}
func(r *Registry)Get(id string)(Provider,bool){r.mu.RLock();defer r.mu.RUnlock();p,ok:=r.items[id];return p,ok}
func(r *Registry)IDs()[]string{r.mu.RLock();defer r.mu.RUnlock();out:=make([]string,0,len(r.items));for k:=range r.items{out=append(out,k)};sort.Strings(out);return out}
