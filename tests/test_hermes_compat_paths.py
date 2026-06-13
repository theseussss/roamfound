import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class FakeCtx:
    def __init__(self):
        self.hooks = {}
        self.tools = {}
    def register_skill(self, *args, **kwargs):
        return None
    def register_hook(self, name, fn):
        self.hooks[name] = fn
    def register_tool(self, name, **kwargs):
        self.tools[name] = kwargs


APP_ROOT = Path(__file__).resolve().parents[1]
COMPAT_PATH = APP_ROOT / "hermes-plugin" / "compat.py"
PLUGIN_INIT_PATH = APP_ROOT / "hermes-plugin" / "__init__.py"


def load_compat_module():
    spec = importlib.util.spec_from_file_location("jiacong_hermes_compat_path_tests", COMPAT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["jiacong_hermes_compat_path_tests"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_plugin_module():
    spec = importlib.util.spec_from_file_location(
        "jiacong_hermes_plugin_path_tests",
        PLUGIN_INIT_PATH,
        submodule_search_locations=[str(PLUGIN_INIT_PATH.parent)],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "jiacong_hermes_plugin_path_tests"
    sys.modules["jiacong_hermes_plugin_path_tests"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HermesCompatRuntimePathTests(unittest.TestCase):
    def setUp(self):
        self.compat = load_compat_module()

    def test_watcher_metadata_path_defaults_to_jiacong(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                self.compat._watcher_metadata_path(root),
                root / ".jiacong" / "watcher.json",
            )

    def test_watcher_status_prefers_jiacong_pid_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_pid = os.getpid()
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "watcher.pid").write_text(str(current_pid), encoding="utf-8")
            watcher_script = self.compat._watcher_script()
            (root / ".jiacong" / "watcher.json").write_text(
                json.dumps({
                    "kind": "smarter-project-watcher",
                    "pid": current_pid,
                    "project_root": str(root),
                    "watcher_script": str(watcher_script),
                }),
                encoding="utf-8",
            )
            (root / ".claude").mkdir()
            (root / ".claude" / "watcher.pid").write_text("999999", encoding="utf-8")
            (root / ".claude" / "watcher.json").write_text(json.dumps({"pid": 999999}), encoding="utf-8")

            state = self.compat.watcher_status(root)
            self.assertEqual(state["pid"], current_pid)
            self.assertTrue(state["alive"])

    def test_spawn_watcher_creates_jiacong_runtime_dir_not_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "watcher.py"
            script.write_text("print('noop')\n", encoding="utf-8")
            log = root / ".jiacong" / "watcher.log"
            fake_process = Mock(pid=12345)
            with patch.object(self.compat.subprocess, "Popen", return_value=fake_process) as popen:
                pid = self.compat._spawn_watcher(root, script, log)
            self.assertEqual(pid, 12345)
            self.assertTrue((root / ".jiacong").is_dir())
            self.assertFalse((root / ".claude").exists())
            popen.assert_called_once()

    def test_plugin_no_longer_exposes_legacy_root_or_watcher_helpers(self):
        plugin = load_plugin_module()
        for name in ("_resolve_project_root", "_ensure_watcher", "_stop_watcher"):
            self.assertFalse(hasattr(plugin, name), name)

    def test_pre_llm_call_ensures_watcher_for_confirmed_project_root(self):
        plugin = load_plugin_module()
        ctx = FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir(parents=True)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "project.json").write_text(
                json.dumps({"confirmed_root": True}),
                encoding="utf-8",
            )
            with patch.object(plugin.compat, "ensure_watcher", return_value={"started": True, "pid": 123}) as ensure:
                result = ctx.hooks["pre_llm_call"](cwd=str(root), user_message="hello", session_id="s1")
            ensure.assert_called_once_with(root.resolve())
            self.assertIsInstance(result, dict)
            self.assertIn("context", result)

    def test_pre_llm_call_does_not_start_watcher_without_confirmed_root(self):
        plugin = load_plugin_module()
        ctx = FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir(parents=True)
            with patch.object(plugin.compat, "ensure_watcher", return_value={"started": True}) as ensure:
                result = ctx.hooks["pre_llm_call"](cwd=str(root), user_message="hello", session_id="s1")
            ensure.assert_not_called()
            self.assertIsInstance(result, dict)
            self.assertIn("context", result)

    def test_plugin_tool_uses_resolved_project_root_for_subdir_parameter(self):
        plugin = load_plugin_module()
        ctx = FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            subdir = root / "sub"
            subdir.mkdir(parents=True)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "project.json").write_text(
                json.dumps({"confirmed_root": True}),
                encoding="utf-8",
            )

            result = json.loads(ctx.tools["jiacong_flow_watcher"]["handler"]({"project_root": str(subdir), "action": "status"}))
            self.assertTrue(result["success"])
            self.assertEqual(Path(result["project_root"]), root.resolve())
            self.assertEqual(result["requested_path"], str(subdir))

    def test_plugin_relative_tool_path_uses_hook_cwd_not_process_cwd(self):
        plugin = load_plugin_module()
        ctx = FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            target = project / "topics" / "010_Test" / "scratch.md"
            target.parent.mkdir(parents=True)
            target.write_text("# scratch\n", encoding="utf-8")
            (project / ".jiacong").mkdir()
            (project / ".jiacong" / "project.json").write_text(
                json.dumps({"confirmed_root": True}),
                encoding="utf-8",
            )

            ctx.hooks["post_tool_call"](
                cwd=str(project),
                tool_name="write_file",
                args={"path": "topics/010_Test/scratch.md"},
                result="ok",
            )

            touched = project / ".jiacong" / "round_touched.jsonl"
            self.assertTrue(touched.is_file())
            rows = [json.loads(line) for line in touched.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(rows[-1]["file_path"], str(target.resolve()))
            self.assertEqual(rows[-1]["project_root"], str(project.resolve()))


if __name__ == "__main__":
    unittest.main()
