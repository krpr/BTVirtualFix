#!/usr/bin/env python3
"""Run the unchanged production page guard with synthetic or locally verified pages.

Synthetic pages are test fixtures only: they live in a temporary tree and are
never written to Sources/ReferencePage.hpp or used to build a kernel extension.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_reference as reference


def synthetic_header():
    target = reference.load_target()
    pages = []
    for index, spec in enumerate(target["pages"]):
        page = bytearray(hashlib.sha256(f"BTVirtualFix synthetic {index}:{i}".encode()).digest()[0]
                         for i in range(reference.PAGE_SIZE))
        signature = bytes.fromhex(spec["find_hex"])
        within = spec["thin_signature_offset"] % reference.PAGE_SIZE
        page[within:within + len(signature)] = signature
        if page.count(signature) != 1:
            raise ValueError("Synthetic signature is not unique")
        pages.append(bytes(page))
    return "// SYNTHETIC TEST FIXTURES: NOT APPLE CODE, NEVER BUILD A KEXT WITH THESE.\n" + reference.render_header(target, pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--synthetic", action="store_true", help="default; no Apple binary required")
    group.add_argument("--generated", action="store_true", help="use previously verified private reference pages")
    args = parser.parse_args()
    if args.generated:
        header = (ROOT / "Sources/ReferencePage.hpp").read_text()
        manifest = json.loads((ROOT / "reference-manifest.json").read_text())
        if reference.digest(header.encode()) != manifest.get("generated_header_sha256"):
            raise ValueError("Generated reference header does not match its manifest")
        mode = "verified local references"
    else:
        header = synthetic_header()
        mode = "synthetic test fixtures (not a runtime validation)"
    with tempfile.TemporaryDirectory(prefix="btvirtual-guard-tests-") as directory:
        temporary = Path(directory)
        (temporary / "Sources").mkdir()
        (temporary / "tests").mkdir()
        shutil.copy2(ROOT / "Sources/PageGuard.hpp", temporary / "Sources/PageGuard.hpp")
        shutil.copy2(ROOT / "tests/page_guard_test.cpp", temporary / "tests/page_guard_test.cpp")
        (temporary / "Sources/ReferencePage.hpp").write_text(header)
        compiler = ["xcrun", "clang++"] if sys.platform == "darwin" else ["clang++"]
        subprocess.run(compiler + ["-std=c++14", "-O1", "-g", "-fsanitize=address,undefined",
                                   str(temporary / "tests/page_guard_test.cpp"), "-o", str(temporary / "guard_test")], check=True)
        print(f"Reference mode: {mode}", flush=True)
        subprocess.run([str(temporary / "guard_test")], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Guard test failed: {error}", file=sys.stderr)
        sys.exit(1)
