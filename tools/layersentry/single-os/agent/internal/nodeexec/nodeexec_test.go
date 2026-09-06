package nodeexec

import "testing"

func TestNodeModuleHelperAllowsQualifiedStreamOnly(t *testing.T) {
	if err := validateDNF([]string{"-y", "module", "enable", "nodejs:20"}); err != nil {
		t.Fatalf("expected nodejs:20 enable to be accepted: %v", err)
	}
	if err := validateDNF([]string{"-y", "module", "enable", "nodejs:22"}); err == nil {
		t.Fatal("expected unqualified nodejs:22 stream to be rejected")
	}
}

func TestNodeModuleHelperRejectsArbitraryPackage(t *testing.T) {
	if err := validateDNF([]string{"-y", "--setopt=install_weak_deps=False", "--disablerepo=*", "--enablerepo=appstream", "install", "bash-5.1-1.el9.x86_64"}); err == nil {
		t.Fatal("expected non-nodejs package install to be rejected")
	}
}

func TestNodeModuleHelperRejectsShell(t *testing.T) {
	if err := validate("/bin/sh", []string{"-c", "id"}); err == nil {
		t.Fatal("expected shell execution to be rejected")
	}
}

func TestNodeModuleRepoqueryIsReadOnlyAndPinned(t *testing.T) {
	if err := validateDNF([]string{"-q", "module", "repoquery", "--available", "nodejs:20"}); err != nil {
		t.Fatalf("expected nodejs:20 module repoquery to be accepted: %v", err)
	}
}
