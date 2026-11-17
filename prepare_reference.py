#!/usr/bin/env python3
"""Generate private page references from the exact, locally supplied Apple binary.

No Apple executable or full reference page is distributed with the repository.
All identity checks use explicit exceptions, including under python -O.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PAGE_SIZE = 4096


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_target():
    return json.loads((ROOT / "targets.json").read_text())


def extract_x86_64(fat):
    """Parse the reviewed 32-bit fat-container format, rejecting malformed bounds."""
    require(len(fat) >= 8, "Truncated universal Mach-O header")
    magic, count = struct.unpack_from(">II", fat)
    require(magic == 0xCAFEBABE, "Expected the reviewed universal Mach-O format")
    require(0 < count <= 64 and 8 + 20 * count <= len(fat), "Invalid fat architecture table")
    matches = []
    for index in range(count):
        cpu, subtype, offset, size, alignment = struct.unpack_from(">IIIII", fat, 8 + 20 * index)
        require(size > 0 and offset >= 8 + 20 * count and offset + size <= len(fat),
                "Mach-O architecture slice is outside the file")
        require(alignment < 32 and offset % (1 << alignment) == 0,
                "Invalid Mach-O slice alignment")
        if cpu == 0x1000007:
            matches.append((offset, fat[offset:offset + size]))
    require(len(matches) == 1, "Expected exactly one x86_64 slice")
    return matches[0]


def macho_uuid(thin):
    require(len(thin) >= 32, "Truncated x86_64 Mach-O header")
    magic, cpu = struct.unpack_from("<II", thin)
    require(magic == 0xFEEDFACF and cpu == 0x1000007, "Expected a little-endian x86_64 Mach-O")
    count, command_bytes = struct.unpack_from("<II", thin, 16)
    end = 32 + command_bytes
    require(end <= len(thin) and count <= command_bytes // 8, "Invalid Mach-O load-command table")
    position, uuids = 32, []
    for _ in range(count):
        require(position + 8 <= end, "Truncated Mach-O load command")
        command, size = struct.unpack_from("<II", thin, position)
        require(size >= 8 and size % 8 == 0 and position + size <= end, "Invalid Mach-O load-command size")
        if command == 0x1B:
            require(size == 24, "Invalid LC_UUID size")
            uuids.append(thin[position + 8:position + 24].hex())
        position += size
    require(position == end and len(uuids) == 1, "Expected exactly one Mach-O UUID")
    return uuids[0]


def verify_binary(fat, target):
    require(digest(fat) == target["universal_sha256"],
            "bluetoothd SHA-256 mismatch: only macOS 15.4.1 build 24E263 is supported")
    offset, thin = extract_x86_64(fat)
    require(offset == target["slice_offset"], "Unexpected x86_64 slice offset")
    require(digest(thin) == target["thin_sha256"], "x86_64 slice SHA-256 mismatch")
    require(macho_uuid(thin) == target["x86_64_uuid"], "x86_64 Mach-O UUID mismatch")
    pages = []
    for spec in target["pages"]:
        find, replacement = bytes.fromhex(spec["find_hex"]), bytes.fromhex(spec["replace_hex"])
        require(find and len(find) == len(replacement), "Invalid patch signature lengths")
        require(thin.count(find) == fat.count(find) == 1, "Patch signature must be unique")
        require(thin.count(replacement) == 0, "Input already contains a replacement signature")
        signature_offset = spec["thin_signature_offset"]
        require(thin.find(find) == signature_offset, "Patch signature offset differs")
        within = signature_offset % PAGE_SIZE
        page_start = signature_offset - within
        page = thin[page_start:page_start + PAGE_SIZE]
        require(len(page) == PAGE_SIZE and within + len(find) <= PAGE_SIZE,
                "Patch does not fit one complete code page")
        require(digest(page) == spec["page_sha256"], "Full code-page SHA-256 mismatch")
        changed = [within + i for i, (old, new) in enumerate(zip(find, replacement)) if old != new]
        require(changed == spec["changed_offsets"], "Patch changes unexpected bytes")
        pages.append(page)
    require(sum(len(s["changed_offsets"]) for s in target["pages"]) == 7,
            "Reviewed target must change exactly seven bytes")
    return pages


def array(name, value):
    rows = ["    " + ", ".join(f"0x{b:02X}" for b in value[i:i + 16]) + ","
            for i in range(0, len(value), 16)]
    return f"static const uint8_t {name}[] = {{\n" + "\n".join(rows) + "\n};\n"


def render_header(target, pages):
    """Render verified pages; the CLI calls verify_binary before this function."""
    require(len(pages) == len(target["pages"]), "Reference-page count differs")
    header = "// Generated from the hash-pinned local binary. Do not hand-edit.\n#pragma once\n#include <stdint.h>\n#include <stddef.h>\n"
    header += "namespace BTVirtualReferences {\n"
    entries = []
    for spec, page in zip(target["pages"], pages):
        name = spec["name"]
        require(name.isidentifier(), "Invalid reference name")
        find, replacement = bytes.fromhex(spec["find_hex"]), bytes.fromhex(spec["replace_hex"])
        within = spec["thin_signature_offset"] % PAGE_SIZE
        start = spec["thin_signature_offset"] - within
        header += array(f"k{name}OriginalPage", page)
        header += array(f"k{name}Find", find) + array(f"k{name}Replace", replacement)
        entries.append(f'    {{"{spec["purpose"]}", k{name}OriginalPage, k{name}Find, k{name}Replace, sizeof(k{name}Find), 0x{start:X}, 0x{start + target["slice_offset"]:X}, 0x{within:X}, {len(spec["changed_offsets"])}}},')
    header += """struct PageReference {
    const char *label;
    const uint8_t *original;
    const uint8_t *find;
    const uint8_t *replacement;
    size_t signatureSize;
    uint64_t thinOffset;
    uint64_t fatOffset;
    size_t signatureOffset;
    size_t changedBytes;
};
static constexpr size_t kPageSize = 4096;
static const PageReference kPages[] = {
"""
    return header + "\n".join(entries) + "\n};\n}\n"


def make_reference_manifest(target, pages, header):
    manifest_pages = []
    for spec, page in zip(target["pages"], pages):
        within = spec["thin_signature_offset"] % PAGE_SIZE
        start = spec["thin_signature_offset"] - within
        replacement = bytes.fromhex(spec["replace_hex"])
        patched = page[:within] + replacement + page[within + len(replacement):]
        manifest_pages.append({
            "name": spec["name"], "purpose": spec["purpose"],
            "find_hex": spec["find_hex"], "replace_hex": spec["replace_hex"],
            "signature_count_in_thin": 1, "signature_count_in_universal": 1,
            "thin_page_offset": hex(start), "universal_page_offset": hex(start + target["slice_offset"]),
            "signature_page_offset": hex(within), "page_sha256": digest(page),
            "patched_page_sha256": digest(patched),
            "changed_page_offsets": [hex(i) for i in spec["changed_offsets"]],
            "changed_bytes": len(spec["changed_offsets"]),
        })
    return {"target_darwin": target["darwin"], "target_build": target["build"],
            "target_path": target["path"], "thin_sha256": target["thin_sha256"],
            "universal_sha256": target["universal_sha256"], "x86_64_uuid": target["x86_64_uuid"],
            "pages": manifest_pages, "total_changed_bytes": 7,
            "generated_header_sha256": digest(header.encode()), "reference_origin": "verified local Apple binary"}


def atomic_write(path, text):
    fd, temporary = tempfile.mkstemp(prefix=".btvirtual-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bluetoothd", type=Path, default=Path("/usr/sbin/bluetoothd"),
                        help="exact universal binary from macOS 15.4.1 build 24E263")
    args = parser.parse_args()
    target = load_target()
    pages = verify_binary(args.bluetoothd.read_bytes(), target)
    header = render_header(target, pages)
    manifest = make_reference_manifest(target, pages, header)
    # No generated output is touched until every target check has passed.
    atomic_write(ROOT / "Sources/ReferencePage.hpp", header)
    atomic_write(ROOT / "reference-manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, struct.error) as error:
        print(f"Reference generation refused: {error}", file=sys.stderr)
        sys.exit(1)
