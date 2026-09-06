# Package BFF and durable lifecycle source checkpoint

Status: SOURCE_COMPLETE / local tests only. Production certified: false.

The package service is connected to the authenticated BFF and protected runtime
catalog configuration. It shares durable project/cluster reservations with
cluster creation, scaling and deletion, including unresolved UNKNOWN outcomes.
Immutable accepted catalog history and Cluster UID are reconciled before native
Flux writes. Full-profile native ownership survives unrelated catalog additions;
modified profiles or added Helm values/overrides do not pass readiness checks.

Review found and corrected dependency reservation deadlock, lost-receipt retries,
catalog revision lifecycle breakage and additive spec drift. The exact Flux
2.9.5 release schema SHA-256 is
`cc3dcd743af16215838b6937e1fce83745bf24c0dcc6c59737c59df15429caaf`.
The only applicable additive default is OCIRepository `spec.provider=generic`;
absent chart/verification parent objects are not synthesized.

Local full Kubernetes suite: 179 tests passed, one environment-dependent Nginx
skip. Tests include a concurrent SQLite acceptance race, accepted request restart
after an ambiguous native create, cluster replacement before the first write,
historical approved catalog uninstall, dependency/dependent admission, exact
spec drift rejection, authenticated operation observation and preserving a
cluster while its package resources remain. These are source-level simulations,
not a running operator, database, GUI, restore or production certification.

Earlier combined source `2b7f06773216d76c455be1ab32d483cebbd38804` passed exact
Rocky container workflow `34056716860`; it does not include this package BFF
continuation. The next combined source requires its own Rocky qualification.
