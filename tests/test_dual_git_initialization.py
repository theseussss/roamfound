import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = APP_ROOT / "skills" / "smarter-project" / "scripts"
INIT_PROJECT_PATH = SCRIPTS_ROOT / "init_project.py"


def load_init_project_module():
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(SCRIPTS_ROOT))
        spec = importlib.util.spec_from_file_location("jiacong_init_project_dual_git", INIT_PROJECT_PATH)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["jiacong_init_project_dual_git"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path


class DualGitInitializationTests(unittest.TestCase):
    def setUp(self):
        self.init_project = load_init_project_module()

    def test_plain_project_init_does_not_create_management_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            self.init_project.init_project_root(root, "代码", skip_source_dirs=True)

            self.assertTrue((root / ".jiacong" / "project.json").is_file())
            self.assertFalse((root / ".git").exists())
            self.assertFalse((root / "source" / ".repo.git").exists())

    def test_init_management_git_creates_root_git_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            report, _legacy = self.init_project.init_project_root(root, "代码", skip_source_dirs=True)
            self.init_project.init_management_git(root, report)

            self.assertTrue((root / ".git").exists())
            self.assertFalse((root / "source" / ".repo.git").exists())
            self.assertTrue(any("管理层 Git" in item for item in report))

    def test_source_workspace_creates_source_git_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            report, _legacy = self.init_project.init_project_root(root, "代码", skip_source_dirs=True)
            self.init_project.init_source_workspace(root, source_dir="app", report=report)

            self.assertFalse((root / ".git").exists())
            self.assertTrue((root / "source" / ".repo.git").is_dir())
            self.assertTrue((root / "source" / "main" / "app").is_dir())
            self.assertTrue((root / ".jiacong" / "source.json").is_file())

    def test_management_git_and_source_workspace_form_dual_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            report, _legacy = self.init_project.init_project_root(root, "代码", skip_source_dirs=True)
            self.init_project.init_management_git(root, report)
            self.init_project.init_source_workspace(root, source_dir="app", report=report)

            self.assertTrue((root / ".git").exists())
            self.assertTrue((root / "source" / ".repo.git").is_dir())
            self.assertTrue((root / "source" / "main" / "app").is_dir())
            self.assertTrue((root / ".jiacong" / "source.json").is_file())
            self.assertTrue(any("管理层 Git" in item for item in report))
            self.assertTrue(any("源码层 workspace" in item for item in report))

    def test_dual_git_flag_is_documented_as_shortcut(self):
        script_text = INIT_PROJECT_PATH.read_text(encoding="utf-8")
        self.assertIn("--dual-git", script_text)
        self.assertIn("等价于 --init-management-git --source-workspace", script_text)
        self.assertIn("legacy 管理层 workspace", script_text)


if __name__ == "__main__":
    unittest.main()
