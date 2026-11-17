# Design and exact target

BTVirtualFix addresses a specific failure chain in the native virtual Bluetooth implementation of the inspected macOS 15.4.1 daemon. It does not implement a Bluetooth controller in QEMU or add a physical transport.

## Failure chain and complete setup

In the tested no-hardware VM, the original configuration selected a physical controller path that could not initialize. The daemon also needed to recognize that it ran in a VM before using the built-in virtual implementation.

The complete tested setup has three parts:

1. `bt-transport-override=10` selects the native virtual transport.
2. The tested VMHide 1.1.3 process filter has an OpenCore memory-patch exception for `bluetoothd`, allowing that process to observe VM presence. Other VMHide process filters stay as configured.
3. BTVirtualFix, enabled by `-btvirtfix`, addresses two remaining initialization blockers.

Changing the transport argument alone did not complete initialization. Nor did adding a temporary QEMU USB test device solve this VM's selection and initialization path. That prototype is outside this project's implementation.

The VMHide exception is conditional on actually using the reviewed VMHide build. It changes the unique `bluetoothd` NUL-terminated filter entry to the equal-length `btvm_nohit` entry in VMHide's loaded image. It is not a modification to VMHide on disk, and it is not a global request to expose VM detection to every process. A VM without VMHide does not need that specific exception, but such a configuration has not been covered by the reported runtime test.

The tested VMHide executable SHA-256 is:

```text
fe6bf5a2087966cd93d91176179eaae51fe44ccc5a92907ca67d48f0471f1bbe
```

The upstream VMHide source recorded a kernel-panic concern near its `bluetoothd` filter. The reported successful boot is evidence for the single tested combination, not proof that removing that filter is safe across other configurations.

## Two initialization changes

| Change | Original behavior | Patched behavior | Bytes changed |
| --- | --- | --- | --- |
| `BTVCLinkController::activate` | An internal-diagnostics condition can return before creating the LinkAgent | Skip that local early return and retain later feature/framework checks | 6 |
| Read UHE / firmware query | An existing exclusion includes chipsets 5000–5999 but misses virtual chipset 6000 | Change one `jb` to `jbe`, including exactly the boundary value 6000 | 1 |

The second change reuses an existing “continue initialization without this query” path. It does not fabricate a firmware response or register vendor-command callbacks for a physical chipset.

The activation-only 0.1.0 trial completed Reset but then failed the unsupported Read UHE query with `STATUS3601` and restart reason 108. Version 0.1.1 adds the boundary correction; the resulting observed boot reached `Stack initialization complete`.

The tested MacPro7,1 board ID, `Mac-27AD2F918AE68F61`, makes the inspected Lighthouse capability false. No Lighthouse patch is included. Other board IDs may follow additional initialization paths and require separate analysis.

## Binary identity

| Property | Value |
| --- | --- |
| OS build | `24E263` |
| Kernel | Darwin `24.4.0` |
| Architecture | x86_64 |
| Target path | `/usr/sbin/bluetoothd` |
| x86_64 Mach-O UUID | `4FF3B4DD-BCB2-3A24-A026-BF49E69B76E4` |
| Universal SHA-256 | `ac139b25e538e1e6672ff09a064198bcabda4a6eb1e1f5cd00fa53636380d348` |
| x86_64 slice SHA-256 | `5bbdbf61bccb453da4c37e6e9c71909c1e64b8d286917c0bb37c015caced801e` |

The build verifies the full universal input, its x86_64 slice, UUID, signatures, and page hashes before generating the local references. Complete Apple binaries and reference pages are not tracked in this repository.

| Reference page | Universal offset | x86_64 slice offset | Original page SHA-256 |
| --- | --- | --- | --- |
| Activation | `0x414000` | `0x410000` | `60c52b5c1957da4228a45716f3e3e89a3827b4667f60dfa043bdc0ac6b8f16b7` |
| Read UHE | `0x148000` | `0x144000` | `0aaad511812bf37c17c73bb90b14bfa6343e9182bedca7941b28348e97d5d407` |

The activation change affects page offsets `0xF64`–`0xF69`. The Read UHE change affects page offset `0x2FF` (`0x72` → `0x76`).

## Runtime guards

The plugin uses Lilu's long-route mechanism around `_cs_validate_page`. The chained original function executes first. Only then can the plugin inspect and change a page.

A page must satisfy all of these conditions:

- Explicit opt-in is active and the kernel is exactly Darwin 24.4.0.
- The resolved vnode path is exactly `/usr/sbin/bluetoothd`.
- The callback file offset matches a reviewed universal-file page offset; the thin-slice offsets are not accepted there.
- The supplied page is exactly 4096 bytes and the original validator marked it validated, untainted, and executable.
- All 4096 original bytes match the generated reference.
- The reviewed signature occurs exactly once, at its expected location.

Only the differing bytes are written. Validation outputs, surrounding page bytes, Apple files on disk, and SIP settings are not rewritten by the plugin. A rejected page remains unchanged. The pages are handled separately: accepting one does not guarantee that the other will be accepted.

`-btvirtfixoff` is the Lilu plugin disable argument. It is useful for diagnosis but does not undo other configuration changes described above.

## Limits

The native virtual implementation is not a complete substitute for wireless hardware. Static review found limitations in unused ISO-related response fields and an optional stored-key response path; these did not block the tested initialization path. No physical Bluetooth protocol, RF, pairing, or audio interoperability claim is made.

Exact version and page guards deliberately reject unreviewed code. That does not make an OS update automatically compatible: the retained transport settings can still leave Bluetooth unable to initialize when the plugin declines to patch. Revalidate or restore the complete prior configuration before moving to an unsupported OS.
