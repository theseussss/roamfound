import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
INSTALL_PATH = APP_ROOT / "install.py"
HOOK_AUTO_INSTALL_PATH = APP_ROOT / "hooks" / "hook_auto_install.py"


WINDOWS_PYTHON = "C:/Users/jiacong/AppData/Local/Programs/Python/Python312/python.exe"
WINDOWS_PYTHON_BACKSLASH = "C:\\Users\\jiacong\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def all_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for groups in hooks.values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if command:
                    commands.append(command)
    return commands


class HookPythonCommandTests(unittest.TestCase):
    def test_user_bootstrap_hook_uses_python3_for_posix_script_when_executable_is_windows(self):
        install = load_module("jiacong_install_hook_command_test", INSTALL_PATH)
        command = install._hook_command(
            Path("/mnt/h/path with space/app/hooks/hook_auto_install.py"),
            "--agent",
            "claude",
            executable=WINDOWS_PYTHON,
        )
        self.assertTrue(command.startswith("python3 "), command)
        self.assertNotIn("python.exe", command.lower())
        self.assertIn('"/mnt/h/path with space/app/hooks/hook_auto_install.py"', command)

    def test_user_bootstrap_hook_keeps_windows_python_for_windows_script(self):
        install = load_module("jiacong_install_hook_command_windows_test", INSTALL_PATH)
        command = install._hook_command(
            Path("C:/Users/jiacong/app/hooks/hook_auto_install.py"),
            "--agent",
            "claude",
            executable=WINDOWS_PYTHON,
        )
        self.assertIn("python.exe", command.lower())
        self.assertIn("C:/Users/jiacong/app/hooks/hook_auto_install.py", command)

    def test_project_hooks_for_all_agents_avoid_windows_python_for_posix_install_path(self):
        hook_auto_install = load_module("jiacong_hook_auto_install_command_test", HOOK_AUTO_INSTALL_PATH)
        old_executable = sys.executable
        try:
            sys.executable = WINDOWS_PYTHON_BACKSLASH
            for agent in ("claude", "codex", "gemini"):
                with self.subTest(agent=agent):
                    hooks = hook_auto_install._build_hooks(
                        Path("/mnt/h/path with space/jiacong-flow/app"),
                        agent,
                    )
                    commands = all_commands(hooks)
                    self.assertGreater(len(commands), 0)
                    self.assertTrue(any("flow_hook.py" in command for command in commands))
                    for command in commands:
                        self.assertNotIn("python.exe", command.lower(), command)
                        self.assertIn("python3", command.split()[0], command)
        finally:
            sys.executable = old_executable

    def test_project_hooks_keep_windows_python_for_windows_install_path(self):
        hook_auto_install = load_module("jiacong_hook_auto_install_command_windows_test", HOOK_AUTO_INSTALL_PATH)
        old_executable = sys.executable
        try:
            sys.executable = WINDOWS_PYTHON_BACKSLASH
            hooks = hook_auto_install._build_hooks(
                Path("C:/Users/jiacong/app"),
                "claude",
            )
            commands = all_commands(hooks)
            self.assertGreater(len(commands), 0)
            self.assertTrue(any("python.exe" in command.lower() for command in commands))
        finally:
            sys.executable = old_executable


if __name__ == "__main__":
    unittest.main()
