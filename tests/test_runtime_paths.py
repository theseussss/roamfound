import importlib
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
HOOKS_ROOT = APP_ROOT / "hooks"


def load_hook_lib_module(name: str):
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(HOOKS_ROOT))
        return importlib.import_module(name)
    finally:
        sys.path = old_path


class ProjectPathsContractTests(unittest.TestCase):
    def setUp(self):
        self.project_paths = load_hook_lib_module("lib.project_paths")
        self.root = Path("/tmp/jiacong-flow-test-project")

    def test_metadata_and_entrypoint_paths_live_under_jiacong(self):
        self.assertEqual(
            self.project_paths.jiacong_dir(self.root),
            self.root / ".jiacong",
        )
        self.assertEqual(
            self.project_paths.project_marker_path(self.root),
            self.root / ".jiacong" / "project.json",
        )
        self.assertEqual(
            self.project_paths.entrypoints_path(self.root),
            self.root / ".jiacong" / "entrypoints.json",
        )

    def test_current_state_paths_live_under_jiacong(self):
        self.assertEqual(
            self.project_paths.focus_state_path(self.root),
            self.root / ".jiacong" / "focus.json",
        )
        self.assertEqual(
            self.project_paths.round_state_path(self.root),
            self.root / ".jiacong" / "round_state.json",
        )
        self.assertEqual(
            self.project_paths.round_touched_path(self.root),
            self.root / ".jiacong" / "round_touched.jsonl",
        )

    def test_roots_state_dir_uses_jiacong_as_default_runtime_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roots = load_hook_lib_module("lib.roots")
            self.assertEqual(roots.state_dir(root), root / ".jiacong")
            self.assertTrue((root / ".jiacong").is_dir())
            self.assertFalse((root / ".claude").exists())

    def test_runtime_artifact_paths_live_under_jiacong(self):
        self.assertEqual(
            self.project_paths.watcher_pid_path(self.root),
            self.root / ".jiacong" / "watcher.pid",
        )
        self.assertEqual(
            self.project_paths.watcher_metadata_path(self.root),
            self.root / ".jiacong" / "watcher.json",
        )
        self.assertEqual(
            self.project_paths.watcher_log_path(self.root),
            self.root / ".jiacong" / "watcher.log",
        )
        self.assertEqual(
            self.project_paths.hook_debug_path(self.root),
            self.root / ".jiacong" / "hook_debug.log",
        )
        self.assertEqual(
            self.project_paths.session_report_path(self.root),
            self.root / ".jiacong" / "session_report.json",
        )

    def test_generated_and_cache_paths_live_under_jiacong(self):
        self.assertEqual(
            self.project_paths.dashboard_dir(self.root),
            self.root / ".jiacong" / "dashboard",
        )
        self.assertEqual(
            self.project_paths.dashboard_index_path(self.root),
            self.root / ".jiacong" / "dashboard" / "index.html",
        )
        self.assertEqual(
            self.project_paths.dashboard_state_path(self.root),
            self.root / ".jiacong" / "dashboard" / "state.json",
        )
        self.assertEqual(
            self.project_paths.role_manager_path(self.root),
            self.root / ".jiacong" / "dashboard" / "role_manager.html",
        )
        self.assertEqual(
            self.project_paths.cache_dir(self.root),
            self.root / ".jiacong" / "cache",
        )
        self.assertEqual(
            self.project_paths.card_edits_path(self.root),
            self.root / ".jiacong" / "cache" / "card-edits.jsonl",
        )

    def test_legacy_paths_are_explicitly_named_and_live_under_claude(self):
        legacy_expectations = {
            "legacy_focus_path": self.root / ".claude" / "focus",
            "legacy_round_state_path": self.root / ".claude" / ".round_state.json",
            "legacy_round_touched_path": self.root / ".claude" / ".round_touched.jsonl",
            "legacy_hook_debug_path": self.root / ".claude" / "hook_debug.log",
            "legacy_session_report_path": self.root / ".claude" / "session_report.json",
            "legacy_dashboard_path": self.root / ".claude" / "dashboard.html",
            "legacy_watcher_pid_path": self.root / ".claude" / "watcher.pid",
        }
        for function_name, expected in legacy_expectations.items():
            with self.subTest(function_name=function_name):
                self.assertTrue(function_name.startswith("legacy_"))
                self.assertEqual(getattr(self.project_paths, function_name)(self.root), expected)


class RoundStatePathTests(unittest.TestCase):
    def setUp(self):
        self.round_state = load_hook_lib_module("lib.round_state")

    def test_round_state_paths_default_to_jiacong_and_keep_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_paths = self.round_state._round_state_paths(root)
            read_paths = self.round_state._round_state_paths(root, create=False)
            self.assertIn(root / ".jiacong" / "round_state.json", current_paths)
            self.assertIn(root / ".jiacong" / "round_state.json", read_paths)
            self.assertIn(root / ".claude" / ".round_state.json", read_paths)
            self.assertNotIn(root / ".jiacong" / ".round_state.json", current_paths)

    def test_round_touched_paths_default_to_jiacong_and_keep_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.round_state.round_touched_paths(root)
            self.assertIn(root / ".jiacong" / "round_touched.jsonl", paths)
            self.assertIn(root / ".claude" / ".round_touched.jsonl", paths)
            self.assertNotIn(root / ".jiacong" / ".round_touched.jsonl", paths)


class FocusStatePathTests(unittest.TestCase):
    def setUp(self):
        self.focus = load_hook_lib_module("lib.focus")

    def test_focus_json_is_preferred_over_legacy_text_when_both_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "focus.json").write_text(
                '{"schema_version": 1, "topic_id": "020", "source": "test"}\n',
                encoding="utf-8",
            )
            (root / ".claude").mkdir()
            (root / ".claude" / "focus").write_text("010_Old\n", encoding="utf-8")

            state = self.focus.read_focus_state(root)
            self.assertEqual(state["topic_id"], "020")
            self.assertEqual(self.focus.focus_value(root), "020")

    def test_legacy_focus_is_read_when_focus_json_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "focus").write_text("010_Old\n", encoding="utf-8")

            state = self.focus.read_focus_state(root)
            self.assertEqual(state["topic_id"], "010")
            self.assertEqual(state["source"], "legacy_fallback")

    def test_write_focus_state_defaults_to_jiacong_without_mirroring_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.focus.write_focus_state(root, "020", source="test")
            self.assertEqual(state["topic_id"], "020")
            self.assertTrue((root / ".jiacong" / "focus.json").is_file())
            self.assertFalse((root / ".claude" / "focus").exists())

    def test_write_focus_state_can_explicitly_mirror_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.focus.write_focus_state(root, "020", source="test", mirror_legacy=True)
            self.assertTrue((root / ".jiacong" / "focus.json").is_file())
            self.assertEqual((root / ".claude" / "focus").read_text(encoding="utf-8"), "020\n")


if __name__ == "__main__":
    unittest.main()
