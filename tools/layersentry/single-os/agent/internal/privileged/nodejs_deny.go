package privileged

// Node.js lifecycle is module-stream aware and is deliberately isolated behind
// internal/nodeexec. Remove it from the generic AppStream allowlist at package
// initialization so repoquery/install/remove requests for nodejs are rejected
// by the core helper even though older source tables still mention the package.
func init() {
	delete(appstreamPackages, "nodejs")
}
