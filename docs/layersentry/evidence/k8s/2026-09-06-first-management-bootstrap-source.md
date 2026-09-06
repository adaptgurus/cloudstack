# First management RKE2 bootstrap: source qualification

Status: `SOURCE_COMPLETE` for the bounded native bootstrap implementation; live execution `NOT_TESTED`; production certification `BLOCKED`.

## Decision and research

The existing E contract requires the first dedicated management RKE2 cluster to be created through native CloudStack APIs and a bounded Runner path. The existing controller consumes an already running Kubernetes API; emitting CAPI resources cannot create that first API. `tools/layersentry-management/bootstrap-rocky9-management.sh` installs CloudStack management packages and is unrelated to Kubernetes bootstrap. Historical sen2/Rancher/Harvester repair workflows are also not this lifecycle owner.

Retain native CloudStack allocation, tenancy, networking and async jobs for the first three management nodes. After management CAPI is installed and qualified, tenant clusters remain owned by CAPI/CAPC/CAPRKE2. No CloudStack Java, schema, KVM core, existing controller implementation, tenant lifecycle or Single-OS lifecycle is changed by this addition.

Exact CloudStack 4.22.1.1 source findings:

- `BaseDeployVMCmd` extends `BaseAsyncCreateCustomIdCmd`; `customid` is Root Admin only. Deterministic UUIDs provide exact observation after an ambiguous deployment submission; they do not justify replaying an unobserved mutation.
- `UserVmVO.userData` persists userdata, `ListVMsCmd` supports returning it, `UserVmJoinDaoImpl` populates it when requested, and `GetVMUserDataCmd` checks account access. Base64 userdata is not a confidential secret channel.
- `CreateLoadBalancerRuleCmd.getSourceCidrList()` rejects the deprecated `cidrlist` parameter. This bootstrap uses `openfirewall=false` and separate `createFirewallRule` operations with exact approved sources.
- Libvirt domain UUID comes from the VM transfer object's UUID. The trusted host transport checks native instance name → UUID and addresses QGA by the checked UUID.

Official sources reviewed: [CloudStack 4.22 API index](https://cloudstack.apache.org/api/apidocs-4.22/), [RKE2 v1.36.4+rke2r1](https://github.com/rancher/rke2/releases/tag/v1.36.4%2Brke2r1), [RKE2 HA procedure](https://docs.rke2.io/install/ha), [RKE2 air-gap installation](https://docs.rke2.io/install/airgap), and [CAPRKE2 v0.25.2 cloud-init implementation](https://github.com/rancher/cluster-api-provider-rke2/tree/v0.25.2/bootstrap/internal/cloudinit). RKE2 requires the fixed registration endpoint on 9345 and Kubernetes API on 6443; token/config consistency and an odd server count are required. The implementation fixes this first profile to three servers and Canal.

Alternatives considered: native CKS would create a different managed lifecycle; using CAPI for the first management plane creates a circular dependency; placing a join token in runtime-generated cloud-init is executable but retains it in CloudStack userdata. The selected trusted Runner transport keeps private keys and RKE2 tokens out of userdata, API requests, journals and emitted evidence. It adds a dependency on an approved KVM-host SSH trust path and QGA, which is explicit and fails closed.

## Implemented path

`bootstrap_management.py` → native scoped inventory and signed image attestation → journaled native VM/LB/firewall operations → QGA public-host-key observation through pinned KVM SSH → strictly verified guest SSH → seed initialization → two automatic joins → read-only exact-node/version/role readiness and endpoint verification.

- Exactly three deterministic management VM identities are bound to the selected project, Site, implemented isolated non-VPC network, fixed compute offering, exact qualified image and selected KVM hosts.
- Native userdata contains only the root operator public key, deterministic hostname and QGA enablement. Password SSH is disabled. No token, private key, API key or arbitrary customer script is included.
- The bootstrap input must carry a trusted-key verified image attestation. A Ready KVM template alone is insufficient. The native template checksum must be exactly `{SHA-256}<attested digest>`, matching `ChecksumValue`/`DownloadManagerImpl`; an unprefixed native checksum means MD5, not SHA-256.
- The first release profile requires native Lb, Firewall and PortForwarding services. VPC ACLs and other endpoint providers are unsupported by this first bootstrap and are rejected.
- 6443/9345 LB rules are separate from firewall ownership. Firewall source ranges are the selected management network, its observed source-NAT IP and explicit operator ranges of /24 or narrower. Existing broader/overlapping rules are rejected, not silently adopted.
- The journal is stored in a private directory with exclusive writer locking and atomic fsync-backed replacement. It records plan identity, safe resource/job IDs and submission states. A timed-out or interrupted native submission is observed by exact identity before proceeding; an absent result is `UNKNOWN` and is never blindly replayed.
- KVM SSH uses an operator-approved known-hosts file. Host ID/address, VM UUID and instance name are bound to live native API observations. A fixed QGA operation reads only the root-owned Ed25519 host public key. No arbitrary QGA command or customer script is forwarded.
- Guest SSH connects through native, journal-owned public endpoint ports 2201–2203 forwarded to the exact VM private port 22. It does not assume a route to the isolated guest subnet. Each port uses `openfirewall=false` and a separate exact Runner /32 firewall rule; foreign, broader or overlapping rules fail before forwarding creation. Guest SSH accepts only that observed host key, pinned as `[publicIP]:port`. Its private operator key and strong stable RKE2 token come from protected runtime files. The token travels through SSH stdin to mode-0600 guest RKE2 configuration. A changed token or configuration is rejected during resume.
- Guest firewall changes retain Enforcing SELinux and active firewalld. They restrict control-plane/etcd/kubelet/Canal ports to observed peers/router and SSH to the current authenticated Runner source. The fixed dedicated management pod CIDR is trusted for management pod networking; it must not be reused as a tenant workload-node security profile. Unchanged firewall configuration is queried and does not cause another reload.
- Seed-only LB membership is established first. The seed becomes readable before joiners start. Final membership includes the three owned nodes. Readiness requires exactly the expected names, roles, RKE2 version and Ready conditions; the final API query goes through the fixed endpoint with CA verification, and 9345 is separately TLS-verified.
- After formation, the verified SSH channel exports a flattened management kubeconfig to the explicit private runtime output file. Only embedded CA/client certificate/key credentials survive; no exec, token, proxy or path hooks are accepted. The file fixes the API endpoint, is atomically created without replacing existing credentials, and is mode 0600. The Runner verifies the API and 9345 using its CA before recording a safe file digest and closing only journal-owned temporary SSH firewall/forwarding rules. Cleanup observes exact resource IDs and never replays ambiguous deletion. Credentials remain outside logs, journals and CI artifacts.
- Completed reconciles and inspections use the protected kubeconfig directly and do not recreate SSH. Missing/drifted credentials block recovery. Failed export/API verification retains the owned transport as pending; incomplete cleanup cannot report complete bootstrap.
- The `inspect` action performs remote reads only. Local journal/temporary trust files may be created. It never deploys a VM, changes LB/firewall state or configures a guest.

## Operator inputs

Runtime configuration is a private JSON file with exactly `plan`, `image`, `cloudstack`, `journal`, `operatorKeyFile`, `tokenFile`, `hosts`, `managementKubeconfigFile` and `providerBundle`.

| Object | Required inputs |
| --- | --- |
| `plan` | `bootstrapId`, `name`, `projectId`, `zoneId`, `networkId`, `serviceOfferingId`, `templateId`, `publicIpId`, three `hostIds`, explicit `apiSourceCidrs`, exact Runner `sshSourceCidrs` (/32, within approved API ranges) |
| `image` | `attestationFile`, detached `signatureFile`, operator-trusted `publicKeyFile` |
| `cloudstack` | HTTPS `endpoint`, protected `apiKeyFile`, protected `secretKeyFile`, verified `caFile` |
| `hosts` | Map from exact host UUID to approved `address`, `user` = `root`, protected `keyFile`, pinned `knownHostsFile` |
| `providerBundle` | Exact immutable bundle `directory`, `sha256` and `qualificationEnvironment=disposable-lab`; see the management installer README |
| Other | Private existing journal directory, stable protected Ed25519 operator key and strong RKE2 token files; explicit management kubeconfig output file in an existing private operator directory |

The image attestation requires `schemaVersion=1.0`, `artifactType=layersentry-rke2-node-image`, exact `templateId`, `os=rocky9`, `architecture=amd64`, `rke2Version=v1.36.4+rke2r1`, `qualificationStatus=LIVE_VERIFIED`, `rke2Installed=true`, `qemuGuestAgentInstalled=true`, `sshEnabled=true`, `selinuxEnforcing=true`, `sha256` and `qualificationEvidenceSha256`. Those values must come from the image release/qualification path, not be fabricated to pass preflight.

```bash
python3 tools/layersentry/k8s/bootstrap_management.py inspect --config /etc/layersentry/k8s/bootstrap-runtime.json
python3 tools/layersentry/k8s/bootstrap_management.py reconcile --config /etc/layersentry/k8s/bootstrap-runtime.json
```

A reconcile invocation advances bounded work and exits. Exit 2 reports pending formation/native work; exit 1 reports a blocker; exit 0 requires verified formation. Repeating the same protected configuration and journal observes existing operations. There is no automatic destructive rollback. Recover a failed/unknown native operation by its exact journal/resource identity; retain sufficient evidence before any separately authorized rebuild. Replacing a configuration/journal to bypass an unknown submission is not an approved retry.

## Exact artifact audit and remaining gaps

Upstream release metadata confirms RKE2 `v1.36.4+rke2r1` and its amd64 binary/core/Canal archives, CAPI `v1.13.5` core components, CAPRKE2 `v0.25.2` bootstrap/control-plane components, and CAPC `v0.6.1` infrastructure components. CAPI `v1.13.5` source defaults clusterctl's cert-manager dependency to `v1.21.1`. These are upstream candidates, not a LayerSentry-qualified provider installation. CAPC still requires the reviewed endpoint/volume-ownership downstream image. Flux also requires a selected, immutable release/catalog.

The coordinated CPU image builder is a separate task. At this checkpoint no qualified signed Rocky image attestation, native registered template, executable installed CAPI/Flux provider plane, completed three-node runtime formation, destructive recovery/upgrade test, or production failure-domain proof has been supplied. A same-host three-VM lab can prove functional formation; it cannot prove independent-host or independent-Site survival. The `productionCertified` output remains false even after a formation pass.

## Validation and handoff

Original source qualification: 27 management-bootstrap tests passed, covering native ambiguity/no replay, identity drift, job retention, exclusive journal locking, symlink/rebind rejection, scoped LB/firewall behavior, real OpenSSL signature/tamper/unqualified-image rejection, fixed embedded-program compilation, KVM/guest host-key binding, secret stdin separation, token drift, seed-before-join and read-only inspection. The full existing E source regression passed: 101 tests in total, including these 27 tests. No host, guest, CloudStack resource, storage or network mutation occurred during this source task.

Integration owns the shared ledger/knowledge-graph update, versioned approved runner delivery, actual image qualification and end-to-end Rocky/Chrome/Firefox evidence. DBaaS/APaaS and provider installation are not completed by management-node bootstrap.


## Transport and credential lifecycle correction

The initial source implementation assumed direct Runner access to an isolated guest IP; review found that no such route was guaranteed. The correction uses exact native `CreatePortForwardingRuleCmd` parameters (`publicport/publicendport`, `privateport/privateendport`, `virtualmachineid`, `vmguestip`, `networkid`, `openfirewall=false`) and `FirewallRuleResponse` binding fields. `ListPortForwardingRulesCmd`, `DeletePortForwardingRuleCmd`, `ListFirewallRulesCmd` and `DeleteFirewallRuleCmd` support read-before-delete without touching unrelated rules. Public forwarding requires the allocated endpoint to be routable from the approved Runner; inability to reach it remains a visible gate, not an assumed pass.

Protected inputs additionally reject unexpected owners and hardlinks. The management credential output requires a private, operator-owned existing directory. A completed journal stores only the kubeconfig digest and transport state. Subsequent provider installation consumes that runtime kubeconfig through its native tooling; installation is not performed by this bounded bootstrap.

Correction qualification: the full E regression passes 114 tests, including 40 focused offline bootstrap tests (27 original plus 13 new transport/credential/lifecycle tests). Tests cover foreign-rule rejection, exact VM/address/port binding, restricted source rules, ambiguous-delete no replay, mandatory escrow before cleanup, no private-IP fallback, no reopened forwarding after completion, kubeconfig hook/TLS bypass rejection, private exclusive output, unsafe owner/hardlink/symlink rejection, and authenticated-API-only completed reconciliation. No runtime credentials or live lab endpoints were used by the tests.

## Provider installation completion gate

The subsequent management installer source extends this lifecycle: protected kubeconfig export occurs after formation, but credential escrow completion and temporary SSH cleanup now wait for the bound provider bundle to be imported on all three nodes and native CAPI/CAPRKE2/CAPC plus cert-manager readiness to be observed. See [management installer contract](../../../../tools/layersentry/k8s/management/README.md). CCM stays unactivated and all production gates remain false. Historical validation counts above describe their original commits, not this later installer qualification.
