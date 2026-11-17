import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_target", ROOT / "scripts/check_target.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TargetChecks(unittest.TestCase):
    def test_platform_mismatch_fails(self):
        self.assertTrue(checker.evaluate_platform({"system": "Linux"}, checker.load_target()))

    def test_reviewed_platform(self):
        detected = {"system": "Darwin", "architecture": "x86_64", "darwin": "24.4.0",
                    "build": "24E263", "board_id": checker.TESTED_BOARD, "virtual_machine": True}
        self.assertEqual(checker.evaluate_platform(detected, checker.load_target()), [])
        detected["virtual_machine"] = False
        self.assertTrue(checker.evaluate_platform(detected, checker.load_target()))

    def test_conflicting_configuration_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            oc = Path(temp)
            data = plistlib.dumps({"Kernel": {"Add": []}, "NVRAM": {"Add": {
                checker.APPLE_GUID: {"boot-args": "vmhState=strict bt-transport-override=5 -btvirtfixoff"}}}})
            path = oc / "config.plist"
            path.write_bytes(data)
            result, errors = checker.inspect_oc(oc)
            self.assertEqual(len(errors), 4)
            self.assertFalse(result["virtual_transport_configured"])
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(list(oc.iterdir()), [path])

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                checker.bundle_files(Path(temp), {"BundlePath": "../../outside.kext"})


if __name__ == "__main__":
    unittest.main()
