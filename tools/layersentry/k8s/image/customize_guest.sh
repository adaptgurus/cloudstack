#!/bin/bash
# Runs only inside the offline libguestfs appliance against a fresh build copy.
set -euo pipefail
trap 'printf "Image customization failed at line %s\n" "$LINENO" >&2' ERR
bundle=/opt/layersentry-node-inputs
cd "$bundle"
python3 - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path('.')
lock=json.loads((root/'inputs.lock.json').read_text())
for item in [*lock['rke2Archives'],lock['selinuxRpm'],*lock['rpmPackages']]:
 p=root/item['file'];d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):d.update(b)
 assert p.stat().st_size==item['size'] and d.hexdigest()==item['sha256'],item['file']
PY
rpmkeys --import trust/RPM-GPG-KEY-Rocky-9 trust/RPM-GPG-KEY-Rancher
rpmkeys --checksig ./*.rpm
dnf -y --disablerepo='*' --setopt=localpkg_gpgcheck=1 --setopt=install_weak_deps=False install ./*.rpm
# The verified official archive uses only bin/, lib/systemd/ and share/rke2/.
tar -xzf rke2.linux-amd64.tar.gz -C /usr/local
install -d -m 0755 /var/lib/rancher/rke2/agent/images /etc/rancher/rke2 /etc/sysconfig
install -m 0644 rke2-images.linux-amd64.tar.zst /var/lib/rancher/rke2/agent/images/rke2-images.linux-amd64.tar.zst
install -m 0644 /usr/local/lib/systemd/system/rke2-server.service /etc/systemd/system/rke2-server.service
install -m 0644 /usr/local/lib/systemd/system/rke2-agent.service /etc/systemd/system/rke2-agent.service
printf '%s\n' 'RKE2_SELINUX=true' > /etc/sysconfig/rke2-server
printf '%s\n' 'RKE2_SELINUX=true' > /etc/sysconfig/rke2-agent
chmod 0600 /etc/sysconfig/rke2-server /etc/sysconfig/rke2-agent
systemctl disable rke2-server.service rke2-agent.service
systemctl enable qemu-guest-agent.service sshd.service NetworkManager.service firewalld.service
systemctl enable cloud-init-local.service cloud-init.service cloud-config.service cloud-final.service
for unit in iscsid.service iscsid.socket iscsi.service iscsiuio.service iscsiuio.socket multipathd.service multipathd.socket; do
  if systemctl list-unit-files "$unit" --no-legend | grep -q "$unit"; then systemctl disable "$unit"; fi
done
# NetworkManager must leave Canal-created interfaces to the CNI owner.
install -d -m 0755 /etc/NetworkManager/conf.d /etc/ssh/sshd_config.d /etc/cloud/cloud.cfg.d
cat > /etc/NetworkManager/conf.d/90-layersentry-rke2-canal.conf <<'CONFIG'
[keyfile]
unmanaged-devices=interface-name:cali*;interface-name:flannel*
CONFIG
for unit in nm-cloud-setup.service nm-cloud-setup.timer; do
  if systemctl list-unit-files "$unit" --no-legend | grep -q "$unit"; then systemctl disable "$unit"; fi
done
cat > /etc/ssh/sshd_config.d/00-layersentry-key-only.conf <<'CONFIG'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
CONFIG
cat > /etc/cloud/cloud.cfg.d/90-layersentry-node.cfg <<'CONFIG'
ssh_pwauth: false
disable_root: false
ssh_deletekeys: true
ssh_genkeytypes: [ed25519, rsa]
datasource_list: [CloudStack, NoCloud, None]
CONFIG
sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
test "$(grep '^SELINUX=' /etc/selinux/config)" = SELINUX=enforcing
passwd -l root
# GenericCloud swap entries are disabled; no block device is formatted here.
sed -i '/^[^#].*[[:space:]]swap[[:space:]]/s/^/# LayerSentry disabled swap: /' /etc/fstab
install -d -m 0755 /usr/share/layersentry/node-image
/usr/local/bin/rke2 --version > /usr/share/layersentry/node-image/rke2-version.txt
grep -F 'v1.36.4+rke2r1' /usr/share/layersentry/node-image/rke2-version.txt
rpm -qa --qf '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\t%{LICENSE}\n' | sort > /usr/share/layersentry/node-image/rpm-inventory.tsv
for command in cloud-init qemu-ga python3 sshd iscsiadm lsscsi sg_inq multipath nvme mount.nfs lvm mdadm mkfs.xfs xfs_growfs mkfs.ext4 resize2fs cryptsetup fio smartctl iostat iotop ip ethtool conntrack socat tcpdump mtr dig curl jq openssl rsync zstd; do
  command -v "$command"
done
rpm -q rke2-selinux container-selinux
# No image can contain host identity, authentication material or join state.
cloud-init clean --logs --machine-id
rm -f /etc/ssh/ssh_host_* /root/.ssh/authorized_keys
find /home -path '*/.ssh/authorized_keys' -type f -delete
truncate -s 0 /etc/machine-id
install -d -m 0755 /var/lib/dbus
rm -f /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id
rm -rf /var/lib/cloud/instances /var/lib/cloud/instance
rm -f /root/.bash_history /var/log/secure /var/log/lastlog /var/log/wtmp /var/log/btmp
test -z "$(find /etc/ssh -maxdepth 1 -name 'ssh_host_*' -print -quit)"
test ! -e /root/.ssh/authorized_keys
test ! -e /etc/rancher/rke2/config.yaml
test ! -e /var/lib/rancher/rke2/server
test ! -s /etc/machine-id
python3 -c 'from cloudinit.sources import DataSourceCloudStack, DataSourceNoCloud'
install -m 0644 inputs.lock.json /usr/share/layersentry/node-image/inputs.lock.json
cd /
rm -rf "$bundle"
dnf clean all
