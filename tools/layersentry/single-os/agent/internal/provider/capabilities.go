package provider

import (
	"errors"
	"fmt"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

// ValidateIntentCapabilities is a second, provider-independent guard against
// confused or malicious callers supplying fields a provider does not own. A
// provider still performs its product-specific validation afterwards.
func ValidateIntentCapabilities(id string, r model.ServiceRequest) error {
	switch id {
	case "postgresql":
		return onlySecretRefs(r, "admin_password")
	case "mysql", "mariadb", "redis":
		if len(r.Storage) != 0 {
			return fmt.Errorf("%s does not consume attached storage in the current qualified provider", id)
		}
		return onlySecretRefs(r, "admin_password")
	case "nginx", "apache-httpd", "tomcat":
		if len(r.Storage) != 0 {
			return fmt.Errorf("%s does not consume attached storage", id)
		}
		if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
			return fmt.Errorf("%s does not own customer application-data backup", id)
		}
		if len(r.SecretRefs) != 0 {
			return fmt.Errorf("%s does not consume secret references", id)
		}
	case "nodejs-runtime", "python-runtime", "podman-runtime":
		if len(r.Storage) != 0 {
			return errors.New("package-only runtime providers do not consume attached storage")
		}
		if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 {
			return errors.New("package-only runtime providers do not own customer application-data backup")
		}
		if len(r.SecretRefs) != 0 {
			return errors.New("package-only runtime providers do not consume secret references")
		}
		if r.Network.Port != 0 || r.Network.ListenAddress != "" || len(r.Network.AllowedCIDRs) != 0 {
			return errors.New("package-only runtime providers do not own a network listener")
		}
	}
	return nil
}

func onlySecretRefs(r model.ServiceRequest, allowed ...string) error {
	set := make(map[string]struct{}, len(allowed))
	for _, name := range allowed {
		set[name] = struct{}{}
	}
	for name := range r.SecretRefs {
		if _, ok := set[name]; !ok {
			return fmt.Errorf("provider %s does not consume secret reference %q", r.Provider, name)
		}
	}
	return nil
}
