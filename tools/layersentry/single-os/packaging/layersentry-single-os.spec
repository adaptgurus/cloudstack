Name:           layersentry-single-os
Version:        0.1.0
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

Requires:       ca-certificates
Requires:       firewalld
Requires:       policycoreutils
Requires:       util-linux
Requires:       xfsprogs
Requires:       e2fsprogs
Requires:       dnf-plugins-core

%description
LayerSentry guest lifecycle agent for installing and managing supported
VM-native database and application services inside a hardened Rocky Linux 9 VM.

%prep

%build

%install
install -Dpm0755 %{SOURCE0} %{buildroot}%{_bindir}/layersentryd
install -Dpm0755 %{SOURCE1} %{buildroot}%{_bindir}/layersentryctl
install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/layersentryd.service
install -Dpm0644 %{SOURCE3} %{buildroot}%{_unitdir}/layersentry-firstboot.service
install -Dpm0644 %{SOURCE4} %{buildroot}%{_unitdir}/layersentry-maintenance.service
install -Dpm0644 %{SOURCE5} %{buildroot}%{_unitdir}/layersentry-maintenance.timer
install -Dpm0644 %{SOURCE6} %{buildroot}%{_tmpfilesdir}/layersentryd.conf
install -Dpm0644 %{SOURCE7} %{buildroot}%{_sysusersdir}/layersentryd.conf

%post
%systemd_post layersentryd.service layersentry-firstboot.service layersentry-maintenance.timer
systemd-tmpfiles --create %{_tmpfilesdir}/layersentryd.conf >/dev/null 2>&1 || :

%preun
%systemd_preun layersentryd.service layersentry-firstboot.service layersentry-maintenance.timer

%postun
%systemd_postun_with_restart layersentryd.service

%files
%{_bindir}/layersentryd
%{_bindir}/layersentryctl
%{_unitdir}/layersentryd.service
%{_unitdir}/layersentry-firstboot.service
%{_unitdir}/layersentry-maintenance.service
%{_unitdir}/layersentry-maintenance.timer
%{_tmpfilesdir}/layersentryd.conf
%{_sysusersdir}/layersentryd.conf

%changelog
* Sun Sep 06 2026 LayerSentry Engineering <engineering@layersentry.local> - 0.1.0-1
- Initial VM-native Single-OS lifecycle agent package.
