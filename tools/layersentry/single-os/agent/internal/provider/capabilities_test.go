package provider

import (
	"testing"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func TestDatabaseAutoPatchRequiresBackup(t *testing.T) {
	r := model.ServiceRequest{Category: model.CategoryDatabase, Provider: "postgresql", Maintenance: model.MaintenancePolicy{AutoPatch: true}}
	if err := ValidateIntentCapabilities("postgresql", r); err == nil {
		t.Fatal("expected database auto-patch without backup to be rejected")
	}
}

func TestNginxRejectsIgnoredStorage(t *testing.T) {
	r := model.ServiceRequest{Category: model.CategoryApplication, Provider: "nginx", Storage: []model.StorageAssignment{{Device: "/dev/disk/by-id/wwn-test"}}}
	if err := ValidateIntentCapabilities("nginx", r); err == nil {
		t.Fatal("expected nginx storage assignment to be rejected")
	}
}

func TestRuntimeRejectsListenerAndSecrets(t *testing.T) {
	r := model.ServiceRequest{Category: model.CategoryApplication, Provider: "nodejs-runtime", Network: model.NetworkSpec{ListenAddress: "127.0.0.1", Port: 3000}, SecretRefs: map[string]string{"token": "secret://00000000000000000000000000000000"}}
	if err := ValidateIntentCapabilities("nodejs-runtime", r); err == nil {
		t.Fatal("expected runtime listener/secret intent to be rejected")
	}
}

func TestPostgreSQLRejectsUnknownSecretReference(t *testing.T) {
	r := model.ServiceRequest{Category: model.CategoryDatabase, Provider: "postgresql", SecretRefs: map[string]string{"admin_password": "secret://00000000000000000000000000000000", "api_token": "secret://11111111111111111111111111111111"}}
	if err := ValidateIntentCapabilities("postgresql", r); err == nil {
		t.Fatal("expected unknown PostgreSQL secret reference to be rejected")
	}
}

func TestMySQLAllowsOnlyAdminSecretWhenBackupConfigured(t *testing.T) {
	r := model.ServiceRequest{Category: model.CategoryDatabase, Provider: "mysql", Backup: model.BackupPolicy{Enabled: true, Schedule: "daily", Retention: 7}, SecretRefs: map[string]string{"admin_password": "secret://00000000000000000000000000000000"}}
	if err := ValidateIntentCapabilities("mysql", r); err != nil {
		t.Fatalf("expected supported MySQL intent capabilities: %v", err)
	}
}
