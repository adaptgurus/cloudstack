# First-management RKE2 CPU image build decision

Status: `DESIGN_DEFINED`; actual Rocky boot, join and storage qualification remains `NOT_TESTED`. Scope: versioned amd64 CPU QCOW2 for the first dedicated management cluster. No CloudStack core or lab mutation.

## Research and decision

The existing Kubernetes contract requires native CloudStack/template/cloud-init/Runner bootstrap for the first management cluster, then CAPC/CAPRKE2 lifecycle for tenant clusters. It requires an immutable universal CPU image with host storage/network diagnostics, rather than installing all workload operators into the host. No existing Workstream E QCOW2 builder was present. The Single-OS appliance builder is a separate lifecycle and is not reused or modified.

Choose the exact official `Rocky-9-GenericCloud-Base-9.8-20260525.0.x86_64.qcow2`, verified against its Rocky-signed checksum and pinned SHA-256, rather than a moving latest image or a new unattended ISO installation. GenericCloud supplies the intended cloud-init and virtual-machine foundation, reducing installer and bootloader divergence. Use libguestfs against a fresh copied image, with network disabled throughout guest customization. Package dependencies and RKE2 artifacts are materialized and verified before the offline build; dynamic repository resolution is prohibited in the resulting image build.

RKE2 is fixed to `v1.36.4+rke2r1`, exact upstream source `7479a59cdd2c8ce0b8871699a24daa4b7c28cc64`. Use its binary tarball and complete Canal air-gap image archive. The [official air-gap instructions](https://docs.rke2.io/install/airgap) define the binary archive layout, image archive directory and separate SELinux RPM prerequisite. The [official Rocky image repository](https://download.rockylinux.org/pub/rocky/9/images/x86_64/) supplies a dated 9.8 GenericCloud build with checksum/signature. The [libguestfs customization contract](https://libguestfs.org/virt-customize.1.html) supports offline customization of a stopped image without booting the guest. No native CloudStack API/plugin/XaaS change is needed; registration and first-node VM deployment stay in the existing native API bootstrap path.

An ISO installation or Packer boot-driven provisioner would add unnecessary kickstart, credentials and transient networking. A generic container root filesystem would require inventing a bootable VM disk/kernel/initramfs/partition lifecycle. Retain the official QCOW2 and mutate a fresh local build copy only. Package updates produce a new locked image revision; do not hand-patch customer nodes.

## Image and bootstrap contract

Preserve cloud-init with CloudStack and NoCloud datasource support, QEMU guest agent, Python 3, OpenSSH server and generation of unique Ed25519 host keys at first boot. Enable root SSH public-key authentication and disable all password authentication. Do not bake authorized keys, SSH host private keys, CloudStack API credentials, kubeconfigs, RKE2 tokens, certificates or per-cluster config into the image. Initial user data may supply deterministic hostname and an authorized SSH public key only; Runner verifies the parent KVM host key, obtains the guest host public key through QGA, then connects with strict SSH host-key checking. Runner injects cluster-specific RKE2 configuration/token through its protected runtime channel.

Install RKE2 and its exact SELinux policy but leave `rke2-server` and `rke2-agent` stopped/disabled. Pre-stage the complete Canal image archive without image-cache shortcuts. Preserve SELinux enforcing and firewalld; per-cluster network/storage activation and firewall rules are a separate validated bootstrap/profile concern. Universal storage capabilities are installed but iSCSI sessions, multipath and RDMA configuration are not activated by the image builder.

Builder metadata is unsigned and reports candidate build status, exact source/input/output digests and qualification false. It cannot emit `LIVE_VERIFIED`, a trusted template ID or a signed qualification attestation. Real Rocky boot, cloud-init/QGA/SSH trust, automatic three-server formation, Canal, SELinux/firewall behavior, storage and subsequent bootstrap tests must produce those facts through the approved runner path.

## Rollback and remaining gates

The source image is immutable and never changed; a failed build discards only its output copy. Publish/register no image in this task. Release promotion requires retaining the exact QCOW2 and input bundle, SBOM/provenance/license and vulnerability evidence, signing and exact Rocky runtime tests. Three-node HA and independent failure domains are not established by an image build.
