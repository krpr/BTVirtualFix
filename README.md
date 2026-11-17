# BTVirtualFix

[简体中文](README.zh-CN.md)

An experimental Lilu plugin that lets the native virtual Bluetooth controller finish initialization on an exact macOS VM configuration without physical Bluetooth hardware.

**Version 0.1.1 completed initialization and stopped the observed `bluetoothd` restart loop on one tested VM.** It does not create a Bluetooth radio, implement a QEMU USB Bluetooth device, or resolve every source of host CPU spikes.

## Tested configuration

| Component | Tested value |
| --- | --- |
| Guest | macOS 15.4.1, build `24E263`, x86_64 |
| Kernel | Darwin `24.4.0` |
| Bootloader | OpenCore 1.0.8 |
| Lilu | 1.7.2 |
| VM detection filter | VMHide 1.1.3, with a narrowly scoped exception for `bluetoothd` |
| Model / board ID | MacPro7,1 / `Mac-27AD2F918AE68F61` |
| Virtualization | QEMU 10.2.1 / libvirt 12.0.0; 4 vCPUs, 8 GiB RAM |
| Bluetooth hardware | None |

This is a tested configuration, not a general compatibility matrix. The plugin requires an exact kernel version and exact original code pages. The build also checks the complete target binary. Other macOS builds, architectures, board IDs, and dependency versions have not been validated.

## What it changes

The tested setup selects Apple's native virtual transport with `bt-transport-override=10` and lets `bluetoothd` see that it runs in a VM. The plugin then makes two changes to validated in-memory pages of `/usr/sbin/bluetoothd`:

1. Skip a local internal-diagnostics early return that prevented the virtual controller's LinkAgent from activating: **6 bytes**.
2. Include `APPLE_VIRTUAL` (chipset 6000) in an existing branch that skips a physical firmware query unsupported by that controller: **1 byte**.

The plugin requires `-btvirtfix`. It calls the existing code-page validator first, preserves its validation outputs, and rejects a page unless its contents, location, signature, and process path match the reviewed target. Apple files on disk are not modified. The two pages are handled independently; there is no atomic two-page transaction.

See [design and exact target](docs/design.md).

## Build

Use macOS with full Xcode and Python 3. Provide an unmodified universal `/usr/sbin/bluetoothd` from the supported guest. The build machine may use a different macOS version, but its own daemon will usually not match.

```sh
git clone https://github.com/krpr/BTVirtualFix.git
cd BTVirtualFix
python3 scripts/bootstrap.py
bash build.sh --bluetoothd /path/to/supported/bluetoothd
```

The build produces `build/Release/BTVirtualFix.kext` and local manifests. This source repository does not distribute Apple binaries, complete Apple reference pages, or a prebuilt kext. Reference pages are generated locally from the verified input and are ignored by Git.

Guard tests can run without an Apple binary:

```sh
python3 scripts/test_guards.py --synthetic
```

Run Python helper tests with `python3 -m unittest discover -s tests -p 'test_*.py' -v`. Synthetic guard tests exercise the page guards and byte changes. They do not establish compatibility with an actual macOS binary or validate a boot.

The [GitHub Actions template](ci/README.md) is included but not enabled. All checks above passed locally; a GitHub-hosted run has not yet been verified.

## Install and verify

Read the [installation and full rollback guide](docs/installation.md) before editing EFI. Use the [OpenCore fragment](examples/opencore-fragment.plist) as a merge reference, not as a replacement `config.plist`. The original machine-specific installer is intentionally not a general installer for other systems.

The optional checker reads the target system without changing it:

```sh
python3 scripts/check_target.py
python3 scripts/check_target.py --oc-dir /Volumes/EFI/EFI/OC
```

Without `--oc-dir`, the checker does not inspect EFI configuration. Even a successful check does not prove that the firmware boots from the inspected EFI or that the next boot will work.

Keep Bluetooth and audio services enabled. Verify `Stack initialization complete`, stable service lifetimes, and absence of the former HCI failure/restart sequence. A reported `APPLE_VIRTUAL` controller does not provide wireless pairing or audio transport.

## Observed result

In the November 18, 2026 validation, the Bluetooth stack completed initialization and the Bluetooth/audio/Hearing service processes remained stable for nearly 20 minutes. A strict six-minute window contained no HCI initialization failures, HCI timeouts, reason-108 restarts, or related audio/Hearing Bluetooth XPC interruptions.

Host CPU still had other short peaks. In the six-minute window, this VM averaged **3.375% of a 16-thread host**, with a **21.502%** peak at 0.25-second resolution. After guest sampling ended, a separate 45-second observation averaged **1.232%**. These are different windows, not a controlled before/after comparison. The largest whole-host spike was mostly attributable to two other VMs.

See the [sanitized validation record](docs/validation.md) for method, overhead, and limitations. Do not infer a general CPU reduction percentage from these observations.

## Maintenance

Revalidate before updating macOS or changing the tested configuration. This version does not adapt itself to a new binary. `-btvirtfixoff` disables the plugin; it does not undo the native-transport setting or the VMHide exception. Use the full rollback procedure when returning to the original configuration.

Contributions should identify the exact OS build, binary hashes, initialization behavior, and regression tests. Do not submit serial numbers, personal EFI configurations, credentials, or unredacted logs.

[Changelog](CHANGELOG.md) · [License](LICENSE) · [Third-party notices](NOTICE.md)
