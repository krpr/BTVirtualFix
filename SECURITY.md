# Security and compatibility reports

BTVirtualFix is experimental kernel extension code. Version 0.1.1 has been
observed on one x86_64 macOS 15.4.1 build 24E263 configuration. There is no
general support commitment for other builds or platforms.

The exact process path, Darwin version, validation result, file offset,
complete original page, and unique patch signature are part of the safety
boundary. A proposal that weakens any of these checks needs explicit review;
failure to patch an unsupported system is expected behavior.

For a suspected security defect, use the repository's private vulnerability
reporting option if it is available. If it is unavailable, open a minimal
issue requesting private coordination and omit exploit details and sensitive
data until a private channel is agreed. No response-time guarantee is offered.

Ordinary compatibility and build failures can use the bug report template.
Include the exact OS build, kernel version, plugin version, and minimal relevant
output. Remove addresses, usernames, serial numbers, EFI identifiers, device
identifiers, and tokens. Do not attach full OpenCore configurations, Apple
binaries, generated reference pages, complete logs, or disk images.

Keep a known-good boot configuration and recovery path before testing. Disabling
the plugin alone is not a complete rollback of the native virtual transport
configuration; follow [the installation and rollback guide](docs/installation.md).
