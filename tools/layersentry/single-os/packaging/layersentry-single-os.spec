Name:           layersentry-single-os
Version:        0.2.0
Release:        1%{?dist}
Summary:        LayerSentry VM-native Single-OS DBaaS/APaaS lifecycle agent
License:        Apache-2.0
URL:            https://github.com/adaptgurus/cloudstack
Source0:        layersentryd
Source1:        layersentryctl
Source2:        layersentryd.service
Source3:        layersentry-firstboot.service
Source4:        layersentry-maintenance.service
Source5:        layersentry-maintenance.timer
Source6:        tmpfiles.conf
Source7:        sysusers.conf
Source8:        layersentry-privileged.service
Source9:        configure-from-file.sh
Source10:       ansible-project.tar.gz

BuildRequires:  systemd-rpm-macros
Requires:       ansible-core
Requires:       ca-certificates
Requires:       firewalld
Requires:       policycoreutils
Requires:       policycoreutils-python-utils
Requires:       util-linux
Requires:       xfsprogs
Requires:       e2fsprogs
Requires:       dnf-plugins-core
Requires:       lvm2
Requires:       NetworkManager
Requires:       systemd

%description
LayerSentry guest lifecycle agent for installing and managing supported
VM-native database and application services inside a hardened Rocky Linux 9 VM.
Go retains schema, immutable plan, idempotency, state, secrets and evidence
control. Reviewed local Ansible roles/modules own migrated guest mutation.
Provider packages and Keepalived are installed on demand from confirmed plans
rather than baked into the reusable image.

%prep

%build

%install
install -Dpm0755 %{SOURCE0} %{buildroot}%{_bindir}/layersentryd
install -Dpm0755 %{SOURCE1} %{buildroot}%{_bindir}/layersentryctl
install -Dpm0755 %{SOURCE9} %{buildroot}%{_bindir}/layersentry-configure-from-file
install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/layersentryd.service
install -Dpm0644 %{SOURCE3} %{buildroot}%{_unitdir}/layersentry-firstboot.service
install -Dpm0644 %{SOURCE4} %{buildroot}%{_unitdir}/layersentry-maintenance.service
install -Dpm0644 %{SOURCE5} %{buildroot}%{_unitdir}/layersentry-maintenance.timer
install -Dpm0644 %{SOURCE6} %{buildroot}%{_tmpfilesdir}/layersentryd.conf
install -Dpm0644 %{SOURCE7} %{buildroot}%{_sysusersdir}/layersentryd.conf
install -Dpm0644 %{SOURCE8} %{buildroot}%{_unitdir}/layersentry-privileged.service
mkdir -p %{buildroot}%{_prefix}/lib/layersentry/ansible
tar -C %{buildroot}%{_prefix}/lib/layersentry/ansible -xzf %{SOURCE10}
find %{buildroot}%{_prefix}/lib/layersentry/ansible -type d -exec chmod 0755 {} +
find %{buildroot}%{_prefix}/lib/layersentry/ansible -type f -exec chmod 0644 {} +

%post
systemd-sysusers %{_sysusersdir}/layersentryd.conf >/dev/null 2>&1 || :
systemd-tmpfiles --create %{_tmpfilesdir}/layersentryd.conf >/dev/null 2>&1 || :
%systemd_post layersentry-privileged.service layersentryd.service layersentry-firstboot.service layersentry-maintenance.timer

%preun
%systemd_preun layersentry-privileged.service layersentryd.service layersentry-firstboot.service layersentry-maintenance.timer

%postun
%systemd_postun_with_restart layersentry-privileged.service layersentryd.service

%files
%{_bindir}/layersentryd
%{_bindir}/layersentryctl
%{_bindir}/layersentry-configure-from-file
%{_unitdir}/layersentry-privileged.service
%{_unitdir}/layersentryd.service
%{_unitdir}/layersentry-firstboot.service
%{_unitdir}/layersentry-maintenance.service
%{_unitdir}/layersentry-maintenance.timer
%{_tmpfilesdir}/layersentryd.conf
%{_sysusersdir}/layersentryd.conf
%{_prefix}/lib/layersentry/ansible

%changelog
* Mon Sep 07 2026 LayerSentry Engineering <engineering@layersentry.local> - 0.2.0-1
- Add typed Go-to-Ansible execution boundary and PostgreSQL standalone vertical slice.
- Package reviewed local ansible-core project; no runtime Galaxy dependency.

* Sun Sep 06 2026 LayerSentry Engineering <engineering@layersentry.local> - 0.1.0-1
- Initial VM-native Single-OS lifecycle agent package with privilege separation.
