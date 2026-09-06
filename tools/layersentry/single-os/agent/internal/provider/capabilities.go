package provider

import (
	"errors"
	"fmt"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

// ValidateIntentCapabilities is a provider-independent confused-deputy guard.
// It rejects data roles, backup semantics and secrets a provider does not own;
// each provider still performs product-specific validation afterwards.
func ValidateIntentCapabilities(id string, r model.ServiceRequest) error {
	if r.Category == model.CategoryDatabase && r.Maintenance.AutoPatch && !r.Backup.Enabled {
		return errors.New("automatic database patching requires a provider-managed backup policy")
	}
	switch id {
	case "postgresql":
		if err:=allowedStoragePurposes(r,"database-data","database-wal","database-logs");err!=nil{return err}
		return onlySecretRefs(r, "admin_password")
	case "mysql", "mariadb":
		if err:=allowedStoragePurposes(r,"database-data","database-logs");err!=nil{return err}
		return onlySecretRefs(r, "admin_password")
	case "redis", "valkey":
		if err:=allowedStoragePurposes(r,"database-data");err!=nil{return err}
		return onlySecretRefs(r, "admin_password")
	case "nginx", "apache-httpd", "tomcat":
		if err:=allowedStoragePurposes(r,"application-data");err!=nil{return err}
		if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
			return fmt.Errorf("%s does not own customer application-data backup", id)
		}
		if len(r.SecretRefs) != 0 {
			return fmt.Errorf("%s does not consume secret references", id)
		}
	case "nodejs-runtime", "python-runtime", "podman-runtime":
		if len(r.Storage) != 0 || len(r.LVM)!=0 {
			return errors.New("package-only runtime providers do not consume attached storage; mount application workspaces independently of the runtime package provider")
		}
		if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
			return errors.New("package-only runtime providers do not own customer application-data backup")
		}
		if len(r.SecretRefs) != 0 {
			return errors.New("package-only runtime providers do not consume secret references")
		}
		if r.Network.Port != 0 || r.Network.ListenAddress != "" || len(r.Network.AllowedCIDRs) != 0 || r.Network.VIP.Mode!="" {
			return errors.New("package-only runtime providers do not own a network listener or VIP")
		}
	}
	return nil
}

func allowedStoragePurposes(r model.ServiceRequest, allowed ...string) error {
	set:=make(map[string]struct{},len(allowed));for _,v:=range allowed{set[v]=struct{}{}}
	check:=func(purpose string)error{if _,ok:=set[purpose];!ok{return fmt.Errorf("provider %s does not consume storage purpose %q",r.Provider,purpose)};return nil}
	for _,s:=range r.Storage{if err:=check(s.Purpose);err!=nil{return err}}
	for _,g:=range r.LVM{for _,lv:=range g.LogicalVolumes{if err:=check(lv.Purpose);err!=nil{return err}}}
	return nil
}
func onlySecretRefs(r model.ServiceRequest, allowed ...string) error {
	set := make(map[string]struct{}, len(allowed))
	for _, name := range allowed { set[name] = struct{}{} }
	for name := range r.SecretRefs { if _, ok := set[name]; !ok { return fmt.Errorf("provider %s does not consume secret reference %q", r.Provider, name) } }
	return nil
}
