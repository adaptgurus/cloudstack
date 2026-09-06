# Native backup restore start policy revalidation

Status: `SOURCE_COMPLETE` for this bounded source-contract audit; live restore remains `NOT_TESTED`.

The API class description says that `createVMFromBackup` automatically starts the VM. That describes its default and is insufficient to determine explicit `startvm=false` behavior. The current acceptance adapter and `NativeNasRecoveryProvider` correctly send `startvm=false` and require a stopped clone; no implementation change is needed.

The exact retained CloudStack 4.22.1.1 source establishes the complete path:

- `api/src/main/java/org/apache/cloudstack/api/command/user/vm/CreateVMFromBackupCmd.java` extends `BaseDeployVMCmd` and delegates execution to `restoreVMFromBackup`.
- `BaseDeployVMCmd.java:198` declares the inherited `START_VM` parameter. Its getter at line 598 returns the supplied false value; only absence defaults to true.
- `server/src/main/java/com/cloud/vm/UserVmManagerImpl.java:9812` sets `ReturnAfterVolumePrepare=true` for the first apparent start call. `engine/orchestration/src/main/java/com/cloud/vm/VirtualMachineManagerImpl.java:1507` handles that flag by preparing volumes, transitioning the VM to `Stopped` and returning before guest startup.
- `UserVmManagerImpl.java:9847` guards the final actual start with `cmd.getStartVm()`. The explicit false therefore leaves the restored clone stopped.

The misleading default description was compared against the inherited parameter, accessor, orchestrator early-return path and final conditional before changing any code. The proposed unconditional-autostart interpretation was rejected and communicated to the native-fixture owner. Existing source tests retain the stopped-clone contract; those tests are not a substitute for the pending exact native API/host/guest verification. Recovery network isolation must still precede any later explicit guest start, and source/backup metadata must remain retained.
