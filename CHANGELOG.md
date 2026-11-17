# Changelog

## 0.1.1 — 2026-11-18

- Extend the existing physical-firmware-query exclusion to include `APPLE_VIRTUAL` (chipset 6000), changing one conditional-branch byte.
- Retain the six-byte activation fix, explicit opt-in, exact Darwin restriction, full-page references, and unique-signature guards.
- Complete Reset and Bluetooth stack initialization in the tested macOS 15.4.1 VM; observe stable Bluetooth/audio/Hearing services for nearly 20 minutes.
- Record a strict six-minute acceptance window with no HCI initialization failures, HCI timeouts, reason-108 restarts, or related audio/Hearing Bluetooth XPC interruptions.
- Publish a source project with bilingual documentation, portable local reference generation, pinned dependencies, and synthetic guard testing. Keep private deployment configuration, Apple binaries, and generated full-page references out of source control.

Other host CPU peaks remain outside the verified fix. This version does not provide physical Bluetooth connectivity and does not broaden the tested OS/board configuration.

## 0.1.0 — 2026-11-18

- Initial experimental Lilu plugin for the reviewed macOS 15.4.1 daemon.
- Skip the local internal-diagnostics early return in virtual-controller activation.
- Require explicit `-btvirtfix`, exact Darwin 24.4.0, a validated executable page, the exact process path, full-page equality, and a unique reviewed signature.
- Observe successful HCI Reset after deployment, followed by an unsupported Read UHE query and continued reason-108 restarts. This version did not complete initialization.

The native transport argument and VMHide exception preceded the plugin and remain separately documented configuration requirements for the tested environment.
