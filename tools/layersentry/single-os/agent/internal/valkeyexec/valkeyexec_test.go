package valkeyexec

import "testing"

func TestValkeyHelperAllowsAppStreamOnly(t *testing.T) {
	if err := validateDNF([]string{"-q", "config-manager", "--dump", "appstream"}); err != nil {
		t.Fatalf("expected appstream inspection to be accepted: %v", err)
	}
	if err := validateDNF([]string{"-q", "config-manager", "--dump", "epel"}); err == nil {
		t.Fatal("expected foreign repository to be rejected")
	}
}

func TestValkeyHelperRejectsOtherSystemdUnits(t *testing.T) {
	if err := validateSystemctl([]string{"restart", "sshd.service"}); err == nil {
		t.Fatal("expected foreign systemd unit to be rejected")
	}
	if err := validateSystemctl([]string{"restart", "valkey.service"}); err != nil {
		t.Fatalf("expected valkey.service to be accepted: %v", err)
	}
}

func TestValkeyHelperRejectsArbitraryPrivilegedCopy(t *testing.T) {
	if err := validateInstall([]string{"--mode=04755", "--owner=root", "--group=root", "/bin/sh", "/tmp/rootsh"}); err == nil {
		t.Fatal("expected arbitrary file copy to be rejected")
	}
}

func TestValkeyHelperRejectsShell(t *testing.T) {
	if err := validate("/bin/sh", []string{"-c", "id"}); err == nil {
		t.Fatal("expected shell execution to be rejected")
	}
}
