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
