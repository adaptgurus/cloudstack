# Confined QGA public host-key export contract

Reader status: `SOURCE_COMPLETE`; image exporter and live confined-QGA access
must be qualified by the coordinated CPU image workstream. This checkpoint
does not assert that the current image is qualified or production ready.

The CPU image boot audit reports that Rocky's vendor SELinux policy labels
the SSH public host key `sshd_key_t`, alongside private key material. Broad
QGA unconfined/SSH-management booleans and relabeling vendor key paths are not
part of this change. In particular, changing the original public key to a
generic type could interfere with confined key regeneration.

The image-owned post-cloud-final service exports only
`/etc/ssh/ssh_host_ed25519_key.pub` to
`/usr/share/layersentry/node-image/ssh_host_ed25519_key.pub`. The exporter must
run after host-key generation on every boot, atomically replace a regular
root:root 0644 public file, and preserve vendor private key labels/permissions.
The image builder must remove any export before sealing. Parent directories
must be real root-owned directories without group/other write permission.
The image agent owns SELinux label/access and first-boot evidence.

The fixed bootstrap reader now reads only that exact export, validates all
parents, opens with `O_NOFOLLOW|O_NONBLOCK`, checks the opened descriptor for
regular type/root ownership/single link/bounded size/non-writable mode, and
accepts only one line. It never falls back to `/etc/ssh` or any private path.
The existing host instance-name → VM UUID → QGA binding remains intact; strict
guest SSH proves the corresponding private key before delivering credentials.
A stale or incorrect export therefore blocks SSH instead of bypassing trust.

Source qualification passed 44 focused tests: the existing 40 bootstrap and
transport tests plus four export-reader tests covering unsafe ownership,
writable/link parents, hardlinks, special/oversized files, missing/symlink
exports, fixed path/no fallback and multiline rejection. No guest or host
operation was performed. This reader change is separate from provider bundle
build source `87cc2c84ef`; the immutable bundle bytes are unchanged.
