#!/usr/bin/env python3
"""Read-only prerequisite checks; never mount EFI, edit NVRAM, or install files."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_reference import load_target, verify_binary

TESTED_BOARD = "Mac-27AD2F918AE68F61"
VMHIDE_SHA = "fe6bf5a2087966cd93d91176179eaae51fe44ccc5a92907ca67d48f0471f1bbe"
APPLE_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=15).strip()


def virtual_machine_present():
    library = ctypes.CDLL(None)
    function = library.sysctlbyname
    function.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                         ctypes.c_void_p, ctypes.c_size_t]
    function.restype = ctypes.c_int
    value = ctypes.c_int()
    size = ctypes.c_size_t(ctypes.sizeof(value))
    if function(b"kern.hv_vmm_present", ctypes.byref(value), ctypes.byref(size), None, 0):
        return None
    return value.value == 1


def evaluate_platform(detected, target):
    errors = []
    for key, expected in (("system", "Darwin"), ("architecture", target["architecture"]),
                          ("darwin", target["darwin"]), ("build", target["build"]),
                          ("board_id", TESTED_BOARD)):
        if detected.get(key) != expected:
            errors.append("Unsupported or unverified {} (expected {}).".format(key, expected))
    if detected.get("virtual_machine") is not True:
        errors.append("The native virtual transport requires visible VM detection.")
    return errors


def bundle_files(oc, entry):
    name = entry.get("BundlePath", "")
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Invalid enabled kext bundle path in the supplied configuration.")
    directory = oc / "Kexts" / name
    # Refuse config paths that resolve outside this EFI/OC directory.
    try:
        directory.resolve().relative_to(oc.resolve())
    except ValueError:
        raise ValueError("An enabled kext resolves outside the supplied OpenCore directory.")
    info = plistlib.loads((directory / "Contents/Info.plist").read_bytes())
    return directory, info


def inspect_oc(oc):
    config = plistlib.loads((oc / "config.plist").read_bytes())
    entries = config.get("Kernel", {}).get("Add", [])
    results, errors = {}, []
    args = config.get("NVRAM", {}).get("Add", {}).get(APPLE_GUID, {}).get("boot-args", "")
    if not isinstance(args, str):
        raise ValueError("OpenCore boot-args must be a string.")
    tokens = args.split()
    if "vmhState=strict" in tokens:
        errors.append("VMHide strict mode is outside the reviewed configuration.")
    if any(t.startswith("bt-transport-override=") and t != "bt-transport-override=10" for t in tokens):
        errors.append("An existing Bluetooth transport override conflicts with the virtual transport.")
    results["virtual_transport_configured"] = "bt-transport-override=10" in tokens
    results["plugin_opt_in_configured"] = "-btvirtfix" in tokens
    results["plugin_opt_out_configured"] = "-btvirtfixoff" in tokens
    if results["plugin_opt_out_configured"]:
        errors.append("-btvirtfixoff disables the plugin; review it before installation.")
    found = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("Enabled"):
            continue
        directory, info = bundle_files(oc, entry)
        identifier = info.get("CFBundleIdentifier", "")
        if identifier in ("as.vit9696.Lilu", "org.Carnations.VMHide", "org.lotten.BTVirtualFix"):
            found.setdefault(identifier, []).append((directory, info))
    lilu = found.get("as.vit9696.Lilu", [])
    if len(lilu) != 1 or lilu[0][1].get("CFBundleVersion") != "1.7.2":
        errors.append("Expected one enabled Lilu 1.7.2 dependency; other versions are unverified.")
    else:
        results["lilu_version"] = "1.7.2"
    vmhide = found.get("org.Carnations.VMHide", [])
    results["vmhide_enabled"] = bool(vmhide)
    if len(vmhide) > 1:
        errors.append("Multiple enabled VMHide bundles require manual review.")
    elif vmhide:
        directory, info = vmhide[0]
        data = (directory / "Contents/MacOS/VMHide").read_bytes()
        matched = (info.get("CFBundleVersion") == "1.1.3" and
                   hashlib.sha256(data).hexdigest() == VMHIDE_SHA and
                   data.count(b"bluetoothd\0") == 1)
        results["vmhide_matches_reviewed_binary"] = matched
        if not matched:
            errors.append("VMHide differs from the binary reviewed for the example exception.")
    if len(found.get("org.lotten.BTVirtualFix", [])) > 1:
        errors.append("Multiple BTVirtualFix versions are enabled.")
    return results, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oc-dir", type=Path, help="Optional, already mounted EFI/OC directory")
    options = parser.parse_args()
    target = load_target()
    detected = {"system": platform.system(), "architecture": platform.machine(),
                "darwin": platform.release()}
    errors = []
    if detected["system"] == "Darwin":
        try:
            detected["build"] = command("/usr/bin/sw_vers", "-buildVersion")
            data = command("/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice")
            board = re.search(r'"board-id"\s*=\s*<"([^"]+)"', data)
            detected["board_id"] = board.group(1) if board else None
            detected["virtual_machine"] = virtual_machine_present()
        except (OSError, subprocess.SubprocessError, AttributeError):
            errors.append("Could not read all platform prerequisites.")
    errors.extend(evaluate_platform(detected, target))
    binary_matches = False
    if detected["system"] == "Darwin":
        try:
            verify_binary(Path(target["path"]).read_bytes(), target)
            binary_matches = True
        except (OSError, ValueError):
            errors.append("The local bluetoothd does not match the exact reviewed executable.")
    else:
        errors.append("Run this checker inside the target macOS guest.")
    result = {"read_only": True, "detected": detected, "bluetoothd_matches": binary_matches,
              "efi_checked": options.oc_dir is not None, "errors": errors}
    if options.oc_dir is not None:
        try:
            result["opencore"], oc_errors = inspect_oc(options.oc_dir)
            errors.extend(oc_errors)
        except (OSError, ValueError, plistlib.InvalidFileException, TypeError, AttributeError):
            errors.append("Could not inspect the supplied OpenCore configuration and enabled bundles.")
    result["status"] = "prerequisites_match" if not errors else "unsupported_or_incomplete"
    result["scope"] = ("Read-only prerequisites only. This does not validate an installation, "
                       "EFI selection, configuration merge, runtime stability, or radio functionality.")
    if options.oc_dir is None:
        result["note"] = "EFI dependencies were not checked; optionally supply --oc-dir."
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
