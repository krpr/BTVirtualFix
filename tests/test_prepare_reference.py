"""Rejection and parser tests; these fixtures contain no Apple code pages."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_reference as reference


def thin_fixture(uuid=bytes(range(16))):
    return struct.pack('<IIIIIIII', 0xFEEDFACF, 0x1000007, 3, 2, 1, 24, 0, 0) + struct.pack('<II', 0x1B, 24) + uuid


def fat_fixture(thin=None):
    thin = thin_fixture() if thin is None else thin
    return struct.pack('>IIIIIII', 0xCAFEBABE, 1, 0x1000007, 3, 4096, len(thin), 12) + bytes(4096 - 28) + thin


class ReferenceRejectionTests(unittest.TestCase):
    def test_wrong_binary_identity(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            reference.verify_binary(fat_fixture(), reference.load_target())

    def test_extract_well_formed_fixture(self):
        offset, thin = reference.extract_x86_64(fat_fixture())
        self.assertEqual(offset, 4096)
        self.assertEqual(reference.macho_uuid(thin), bytes(range(16)).hex())

    def test_truncated_fat_header(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            reference.extract_x86_64(b'\xca\xfe')

    def test_wrong_container(self):
        with self.assertRaisesRegex(ValueError, 'universal Mach-O'):
            reference.extract_x86_64(thin_fixture())

    def test_architecture_table_bounds(self):
        data = bytearray(fat_fixture())
        struct.pack_into('>I', data, 4, 65)
        with self.assertRaisesRegex(ValueError, 'architecture table'):
            reference.extract_x86_64(data)

    def test_slice_out_of_bounds(self):
        data = bytearray(fat_fixture())
        struct.pack_into('>I', data, 20, len(data) + 1)
        with self.assertRaisesRegex(ValueError, 'outside the file'):
            reference.extract_x86_64(data)

    def test_wrong_slice_alignment(self):
        data = bytearray(fat_fixture())
        struct.pack_into('>I', data, 24, 31)
        with self.assertRaisesRegex(ValueError, 'alignment'):
            reference.extract_x86_64(data)

    def test_missing_x86_slice(self):
        data = bytearray(fat_fixture())
        struct.pack_into('>I', data, 8, 0x100000C)
        with self.assertRaisesRegex(ValueError, 'exactly one x86_64'):
            reference.extract_x86_64(data)

    def test_duplicate_x86_slice(self):
        data = bytearray(fat_fixture())
        struct.pack_into('>I', data, 4, 2)
        data[28:48] = data[8:28]
        with self.assertRaisesRegex(ValueError, 'exactly one x86_64'):
            reference.extract_x86_64(data)

    def test_uuid_command_bounds(self):
        data = bytearray(thin_fixture())
        struct.pack_into('<I', data, 36, 32)
        with self.assertRaisesRegex(ValueError, 'load-command size'):
            reference.macho_uuid(data)

    def test_zero_load_command_rejected(self):
        data = bytearray(thin_fixture())
        struct.pack_into('<I', data, 36, 0)
        with self.assertRaisesRegex(ValueError, 'load-command size'):
            reference.macho_uuid(data)

    def test_missing_uuid(self):
        data = bytearray(thin_fixture())
        struct.pack_into('<I', data, 32, 0x20)
        with self.assertRaisesRegex(ValueError, 'exactly one Mach-O UUID'):
            reference.macho_uuid(data)

    def test_pinned_uuid_is_checked_after_hashes(self):
        data = fat_fixture()
        target = copy.deepcopy(reference.load_target())
        target['universal_sha256'] = reference.digest(data)
        target['thin_sha256'] = reference.digest(thin_fixture())
        target['slice_offset'] = 4096
        with self.assertRaisesRegex(ValueError, 'UUID mismatch'):
            reference.verify_binary(data, target)

    def test_optimized_cli_rejects_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Sources').mkdir()
            shutil.copy2(ROOT / 'prepare_reference.py', root / 'prepare_reference.py')
            shutil.copy2(ROOT / 'targets.json', root / 'targets.json')
            (root / 'input').write_bytes(fat_fixture())
            header = root / 'Sources/ReferencePage.hpp'
            manifest = root / 'reference-manifest.json'
            header.write_text('existing-header')
            manifest.write_text('existing-manifest')
            result = subprocess.run([sys.executable, '-O', str(root / 'prepare_reference.py'),
                                     '--bluetoothd', str(root / 'input')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SHA-256 mismatch', result.stderr)
            self.assertEqual(header.read_text(), 'existing-header')
            self.assertEqual(manifest.read_text(), 'existing-manifest')


if __name__ == '__main__':
    unittest.main()
