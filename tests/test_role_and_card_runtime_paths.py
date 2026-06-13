import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = APP_ROOT / "skills" / "smarter-project" / "scripts"
ROLE_MANAGER_PATH = SCRIPTS_ROOT / "role_manager.py"
CARD_WRITE_PATH = SCRIPTS_ROOT / "card_write.py"


def load_script_module(name: str, path: Path):
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(SCRIPTS_ROOT))
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path


class RoleAndCardRuntimePathTests(unittest.TestCase):
    def setUp(self):
        self.role_manager = load_script_module("jiacong_role_manager_runtime_path_tests", ROLE_MANAGER_PATH)
        self.card_write = load_script_module("jiacong_card_write_runtime_path_tests", CARD_WRITE_PATH)

    def test_role_manager_outputs_under_jiacong_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            result = self.role_manager.main([str(root), "--no-open"])
            self.assertEqual(result, 0)
            self.assertTrue((root / ".jiacong" / "dashboard" / "role_manager.html").is_file())
            self.assertFalse((root / ".claude" / "role_manager.html").exists())

    def test_card_write_edit_log_lives_under_jiacong_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.card_write._log_edit(root, "020", "1", "integrate")
            current = root / ".jiacong" / "cache" / "card-edits.jsonl"
            legacy = root / ".claude" / ".cache" / "card-edits.jsonl"
            self.assertTrue(current.is_file())
            self.assertFalse(legacy.exists())
            record = json.loads(current.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["topic"], "020")
            self.assertEqual(record["section"], "1")
            self.assertEqual(record["mode"], "integrate")


if __name__ == "__main__":
    unittest.main()
