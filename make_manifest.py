#!/usr/bin/env python3
"""Record a local build without embedding machine paths or runtime claims."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "build/Release/BTVirtualFix.kext"
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap import check_all


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = sorted(p for p in BUNDLE.rglob("*") if p.is_file())
    if [p.relative_to(BUNDLE).as_posix() for p in files] != ["Contents/Info.plist", "Contents/MacOS/BTVirtualFix"]:
        raise ValueError("Built bundle is missing files or contains unexpected files")
    if any(p.is_symlink() for p in BUNDLE.rglob("*")):
        raise ValueError("Built bundle must not contain symlinks")
    dependencies = check_all()
    info = plistlib.loads((BUNDLE / "Contents/Info.plist").read_bytes())
    reference = json.loads((ROOT / "reference-manifest.json").read_text())
    if digest(ROOT / "Sources/ReferencePage.hpp") != reference.get("generated_header_sha256"):
        raise ValueError("Generated reference header differs from the verified manifest")
    sources = []
    for directory in ("Sources", "scripts", "tests"):
        sources += [p for p in (ROOT / directory).rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts]
    sources += [ROOT / name for name in ("BTVirtualFix.xcodeproj/project.pbxproj", "prepare_reference.py",
                "build.sh", "make_manifest.py", "targets.json", "dependencies.lock.json")]
    manifest = {
        "status": "LOCAL BUILD ONLY; this artifact has not been installed or runtime-validated",
        "bundle_identifier": info["CFBundleIdentifier"], "bundle_version": info["CFBundleVersion"],
        "bundle_path": BUNDLE.relative_to(ROOT).as_posix(),
        "files": {p.relative_to(BUNDLE).as_posix(): digest(p) for p in files},
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(sources)},
        "dependencies": dependencies,
        "xcode": subprocess.check_output(["xcodebuild", "-version"], text=True).strip(),
        "expected_os": "Darwin 24.4.0 / macOS 15.4.1 24E263",
        "enable_boot_argument": "-btvirtfix", "disable_boot_argument": "-btvirtfixoff",
        "reference_manifest_sha256": digest(ROOT / "reference-manifest.json"),
        "guard_tests": (ROOT / "logs/page-guard-tests.txt").read_text().strip(),
    }
    (ROOT / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Manifest generation failed: {error}", file=sys.stderr)
        sys.exit(1)
