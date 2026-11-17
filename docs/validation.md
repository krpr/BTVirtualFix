# Runtime validation record

This is a sanitized summary of a single-machine experiment performed on November 18, 2026. It retains measured outcomes and their limits. It does not include private EFI configuration, machine identifiers, network addresses, complete logs, or Apple binaries.

## Test environment

- macOS 15.4.1 (`24E263`), Darwin 24.4.0, x86_64.
- OpenCore 1.0.8; Lilu 1.7.2; VMHide 1.1.3 with the documented process-specific exception.
- MacPro7,1, board ID `Mac-27AD2F918AE68F61`.
- QEMU 10.2.1 / libvirt 12.0.0; guest 4 vCPUs and 8 GiB RAM; host 16 logical CPUs.
- No physical Bluetooth device. The pre-existing `SkipBluetoothAutomaticFirmwareUpdate` marker was retained.
- BTVirtualFix 0.1.1 with `bt-transport-override=10 -btvirtfix`.

These observations validate this combination only. A newly built bundle and a different VM still require their own boot and runtime checks.

## Service acceptance

| Observation | Result |
| --- | --- |
| HCI Reset (`0x0C03`) | Completed with status 0 |
| Bluetooth stack | `Stack initialization complete` |
| 40 service snapshots | Bluetooth, audio, and Hearing services retained their process IDs; each reported one launch |
| Final follow-up | Same service processes still running nearly 20 minutes after launch |
| Bluetooth process CPU at final follow-up | 1.61 cumulative CPU seconds over 19 minutes 40 seconds of process lifetime |
| Bluetooth status query | Returned successfully in 0.560 seconds; `APPLE_VIRTUAL`, state `on` |

In the strict six-minute host-observation window, the following counts were all zero:

- HCI initialization failures and HCI timeouts.
- Read UHE failures and reason-108 restarts.
- Related audio/Hearing-to-Bluetooth XPC interruptions.

The whole boot was not free of every diagnostic message. One `ReadLocalVersionInformation failed STATUS408, but we move forward` message was followed by successful continuation and stack completion. One XPC connection rebuild was traced to `bluetoothd` → `trustd`, not to the audio/Hearing retry chain. These were not classified as fatal initialization failures.

A responsive virtual-controller query demonstrates service responsiveness; it does not demonstrate wireless connectivity.

## Host CPU observations

“One core” percentages use 100% for one logical CPU. “Whole host” percentages use 100% for all 16 logical CPUs. The guest has four vCPUs. Mixing these units can make the same workload appear 16 times larger or smaller.

The first observation lasted 360 seconds with 0.25-second thread samples and approximately one-second process CPU counters.

| Metric | Whole-host share |
| --- | ---: |
| macOS QEMU average | 3.375% |
| macOS QEMU 0.25-second peak | 21.502% |
| Whole-host average busy | 13.720% |
| Whole-host 0.25-second peak busy | 63.520% |
| Sampler average overhead | 0.545% |

At the largest whole-host peak, two other VMs together consumed approximately 49.950% of host capacity; macOS contributed 0.878%. That peak cannot be attributed to this Bluetooth initialization failure chain.

A later 120-second synchronized observation showed guest system activity correlated with QEMU activity and a declining load over time. The final minute averaged 1.658% of host capacity for QEMU, with a 0.25-second peak of 4.802%. It did not show a stable recurrence of the original approximately 32-second Bluetooth retry pattern.

Guest process attribution had limitations: root-owned processes were not all readable through the unprivileged process API, a supplemental `ps` capture missed the first 56 seconds, and short-lived processes or kernel work were not completely attributable. Missing entries were not treated as zero CPU. The visible data did not justify disabling `warmd`, `trustd`, `bluetoothd`, or `coreaudiod`.

After guest sampling ended, a separate 45.031-second observation found 8.88 QEMU CPU seconds: 19.720% of one core, or **1.232% of the whole host**. KVM halt-poll counters accumulated 0.336 seconds of elapsed time. These counters can include preemption time and are not interchangeable with thread CPU time; they were not subtracted from QEMU CPU usage. Global KVM parameters were not changed.

## What this establishes

The observed native-controller initialization and daemon restart loop stopped, and the dependent services remained stable within the measured windows. Other short host CPU peaks remained. No matched historical baseline exists for a controlled CPU-improvement percentage, and the observation windows and sampling overhead differ.

The private original build passed 44 ASan/UBSan page-guard assertions before deployment. The CI template uses synthetic reference pages so it can exercise the guard logic without distributing Apple code. A successful run of the synthetic CI template is not a runtime compatibility result, and it does not replace building against the exact input and testing a recoverable VM.

## Reproduction checklist

1. Record OS build, kernel, architecture, model, dependency versions, and the exact target binary hashes.
2. Confirm the effective boot arguments and intended OpenCore entry after reboot.
3. Capture only the current boot's initialization sequence and check for stack completion.
4. Observe service process IDs and launch counts over a bounded interval.
5. Separate expected startup diagnostics from initialization failures and relevant client retry loops.
6. Measure the target QEMU process and whole host together, identifying other workloads and collector overhead.
7. Report remaining peaks and missing process coverage explicitly; preserve a recovery route throughout testing.

Do not publish raw serial numbers, addresses, full EFI files, credentials, or complete Apple binaries when reporting a result.
