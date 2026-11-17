# Build, install, verify, and roll back

This procedure is for an experimental source build targeting macOS 15.4.1 (`24E263`), Darwin 24.4.0, x86_64. Only the configuration in the README has runtime evidence. The repository does not provide a cross-machine EFI installer or choose your startup partition for you.

## 1. Confirm the target and prepare recovery

Keep a working recovery boot path and back up the current OpenCore configuration and affected kexts before changing them. For a VM, a complete backup of the boot image is useful in addition to individual EFI files. Create or restore a directly copied boot-image backup only with the VM stopped; do not overwrite a live qcow2 image.

Record the actual startup EFI partition identity. Disk numbers can change after reboot. Do not assume an EFI mounted at `/Volumes/EFI` is the one the VM uses.

On the intended guest, run the optional read-only checker:

```sh
python3 scripts/check_target.py
```

After you have identified and mounted the correct EFI, it can inspect that OpenCore directory as well:

```sh
python3 scripts/check_target.py --oc-dir /Volumes/EFI/EFI/OC
```

The path is an example and must match your actual mount. The checker does not modify or mount EFI. Omitting `--oc-dir` leaves EFI unchecked. With `--oc-dir`, it checks relevant dependency identities and conflicts; it does not certify that every installation step or boot-argument merge is complete. A successful check is not a boot test or a proof that the firmware selected that EFI.

Check the tested kernel, OS build, architecture, complete daemon hash, model/board ID, Lilu version, and VMHide build if used. Unknown configurations need review; do not remove a version or hash guard merely to make a check pass.

## 2. Build from the exact supported binary

Use macOS with full Xcode and Python 3:

```sh
python3 scripts/bootstrap.py
bash build.sh --bluetoothd /path/to/supported/bluetoothd
```

Supply an unmodified universal daemon from the supported guest. Do not use a different build's daemon just because its filename is the same. The build extracts and verifies the x86_64 slice and generates ignored reference pages locally.

The result is:

```text
build/Release/BTVirtualFix.kext
```

Inspect the local build log and manifests. The project records build identity; a successful build does not establish runtime compatibility. To exercise guards without an Apple binary, use `python3 scripts/test_guards.py --synthetic`; that mode cannot produce a production kext.

## 3. Copy the bundle and merge the OpenCore settings

Work on a backed-up copy of your configuration first. Use [`examples/opencore-fragment.plist`](../examples/opencore-fragment.plist) as a reference for the entries to merge. It is a fragment, not a bootable replacement configuration.

Copy the built bundle into the verified EFI under:

```text
EFI/OC/Kexts/BTVirtualFix-v0.1.1.kext
```

The source bundle is named `BTVirtualFix.kext`; the versioned name above is the installation directory used by the example. Add one enabled `Kernel/Add` entry with that exact `BundlePath`, `Arch = x86_64`, and both `MinKernel` and `MaxKernel` set to `24.4.0`. Keep it after the enabled Lilu dependency. If upgrading an existing BTVirtualFix entry, update that entry rather than loading two versions. Keep prior files in the backup until verification succeeds.

Append these to the existing boot arguments, preserving unrelated settings:

```text
bt-transport-override=10 -btvirtfix
```

Resolve any older contradictory `bt-transport-override` value instead of leaving duplicate values. Ensure the effective NVRAM boot arguments will actually be updated using your established OpenCore configuration. The fragment shows the relevant `NVRAM/Add` value and `NVRAM/Delete` boot-args key; merge these with existing keys rather than replacing the whole NVRAM section.

### VMHide condition

The native controller must see the VM environment. The reviewed VMHide 1.1.3 build filters `bluetoothd`, so the tested configuration needs the narrowly scoped `Kernel/Patch` entry in [`examples/vmhide-1.1.3-exception.plist`](../examples/vmhide-1.1.3-exception.plist). This is a separate, conditional fragment; it is not part of the basic kext/boot-argument fragment. Use it only after confirming the reviewed VMHide executable hash and matching unique filter string; the exact identity is documented in [design.md](design.md).

This exception replaces `bluetoothd` plus its trailing NUL with the equal-length `btvm_nohit` plus NUL in VMHide's loaded image. Its identifier is `org.Carnations.VMHide`, its count is one, and its kernel bounds are `24.4.0`. It leaves VMHide's other process filters as configured.

If VMHide is absent, do not add an irrelevant patch. That is not a claim that an untested no-VMHide configuration is validated. Similarly, a different VM-detection filter needs its own analysis. The ordinary `sysctl kern.hv_vmm_present` command can still report a hidden VM because this exception applies only to `bluetoothd`; that command alone cannot verify the exception.

The tested machine already had `/etc/bluetool/SkipBluetoothAutomaticFirmwareUpdate`; that marker was retained. Its presence alone is not the repair described here. Keep Bluetooth and audio services enabled, and preserve existing SIP and dependency settings.

## 4. Validate before rebooting

Use the official `ocvalidate` matching your installed OpenCore version against the complete proposed configuration. Review the diff against your backup, including the kext load order, kernel bounds, boot arguments, and conditional VMHide exception. Confirm the copied bundle matches your local build manifest and that only one BTVirtualFix entry is enabled.

The tested original configuration used OpenCore `Vault = Optional`. A signed or secured vault needs its normal update procedure; this project does not rebuild a vault or instruct you to lower that setting. Do not transplant another machine's full configuration, identifiers, or boot image.

Once the configuration is validated and recovery is available, install the reviewed configuration using your normal EFI maintenance procedure, then reboot. The project scripts do not reboot the machine automatically.

## 5. Verify the current boot

Confirm the kernel/build and effective boot arguments. Then look for the sequence:

```text
HCI Reset 0x0C03 completes with status 0
Stack initialization complete
```

Check that `bluetoothd`, `coreaudiod`, and the relevant Hearing service remain stable rather than repeatedly changing process IDs or launch counts. Check for a recurring HCI failure, timeout, reason-108 exit, or related audio/Hearing Bluetooth XPC interruption in the current boot.

A bounded query can confirm service responsiveness:

```sh
system_profiler -json -detailLevel mini -timeout 15 SPBluetoothDataType
```

The validated configuration reported `APPLE_VIRTUAL`, state `on`. That is a virtual-controller service result, not a wireless capability test.

Measure CPU only after confirming initialization, and distinguish the target QEMU process from other host workloads. Do not disable Bluetooth/audio services to hide a failed initialization. The [validation record](validation.md) describes what passed and what remained unresolved.

## Full rollback

The complete setup spans three settings. Disabling only the plugin can leave the native controller selected but unable to initialize.

If the guest remains accessible, restore the pre-change configuration and affected files from your own backup, or carefully reverse only these changes while preserving later unrelated edits:

1. Remove or disable the BTVirtualFix `Kernel/Add` entry and remove its `-btvirtfix` opt-in argument.
2. Restore the original Bluetooth transport boot argument state, including removal of the added `bt-transport-override=10` when it was not present before this setup.
3. Remove the VMHide `bluetoothd` exception added for this setup, returning that filter to its original state.

Validate the complete configuration and reboot. Inactive kext files may remain until recovery is confirmed; do not remove a file that is still referenced by an enabled entry. Retain any pre-existing firmware-skip marker and unrelated settings according to the original backup.

`-btvirtfixoff` stops this plugin only. It is a diagnostic disable switch, not a full rollback of the three-part setup. Returning only to 0.1.0 also returns to the observed Read UHE failure; it is not the same as restoring the original configuration.

If the guest cannot boot, stop the VM completely and select or restore the verified backup boot image through the host's normal recovery procedure. Never replace an image while QEMU is using it. This restores a known boot path; it does not promise that the original no-hardware Bluetooth issue disappears.
