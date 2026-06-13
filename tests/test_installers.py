import importlib
import importlib.util
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = APP_ROOT / "skills"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, APP_ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_hook_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, APP_ROOT / "hooks" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_skill_script_module(name: str, skill_name: str, script_name: str):
    path = SKILLS_ROOT / skill_name / "scripts" / script_name
    scripts_dir = path.parent
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(scripts_dir))
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path


def load_hook_package_module(name: str):
    hooks_dir = APP_ROOT / "hooks"
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(hooks_dir))
        return importlib.import_module(name)
    finally:
        sys.path = old_path


install = load_module("jiacong_install", "install.py")
uninstall = load_module("jiacong_uninstall", "uninstall.py")
workspace_use = load_module("jiacong_workspace_use", "workspace_use.py")
hook_common = load_hook_module("jiacong_hook_common", "_common.py")
hook_messages = load_hook_module("jiacong_hook_messages", "lib/messages.py")
hook_roots = load_hook_package_module("lib.roots")
hook_auto_install = load_hook_module("jiacong_hook_auto_install", "hook_auto_install.py")
hook_session_end = load_hook_module("jiacong_hook_session_end", "hook_session_end.py")
hook_session_start = load_hook_module("jiacong_hook_session_start", "hook_session_start.py")
hook_stop = load_hook_module("jiacong_hook_stop", "hook_stop.py")
hook_user_prompt = load_hook_module("jiacong_hook_user_prompt", "hook_user_prompt.py")
init_project = load_skill_script_module(
    "jiacong_init_project",
    "smarter-project",
    "init_project.py",
)
flow_hook = load_skill_script_module(
    "jiacong_flow_hook",
    "smarter-project",
    "flow_hook.py",
)
watcher = load_skill_script_module(
    "jiacong_watcher",
    "smarter-project",
    "watcher.py",
)


def make_managed_project(root: Path) -> None:
    (root / ".jiacong").mkdir(parents=True, exist_ok=True)
    (root / ".jiacong" / "project.json").write_text(
        json.dumps({"project_id": "test", "confirmed_root": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "CLAUDE.md").write_text("# project\n", encoding="utf-8")
    (root / "topics").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "stream.md").write_text("", encoding="utf-8")


def make_focused_topic(root: Path, topic_id: str = "010", name: str = "Test") -> Path:
    topic_dir = root / "topics" / f"{topic_id}_{name}"
    topic_dir.mkdir(parents=True)
    (topic_dir / "card.md").write_text(
        "---\n"
        f"topic_id: {topic_id}_{name}\n"
        "status: ⏳ 进行中\n"
        "root: 🛠️工具\n"
        "parent: null\n"
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )
    (topic_dir / "scratch.md").write_text(
        "### S001 · [05-17 00:00] baseline\n\n初始记录。\n",
        encoding="utf-8",
    )
    (root / ".claude" / "focus").write_text(f"{topic_id}_{name}\n", encoding="utf-8")
    return topic_dir


def make_workspace_container(workspace: Path) -> None:
    (workspace / ".repo.git").mkdir(parents=True)
    (workspace / "main").mkdir(parents=True)
    (workspace / "worktrees").mkdir(parents=True)
    (workspace / "AGENTS.md").write_text(
        "This directory is a workspace container. Use worktrees/<branch>.\n",
        encoding="utf-8",
    )


def select_worktree(workspace: Path, selection: str) -> None:
    state_dir = workspace / hook_common.WORKSPACE_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "current-worktree").write_text(selection + "\n", encoding="utf-8")


def append_scratch(topic_dir: Path, text: str = "本轮记录。") -> None:
    with (topic_dir / "scratch.md").open("a", encoding="utf-8") as fh:
        fh.write(f"\n### S999 · [05-18 00:00] test\n\n{text}\n")


def run_hook_main(module, argv: list[str], event: dict, *, stdout: io.StringIO | None = None) -> int | str | None:
    old_argv = sys.argv[:]
    old_stdin = sys.stdin
    out = stdout or io.StringIO()
    try:
        sys.argv = argv
        sys.stdin = io.StringIO(json.dumps(event, ensure_ascii=False))
        with contextlib.redirect_stdout(out):
            try:
                module.main()
            except SystemExit as exc:
                return exc.code
    finally:
        sys.argv = old_argv
        sys.stdin = old_stdin
    return None


class AgentParsingTests(unittest.TestCase):
    def test_parse_single_and_multiple_agents(self):
        self.assertEqual(install._parse_agents("codex"), ["codex"])
        self.assertEqual(install._parse_agents("claude,codex"), ["claude", "codex"])
        self.assertEqual(install._parse_agents("codex codex gemini"), ["codex", "gemini"])
        self.assertEqual(install._parse_agents("all"), ["claude", "codex", "gemini", "hermes"])
        self.assertEqual(uninstall._parse_agents("all"), ["claude", "codex", "gemini", "hermes"])
        self.assertEqual(uninstall._default_target("hermes"), uninstall.DEFAULT_HERMES_SOUL)

    def test_parse_rejects_unknown_agents(self):
        with self.assertRaises(ValueError):
            install._parse_agents("codex,unknown")


class InstallerIdempotenceTests(unittest.TestCase):
    def test_skill_sources_include_peer_one_turn_proposal(self):
        self.assertTrue((SKILLS_ROOT / "smarter-project" / "SKILL.md").is_file())
        self.assertTrue((SKILLS_ROOT / "one-turn-proposal" / "SKILL.md").is_file())
        self.assertTrue(
            (
                SKILLS_ROOT
                / "one-turn-proposal"
                / "schemas"
                / "one-turn-proposal.schema.json"
            ).is_file()
        )

    def test_codex_install_updates_managed_marker_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            self.assertEqual(
                install.install_codex(target, skill_mode="none"),
                0,
            )
            first = target.read_text(encoding="utf-8")
            self.assertIn("JC:CODEX_GLOBAL:BEGIN", first)
            self.assertEqual(first.count("JC:CODEX_GLOBAL:BEGIN"), 1)

            self.assertEqual(
                install.install_codex(target, skill_mode="none"),
                0,
            )
            second = target.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(second.count("JC:CODEX_GLOBAL:BEGIN"), 1)

    def test_gemini_install_updates_managed_marker_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "GEMINI.md"
            self.assertEqual(
                install.install_gemini(target, skill_mode="none"),
                0,
            )
            first = target.read_text(encoding="utf-8")
            self.assertIn("JC:GEMINI_GLOBAL:BEGIN", first)
            self.assertEqual(first.count("JC:GEMINI_GLOBAL:BEGIN"), 1)

            self.assertEqual(
                install.install_gemini(target, skill_mode="none"),
                0,
            )
            second = target.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(second.count("JC:GEMINI_GLOBAL:BEGIN"), 1)

    def test_copy_skill_mode_is_idempotent_and_removable(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills" / "smarter-project"
            skill_id, action, ok = install._install_cli_skill(
                "codex",
                dest,
                skill_mode="copy",
                replace_skill=False,
                dry_run=False,
            )
            self.assertEqual((skill_id, action, ok), ("codex_skill", "copied", True))

            skill_id, action, ok = install._install_cli_skill(
                "codex",
                dest,
                skill_mode="copy",
                replace_skill=False,
                dry_run=False,
            )
            self.assertEqual((skill_id, action, ok), ("codex_skill", "current", True))

            action, removed, ok = uninstall._remove_cli_skill(dest, dry_run=False)
            self.assertEqual((action, removed, ok), ("removed copy", True, True))
            self.assertFalse(dest.exists())

    def test_copy_all_peer_skills_is_idempotent_and_removable(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "skills"
            reports = install._install_cli_skills(
                "codex",
                skills_dir,
                skill_mode="copy",
                replace_skill=False,
                dry_run=False,
            )
            actions = {skill_id: action for skill_id, action, ok in reports if ok}
            self.assertEqual(actions["codex_skill_smarter-project"], "copied")
            self.assertEqual(actions["codex_skill_one-turn-proposal"], "copied")
            self.assertTrue((skills_dir / "smarter-project" / "SKILL.md").is_file())
            self.assertTrue((skills_dir / "one-turn-proposal" / "SKILL.md").is_file())

            reports = install._install_cli_skills(
                "codex",
                skills_dir,
                skill_mode="copy",
                replace_skill=False,
                dry_run=False,
            )
            actions = {skill_id: action for skill_id, action, ok in reports if ok}
            self.assertEqual(actions["codex_skill_smarter-project"], "current")
            self.assertEqual(actions["codex_skill_one-turn-proposal"], "current")

            remove_reports = uninstall._remove_cli_skills(
                "codex",
                skills_dir,
                dry_run=False,
            )
            remove_actions = {
                skill_id: (action, removed, ok)
                for skill_id, action, removed, ok in remove_reports
            }
            self.assertEqual(
                remove_actions["codex_skill_smarter-project"],
                ("removed copy", True, True),
            )
            self.assertEqual(
                remove_actions["codex_skill_one-turn-proposal"],
                ("removed copy", True, True),
            )
            self.assertFalse((skills_dir / "smarter-project").exists())
            self.assertFalse((skills_dir / "one-turn-proposal").exists())

    def test_codex_hooks_install_and_uninstall_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks_path = Path(tmp) / "hooks.json"
            first = install._install_codex_hooks(hooks_path, dry_run=False)
            self.assertTrue(all(action == "register" for _hook_id, action in first))
            data = hooks_path.read_text(encoding="utf-8")
            self.assertIn("SessionStart", data)
            self.assertIn("hook_auto_install.py", data)
            self.assertIn("--agent codex", data)
            self.assertNotIn("hook_user_prompt.py", data)
            self.assertNotIn("hook_stop.py", data)

            second = install._install_codex_hooks(hooks_path, dry_run=False)
            self.assertTrue(all(action == "current" for _hook_id, action in second))

            removed = uninstall._uninstall_codex_hooks(hooks_path, dry_run=False)
            self.assertTrue(any(action == "removed" for _hook_id, action in removed))
            after = hooks_path.read_text(encoding="utf-8")
            self.assertNotIn("hook_auto_install.py", after)

    def test_gemini_hooks_install_and_uninstall_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            first = install._install_gemini_hooks(settings_path, dry_run=False)
            self.assertTrue(all(action == "register" for _hook_id, action in first))
            data = settings_path.read_text(encoding="utf-8")
            self.assertIn("SessionStart", data)
            self.assertIn("hook_auto_install.py", data)
            self.assertIn("--agent gemini", data)
            self.assertNotIn("hook_user_prompt.py", data)

            second = install._install_gemini_hooks(settings_path, dry_run=False)
            self.assertTrue(all(action == "current" for _hook_id, action in second))

            removed = uninstall._uninstall_gemini_hooks(settings_path, dry_run=False)
            self.assertTrue(any(action == "removed" for _hook_id, action in removed))
            after = settings_path.read_text(encoding="utf-8")
            self.assertNotIn("hook_auto_install.py", after)

    def test_claude_trigger_uses_plugin_root_and_migrates_copied_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": '"python" "C:/Users/Administrator/.claude/hooks/jiacong_flow_trigger.py"',
                                            "timeout": 15,
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_settings = install.SETTINGS_PATH
            try:
                install.SETTINGS_PATH = settings_path
                report = install._install_trigger(dry_run=False)
                self.assertIn(("trigger_hook", "migrated"), report)
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                commands = [
                    hook["command"]
                    for group in data["hooks"]["SessionStart"]
                    for hook in group.get("hooks", [])
                ]
                self.assertEqual(len(commands), 1)
                self.assertIn("hook_auto_install.py", commands[0])
                self.assertIn("--agent claude", commands[0])
                self.assertIn("--plugin-root", commands[0])
                self.assertNotIn("jiacong_flow_trigger.py", commands[0])

                second = install._install_trigger(dry_run=False)
                self.assertIn(("trigger_hook", "current"), second)
            finally:
                install.SETTINGS_PATH = old_settings

    def test_claude_trigger_migrates_stale_plugin_root_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": '"python" "D:/old/jiacong-flow/app/hooks/hook_auto_install.py" --agent claude --plugin-root "D:/old/jiacong-flow/app"',
                                            "timeout": 15,
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_settings = install.SETTINGS_PATH
            try:
                install.SETTINGS_PATH = settings_path
                report = install._install_trigger(dry_run=False)
                self.assertIn(("trigger_hook", "migrated"), report)
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                commands = [
                    hook["command"]
                    for group in data["hooks"]["SessionStart"]
                    for hook in group.get("hooks", [])
                ]
                self.assertEqual(len(commands), 1)
                self.assertIn(str(install.PLUGIN_ROOT).replace("\\", "/"), commands[0])
                self.assertNotIn("D:/old/jiacong-flow", commands[0])
            finally:
                install.SETTINGS_PATH = old_settings

    def test_codex_hooks_migrate_stale_bootstrap_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks_path = Path(tmp) / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "startup|resume",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": '"python" "D:/old/jiacong-flow/app/hooks/hook_auto_install.py" --agent codex --plugin-root "D:/old/jiacong-flow/app"',
                                            "timeout": 15,
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = install._install_codex_hooks(hooks_path, dry_run=False)
            self.assertIn(("codex_hook_SessionStart", "migrate"), report)
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for group in data["hooks"]["SessionStart"]
                for hook in group.get("hooks", [])
            ]
            self.assertEqual(len(commands), 1)
            self.assertIn(str(install.PLUGIN_ROOT).replace("\\", "/"), commands[0])
            self.assertNotIn("D:/old/jiacong-flow", commands[0])

    def test_codex_project_hooks_are_written_by_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)

            self.assertTrue(hook_auto_install._install_hooks(project, APP_ROOT, "codex"))
            hooks_path = project / ".codex" / "hooks.json"
            data = hooks_path.read_text(encoding="utf-8")
            self.assertIn("UserPromptSubmit", data)
            self.assertIn("hook_user_prompt.py", data)
            self.assertIn("hook_stop.py", data)
            self.assertIn("--agent codex", data)
            self.assertNotIn("SessionEnd", data)
            self.assertNotIn('"version"', data)

            parsed = json.loads(data)
            commands = [
                hook["command"]
                for groups in parsed["hooks"].values()
                for group in groups
                for hook in group.get("hooks", [])
            ]
            self.assertTrue(
                any("hook_session_start.py" in cmd and "--agent codex" in cmd for cmd in commands)
            )
            self.assertTrue(
                any("hook_user_prompt.py" in cmd and "--agent codex" in cmd for cmd in commands)
            )
            self.assertTrue(
                any("hook_stop.py" in cmd and "--agent codex" in cmd for cmd in commands)
            )
            self.assertTrue(
                all(not cmd.startswith('"') for cmd in commands),
                "Codex hook commands should not start with a quoted executable",
            )

            parsed = json.loads(data)
            parsed["hooks"]["SessionEnd"] = hook_auto_install._build_hooks(
                APP_ROOT,
                "claude",
            )["SessionEnd"]
            hooks_path.write_text(
                json.dumps(parsed, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertFalse(
                hook_auto_install._has_current_jiacong_hooks(
                    hooks_path,
                    APP_ROOT,
                    "codex",
                )
            )

    def test_gemini_project_hooks_use_native_event_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)

            self.assertTrue(hook_auto_install._install_hooks(project, APP_ROOT, "gemini"))
            hooks_path = project / ".gemini" / "settings.json"
            data = hooks_path.read_text(encoding="utf-8")
            self.assertIn("BeforeAgent", data)
            self.assertIn("AfterTool", data)
            self.assertIn("AfterAgent", data)
            self.assertNotIn("UserPromptSubmit", data)
            self.assertNotIn("PostToolUse", data)
            self.assertNotIn('"Stop"', data)
            self.assertIn("hook_user_prompt.py", data)
            self.assertIn("hook_stop.py", data)
            self.assertIn("--agent gemini", data)

            parsed = json.loads(data)
            self.assertIn("startup", json.dumps(parsed["hooks"]["SessionStart"]))
            self.assertIn("*", json.dumps(parsed["hooks"]["BeforeAgent"]))
            self.assertIn("*", json.dumps(parsed["hooks"]["AfterTool"]))
            self.assertIn("exit", json.dumps(parsed["hooks"]["SessionEnd"]))

    def test_codex_stop_output_uses_native_block_schema(self):
        hook_stop._messages[:] = ["[jiacong] must write scratch"]
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                hook_stop._flush_codex_block()
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["decision"], "block")
            self.assertEqual(payload["reason"], "[jiacong] must write scratch")
            self.assertNotIn("hookSpecificOutput", payload)
        finally:
            hook_stop._messages[:] = []

    def test_codex_context_outputs_use_native_additional_context_schema(self):
        old_argv = sys.argv[:]
        try:
            sys.argv = ["hook_user_prompt.py", "--agent", "codex"]
            hook_user_prompt._messages[:] = ["[jiacong] focus check"]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                hook_user_prompt._flush_output()
            payload = json.loads(stdout.getvalue())
            self.assertNotIn("systemMessage", payload)
            self.assertEqual(
                payload["hookSpecificOutput"]["hookEventName"],
                "UserPromptSubmit",
            )
            self.assertIn(
                "[jiacong] focus check",
                payload["hookSpecificOutput"]["additionalContext"],
            )

            sys.argv = ["hook_session_start.py", "--agent", "codex"]
            hook_session_start._messages[:] = ["[startup] focus"]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                hook_session_start._flush_output()
            payload = json.loads(stdout.getvalue())
            self.assertNotIn("systemMessage", payload)
            self.assertEqual(
                payload["hookSpecificOutput"]["hookEventName"],
                "SessionStart",
            )
            self.assertEqual(
                payload["hookSpecificOutput"]["additionalContext"],
                "[startup] focus",
            )
        finally:
            sys.argv = old_argv
            hook_user_prompt._messages[:] = []
            hook_session_start._messages[:] = []

    def test_gemini_context_outputs_use_before_agent_schema(self):
        old_argv = sys.argv[:]
        try:
            sys.argv = ["hook_user_prompt.py", "--agent", "gemini"]
            hook_user_prompt._messages[:] = ["[jiacong] focus check"]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                hook_user_prompt._flush_output()
            payload = json.loads(stdout.getvalue())
            self.assertIn("systemMessage", payload)
            self.assertEqual(
                payload["hookSpecificOutput"]["hookEventName"],
                "BeforeAgent",
            )
            self.assertIn(
                "[jiacong] focus check",
                payload["hookSpecificOutput"]["additionalContext"],
            )
        finally:
            sys.argv = old_argv
            hook_user_prompt._messages[:] = []

    def test_user_prompt_main_codex_uses_runtime_context_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            make_focused_topic(project)

            hook_user_prompt._messages[:] = []
            stdout = io.StringIO()
            code = run_hook_main(
                hook_user_prompt,
                ["hook_user_prompt.py", "--agent", "codex"],
                {
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(project),
                    "prompt": "设计一个输出协议并做来源审查",
                },
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertNotIn("systemMessage", payload)
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("[Jiacong Flow] 管理根", context)
            self.assertIn("文件操作前先判断改动层级：管理层 / 内容层 / 混合", context)
            self.assertIn("[Jiacong Flow] 当前话题", context)
            self.assertIn("bridge 常驻", context)
            self.assertIn("bridge 信号", context)

    def test_user_prompt_main_gemini_uses_before_agent_context_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            make_focused_topic(project)

            hook_user_prompt._messages[:] = []
            stdout = io.StringIO()
            code = run_hook_main(
                hook_user_prompt,
                ["hook_user_prompt.py", "--agent", "gemini"],
                {
                    "hook_event_name": "BeforeAgent",
                    "cwd": str(project),
                    "llm_request": {
                        "messages": [
                            {"role": "system", "content": "system context"},
                            {"role": "user", "content": "比较两个方案的证据强度"},
                        ]
                    },
                },
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("systemMessage", payload)
            self.assertEqual(
                payload["hookSpecificOutput"]["hookEventName"],
                "BeforeAgent",
            )
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("[Jiacong Flow] 管理根", context)
            self.assertIn("文件操作前先判断改动层级：管理层 / 内容层 / 混合", context)
            self.assertIn("bridge 信号", context)

    def test_stop_main_codex_uses_runtime_decision_block_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            topic_dir = make_focused_topic(project)
            scratch_lines = len((topic_dir / "scratch.md").read_text(encoding="utf-8").splitlines())
            (project / ".claude" / ".round_state.json").write_text(
                json.dumps(
                    {
                        "focus": "010_Test",
                        "topic_id": "010",
                        "scratch_map": {"010": scratch_lines},
                        "stream_lines": 0,
                        "ts": "2026-05-17T00:00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            hook_stop._messages[:] = []
            stdout = io.StringIO()
            code = run_hook_main(
                hook_stop,
                ["hook_stop.py", "--agent", "codex"],
                {"hook_event_name": "Stop", "cwd": str(project)},
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["decision"], "block")
            self.assertIn("本轮未写 scratch", payload["reason"])
            self.assertNotIn("hookSpecificOutput", payload)

    def test_stop_main_gemini_uses_after_agent_block_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            topic_dir = make_focused_topic(project)
            scratch_lines = len((topic_dir / "scratch.md").read_text(encoding="utf-8").splitlines())
            (project / ".claude" / ".round_state.json").write_text(
                json.dumps(
                    {
                        "focus": "010_Test",
                        "topic_id": "010",
                        "scratch_map": {"010": scratch_lines},
                        "stream_lines": 0,
                        "ts": "2026-05-17T00:00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            hook_stop._messages[:] = []
            stdout = io.StringIO()
            code = run_hook_main(
                hook_stop,
                ["hook_stop.py", "--agent", "gemini"],
                {"hook_event_name": "AfterAgent", "cwd": str(project)},
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["decision"], "block")
            self.assertIn("本轮未写 scratch", payload["reason"])
            self.assertIn("本轮未写 scratch", payload["systemMessage"])


class BranchAwareStopTests(unittest.TestCase):
    class BytesStdin:
        encoding = "gbk"

        def __init__(self, data: bytes) -> None:
            self.buffer = io.BytesIO(data)

    def make_workspace_with_peer(self, tmp: str) -> tuple[Path, Path, Path, Path, Path]:
        workspace = Path(tmp) / "jiacong-flow"
        make_workspace_container(workspace)

        main = workspace / "main"
        make_managed_project(main)
        main_topic = make_focused_topic(main)

        peer = workspace / "worktrees" / "peer-skillfusion"
        make_managed_project(peer)
        peer_topic = make_focused_topic(peer)
        (peer / ".git").write_text(
            "gitdir: ../../.repo.git/worktrees/peer-skillfusion\n",
            encoding="utf-8",
        )

        select_worktree(workspace, "main")
        return workspace, main, main_topic, peer, peer_topic

    def save_round_from_workspace(self, workspace: Path) -> None:
        stdout = io.StringIO()
        code = run_hook_main(
            hook_user_prompt,
            ["hook_user_prompt.py", "--agent", "codex"],
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(workspace),
                "prompt": "继续当前任务",
            },
            stdout=stdout,
        )
        self.assertEqual(code, 0)

    def record_peer_card_edit(self, peer_topic: Path) -> None:
        card = peer_topic / "card.md"
        card.write_text(
            card.read_text(encoding="utf-8") + "\n补充一行实现说明。\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(flow_hook.handle_edit(str(card), tool_name="Edit"), 0)

    def run_stop_from_workspace(self, workspace: Path) -> tuple[int | str | None, str]:
        stdout = io.StringIO()
        code = run_hook_main(
            hook_stop,
            ["hook_stop.py", "--agent", "codex"],
            {"hook_event_name": "Stop", "cwd": str(workspace)},
            stdout=stdout,
        )
        return code, stdout.getvalue()

    def test_user_prompt_workspace_state_indexes_known_worktrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, main, _main_topic, peer, _peer_topic = self.make_workspace_with_peer(tmp)

            stdout = io.StringIO()
            code = run_hook_main(
                hook_user_prompt,
                ["hook_user_prompt.py", "--agent", "codex"],
                {
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(workspace),
                    "prompt": "继续当前任务",
                },
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            context = json.loads(stdout.getvalue())["hookSpecificOutput"]["additionalContext"]
            self.assertIn("管理根", context)
            self.assertIn("main", context)
            self.assertIn("selection=main", context)

            state_path = workspace / ".jiacong-workspace" / "round_state.json"
            self.assertTrue(state_path.is_file())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["version"], 2)
            self.assertEqual(state["active_project_root"], str(main.resolve()))
            self.assertIn(str(main.resolve()), state["known_project_roots"])
            self.assertIn(str(peer.resolve()), state["known_project_roots"])
            self.assertTrue((main / ".jiacong" / "round_state.json").is_file())
            self.assertFalse((main / ".claude" / ".round_state.json").exists())

    def test_stop_allows_touched_peer_topic_when_same_topic_scratch_increments(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _main, _main_topic, _peer, peer_topic = self.make_workspace_with_peer(tmp)
            self.save_round_from_workspace(workspace)

            self.record_peer_card_edit(peer_topic)
            append_scratch(peer_topic, "peer worktree 的同话题 scratch 已闭环。")

            code, output = self.run_stop_from_workspace(workspace)
            self.assertEqual(code, 0)
            self.assertEqual(output, "")

    def test_stop_blocks_touched_peer_topic_without_same_topic_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _main, _main_topic, _peer, peer_topic = self.make_workspace_with_peer(tmp)
            self.save_round_from_workspace(workspace)

            self.record_peer_card_edit(peer_topic)

            code, output = self.run_stop_from_workspace(workspace)
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("对应话题 scratch 没有增量", payload["reason"])
            self.assertIn("peer-skillfusion", payload["reason"])

    def test_flow_hook_records_non_topic_project_file_touch(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _main, _main_topic, peer, _peer_topic = self.make_workspace_with_peer(tmp)
            readme = peer / "README.md"
            readme.write_text("note\n", encoding="utf-8")

            self.assertEqual(flow_hook.handle_edit(str(readme), tool_name="Write"), 0)

            touched = workspace / ".jiacong-workspace" / "round_touched.jsonl"
            self.assertTrue(touched.is_file())
            records = [
                json.loads(line)
                for line in touched.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(records[-1]["project_root"], str(peer.resolve()))
            self.assertEqual(records[-1]["kind"], "other")
            self.assertEqual(records[-1]["topic_id"], "")

    def test_flow_hook_event_json_prefers_utf8_bytes_for_chinese_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _main, _main_topic, peer, _peer_topic = self.make_workspace_with_peer(tmp)
            target = peer / "topics" / "010_融合skill升级" / "tasks.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("tasks\n", encoding="utf-8")

            event = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
            }
            old_argv = sys.argv[:]
            old_stdin = sys.stdin
            try:
                sys.argv = ["flow_hook.py", "--event-json"]
                sys.stdin = self.BytesStdin(json.dumps(event, ensure_ascii=False).encode("utf-8"))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(flow_hook.main(), 0)
            finally:
                sys.argv = old_argv
                sys.stdin = old_stdin

            touched = workspace / ".jiacong-workspace" / "round_touched.jsonl"
            self.assertTrue(touched.is_file())
            records = [
                json.loads(line)
                for line in touched.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(records[-1]["file_path"], str(target.resolve()))
            self.assertEqual(records[-1]["topic_id"], "010")

    def test_flow_hook_accepts_gemini_after_tool_event_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _main, _main_topic, peer, _peer_topic = self.make_workspace_with_peer(tmp)
            target = peer / "topics" / "010_融合skill升级" / "tasks.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("tasks\n", encoding="utf-8")

            event = {
                "hook_event_name": "AfterTool",
                "tool_name": "write_file",
                "tool_input": {"path": str(target)},
            }
            old_argv = sys.argv[:]
            old_stdin = sys.stdin
            try:
                sys.argv = ["flow_hook.py", "--event-json"]
                sys.stdin = self.BytesStdin(json.dumps(event, ensure_ascii=False).encode("utf-8"))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(flow_hook.main(), 0)
            finally:
                sys.argv = old_argv
                sys.stdin = old_stdin

            touched = workspace / ".jiacong-workspace" / "round_touched.jsonl"
            records = [
                json.loads(line)
                for line in touched.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(records[-1]["file_path"], str(target.resolve()))
            self.assertEqual(records[-1]["topic_id"], "010")


class WatcherOwnershipTests(unittest.TestCase):
    def test_watcher_metadata_records_root_and_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            pidfile = project / ".claude" / "watcher.pid"

            watcher._prepare_pidfile(pidfile)
            watcher._write_metadata(project, pidfile, 1.25)
            data = json.loads((project / ".claude" / "watcher.json").read_text(encoding="utf-8"))

            self.assertEqual(data["kind"], "smarter-project-watcher")
            self.assertEqual(Path(data["project_root"]), project)
            self.assertEqual(data["pid"], os.getpid())
            self.assertTrue(data["watcher_script"].endswith("watcher.py"))
            self.assertIn("app", Path(data["app_root"]).parts)

            watcher._cleanup_pidfile(pidfile)
            watcher._cleanup_metadata(pidfile)
            self.assertFalse(pidfile.exists())
            self.assertFalse((project / ".claude" / "watcher.json").exists())

    def test_session_start_rejects_script_from_other_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            foreign_root = Path(tmp) / "foreign"
            make_managed_project(foreign_root)
            watcher_script = APP_ROOT / "skills" / "smarter-project" / "scripts" / "watcher.py"

            self.assertFalse(
                hook_session_start._script_allowed_for_root(foreign_root, watcher_script)
            )

    def test_session_start_accepts_matching_watcher_metadata(self):
        project_root = APP_ROOT.parent
        watcher_script = APP_ROOT / "skills" / "smarter-project" / "scripts" / "watcher.py"
        metadata = {
            "kind": "smarter-project-watcher",
            "project_root": str(project_root),
            "watcher_script": str(watcher_script),
        }

        self.assertTrue(
            hook_session_start._watcher_is_current(project_root, watcher_script, metadata)
        )


class RootResolutionTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> None:
        (root / ".repo.git").mkdir(parents=True)
        (root / "main").mkdir(parents=True)
        (root / "worktrees").mkdir(parents=True)
        (root / "AGENTS.md").write_text(
            "This directory is a workspace container. Use worktrees/<branch>.\n",
            encoding="utf-8",
        )

    def test_workspace_container_does_not_climb_to_parent_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            make_managed_project(parent)
            workspace = parent / "jiacong-flow"
            self.make_workspace(workspace)

            roots = hook_common.resolve_roots(workspace)
            self.assertEqual(roots.kind, "needs_ai_judgment")
            self.assertIsNone(roots.project_root)
            self.assertEqual(roots.hook_root, workspace.resolve())

    def test_workspace_container_can_be_identified_from_gemini_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            (workspace / ".repo.git").mkdir(parents=True)
            (workspace / "main").mkdir(parents=True)
            (workspace / "worktrees").mkdir(parents=True)
            (workspace / "GEMINI.md").write_text(
                "This is a workspace container. Use worktrees/<branch>.\n",
                encoding="utf-8",
            )

            roots = hook_common.resolve_roots(workspace)
            self.assertEqual(roots.kind, "needs_ai_judgment")
            self.assertEqual(roots.hook_root, workspace.resolve())

    def test_workspace_selection_routes_to_managed_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            self.make_workspace(workspace)
            worktree = workspace / "worktrees" / "peer-skillfusion"
            make_managed_project(worktree)
            (worktree / ".git").write_text("gitdir: ../../.repo.git/worktrees/peer\n", encoding="utf-8")
            state_dir = workspace / hook_common.WORKSPACE_STATE_DIR
            state_dir.mkdir()
            (state_dir / "current-worktree").write_text(
                "worktrees/peer-skillfusion\n",
                encoding="utf-8",
            )

            roots = hook_common.resolve_roots(workspace)
            self.assertEqual(roots.kind, "workspace_selected_managed")
            self.assertEqual(roots.project_root, worktree.resolve())
            self.assertEqual(roots.hook_root, workspace.resolve())

    def test_direct_nested_worktree_resolves_to_nearest_git_file_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            self.make_workspace(workspace)
            worktree = workspace / "worktrees" / "refactor" / "judgment-chain"
            make_managed_project(worktree)
            (worktree / ".git").write_text("gitdir: ../../../.repo.git/worktrees/refactor\n", encoding="utf-8")
            nested = worktree / "app" / "hooks"
            nested.mkdir(parents=True)

            roots = hook_common.resolve_roots(nested)
            self.assertEqual(roots.kind, "confirmed_subdir")
            self.assertEqual(roots.project_root, worktree.resolve())
            self.assertEqual(roots.hook_root, worktree.resolve())

    def test_empty_directory_is_candidate_not_managed_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "empty-project"
            candidate.mkdir()

            roots = hook_common.resolve_roots(candidate)
            self.assertEqual(roots.kind, "needs_ai_judgment")
            self.assertIsNone(roots.project_root)
            self.assertEqual(roots.candidate_root, candidate.resolve())

    def test_bootstrap_installs_workspace_hooks_when_selection_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            self.make_workspace(workspace)
            worktree = workspace / "worktrees" / "peer-skillfusion"
            make_managed_project(worktree)
            (worktree / ".git").write_text("gitdir: ../../.repo.git/worktrees/peer\n", encoding="utf-8")
            state_dir = workspace / hook_common.WORKSPACE_STATE_DIR
            state_dir.mkdir()
            (state_dir / "current-worktree").write_text(
                "worktrees/peer-skillfusion\n",
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            saved_env = {name: os.environ.get(name) for name in ["JIACONG_FLOW_PROJECT_ROOT", "JIACONG_FLOW_HOOK_ROOT", "JIACONG_FLOW_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "TERMINAL_CWD", "HERMES_CWD"]}
            try:
                for name in saved_env:
                    os.environ.pop(name, None)
                os.chdir(workspace)
                roots = hook_auto_install._resolve_roots()
            finally:
                os.chdir(old_cwd)
                for name, value in saved_env.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value

            self.assertEqual(roots.project_root, worktree.resolve())
            self.assertEqual(roots.hook_root, workspace.resolve())
            self.assertTrue(
                hook_auto_install._install_hooks(roots.hook_root, APP_ROOT, "codex")
            )
            data = (workspace / ".codex" / "hooks.json").read_text(encoding="utf-8")
            self.assertIn("UserPromptSubmit", data)
            self.assertIn("hook_user_prompt.py", data)

    def test_session_end_resolves_project_from_event_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            project = workspace / "project"
            make_managed_project(project)
            old_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                self.assertEqual(
                    hook_session_end._find_project_root(str(project)),
                    project.resolve(),
                )
            finally:
                os.chdir(old_cwd)


class WorkspaceUseTests(unittest.TestCase):
    def test_parse_worktree_porcelain_skips_bare_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            workspace.mkdir()
            text = f"""worktree {workspace / '.repo.git'}
bare

worktree {workspace / 'main'}
HEAD abc
branch refs/heads/main

worktree {workspace / 'worktrees' / 'peer-skillfusion'}
HEAD def
branch refs/heads/peer-skillfusion
"""
            items = workspace_use.parse_worktree_porcelain(text, workspace)
            self.assertEqual([item.rel for item in items], ["main", "worktrees/peer-skillfusion"])
            self.assertEqual([item.branch for item in items], ["main", "peer-skillfusion"])

    def test_workspace_use_writes_current_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            workspace.mkdir()
            target = workspace / "worktrees" / "peer-skillfusion"
            make_managed_project(target)
            item = workspace_use.Worktree(
                path=target.resolve(),
                rel="worktrees/peer-skillfusion",
                branch="peer-skillfusion",
            )

            workspace_use.write_current(workspace, item)
            self.assertEqual(workspace_use.read_current(workspace), "worktrees/peer-skillfusion")
            meta = json.loads(
                (workspace / ".jiacong-workspace" / "current-worktree.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(meta["branch"], "peer-skillfusion")
            self.assertTrue(meta["managed"])

    def test_resolve_target_accepts_branch_rel_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            target = workspace / "worktrees" / "peer-skillfusion"
            target.mkdir(parents=True)
            items = [
                workspace_use.Worktree(
                    path=target.resolve(),
                    rel="worktrees/peer-skillfusion",
                    branch="peer-skillfusion",
                )
            ]
            self.assertEqual(
                workspace_use.resolve_target("peer-skillfusion", items, workspace).rel,
                "worktrees/peer-skillfusion",
            )
            self.assertEqual(
                workspace_use.resolve_target("worktrees/peer-skillfusion", items, workspace).branch,
                "peer-skillfusion",
            )
            self.assertEqual(
                workspace_use.resolve_target(str(target), items, workspace).branch,
                "peer-skillfusion",
            )

    def test_archive_worktree_dry_run_defaults_to_branch_hiding(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            target = workspace / "worktrees" / "feature-x"
            target.mkdir(parents=True)
            item = workspace_use.Worktree(
                path=target.resolve(),
                rel="worktrees/feature-x",
                branch="feature-x",
                head="abc123",
            )
            old_status = workspace_use._git_status
            try:
                workspace_use._git_status = lambda _path: ""
                plan = workspace_use.archive_worktree(
                    workspace,
                    item,
                    [item],
                    dry_run=True,
                    timestamp="20260518-230000",
                )
            finally:
                workspace_use._git_status = old_status

            self.assertTrue(plan.delete_branch)
            self.assertEqual(plan.tag, "archive/feature-x/20260518-230000")
            self.assertEqual(
                plan.snapshot_dir,
                workspace
                / ".jiacong-workspace"
                / "archive"
                / "branches"
                / "feature-x"
                / "20260518-230000"
                / "snapshot",
            )
            self.assertFalse(plan.archive_dir.exists())

    def test_archive_worktree_rejects_active_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            target = workspace / "worktrees" / "feature-x"
            target.mkdir(parents=True)
            (workspace / ".jiacong-workspace").mkdir(parents=True)
            (workspace / ".jiacong-workspace" / "current-worktree").write_text(
                "worktrees/feature-x\n",
                encoding="utf-8",
            )
            item = workspace_use.Worktree(
                path=target.resolve(),
                rel="worktrees/feature-x",
                branch="feature-x",
                head="abc123",
            )

            with self.assertRaises(SystemExit) as raised:
                workspace_use.archive_worktree(
                    workspace,
                    item,
                    [item],
                    dry_run=True,
                    timestamp="20260518-230000",
                )
            self.assertIn("active worktree", str(raised.exception))

    def test_archive_snapshot_excludes_git_marker_and_writes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            target = workspace / "worktrees" / "feature-x"
            target.mkdir(parents=True)
            (target / "file.txt").write_text("payload\n", encoding="utf-8")
            (target / ".git").write_text("gitdir: ../../.repo.git/worktrees/feature-x\n", encoding="utf-8")
            item = workspace_use.Worktree(
                path=target.resolve(),
                rel="worktrees/feature-x",
                branch="feature-x",
                head="abc123",
            )
            plan = workspace_use.build_archive_plan(
                workspace,
                item,
                timestamp="20260518-230000",
            )

            workspace_use._copy_archive_snapshot(plan)
            workspace_use._write_archive_metadata(workspace, plan)

            self.assertTrue((plan.snapshot_dir / "file.txt").is_file())
            self.assertFalse((plan.snapshot_dir / ".git").exists())
            payload = json.loads(plan.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"]["branch"], "feature-x")
            self.assertEqual(payload["git"]["tag"], "archive/feature-x/20260518-230000")
            self.assertTrue(payload["git"]["branch_deleted"])
            self.assertIn("worktree add -b feature-x", payload["restore"][0])


class WorkspaceInitTests(unittest.TestCase):
    def test_project_init_writes_multi_cli_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            report, legacy = init_project.init_project_root(project, "代码")

            self.assertEqual(legacy, [])
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((project / "CLAUDE.md").is_file())
            self.assertTrue((project / "GEMINI.md").is_file())
            self.assertTrue((project / "HERMES.md").is_file())
            self.assertTrue((project / ".jiacong" / "entrypoints.json").is_file())
            self.assertTrue((project / "topics").is_dir())
            self.assertTrue((project / "logs" / "stream.md").is_file())
            self.assertFalse((project / ".claude" / "CLAUDE.md").exists())
            agents_text = (project / "AGENTS.md").read_text(encoding="utf-8")
            claude_text = (project / "CLAUDE.md").read_text(encoding="utf-8")
            gemini_text = (project / "GEMINI.md").read_text(encoding="utf-8")
            self.assertIn(".jiacong/project.json", agents_text)
            self.assertIn(".jiacong/focus.json", agents_text)
            self.assertIn("AGENTS.md", claude_text)
            self.assertIn("AGENTS.md", gemini_text)
            self.assertNotIn("@./.claude/CLAUDE.md", agents_text)
            self.assertNotIn("@./.claude/CLAUDE.md", gemini_text)
            gitignore_text = (project / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".jiacong/dashboard/", gitignore_text)
            self.assertIn(".jiacong/round_*.json*", gitignore_text)
            self.assertIn(".jiacong/watcher.*", gitignore_text)
            self.assertTrue(any("[write]" in item for item in report))

    def test_workspace_init_creates_container_and_main_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            report, legacy = init_project.init_workspace_root(
                workspace,
                "代码",
                use_git=False,
            )

            self.assertEqual(legacy, [])
            self.assertTrue((workspace / ".repo.git").is_dir())
            self.assertTrue((workspace / "worktrees").is_dir())
            self.assertTrue((workspace / "AGENTS.md").is_file())
            self.assertTrue((workspace / "CLAUDE.md").is_file())
            self.assertTrue((workspace / "GEMINI.md").is_file())
            agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            claude_text = (workspace / "CLAUDE.md").read_text(encoding="utf-8")
            gemini_text = (workspace / "GEMINI.md").read_text(encoding="utf-8")
            self.assertIn("Root decision guard", agents_text)
            self.assertIn("Do not write `topics/` or `logs/` here", agents_text)
            self.assertIn("Root decision guard", claude_text)
            self.assertIn("Root decision guard", gemini_text)
            self.assertEqual(
                (workspace / ".jiacong-workspace" / "current-worktree")
                .read_text(encoding="utf-8")
                .strip(),
                "main",
            )

            main = workspace / "main"
            self.assertTrue((main / "AGENTS.md").is_file())
            self.assertTrue((main / "CLAUDE.md").is_file())
            self.assertTrue((main / "GEMINI.md").is_file())
            self.assertTrue((main / "HERMES.md").is_file())
            self.assertTrue((main / ".jiacong" / "entrypoints.json").is_file())
            self.assertFalse((main / ".claude" / "CLAUDE.md").exists())
            roots = hook_common.resolve_roots(workspace)
            self.assertEqual(roots.kind, "workspace_selected_managed")
            self.assertEqual(roots.project_root, main.resolve())
            self.assertTrue(any("workspace" in item for item in report))

    def test_workspace_init_rejects_existing_project_root_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            make_managed_project(workspace)

            with self.assertRaises(SystemExit) as raised:
                init_project.init_workspace_root(
                    workspace,
                    "代码",
                    use_git=False,
                )

            self.assertIn("不能直接作为 workspace 容器初始化", str(raised.exception))
            self.assertFalse((workspace / "main").exists())

    def test_workspace_init_adopts_unmanaged_history_files_into_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            workspace.mkdir()
            (workspace / "README.md").write_text("history\n", encoding="utf-8")
            (workspace / "src").mkdir()
            (workspace / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (workspace / "draft").mkdir()
            (workspace / "draft" / "note.md").write_text("idea\n", encoding="utf-8")

            report, legacy = init_project.init_workspace_root(
                workspace,
                "代码",
                use_git=False,
                adopt_existing=True,
            )

            self.assertEqual(legacy, [])
            self.assertFalse((workspace / "README.md").exists())
            self.assertFalse((workspace / "src").exists())
            self.assertTrue((workspace / "main" / "README.md").is_file())
            self.assertTrue((workspace / "main" / "src" / "app.py").is_file())
            self.assertTrue((workspace / "main" / "draft" / "note.md").is_file())
            self.assertTrue((workspace / "main" / "AGENTS.md").is_file())
            self.assertTrue((workspace / "main" / "CLAUDE.md").is_file())
            self.assertFalse((workspace / "main" / ".claude" / "CLAUDE.md").exists())
            self.assertTrue(any("[adopt] README.md" in item for item in report))

    def test_workspace_init_adopt_existing_rejects_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            workspace.mkdir()
            (workspace / ".git").mkdir()
            (workspace / "README.md").write_text("history\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as raised:
                init_project.init_workspace_root(
                    workspace,
                    "代码",
                    use_git=False,
                    adopt_existing=True,
                )

            self.assertIn("已有 .git", str(raised.exception))
            self.assertTrue((workspace / "README.md").is_file())
            self.assertFalse((workspace / "main").exists())

    def test_workspace_init_preserves_existing_outer_agent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            workspace.mkdir()
            (workspace / "AGENTS.md").write_text("custom user entry\n", encoding="utf-8")

            init_project.init_workspace_root(
                workspace,
                "代码",
                use_git=False,
            )

            self.assertEqual(
                (workspace / "AGENTS.md").read_text(encoding="utf-8"),
                "custom user entry\n",
            )
            self.assertTrue((workspace / "CLAUDE.md").is_file())
            self.assertTrue((workspace / "GEMINI.md").is_file())
            roots = hook_common.resolve_roots(workspace)
            self.assertEqual(roots.kind, "workspace_selected_managed")

    def test_workspace_init_cli_prints_inner_project_next_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "jiacong-flow"
            old_argv = sys.argv[:]
            stdout = io.StringIO()
            try:
                sys.argv = [
                    "init_project.py",
                    str(workspace),
                    "--type",
                    "代码",
                    "--workspace",
                    "--no-git",
                ]
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(init_project.main(), 0)
            finally:
                sys.argv = old_argv

            output = stdout.getvalue()
            self.assertIn("[workspace] 容器根", output)
            self.assertIn(str((workspace / "main").resolve()), output)
            self.assertTrue((workspace / "main" / "AGENTS.md").is_file())
            self.assertTrue((workspace / "main" / "CLAUDE.md").is_file())
            self.assertFalse((workspace / "main" / ".claude" / "CLAUDE.md").exists())
            for entry in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
                text = (workspace / entry).read_text(encoding="utf-8")
                self.assertIn("AGENTS.md", text)
                self.assertNotIn(".claude/CLAUDE.md", text)


class RoutingBridgeTests(unittest.TestCase):
    def test_bridge_baseline_is_non_signal_reminder(self):
        message = hook_common.bridge_baseline_message()
        self.assertIn("bridge 常驻", message)
        self.assertIn("主门控=smarter-project", message)
        self.assertIn("复杂判断", message)
        self.assertIn("one-turn-proposal", message)
        self.assertIn("回写当前话题", message)
        self.assertNotIn("检测到", message)
        self.assertNotIn("概率", message)
        self.assertNotIn("证据治理", message)

    def test_composite_route_for_project_proposal_persistence(self):
        route = hook_common.classify_route("为当前 010 做融合提案，并补到 scratch")
        self.assertEqual(route["route"], "composite")
        self.assertTrue(route["project_signal"])
        self.assertTrue(route["proposal_signal"])
        self.assertTrue(route["persistence_signal"])

    def test_project_only_route(self):
        route = hook_common.classify_route("新建话题并记录到 tasks")
        self.assertEqual(route["route"], "smarter-project")

    def test_proposal_only_route(self):
        route = hook_common.classify_route("比较两个方案的证据强度")
        self.assertEqual(route["route"], "one-turn-proposal")

    def test_proposal_route_matches_skill_interface_terms(self):
        for prompt in (
            "设计一个输出协议",
            "做来源审查和检索边界说明",
            "把这个想法升级成框架方法论",
            "写一个 ADR 决策备忘",
        ):
            with self.subTest(prompt=prompt):
                route = hook_common.classify_route(prompt)
                self.assertEqual(route["route"], "one-turn-proposal")
                self.assertTrue(route["proposal_signal"])

    def test_prompt_extraction_prefers_prompt_over_longer_metadata(self):
        event = {
            "prompt": "做一个证据检索提案",
            "metadata": {
                "content": "这是一段很长的系统元数据，不应被当作用户 prompt。" * 20
            },
        }
        self.assertEqual(hook_common.extract_user_prompt(event), "做一个证据检索提案")

    def test_bridge_message_points_to_parallel_skill(self):
        message = hook_common.routing_message(
            hook_common.classify_route("比较两个方案的证据强度")
        )
        self.assertIn("bridge 信号", message)
        self.assertIn("复杂判断", message)
        self.assertIn("one-turn-proposal", message)
        self.assertIn("proposal-bridge.md", message)
        self.assertNotIn("检测到", message)
        self.assertNotIn("概率", message)
        self.assertNotIn("证据治理", message)

    def test_bridge_signal_message_is_empty_without_signal(self):
        route = hook_common.classify_route("普通闲聊")
        self.assertEqual(route["route"], "none")
        self.assertEqual(hook_common.routing_message(route), "")

    def test_message_templates_render_and_expose_missing_variables(self):
        rendered = hook_messages.msg("bridge.signal.composite")
        self.assertIn("bridge 信号", rendered)

        missing = hook_messages.msg("stop.scratch_missing")
        self.assertIn("[missing variable:scratch_path]", missing)


class UninstallerTests(unittest.TestCase):
    def test_codex_uninstall_removes_marker_and_preserves_user_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text("before\n", encoding="utf-8")
            self.assertEqual(
                install.install_codex(target, skill_mode="none"),
                0,
            )

            self.assertEqual(
                uninstall.uninstall_codex(target, remove_skill=False),
                0,
            )
            text = target.read_text(encoding="utf-8")
            self.assertIn("before", text)
            self.assertNotIn("JC:CODEX_GLOBAL:BEGIN", text)

    def test_instruction_uninstall_missing_target_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "missing" / "GEMINI.md"
            self.assertEqual(
                uninstall.uninstall_gemini(target, remove_skill=False),
                0,
            )

    def test_claude_trigger_uninstall_removes_plugin_root_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            command = '"python" "D:/old/jiacong-flow/app/hooks/hook_auto_install.py" --agent claude --plugin-root "D:/old/jiacong-flow/app"'
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": command,
                                            "timeout": 15,
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_settings = uninstall.SETTINGS_PATH
            old_trigger_dest = uninstall.TRIGGER_DEST
            try:
                uninstall.SETTINGS_PATH = settings_path
                uninstall.TRIGGER_DEST = Path(tmp) / "jiacong_flow_trigger.py"
                report = uninstall._uninstall_trigger(dry_run=False)
                self.assertIn(("trigger_hook", "removed"), report)
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                self.assertNotIn("SessionStart", data.get("hooks", {}))
            finally:
                uninstall.SETTINGS_PATH = old_settings
                uninstall.TRIGGER_DEST = old_trigger_dest

    def test_uninstall_claude_cleans_hooks_when_markers_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            target.write_text("manual only\n", encoding="utf-8")
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": '"python" "D:/old/jiacong-flow/app/hooks/hook_auto_install.py" --agent claude',
                                            "timeout": 15,
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_settings = uninstall.SETTINGS_PATH
            old_trigger_dest = uninstall.TRIGGER_DEST
            try:
                uninstall.SETTINGS_PATH = settings_path
                uninstall.TRIGGER_DEST = Path(tmp) / "jiacong_flow_trigger.py"
                self.assertEqual(uninstall.uninstall_claude(target, dry_run=False), 0)
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                self.assertNotIn("SessionStart", data.get("hooks", {}))
            finally:
                uninstall.SETTINGS_PATH = old_settings
                uninstall.TRIGGER_DEST = old_trigger_dest


if __name__ == "__main__":
    unittest.main()

old_hook_path = sys.path[:]
try:
    sys.path.insert(0, str(APP_ROOT / "hooks"))
    import lib.roots as hook_roots
finally:
    sys.path = old_hook_path


class RootSafetyResolutionTests(unittest.TestCase):
    def write_marker(self, root: Path, content: str = '{"project_id":"test"}') -> None:
        (root / ".jiacong").mkdir(parents=True, exist_ok=True)
        (root / ".jiacong" / "project.json").write_text(content, encoding="utf-8")

    def test_confirmed_root_and_confirmed_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            child = root / "sub" / "dir"
            child.mkdir(parents=True)
            self.write_marker(root)

            root_resolution = hook_roots.resolve_roots(root)
            self.assertEqual(root_resolution.kind, "confirmed_root")
            self.assertEqual(root_resolution.project_root, root.resolve())

            child_resolution = hook_roots.resolve_roots(child)
            self.assertEqual(child_resolution.kind, "confirmed_subdir")
            self.assertEqual(child_resolution.project_root, root.resolve())

    def test_marker_status_variants_do_not_enable_management(self):
        cases = {
            "invalid": "{bad",
            "unconfirmed": '{"confirmed_root": false}',
            "mismatch": '{"project_root":"/definitely/not/here"}',
        }
        expected = {
            "invalid": "invalid_json",
            "unconfirmed": "unconfirmed_false",
            "mismatch": "path_mismatch",
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name, content in cases.items():
                root = base / name
                root.mkdir()
                self.write_marker(root, content)
                resolution = hook_roots.resolve_roots(root)
                self.assertEqual(resolution.kind, "needs_ai_judgment")
                self.assertIsNone(resolution.project_root)
                self.assertEqual(resolution.scan.current.marker.status, expected[name])

    def test_plain_directory_is_needs_ai_judgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir()
            resolution = hook_roots.resolve_roots(root)
            self.assertEqual(resolution.kind, "needs_ai_judgment")
            self.assertIsNone(resolution.project_root)
            self.assertEqual(resolution.scan.current.marker.status, "missing")

    def test_home_root_and_shallow_mount_are_hard_risks(self):
        home_resolution = hook_roots.resolve_roots(Path.home())
        self.assertEqual(home_resolution.kind, "unsafe_home")
        self.assertIsNone(home_resolution.project_root)

        root_resolution = hook_roots.resolve_roots(Path("/"))
        self.assertEqual(root_resolution.kind, "unsafe_root")
        self.assertIsNone(root_resolution.project_root)

        mount = Path("/mnt/h")
        if mount.exists():
            mount_resolution = hook_roots.resolve_roots(mount)
            self.assertEqual(mount_resolution.kind, "unsafe_mount")
            self.assertIsNone(mount_resolution.project_root)

    def test_child_scan_reports_confirmed_child_without_enabling_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "container"
            child = parent / "project"
            child.mkdir(parents=True)
            self.write_marker(child)

            resolution = hook_roots.resolve_roots(parent)
            self.assertEqual(resolution.kind, "needs_ai_judgment")
            self.assertIsNone(resolution.project_root)
            confirmed_children = resolution.scan.confirmed_children
            self.assertEqual(len(confirmed_children), 1)
            self.assertEqual(confirmed_children[0].path, child)

    def test_session_unsafe_home_message_uses_constraints_not_old_wording(self):
        resolution = hook_roots.resolve_roots(Path.home())
        messages = hook_roots.session_unmanaged_messages(resolution, APP_ROOT)
        self.assertEqual(len(messages), 1)
        text = messages[0]
        self.assertIn("不能在 Home 目录建档", text)
        self.assertIn("不能进入项目治理流程", text)
        self.assertNotIn("旧痕迹不能证明", text)
        self.assertNotIn("本次不启用 focus / scratch / watcher", text)

class HookRuntimeSafetyTests(unittest.TestCase):
    def _context_text(self, output: str) -> str:
        if not output:
            return ""
        payload = json.loads(output)
        return payload.get("hookSpecificOutput", {}).get("additionalContext", "")

    def test_session_start_home_runtime_uses_new_safety_prompt(self):
        hook_session_start._messages.clear()
        stdout = io.StringIO()
        code = run_hook_main(
            hook_session_start,
            ["hook_session_start.py", "--agent", "codex"],
            {"cwd": str(Path.home())},
            stdout=stdout,
        )
        self.assertIn(code, (0, None))
        context = self._context_text(stdout.getvalue())
        self.assertEqual(context, "")

    def test_user_prompt_unmanaged_runtime_does_not_write_round_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir()
            stdout = io.StringIO()
            code = run_hook_main(
                hook_user_prompt,
                ["hook_user_prompt.py", "--agent", "codex"],
                {"cwd": str(root), "prompt": "看一下当前项目焦点"},
                stdout=stdout,
            )
            self.assertIn(code, (0, None))
            context = self._context_text(stdout.getvalue())
            self.assertIn("当前目录尚未确认为项目根", context)
            self.assertIn("AI 只有提议权", context)
            self.assertFalse((root / ".claude" / "round_state.json").exists())
            self.assertFalse((root / "topics").exists())
            self.assertFalse((root / "logs").exists())

    def test_stop_unmanaged_runtime_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir()
            stdout = io.StringIO()
            code = run_hook_main(
                hook_stop,
                ["hook_stop.py", "--agent", "codex"],
                {"cwd": str(root)},
                stdout=stdout,
            )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue(), "")

# Additional auto-install runtime coverage is kept near HookRuntimeSafetyTests.
def _hook_runtime_context(output: str) -> str:
    if not output:
        return ""
    payload = json.loads(output)
    return payload.get("hookSpecificOutput", {}).get("additionalContext", "")


def _run_auto_install_for_test(cwd: Path) -> str:
    stdout = io.StringIO()
    run_hook_main(
        hook_auto_install,
        [
            "hook_auto_install.py",
            "--agent",
            "claude",
            "--plugin-root",
            str(APP_ROOT),
        ],
        {"cwd": str(cwd)},
        stdout=stdout,
    )
    return _hook_runtime_context(stdout.getvalue())


class HookAutoInstallSafetyTests(unittest.TestCase):
    def test_auto_install_project_entry_accepts_jiacong_marker_without_claude_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / ".jiacong").mkdir(parents=True)
            (project / ".jiacong" / "project.json").write_text(
                json.dumps({"confirmed_root": True}),
                encoding="utf-8",
            )
            self.assertTrue(hook_auto_install._has_project_entry(project))

    def test_auto_install_unmanaged_home_is_silent(self):
        hook_auto_install._messages.clear()
        context = _run_auto_install_for_test(Path.home())
        self.assertEqual(context, "")

class RouteTargetTests(unittest.TestCase):
    def write_marker(self, root: Path, content: str = '{"project_id":"test"}') -> None:
        (root / ".jiacong").mkdir(parents=True, exist_ok=True)
        (root / ".jiacong" / "project.json").write_text(content, encoding="utf-8")

    def test_target_inside_confirmed_root_routes_to_that_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            target = root / "app" / "x.py"
            target.parent.mkdir(parents=True)
            target.write_text("x = 1", encoding="utf-8")
            self.write_marker(root)
            self.assertEqual(hook_roots.route_target(target), root.resolve())

    def test_target_is_directory_routes_to_ancestor_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            sub = root / "sub"
            sub.mkdir(parents=True)
            self.write_marker(root)
            self.assertEqual(hook_roots.route_target(sub), root.resolve())

    def test_nearest_confirmed_root_wins_when_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            inner = outer / "inner"
            target = inner / "f.txt"
            target.parent.mkdir(parents=True)
            target.write_text("hi", encoding="utf-8")
            self.write_marker(outer)
            self.write_marker(inner)
            self.assertEqual(hook_roots.route_target(target), inner.resolve())

    def test_target_with_no_confirmed_ancestor_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "plain" / "f.txt"
            target.parent.mkdir(parents=True)
            target.write_text("hi", encoding="utf-8")
            self.assertIsNone(hook_roots.route_target(target))

    def test_invalid_marker_does_not_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            target = root / "f.txt"
            root.mkdir(parents=True)
            target.write_text("hi", encoding="utf-8")
            self.write_marker(root, "{bad json")
            self.assertIsNone(hook_roots.route_target(target))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class HermesPluginTargetRoutingTests(unittest.TestCase):
    def load_plugin(self):
        package = "jiacong_hermes_plugin_test"
        plugin_path = APP_ROOT / "hermes-plugin" / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            package,
            plugin_path,
            submodule_search_locations=[str(plugin_path.parent)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    class FakeCtx:
        def __init__(self):
            self.hooks = {}
        def register_skill(self, *args, **kwargs):
            return None
        def register_hook(self, name, fn):
            self.hooks[name] = fn
        def register_tool(self, *args, **kwargs):
            return None

    def read_touched(self, root: Path) -> list[dict]:
        path = root / ".jiacong" / "round_touched.jsonl"
        if not path.is_file():
            path = root / ".claude" / ".round_touched.jsonl"
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def test_post_tool_call_routes_touched_file_to_target_project_not_cwd_project(self):
        plugin = self.load_plugin()
        ctx = self.FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project_a = base / "A"
            project_b = base / "B"
            make_managed_project(project_a)
            make_managed_project(project_b)
            target = project_b / "topics" / "010_Test" / "scratch.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# scratch\n", encoding="utf-8")

            ctx.hooks["post_tool_call"](
                cwd=str(project_a),
                tool_name="write_file",
                args={"path": str(target)},
                result="ok",
            )

            self.assertEqual(self.read_touched(project_a), [])
            rows_b = [row for row in self.read_touched(project_b) if row.get("tool_name") == "write_file"]
            self.assertEqual(len(rows_b), 1)
            self.assertEqual(rows_b[0]["project_root"], str(project_b.resolve()))
            self.assertEqual(rows_b[0]["file_path"], str(target.resolve()))

    def test_post_tool_call_routes_from_home_to_target_project(self):
        plugin = self.load_plugin()
        ctx = self.FakeCtx()
        plugin.register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            make_managed_project(project)
            target = project / "topics" / "010_Test" / "card.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# card\n", encoding="utf-8")

            ctx.hooks["post_tool_call"](
                cwd=str(Path.home()),
                tool_name="write_file",
                args={"path": str(target)},
                result="ok",
            )

            rows = [row for row in self.read_touched(project) if row.get("tool_name") == "write_file"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["project_root"], str(project.resolve()))
            self.assertEqual(rows[0]["file_path"], str(target.resolve()))


class HermesPluginPreLlmUnmanagedTests(HermesPluginTargetRoutingTests):
    def pre_context(self, first: bool) -> str:
        plugin = self.load_plugin()
        ctx = self.FakeCtx()
        plugin.register(ctx)
        result = ctx.hooks["pre_llm_call"](
            cwd=str(Path.home()),
            user_message="普通问答",
            is_first_turn=first,
            session_id="test-session",
        )
        return (result or {}).get("context", "")

    def test_first_turn_unmanaged_loads_full_startup_context(self):
        context = self.pre_context(True)
        self.assertIn("system_hook_prompt", context)
        self.assertIn("扫描事实", context)
        self.assertIn("硬性约束", context)
        self.assertIn("</system_hook_prompt>", context)

    def test_later_turn_unmanaged_uses_template_followup_strategy(self):
        context = self.pre_context(False)
        self.assertIn("system_hook_prompt", context)
        self.assertIn("分级建档策略", context)
        self.assertIn("当前会话未绑定已确认的项目根", context)
        self.assertIn("source layer / 双层 Git", context)
        self.assertIn("--init-management-git --source-workspace", context)
        self.assertIn("--dual-git", context)
        self.assertIn("理想实践是管理根普通 Git 管治理", context)
        self.assertIn("新项目默认不推荐走这一路", context)
        self.assertNotIn("active worktree", context)
        self.assertNotIn("先让用户选择标准项目根或 workspace 容器", context)
        self.assertNotIn("扫描事实", context)
        self.assertNotIn("下一层=", context)
        self.assertIn("</system_hook_prompt>", context)


class SourceWorkspaceInitTests(unittest.TestCase):
    def run_init(self, args: list[str]) -> tuple[int, str]:
        old_argv = sys.argv[:]
        out = io.StringIO()
        try:
            sys.argv = ["init_project.py", *args]
            with contextlib.redirect_stdout(out):
                try:
                    code = init_project.main()
                except SystemExit as exc:
                    if isinstance(exc.code, str):
                        print(exc.code)
                        code = 1
                    else:
                        code = int(exc.code or 0)
            return int(code or 0), out.getvalue()
        finally:
            sys.argv = old_argv

    def test_source_workspace_initializes_source_layer_without_management_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            code, output = self.run_init([str(root), "--type", "代码", "--source-workspace", "--source-dir", "app"])
            self.assertEqual(code, 0, output)
            self.assertFalse((root / ".git").exists())
            self.assertTrue((root / ".jiacong" / "project.json").is_file())
            self.assertTrue((root / ".jiacong" / "source.json").is_file())
            self.assertTrue((root / "topics").is_dir())
            self.assertTrue((root / "doc" / "Framework").is_dir())
            self.assertFalse((root / "src").exists())
            self.assertTrue((root / "source" / ".repo.git").exists())
            self.assertTrue((root / "source" / "main" / "app").is_dir())
            self.assertFalse((root / "source" / "main" / "topics").exists())
            self.assertFalse((root / "source" / "main" / ".jiacong").exists())
            source = json.loads((root / ".jiacong" / "source.json").read_text(encoding="utf-8"))
            self.assertEqual(source["mode"], "source_workspace")
            self.assertTrue(source["git_enabled"])
            self.assertEqual(source["source_root"], "source")
            self.assertEqual(source["worktrees_root"], "source/worktrees")
            self.assertEqual(source["main_name"], "main")
            self.assertEqual(source["source_dir"], "app")
            self.assertNotIn("active", source)
            self.assertNotIn("active_branch", source)
            self.assertNotIn("active_worktree_path", source)
            self.assertNotIn("content_path", source)
            self.assertNotIn("selection_source", source)
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(".jiacong/project.json", agents_text)
            self.assertIn("AGENTS.md", (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertFalse((root / ".claude" / "CLAUDE.md").exists())

    def test_workspace_and_source_workspace_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "invalid"
            code, output = self.run_init([str(root), "--type", "代码", "--workspace", "--source-workspace"])
            self.assertNotEqual(code, 0)
            self.assertIn("互斥", output)
            self.assertFalse((root / ".jiacong" / "source.json").exists())

    def test_workspace_and_dual_git_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "invalid"
            code, output = self.run_init([str(root), "--type", "代码", "--workspace", "--dual-git"])
            self.assertNotEqual(code, 0)
            self.assertIn("互斥", output)
            self.assertFalse((root / ".jiacong" / "project.json").exists())

    def test_init_management_git_creates_root_git_without_source_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "management"
            code, output = self.run_init([str(root), "--type", "代码", "--init-management-git"])
            self.assertEqual(code, 0, output)
            self.assertTrue((root / ".git").exists())
            self.assertFalse((root / "source" / ".repo.git").exists())
            self.assertIn("管理层 Git", output)

    def test_dual_git_creates_management_git_and_source_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dual"
            code, output = self.run_init([str(root), "--type", "代码", "--dual-git", "--source-dir", "app"])
            self.assertEqual(code, 0, output)
            self.assertTrue((root / ".git").exists())
            self.assertTrue((root / "source" / ".repo.git").is_dir())
            self.assertTrue((root / "source" / "main" / "app").is_dir())
            self.assertTrue((root / ".jiacong" / "source.json").is_file())
            self.assertIn("管理层 Git", output)
            self.assertIn("源码层 workspace", output)

    def test_legacy_workspace_does_not_create_source_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "legacy"
            code, output = self.run_init([str(root), "--type", "代码", "--workspace", "--source-dir", "app"])
            self.assertEqual(code, 0, output)
            self.assertTrue((root / ".repo.git").exists())
            self.assertTrue((root / "main" / ".jiacong").is_dir())
            self.assertTrue((root / "main" / "topics").is_dir())
            self.assertTrue((root / "main" / "doc" / "Framework").is_dir())
            self.assertTrue((root / "main" / "app").is_dir())
            self.assertTrue((root / "worktrees").is_dir())
            self.assertFalse((root / "source").exists())
            self.assertFalse((root / "main" / ".jiacong" / "source.json").exists())

    def test_source_workspace_without_git_writes_non_git_source_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nogit"
            code, output = self.run_init([
                str(root),
                "--type",
                "代码",
                "--source-workspace",
                "--source-dir",
                "app",
                "--no-source-git",
            ])
            self.assertEqual(code, 0, output)
            self.assertTrue((root / ".jiacong" / "source.json").is_file())
            self.assertTrue((root / "source" / "main" / "app").is_dir())
            self.assertFalse((root / "source" / ".repo.git").exists())
            source = json.loads((root / ".jiacong" / "source.json").read_text(encoding="utf-8"))
            self.assertFalse(source["git_enabled"])

    def test_source_workspace_refuses_existing_source_root_without_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing"
            (root / "source").mkdir(parents=True)
            (root / "source" / "keep.txt").write_text("keep", encoding="utf-8")
            code, output = self.run_init([str(root), "--type", "代码", "--source-workspace"])
            self.assertNotEqual(code, 0)
            self.assertIn("source", output)
            self.assertEqual((root / "source" / "keep.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse((root / ".jiacong" / "source.json").exists())

    def test_source_workspace_rejects_unsafe_source_paths_before_side_effects(self):
        unsafe_cases = [
            ["--source-root", "../outside"],
            ["--source-dir", "../../outside"],
            ["--source-main-name", "../main"],
            ["--source-dir", "."],
        ]
        for extra in unsafe_cases:
            with self.subTest(extra=extra):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "unsafe"
                    outside = Path(tmp) / "outside"
                    code, output = self.run_init([str(root), "--type", "代码", "--source-workspace", *extra])
                    self.assertNotEqual(code, 0)
                    self.assertIn("错误", output)
                    self.assertFalse(outside.exists())
                    self.assertFalse((root / ".jiacong" / "source.json").exists())

    def test_source_worktree_cwd_resolves_management_root_and_context_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            code, output = self.run_init([str(root), "--type", "代码", "--source-workspace", "--source-dir", "app"])
            self.assertEqual(code, 0, output)
            cwd = root / "source" / "main" / "app"
            roots = hook_roots.resolve_roots(cwd)
            self.assertEqual(roots.project_root, root.resolve())
            source = hook_roots.resolve_source(roots.project_root)
            self.assertTrue(source.configured)
            self.assertEqual(source.main_worktree, (root / "source" / "main").resolve())
            self.assertEqual(source.worktrees_root, (root / "source" / "worktrees").resolve())
            self.assertEqual(source.source_dir, "app")
            context = hook_roots.project_context_message(roots, roots.project_root)
            self.assertIn("管理根：", context)
            self.assertIn(str(root.resolve()), context)
            self.assertIn("延续当前根", context)
            self.assertNotIn("Hermes cwd", context)
            self.assertNotIn("源码层", context)
            self.assertNotIn("主源码 worktree", context)
            self.assertNotIn("额外源码 worktree 根", context)
            self.assertNotIn("代码操作不由 Jiacong Flow 维护 active 指针", context)
            self.assertNotIn("源码内容目录", context)

