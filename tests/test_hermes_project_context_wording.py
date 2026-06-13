import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


def load_roots_module():
    hooks_dir = APP_ROOT / "hooks"
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(hooks_dir))
        if "lib.roots" in sys.modules:
            del sys.modules["lib.roots"]
        return importlib.import_module("lib.roots")
    finally:
        sys.path = old_path


class HermesProjectContextWordingTests(unittest.TestCase):
    def test_project_context_does_not_tell_agent_to_switch_active_worktree(self):
        roots_mod = load_roots_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "project.json").write_text(
                '{"confirmed_root": true}\n',
                encoding="utf-8",
            )
            roots = roots_mod.resolve_roots(root)
            text = roots_mod.project_context_message(roots, root)
            self.assertIn("管理根：", text)
            self.assertIn("切换项目根", text)
            self.assertNotIn("切换 active worktree", text)

    def test_focus_missing_message_uses_json_not_plain_echo(self):
        roots_mod = load_roots_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".jiacong").mkdir()
            (root / ".jiacong" / "project.json").write_text(
                '{"confirmed_root": true}\n',
                encoding="utf-8",
            )
            roots = roots_mod.resolve_roots(root)
            messages = roots_mod.project_context_message(roots, root)
            # sanity: context helper still renders project root; focus messages are tested through lib.focus below.
            self.assertIn("管理根：", messages)

            hooks_dir = APP_ROOT / "hooks"
            old_path = sys.path[:]
            try:
                sys.path.insert(0, str(hooks_dir))
                if "lib.focus" in sys.modules:
                    del sys.modules["lib.focus"]
                focus_mod = importlib.import_module("lib.focus")
                rendered = "\n".join(focus_mod.focus_messages(root, APP_ROOT / "skills" / "smarter-project"))
            finally:
                sys.path = old_path
            self.assertIn("写入合法 JSON", rendered)
            self.assertIn("schema_version", rendered)
            self.assertNotIn('echo "NNN" >', rendered)

    def test_unmanaged_followup_does_not_say_active_worktree(self):
        hooks_dir = APP_ROOT / "hooks"
        old_path = sys.path[:]
        try:
            sys.path.insert(0, str(hooks_dir))
            if "lib.messages" in sys.modules:
                del sys.modules["lib.messages"]
            messages_mod = importlib.import_module("lib.messages")
            text = messages_mod.msg("session.unmanaged.followup")
        finally:
            sys.path = old_path
        self.assertIn("source layer / 双层 Git", text)
        self.assertIn("--init-management-git --source-workspace", text)
        self.assertIn("--dual-git", text)
        self.assertIn("理想实践是管理根普通 Git 管治理", text)
        self.assertIn("新项目默认不推荐走这一路", text)
        self.assertIn("不能把内容层 Git/worktree 当作管理根授权", text)
        self.assertNotIn("active worktree", text)
        self.assertNotIn("先让用户选择标准项目根或 workspace 容器", text)


if __name__ == "__main__":
    unittest.main()
