import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace


APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = APP_ROOT / "skills" / "smarter-project" / "scripts"
WATCHER_PATH = SCRIPTS_ROOT / "watcher.py"
DASHBOARD_PATH = SCRIPTS_ROOT / "dashboard.py"


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


class WatcherDashboardRuntimePathTests(unittest.TestCase):
    def setUp(self):
        self.watcher = load_script_module("jiacong_watcher_runtime_path_tests", WATCHER_PATH)
        self.dashboard = load_script_module("jiacong_dashboard_runtime_path_tests", DASHBOARD_PATH)

    def test_watcher_observes_jiacong_focus_json_and_legacy_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handler = self.watcher.DebouncedRebuilder(root, 0.1)
            self.assertTrue(handler._is_watched_path(root / ".jiacong" / "focus.json"))
            self.assertTrue(handler._is_watched_path(root / ".claude" / "focus"))
            self.assertFalse(handler._is_watched_path(root / ".jiacong" / "cache" / "tmp.json"))

    def test_watcher_default_pidfile_lives_under_jiacong(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                self.watcher.default_pidfile(root),
                root / ".jiacong" / "watcher.pid",
            )

    def test_watcher_polling_snapshot_works_without_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic = root / "topics" / "010_Test"
            topic.mkdir(parents=True)
            scratch = topic / "scratch.md"
            scratch.write_text("初始记录\n", encoding="utf-8")
            handler = self.watcher.DebouncedRebuilder(root, 0.1)

            first = self.watcher._watched_snapshot(root, handler)
            time.sleep(0.01)
            scratch.write_text("初始记录\n新增一行\n", encoding="utf-8")
            second = self.watcher._watched_snapshot(root, handler)

            self.assertIn(str(scratch.resolve()), first)
            self.assertIn(str(scratch.resolve()), second)
            self.assertNotEqual(first[str(scratch.resolve())], second[str(scratch.resolve())])

    def test_dashboard_reads_focus_json_before_legacy_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "focus.json").write_text(
                json.dumps({"schema_version": 1, "topic_id": "020", "source": "test"}),
                encoding="utf-8",
            )
            (root / ".claude").mkdir()
            (root / ".claude" / "focus").write_text("010:old task\n", encoding="utf-8")
            topics = {"020_入口机制": {"slug": "020_入口机制"}, "010_旧话题": {"slug": "010_旧话题"}}

            focus = self.dashboard._read_focus(root, topics)
            self.assertEqual(focus["raw"], "020")
            self.assertEqual(focus["slug"], "020_入口机制")
            self.assertEqual(focus["task"], "")

    def test_dashboard_watcher_state_prefers_jiacong_metadata_with_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_pid = os.getpid()
            current = root / ".jiacong"
            current.mkdir()
            (current / "watcher.pid").write_text(str(current_pid), encoding="utf-8")
            (current / "watcher.json").write_text(
                json.dumps({
                    "pid": current_pid,
                    "project_root": str(root),
                    "watcher_script": str(root / "app" / "skills" / "smarter-project" / "scripts" / "watcher.py"),
                    "app_root": str(root / "app"),
                }),
                encoding="utf-8",
            )
            legacy = root / ".claude"
            legacy.mkdir()
            (legacy / "watcher.pid").write_text("999999", encoding="utf-8")
            (legacy / "watcher.json").write_text(json.dumps({"pid": 999999}), encoding="utf-8")

            state = self.dashboard._watcher_state(root)
            self.assertEqual(state["pid"], current_pid)
            self.assertTrue(state["metadata_path"].endswith(".jiacong/watcher.json"))

    def test_dashboard_output_path_lives_under_jiacong_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                self.dashboard._dashboard_output_path(root),
                root / ".jiacong" / "dashboard" / "index.html",
            )


if __name__ == "__main__":
    unittest.main()
