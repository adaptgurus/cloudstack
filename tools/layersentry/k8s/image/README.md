# RKE2 universal CPU image candidate

This path builds the first-management amd64 node template from the dated official Rocky 9 GenericCloud image, locked Rocky RPMs and RKE2 v1.36.4+rke2r1 binary/Canal image archives. The output remains unqualified until the approved Rocky runner proves boot, QGA/SSH trust, automatic join, networking/SELinux and storage behavior.

On a controlled builder with Python 3, GnuPG, qemu-img and libguestfs installed:

```bash
python3 tools/layersentry/k8s/image/prepare_inputs.py --output /build/locked-inputs
python3 tools/layersentry/k8s/image/build_cpu_image.py \
  --inputs /build/locked-inputs --output /build/cpu-candidate
```

To build without Internet access, import the exact flat input bundle and run `prepare_inputs.py --cache /imported-inputs --output /build/locked-inputs`; missing bytes never fall back to a network download. Customization always uses `virt-customize --no-network` and `dnf --disablerepo='*'` with local RPM signature checks. `build_cpu_image.py` refuses an existing output and modifies only a fresh converted QCOW2 copy. Hosted qualification uses `.github/workflows/layersentry-rke2-cpu-image-build.yml` on the isolated artifact branch, without lab or registry credentials.

Trust roots are pinned by full fingerprint and file SHA-256 in the input lock. The base's detached Rocky checksum signature is verified again before image conversion. RKE2 GitHub release hashes and all signed RPM bytes are fixed in the lock. Lock refresh is a reviewed source change, never performed by an image build. Current Rocky paths can be retired upstream, so retain the complete input bundle in the platform artifact service for offline and long-term rebuilds.

The host profile includes cloud-init, QGA/Python/SSH, iSCSI/multipath/NVMe/NFS/LVM/mdadm/cryptsetup, ext/XFS tooling and the required common diagnostics. Dedicated RDMA/GPU profiles and workload controllers/operators are excluded; diagnostic dependencies can include RDMA userspace libraries. Fio supplies the initial disk-latency diagnostics; no separate ioping/yq distribution is added to the base. Storage protocols remain inactive until selected by a qualified StorageHostProfile.

Initial bootstrap inputs are deterministic hostname and root SSH public key only. Cloud-init disables passwords; Runner must use the root-specific authorized-key field, because the upstream default user is rocky. QGA supplies the guest SSH host public key through an already trusted KVM transport; Runner must use strict guest known_hosts verification before injecting RKE2 configuration/token. No key, join token, CloudStack credential, kubeconfig or per-cluster address is baked. RKE2 is preinstalled and disabled, with SELinux enabled through its systemd environment and only Canal images staged. Firewalld remains enabled; exact SSH/RKE2/Canal rules belong to the validated bootstrap path.

`candidate-manifest.json` records output digest, source/input/inventory provenance and explicit false runtime qualifications. It is unsigned, has no template ID and is not a trusted live-qualification attestation. The builder is not a replacement for native CloudStack registration or CAPRKE2 tenant lifecycle. License/security review, signing, registry/media retention, Rocky boot/three-server join/storage validation and upgrade/rollback remain release gates.

## Bounded networkless boot and QGA acceptance

`boot_qga_acceptance.py` is executed only through the runtime owner's approved root runner. Host prerequisites are signed Rocky `libvirt-client`, `libvirt-daemon-kvm`, `qemu-img`, `genisoimage` (or `xorriso`), Python 3 and policycoreutils, working local `qemu:///system` sockets, nested KVM and SELinux Enforcing. It does not install packages or alter host services, networks or firewall rules.

Provide the exact downloaded candidate QCOW2 and independently checked candidate manifest SHA-256:

```sh
python3 tools/layersentry/k8s/image/boot_qga_acceptance.py \
  --image /approved/artifact/cpu-image/layersentry-rke2-rocky9-amd64.qcow2 \
  --sha256 "$CANDIDATE_SHA256" --evidence /approved/evidence/unique-boot-run
```

The harness verifies standalone QCOW2 integrity and copies it into `/var/lib/libvirt/images/layersentry-cpuqc-<full UUID>` (root:qemu 0750). It creates one transient BIOS/q35 domain, 2 vCPU/4 GiB, with a virtio disk, read-only CIDATA seed, virtio QGA channel and serial log. It attaches **no network interface**. The NoCloud seed contains only a fresh instance ID, hostname and disabled password authentication; it adds no SSH key or cluster credential. CloudStack/NoCloud/None are the image's supported datasources; OpenStack is not enabled.

Bounded QGA checks require Rocky 9.8, Enforcing SELinux, cloud-init completion, active QGA/SSH/firewalld, a generated machine ID and Ed25519 public host key, key-only effective SSH configuration, disabled/inactive RKE2, absent cluster config/server state and only the loopback interface. They do not start RKE2, test SSH network connectivity, form a cluster or qualify storage. The result is `LIVE_VERIFIED` with scope `networkless Rocky CPU image boot and QGA`; production qualification remains false.

Default behavior shuts down and, after 60 seconds if needed, destroys only the UUID-bound owned transient domain and removes its private runtime copy. `--retain-for-dr-qualification` retains only a passing domain for the runtime owner's bounded capture test. Its root-only `ownership.json` binds the exact UUID, name, disk/seed paths and source SHA. After capture, use:

```sh
python3 tools/layersentry/k8s/image/boot_qga_acceptance.py \
  --cleanup-manifest /var/lib/libvirt/images/layersentry-cpuqc-UUID/ownership.json
```

Cleanup refuses a changed domain disk/network, malformed ownership or failed libvirt connection. The original candidate image remains unchanged. Evidence includes requested/actual XML, guest facts, source image metadata and at most 2 MiB of serial log. A retained runtime copy contains generated guest host keys and must remain private; never upload that mutated disk as the sealed release image. Native CloudStack registration, after separate trusted qualification, represents this SHA-256 checksum as `{SHA-256}<64hex>`; this harness performs no registration.

The exact Rocky QGA policy is extended only with `guest-exec` and `guest-exec-status` for authorized host-mediated SSH host-key discovery and bounded acceptance commands. Existing allowed management RPCs are preserved; all-RPC mode and guest-file RPC additions are prohibited. This is a managed-image trust boundary, not a host-global or customer API permission. The private virtio channel remains accessible only through authorized hypervisor/Runner control. `qga-policy.json` records the policy digest and precise added RPCs in the image.
