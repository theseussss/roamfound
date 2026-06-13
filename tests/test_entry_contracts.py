import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = APP_ROOT / "skills" / "smarter-project" / "scripts"
ENTRYPOINTS_PATH = SCRIPTS_ROOT / "_lib" / "entrypoints.py"
INIT_PROJECT_PATH = SCRIPTS_ROOT / "init_project.py"
INSTALL_PATH = APP_ROOT / "install.py"


def load_entrypoints_module():
    spec = importlib.util.spec_from_file_location("jiacong_entrypoints", ENTRYPOINTS_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["jiacong_entrypoints"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_init_project_module():
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(SCRIPTS_ROOT))
        spec = importlib.util.spec_from_file_location("jiacong_init_project_entry_contracts", INIT_PROJECT_PATH)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["jiacong_init_project_entry_contracts"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path


def load_install_module():
    spec = importlib.util.spec_from_file_location("jiacong_install_entry_contracts", INSTALL_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["jiacong_install_entry_contracts"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProjectEntrypointsContractTests(unittest.TestCase):
    def setUp(self):
        self.entrypoints = load_entrypoints_module()

    def test_project_template_uses_object_name_not_claude_centered_name(self):
        templates = APP_ROOT / "skills" / "smarter-project" / "templates" / "project"
        self.assertTrue((templates / "project_entry.md.tmpl").is_file())
        self.assertFalse((templates / "CLAUDE.md.tmpl").exists())

    def test_payload_distinguishes_canonical_native_adapters_and_legacy(self):
        payload = self.entrypoints.entrypoints_payload()
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["generated_by"], "jiacong-flow")
        self.assertEqual(payload["canonical"], "AGENTS.md")
        self.assertEqual(payload["native"]["codex"], "AGENTS.md")
        self.assertEqual(payload["adapters"]["claude"], "CLAUDE.md")
        self.assertEqual(payload["adapters"]["gemini"], "GEMINI.md")
        self.assertEqual(payload["adapters"]["hermes"], "HERMES.md")
        self.assertEqual(payload["legacy"]["claude"], ".claude/CLAUDE.md")

    def test_agents_entry_fallback_is_minimal_entry_contract(self):
        text = self.entrypoints.render_agents_entry(project_type="学术")
        self.assertIn("AGENTS.md", text)
        self.assertIn("canonical", text.lower())
        self.assertIn(".jiacong/project.json", text)
        self.assertIn(".jiacong/focus.json", text)
        self.assertIn("topics/", text)
        self.assertIn("logs/stream.md", text)
        self.assertNotIn("@./.claude/CLAUDE.md", text)
        self.assertNotIn("以 `.claude/CLAUDE.md` 作为项目管理入口", text)

    def test_cli_adapters_point_to_agents_without_copying_project_rules(self):
        for agent in ("claude", "gemini", "hermes"):
            with self.subTest(agent=agent):
                text = self.entrypoints.render_cli_adapter(agent)
                self.assertIn("AGENTS.md", text)
                self.assertIn("adapter", text.lower())
                self.assertNotIn("@./.claude/CLAUDE.md", text)
                self.assertNotIn("topics/", text)
                self.assertNotIn("logs/stream.md", text)

    def test_write_project_entrypoints_writes_files_and_matching_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.entrypoints.write_project_entrypoints(root, project_type="general")
            expected_files = [
                root / "AGENTS.md",
                root / "CLAUDE.md",
                root / "GEMINI.md",
                root / "HERMES.md",
                root / ".jiacong" / "entrypoints.json",
            ]
            for path in expected_files:
                with self.subTest(path=path):
                    self.assertTrue(path.is_file())

            payload = json.loads((root / ".jiacong" / "entrypoints.json").read_text(encoding="utf-8"))
            self.assertEqual(payload, result)
            self.assertEqual(payload["canonical"], "AGENTS.md")
            for key, rel_path in payload["adapters"].items():
                with self.subTest(adapter=key):
                    self.assertTrue((root / rel_path).is_file())
            self.assertFalse((root / ".claude" / "CLAUDE.md").exists())

    def test_write_project_entrypoints_uses_supplied_agents_entry_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_entry = "# 自定义入口\n\n模板改哪里，这里就写哪里。\n"
            self.entrypoints.write_project_entrypoints(root, project_type="general", agents_entry=agents_entry)
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), agents_entry)

    def test_entrypoints_module_does_not_hide_package_or_template_prose(self):
        text = ENTRYPOINTS_PATH.read_text(encoding="utf-8")
        forbidden = [
            "学术",
            "实证",
            "代码",
            "短平快",
            "项目理想样态",
            "验收标准",
            "doc/Framework",
            "文件索引",
            "project_entry.md.tmpl",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)

    def test_unknown_adapter_is_rejected(self):
        with self.assertRaises(ValueError):
            self.entrypoints.render_cli_adapter("unknown")


class ProjectInitializationEntrypointsTests(unittest.TestCase):
    def setUp(self):
        self.init_project = load_init_project_module()

    def test_init_project_root_writes_canonical_agents_and_root_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            report, legacy = self.init_project.init_project_root(root, "代码", skip_source_dirs=True)
            self.assertIsInstance(report, list)
            self.assertIsInstance(legacy, list)

            self.assertTrue((root / "AGENTS.md").is_file())
            self.assertTrue((root / "CLAUDE.md").is_file())
            self.assertTrue((root / "GEMINI.md").is_file())
            self.assertTrue((root / "HERMES.md").is_file())
            self.assertTrue((root / ".jiacong" / "entrypoints.json").is_file())

            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("项目入口契约", agents_text)
            self.assertIn("Framework", agents_text)
            self.assertIn("文件索引", agents_text)
            self.assertIn("Vision", agents_text)
            self.assertIn("Structure", agents_text)
            self.assertIn("Style", agents_text)
            self.assertIn("Trace", agents_text)
            self.assertIn("使用场景、核心问题、核心能力", agents_text)
            self.assertNotIn("项目理想样态", agents_text)
            self.assertIn(".jiacong/project.json", agents_text)
            self.assertIn(".jiacong/focus.json", agents_text)
            self.assertIn("topics/", agents_text)
            self.assertIn("logs/stream.md", agents_text)
            self.assertNotIn("@./.claude/CLAUDE.md", agents_text)
            self.assertNotIn(".claude/CLAUDE.md` 是项目管理入口", agents_text)

            for adapter in ("CLAUDE.md", "GEMINI.md", "HERMES.md"):
                with self.subTest(adapter=adapter):
                    text = (root / adapter).read_text(encoding="utf-8")
                    self.assertIn("AGENTS.md", text)
                    self.assertNotIn("@./.claude/CLAUDE.md", text)

            self.assertFalse((root / ".claude" / "CLAUDE.md").exists())
            self.assertFalse((root / ".claude").exists())
            self.assertIn(".jiacong/cache/", (root / ".gitignore").read_text(encoding="utf-8"))
            self.assertNotIn(".claude/.cache/", (root / ".gitignore").read_text(encoding="utf-8"))


    def test_init_project_does_not_create_claude_runtime_directory_by_default(self):
        for project_type in ("学术", "实证", "代码", "短平快"):
            with self.subTest(project_type=project_type):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "project"
                    self.init_project.init_project_root(root, project_type, skip_source_dirs=True)
                    self.assertTrue((root / ".jiacong" / "project.json").is_file())
                    self.assertFalse((root / ".claude").exists())
                    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
                    self.assertIn(".jiacong/cache/", gitignore)
                    self.assertNotIn(".claude/.cache/", gitignore)


    def test_init_project_agents_entry_is_differentiated_by_project_type(self):
        cases = {
            "学术": ["研究图景、学术场景、成稿样态", "问题链、概念链、论证链"],
            "实证": ["研究问题、解释对象、预期贡献", "研究设计、数据链条、变量地图"],
            "代码": ["使用场景、核心问题、核心能力", "地图范围、节点地图、关系地图"],
        }
        for project_type, expected_parts in cases.items():
            with self.subTest(project_type=project_type):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "project"
                    self.init_project.init_project_root(root, project_type, skip_source_dirs=True)
                    agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
                    self.assertIn("doc/Framework/Vision/Vision.md", agents_text)
                    self.assertIn("doc/Framework/Structure/Structure.md", agents_text)
                    for part in expected_parts:
                        self.assertIn(part, agents_text)

    def test_short_project_agents_entry_omits_framework_topics_and_base_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "quick"
            self.init_project.init_project_root(root, "短平快", skip_source_dirs=True)
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("短平快类型", agents_text)
            self.assertNotIn("doc/Framework/Vision/Vision.md", agents_text)
            self.assertNotIn("topics/                     — 讨论层话题晶格", agents_text)
            self.assertNotIn("base/                       — 认知基础设施", agents_text)

    def test_init_project_agents_entry_tracks_project_entry_template_changes(self):
        template_path = APP_ROOT / "skills" / "smarter-project" / "templates" / "project" / "project_entry.md.tmpl"
        original = template_path.read_text(encoding="utf-8")
        marker = "\n<!-- TEST_TEMPLATE_PROPAGATION_MARKER -->\n"
        try:
            template_path.write_text(original + marker, encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                self.init_project.init_project_root(root, "代码", skip_source_dirs=True)
                agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn("TEST_TEMPLATE_PROPAGATION_MARKER", agents_text)
        finally:
            template_path.write_text(original, encoding="utf-8")

    def test_init_project_root_preserves_existing_legacy_claude_without_using_it_as_main_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            legacy = root / ".claude" / "CLAUDE.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("# old legacy\n", encoding="utf-8")

            self.init_project.init_project_root(root, "代码", skip_source_dirs=True)

            self.assertEqual(legacy.read_text(encoding="utf-8"), "# old legacy\n")
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("@./.claude/CLAUDE.md", agents_text)
            self.assertIn("AGENTS.md", (root / "CLAUDE.md").read_text(encoding="utf-8"))


class GlobalEntrypointTextTests(unittest.TestCase):
    def setUp(self):
        self.install = load_install_module()

    def test_codex_global_entry_treats_agents_as_canonical_and_claude_as_legacy(self):
        text = self.install._codex_entry()
        self.assertIn("AGENTS.md", text)
        self.assertIn("canonical", text.lower())
        self.assertNotIn("以它作为项目管理入口", text)
        self.assertNotIn("Codex 应遵循本文件与 `.claude/CLAUDE.md`", text)

    def test_gemini_global_entry_treats_agents_as_canonical(self):
        text = self.install._gemini_entry()
        self.assertIn("AGENTS.md", text)
        self.assertIn("canonical", text.lower())
        self.assertNotIn("`.claude/CLAUDE.md` 时，优先读取", text)

    def test_hermes_entry_does_not_make_claude_legacy_the_project_main_entry(self):
        text = self.install._hermes_entry()
        self.assertNotIn("以 `.claude/CLAUDE.md` 作为项目管理入口", text)
        self.assertNotIn("@./.claude/CLAUDE.md", text)


if __name__ == "__main__":
    unittest.main()
