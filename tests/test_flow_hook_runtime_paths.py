import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
FLOW_HOOK_PATH = APP_ROOT / "skills" / "smarter-project" / "scripts" / "flow_hook.py"
SCRIPTS_ROOT = APP_ROOT / "skills" / "smarter-project" / "scripts"


def load_flow_hook_module():
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(SCRIPTS_ROOT))
        spec = importlib.util.spec_from_file_location("jiacong_flow_hook_runtime_paths", FLOW_HOOK_PATH)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["jiacong_flow_hook_runtime_paths"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path


class FlowHookRuntimePathTests(unittest.TestCase):
    def setUp(self):
        self.flow_hook = load_flow_hook_module()

    def make_project(self, root: Path) -> Path:
        topic = root / "topics" / "020_入口机制"
        topic.mkdir(parents=True)
        (root / ".jiacong").mkdir(parents=True)
        (root / ".jiacong" / "project.json").write_text(
            json.dumps({"confirmed_root": True, "project_root": str(root)}, ensure_ascii=False),
            encoding="utf-8",
        )
        card = topic / "card.md"
        card.write_text("---\ntopic_id: '020'\nstatus: '⏳ 进行中'\n---\n", encoding="utf-8")
        return card

    def test_find_project_root_uses_jiacong_marker_not_claude_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            card = self.make_project(root)
            self.assertEqual(self.flow_hook._find_project_root(card), root.resolve())
            self.assertFalse((root / ".claude").exists())

    def test_touched_file_is_recorded_under_jiacong_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            card = self.make_project(root)
            self.flow_hook._record_touched_file(card, root, "Write")
            current = root / ".jiacong" / "round_touched.jsonl"
            legacy = root / ".claude" / ".round_touched.jsonl"
            self.assertTrue(current.is_file())
            self.assertFalse(legacy.exists())
            record = json.loads(current.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["topic_id"], "020")
            self.assertEqual(record["kind"], "card")


if __name__ == "__main__":
    unittest.main()
