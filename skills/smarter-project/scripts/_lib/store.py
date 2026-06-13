# -*- coding: utf-8 -*-
"""
store · 写状态（套餐定义 + 模板渲染 + 项目初始化数据）

负责所有对 canonical markdown 文件的创建和结构化写入所需的数据与工具。
当前承载：架构套餐定义、基础话题卡 TOC、template profile、Jinja2 渲染。
后续承载：init_project / topic_new / card_write / set_focus / manage_roles 业务逻辑。
"""
from __future__ import annotations

import copy
import re
from pathlib import Path


_NUM_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s*$")

DEFAULT_TEMPLATE_REF = "references/base-topic-templates.md"


# --------------------------------------------------------------------------- #
# TOC 种子解析与渲染
# --------------------------------------------------------------------------- #

def parse_toc_seed(item: object, index: int) -> dict:
    """把套餐/脚本传入的 TOC 种子转成 num/title/intent。"""
    if isinstance(item, dict):
        num = str(item.get("num") or index).strip()
        title = str(item.get("title") or item.get("name") or "（待定）").strip()
        intent = str(item.get("intent") or "").strip()
        return {"num": num, "title": title, "intent": intent}

    raw = str(item).strip()
    intent = ""
    if "|" in raw:
        raw, _, intent = raw.partition("|")
        raw = raw.strip()
        intent = intent.strip()
    m = _NUM_PREFIX_RE.match(raw)
    if m:
        return {"num": m.group(1), "title": m.group(2).strip(), "intent": intent}
    return {"num": str(index), "title": raw or "（待定）", "intent": intent}


def render_toc_context(items: list[object] | None = None) -> dict[str, str]:
    """为 card.md.tmpl 渲染 frontmatter toc、只读目录和正文标题。"""
    seeds = items or [
        {"num": "1", "title": "[章节标题]", "intent": "[本章承载什么内容]"},
        {"num": "2", "title": "[章节标题]", "intent": "[本章承载什么内容]"},
    ]
    toc = [parse_toc_seed(item, idx) for idx, item in enumerate(seeds, start=1)]

    yaml_lines: list[str] = []
    view_lines: list[str] = []
    section_lines: list[str] = []
    for entry in toc:
        raw = f"{entry['num']} {entry['title']}"
        if entry["intent"]:
            raw += f" | {entry['intent']}"
        yaml_lines.append(f'  - "{raw}"')

        level = entry["num"].count(".") + 1
        indent = "  " * (level - 1)
        intent_part = f" — *{entry['intent']}*" if entry["intent"] else ""
        view_lines.append(f"{indent}- {entry['num']} {entry['title']}{intent_part}")

        hashes = "#" * (level + 1)
        section_lines.append(f"{hashes} {entry['num']} {entry['title']}\n\n（待填）")

    return {
        "toc_yaml": "\n".join(yaml_lines),
        "toc_rendered": "\n".join(view_lines),
        "sections_rendered": "\n\n".join(section_lines),
    }


# --------------------------------------------------------------------------- #
# 基础话题 template.md 构建数据（template profile）
# --------------------------------------------------------------------------- #

TEMPLATE_PROFILE_SPECS: dict[str, dict] = {
    "generic": {
        "type": "通用建构型",
        "boundary": "说明本话题的写入边界、重复单元和必要的阅读/渲染方式。",
        "section_rules": [
            ("写入边界", "说明 card.md 各 section 应承载什么，不承载什么。"),
            ("重复单元", "列出需要反复实例化的对象模板；未知字段保留“（待定）”。"),
            ("渲染约定", "说明是否需要表格、Mermaid、dashboard 或索引视图。"),
        ],
        "units": [
            {
                "key": "note_unit",
                "name": "通用条目",
                "section": "1",
                "heading": "条目：<名称>",
                "fields": [
                    ("对象", "本条目描述什么"),
                    ("位置", "应归入 card.md 的哪个 section"),
                    ("内容", "当前可确认的结论"),
                    ("待定", "未知或待验证的信息"),
                ],
            },
        ],
        "renderer_rules": ["普通话题默认使用 Markdown 小节和表格；只有地图型对象才生成 Mermaid 或 dashboard。"],
    },
    "vision": {
        "type": "稳定契约型",
        "boundary": "Vision 记录目标对象、使用/发表/验收场景、完成样态、验收标准、边界与非目标，不写执行步骤和完整正文。",
        "section_rules": [
            ("对象与场景", "先写谁会使用、阅读或验收本项目，以及项目完成后要解决什么问题。"),
            ("完成样态", "写成型产物的外观、结构、能力和可交付状态。"),
            ("验收标准", "写可判断的完成证据，不把执行动作冒充目标。"),
            ("边界", "记录暂不纳入的对象、场景和扩展方向。"),
        ],
        "units": [
            {
                "key": "vision_entry",
                "name": "Vision 条目",
                "section": "1",
                "heading": "Vision 条目：<对象名>",
                "fields": [
                    ("目标对象", "项目要生成或完成的对象是什么"),
                    ("使用场景", "谁在什么场景下使用、阅读或验收它"),
                    ("完成样态", "做成后应呈现什么形态"),
                    ("验收证据", "如何判断已经完成"),
                    ("边界", "哪些内容暂不纳入"),
                ],
            },
        ],
        "renderer_rules": ["Vision 通常不需要图形渲染；可在成型后迁入 doc/vision.md。"],
    },
    "academic_structure": {
        "type": "论证地图型",
        "boundary": "学术 Structure 记录问题链、概念链、论证链和材料归位，不写成章节目录树。",
        "section_rules": [
            ("问题链", "说明问题如何递进，而不是罗列章节标题。"),
            ("概念链", "说明核心概念、子概念和边界概念的承载关系。"),
            ("论证链", "用论证节点记录判断、依赖、证据和风险。"),
            ("材料归位", "把文献、案例、图表、公式挂到对应论证节点。"),
        ],
        "units": [
            {
                "key": "argument_node",
                "name": "论证节点",
                "section": "3",
                "heading": "论证节点：<节点名>",
                "fields": [
                    ("要成立的判断", "本节点要证明什么"),
                    ("上游依赖", "它依赖哪些概念、文献或材料"),
                    ("下游作用", "它支撑后文哪个判断"),
                    ("证据配置", "文献、案例、图表、公式"),
                    ("风险", "可能被质疑的地方"),
                ],
            },
        ],
        "renderer_rules": ["可从论证节点生成 Mermaid 依赖图；源数据仍以 card.md 表格和结构化小节为准。"],
    },
    "empirical_structure": {
        "type": "证据链地图型",
        "boundary": "实证 Structure 记录研究设计、数据链条、变量地图、模型路径和结果归位。",
        "section_rules": [
            ("研究设计", "说明问题、假设、样本、变量和识别思路如何对应。"),
            ("变量地图", "记录变量的理论角色、操作化、来源和解释风险。"),
            ("模型路径", "记录模型之间的基准、扩展、稳健性和异质性关系。"),
            ("结果归位", "说明每张表、图和结果服务哪个研究判断。"),
        ],
        "units": [
            {
                "key": "variable_node",
                "name": "变量",
                "section": "3",
                "heading": "变量：<变量名>",
                "fields": [
                    ("理论角色", "被解释变量 / 核心解释变量 / 控制变量 / 机制变量"),
                    ("操作化方式", "如何从数据变成变量"),
                    ("数据来源", "来自哪个数据集或字段"),
                    ("进入模型", "出现在哪些模型中"),
                    ("解释风险", "可能的测量偏差或替代解释"),
                ],
            },
            {
                "key": "model_path",
                "name": "模型路径",
                "section": "4",
                "heading": "模型路径：<模型名>",
                "fields": [
                    ("目的", "这个模型验证什么"),
                    ("输入", "使用哪些样本和变量"),
                    ("输出", "产生哪些结果表或图"),
                    ("对照关系", "与基准、稳健性或异质性模型怎么比较"),
                    ("解释位置", "结果服务哪个研究判断"),
                ],
            },
        ],
        "renderer_rules": ["可从变量和模型路径生成证据链图；结果解释仍回到 card.md 的对应 section。"],
    },
    "code_structure": {
        "type": "codemap 关系地图型",
        "boundary": "代码 Structure 以原子化模块为节点，以调用、依赖、数据流、状态流、事件流为边，不写成文件夹层级。",
        "section_rules": [
            ("地图范围", "说明 codemap 覆盖哪些区域，哪些区域暂未纳入。"),
            ("节点地图", "记录模块、组件、服务或脚本的原子职责、入口和输出。"),
            ("关系地图", "记录调用、读取、写入、订阅、渲染和配置影响等关系边。"),
            ("变更影响", "说明改动节点或关系会牵动哪里。"),
        ],
        "units": [
            {
                "key": "module_node",
                "name": "模块节点",
                "section": "2",
                "heading": "模块节点：<模块名>",
                "fields": [
                    ("原子职责", "这个模块独立承担什么"),
                    ("入口", "从哪里进入它"),
                    ("输出", "它产生什么结果"),
                    ("依赖", "它依赖哪些模块、配置、数据"),
                    ("被谁使用", "哪些模块调用或读取它"),
                    ("变更影响", "改它会牵动哪里"),
                ],
            },
            {
                "key": "relation_edge",
                "name": "关系边",
                "section": "3",
                "heading": "关系边：<起点> → <终点>",
                "fields": [
                    ("关系类型", "调用 / 读取 / 写入 / 订阅 / 渲染 / 配置影响"),
                    ("触发条件", "什么时候发生"),
                    ("传递对象", "参数、状态、事件、数据结构"),
                    ("风险", "断开或改动后会影响什么"),
                ],
            },
        ],
        "renderer_rules": ["可从模块节点和关系边生成 Mermaid 或 HTML codemap；渲染层不替代 card.md。"],
    },
    "academic_style": {
        "type": "文风与语言细节规范型",
        "boundary": "学术 Style 记录文风控制、术语、句法、论证节奏、引文与图表表述，不替正文写作。",
        "section_rules": [
            ("文风基调", "记录语气、姿态、论证节奏和禁忌表达。"),
            ("术语系统", "记录术语、译名、缩写和概念边界。"),
            ("句法与段落", "记录句式密度、段落推进和转折方式。"),
            ("引文与图表表述", "记录文献引入、图表标题、注释和正文衔接。"),
        ],
        "units": [
            {
                "key": "expression_rule",
                "name": "表达规则",
                "section": "1",
                "heading": "表达规则：<规则名>",
                "fields": [
                    ("适用范围", "哪些章节或文本类型适用"),
                    ("规则", "稳定表达方式是什么"),
                    ("例子", "推荐写法或禁忌写法"),
                    ("例外", "哪些场景可以偏离"),
                ],
            },
        ],
        "renderer_rules": ["Style 通常以规则表和例句索引呈现；成熟后可迁入 doc/style.md。"],
    },
    "empirical_style": {
        "type": "结果呈现规范型",
        "boundary": "实证 Style 记录统计报告口径、图表呈现、结果解释节奏和不确定性表达。",
        "section_rules": [
            ("统计报告口径", "记录系数、显著性、标准误、样本量和固定效应如何表述。"),
            ("图表呈现", "记录表题、图题、注释、单位、变量名和版式规则。"),
            ("结果解释节奏", "记录先报告什么、再解释什么。"),
            ("不确定性表达", "记录不显著、反直觉、稳健性不足时如何措辞。"),
        ],
        "units": [
            {
                "key": "result_rule",
                "name": "结果呈现规则",
                "section": "1",
                "heading": "结果呈现规则：<规则名>",
                "fields": [
                    ("适用对象", "表格 / 图形 / 模型结果 / 稳健性说明"),
                    ("报告口径", "系数、显著性、标准误、样本量等如何表述"),
                    ("解释顺序", "先报告什么，再解释什么"),
                    ("不确定性", "不显著、反直觉或稳健性不足时如何写"),
                ],
            },
        ],
        "renderer_rules": ["可生成结果呈现检查表；不替代模型结果本身。"],
    },
    "code_style": {
        "type": "UI 视觉—变量—组件映射型",
        "boundary": "代码 Style 从用户看到的画面出发，记录视觉锚点、状态、交互手感与变量/组件/实现位置的对应关系。",
        "section_rules": [
            ("视觉范围", "记录需要稳定追踪的界面区域与视觉锚点。"),
            ("映射规则", "记录视觉状态如何对应变量、props、class、token 和组件。"),
            ("交互手感", "记录用户操作、反馈、过渡和响应延迟。"),
            ("实现索引", "记录关键视觉规则对应的组件、样式文件和设计 token。"),
        ],
        "units": [
            {
                "key": "visual_anchor",
                "name": "视觉锚点",
                "section": "1",
                "heading": "视觉锚点：<对象名>",
                "fields": [
                    ("用户看到什么", "画面中的位置、形态、层级"),
                    ("状态有哪些", "normal / hover / active / loading / disabled / error"),
                    ("由什么控制", "变量、props、class、token、配置"),
                    ("落在哪里", "组件、样式文件、设计 token、渲染入口"),
                    ("交互手感", "点击、过渡、反馈、延迟、动效"),
                    ("易错点", "用户感受与组件树不一致的地方"),
                ],
            },
        ],
        "renderer_rules": ["可从视觉锚点生成 UI 映射表或 dashboard；必须保留人类从画面读起的顺序。"],
    },
    "trace": {
        "type": "重复任务单元型",
        "boundary": "Trace 以任务为单元保存问题解决全过程；背景、尝试、反馈、转折、验收是单个任务内部字段，不是整张卡的顶层 TOC。",
        "section_rules": [
            ("索引", "记录任务、状态、来源和去向，复杂任务可指向独立 Trace 话题。"),
            ("任务单元", "每个任务内部保留背景、尝试、反馈、转折、验收和遗留。"),
            ("归档与遗留", "记录已解决、冻结、撤销和未排除的风险。"),
        ],
        "units": [
            {
                "key": "trace_task",
                "name": "Trace 任务单元",
                "section": "2",
                "heading": "T{n} <任务名>",
                "fields": [
                    ("背景", "问题从哪里来"),
                    ("尝试", "做过哪些动作"),
                    ("反馈", "用户、测试或事实给了什么反馈"),
                    ("转折", "方案为什么改变"),
                    ("验收", "如何知道这一步完成"),
                    ("遗留", "还没有解决什么"),
                ],
            },
        ],
        "renderer_rules": ["Trace 通常不需要图形渲染；需要时用任务索引表呈现状态和去向。"],
    },
}

BASE_TOPIC_TEMPLATE_PROFILES: dict[str, dict[str, str]] = {
    "学术": {
        "Vision": "vision",
        "Structure": "academic_structure",
        "Style": "academic_style",
        "Trace": "trace",
    },
    "实证": {
        "Vision": "vision",
        "Structure": "empirical_structure",
        "Style": "empirical_style",
        "Trace": "trace",
    },
    "代码": {
        "Vision": "vision",
        "Structure": "code_structure",
        "Style": "code_style",
        "Trace": "trace",
    },
}


# --------------------------------------------------------------------------- #
# template profile 渲染
# --------------------------------------------------------------------------- #

def _render_section_rules(rules: list[tuple[str, str]]) -> str:
    lines = ["| Section/对象 | 写入规则 |", "|:---|:---|"]
    for name, rule in rules:
        lines.append(f"| {name} | {rule} |")
    return "\n".join(lines)


def _render_unit(unit: dict) -> str:
    lines = [
        f"<!-- unit:{unit['key']} section:{unit.get('section', '')} name:{unit['name']} -->",
        f"### {unit['heading']}",
        "",
        "| 字段 | 内容 |",
        "|:---|:---|",
    ]
    for field, desc in unit.get("fields", []):
        lines.append(f"| {field} | {desc} |")
    lines.extend(["<!-- /unit -->"])
    return "\n".join(lines)


def _render_units(units: list[dict]) -> str:
    return "\n\n".join(_render_unit(unit) for unit in units)


def _render_renderer_rules(rules: list[str]) -> str:
    return "\n".join(f"- {rule}" for rule in rules)


def render_template_context(
    topic_name: str,
    template_profile: str = "generic",
    template_ref: str = DEFAULT_TEMPLATE_REF,
) -> dict[str, str]:
    """为 topic/template.md.tmpl 渲染建构说明和单元模板。"""
    spec = TEMPLATE_PROFILE_SPECS.get(template_profile) or TEMPLATE_PROFILE_SPECS["generic"]
    return {
        "topic_name": topic_name,
        "template_profile": template_profile,
        "template_type": spec["type"],
        "template_boundary": spec["boundary"],
        "template_ref": template_ref,
        "section_templates_rendered": _render_section_rules(spec.get("section_rules", [])),
        "unit_templates_rendered": _render_units(spec.get("units", [])),
        "renderer_rules_rendered": _render_renderer_rules(spec.get("renderer_rules", [])),
    }


def framework_doc_path(topic_name: str) -> str:
    """返回 Framework 主文件相对路径。"""
    name = str(topic_name).strip()
    return f"doc/Framework/{name}/{name}.md"


def framework_readme_path(topic_name: str) -> str:
    """返回 Framework 分目录 README 相对路径。"""
    name = str(topic_name).strip()
    return f"doc/Framework/{name}/README.md"


def render_framework_file_context(base_topic: dict) -> dict[str, str]:
    """把旧基础话题语义渲染为 Framework 主文件上下文。

    Framework 迁移只迁移承载位置：TOC 来自 BASE_TOPICS_*，写入边界、
    单元模板和渲染约定来自 TEMPLATE_PROFILE_SPECS。模板只负责排版。
    """
    topic_name = str(base_topic.get("name") or "").strip()
    profile = str(base_topic.get("template_profile") or "generic").strip()
    template_ref = str(base_topic.get("template_ref") or DEFAULT_TEMPLATE_REF).strip()
    toc_ctx = render_toc_context(base_topic.get("toc", []))
    tmpl_ctx = render_template_context(topic_name, profile, template_ref)
    return {
        "framework_name": topic_name,
        "framework_doc_path": framework_doc_path(topic_name),
        "framework_readme_path": framework_readme_path(topic_name),
        "legacy_doc_path": str(base_topic.get("doc") or ""),
        **toc_ctx,
        **tmpl_ctx,
    }


def _attach_template_profiles(pkg: str, package_data: dict) -> dict:
    data = copy.deepcopy(package_data)
    profile_map = BASE_TOPIC_TEMPLATE_PROFILES.get(pkg, {})
    for bt in data.get("base_topics", []):
        bt.setdefault("template_ref", DEFAULT_TEMPLATE_REF)
        bt.setdefault("template_profile", profile_map.get(bt.get("name", ""), "generic"))
    return data


# --------------------------------------------------------------------------- #
# 架构套餐数据
# --------------------------------------------------------------------------- #

DEFAULT_ROOTS_ACADEMIC = [
    ("001_目标", "🎯目标"),
    ("002_论证", "🧠论证"),
    ("003_写作", "✍️写作"),
    ("004_管理", "🛠️管理"),
    ("005_文献", "📚文献"),
]

DEFAULT_ROOTS_EMPIRICAL = DEFAULT_ROOTS_ACADEMIC + [
    ("006_数据", "📊数据"),
    ("007_模型", "🧮模型"),
]

BASE_TOPICS_ACADEMIC: list[dict] = [
    {"name": "Vision", "root": "🛠️管理", "toc": [
        {"num": "0", "title": "选题评估", "intent": "现实背景；理论解释与创新点；大问题小切口；主线是否清晰；方法可行性；目标期刊、理由及匹配度；可衍生哪些相关选题"},
        {"num": "1", "title": "研究图景", "intent": "记录研究对象、问题域和论文想抵达的判断"},
        {"num": "2", "title": "学术场景", "intent": "记录目标读者、期刊语境、审稿关切和共同体预期"},
        {"num": "3", "title": "成稿样态", "intent": "记录论文完成后应具备的结构、论证力度和材料状态"},
        {"num": "4", "title": "验收标准", "intent": "记录判断论文可投稿、可重投或可发表的标准"},
        {"num": "5", "title": "边界与非目标", "intent": "记录本文不解决什么，哪些扩展暂不纳入"},
    ], "doc": "doc/vision.md"},
    {"name": "Structure", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "问题链", "intent": "记录论文如何进入问题，问题之间如何递进"},
        {"num": "2", "title": "概念链", "intent": "记录核心概念、子概念和边界概念之间如何承载"},
        {"num": "3", "title": "论证链", "intent": "记录判断、证据和结论之间如何支撑"},
        {"num": "4", "title": "材料归位", "intent": "记录文献、案例、图表和公式服务哪个论证节点"},
        {"num": "5", "title": "结构变更", "intent": "记录章节、材料或论证重心变化的原因"},
    ], "doc": "doc/structure.md"},
    {"name": "Style", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "文风基调", "intent": "记录语气、姿态、论证节奏和禁忌表达"},
        {"num": "2", "title": "术语系统", "intent": "记录术语、译名、缩写和概念边界的一致性"},
        {"num": "3", "title": "句法与段落", "intent": "记录句式密度、段落推进和转折方式"},
        {"num": "4", "title": "引文与图表表述", "intent": "记录文献引入、图表标题、注释和正文衔接"},
        {"num": "5", "title": "风格例外", "intent": "记录特定章节允许偏技术、偏综述或偏总结的规则"},
    ], "doc": "doc/style.md"},
    {"name": "Trace", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "追踪索引", "intent": "记录当前修订任务、状态、来源和去向"},
        {"num": "2", "title": "任务单元", "intent": "按任务保存背景、尝试、反馈、转折和验收的完整链条"},
        {"num": "3", "title": "归档与遗留", "intent": "记录已完成任务、冻结任务和后续风险"},
    ], "doc": "doc/trace.md"},
]

BASE_TOPICS_EMPIRICAL: list[dict] = [
    {"name": "Vision", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "研究问题", "intent": "记录要回答的问题、理论预期和现实背景"},
        {"num": "2", "title": "解释对象", "intent": "记录被解释现象、样本范围、时空边界和概念边界"},
        {"num": "3", "title": "预期贡献", "intent": "记录研究完成后提供的解释、证据或方法增量"},
        {"num": "4", "title": "结果样态", "intent": "记录表格、图形、模型结果和稳健性应达到的状态"},
        {"num": "5", "title": "验收标准", "intent": "记录数据、模型、解释和呈现何时算完成"},
    ], "doc": "doc/vision.md"},
    {"name": "Structure", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "研究设计", "intent": "记录问题、假设、样本、变量和识别思路如何对应"},
        {"num": "2", "title": "数据链条", "intent": "记录原始数据、清洗规则、中间表和分析数据集之间的关系"},
        {"num": "3", "title": "变量地图", "intent": "记录核心变量、控制变量、机制变量和替代变量的角色"},
        {"num": "4", "title": "模型路径", "intent": "记录基准模型、扩展模型、稳健性和异质性分析的关系"},
        {"num": "5", "title": "结果归位", "intent": "记录每张表、每张图和每个统计结果服务哪个解释节点"},
    ], "doc": "doc/structure.md"},
    {"name": "Style", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "统计报告口径", "intent": "记录系数、显著性、标准误、样本量和固定效应如何表述"},
        {"num": "2", "title": "图表呈现", "intent": "记录表题、图题、注释、单位、变量名和版式规则"},
        {"num": "3", "title": "结果解释节奏", "intent": "记录先报告什么、再解释什么，哪些结果只作补充"},
        {"num": "4", "title": "不确定性表达", "intent": "记录不显著、反直觉、稳健性不足时如何措辞"},
        {"num": "5", "title": "术语与变量命名", "intent": "记录中文术语、英文缩写、变量符号和正文称呼的一致性"},
    ], "doc": "doc/style.md"},
    {"name": "Trace", "root": "🛠️管理", "toc": [
        {"num": "1", "title": "分析索引", "intent": "记录当前数据、模型、结果任务的状态和来源"},
        {"num": "2", "title": "分析任务单元", "intent": "按任务保存数据状态、分析尝试、异常反馈、调整原因和验证遗留"},
        {"num": "3", "title": "归档与遗留", "intent": "记录已完成分析、冻结路线和未排除风险"},
    ], "doc": "doc/trace.md"},
]

BASE_TOPICS_CODE: list[dict] = [
    {"name": "Vision", "root": "🛠️工具", "toc": [
        {"num": "1", "title": "使用场景", "intent": "记录谁在什么情境下使用产品或工具"},
        {"num": "2", "title": "核心问题", "intent": "记录它必须解决的真实问题和不能偏离的目标"},
        {"num": "3", "title": "核心能力", "intent": "记录必须稳定存在的功能、行为和体验"},
        {"num": "4", "title": "完成样态", "intent": "记录做成后用户看到什么、能操作什么、带走什么结果"},
        {"num": "5", "title": "验收标准", "intent": "记录功能、体验、性能和稳定性如何判断达标"},
    ], "doc": "doc/vision.md"},
    {"name": "Structure", "root": "🛠️工具", "toc": [
        {"num": "1", "title": "地图范围", "intent": "记录当前 codemap 覆盖哪些区域，哪些区域暂未纳入"},
        {"num": "2", "title": "节点地图", "intent": "记录原子化模块、组件、服务或脚本的节点说明"},
        {"num": "3", "title": "关系地图", "intent": "记录调用、依赖、数据流、状态流和事件流的勾连关系"},
        {"num": "4", "title": "变更影响", "intent": "记录修改某个节点或关系会牵动哪些位置"},
    ], "doc": "doc/structure.md"},
    {"name": "Style", "root": "🛠️工具", "toc": [
        {"num": "1", "title": "视觉范围", "intent": "记录项目中需要稳定追踪的界面区域与视觉锚点"},
        {"num": "2", "title": "映射规则", "intent": "记录视觉状态如何对应变量、props、class、token 和组件"},
        {"num": "3", "title": "交互手感", "intent": "记录用户操作、反馈、过渡和响应延迟的体验规则"},
        {"num": "4", "title": "实现索引", "intent": "记录关键视觉规则对应的组件、样式文件和设计 token"},
    ], "doc": "doc/style.md"},
    {"name": "Trace", "root": "🛠️工具", "toc": [
        {"num": "1", "title": "问题索引", "intent": "记录当前需求、issue、bug、技术债的状态和来源"},
        {"num": "2", "title": "解决任务单元", "intent": "按问题保存背景、复现、尝试、转折和验证"},
        {"num": "3", "title": "归档与遗留", "intent": "记录已解决问题、冻结方案、风险和后续任务"},
    ], "doc": "doc/trace.md"},
]

ARCHITECTURE_PACKAGES: dict[str, dict] = {
    "学术": {
        "dirs": [
            "topics",
            "logs",
            "doc",
            "manuscript",
            "base",
            "base/perspectives",
            "base/resources",
            "base/tools",
            "base/disposition",
            "draft",
        ],
        "roots": DEFAULT_ROOTS_ACADEMIC,
        "base_topics": BASE_TOPICS_ACADEMIC,
        "files": {
            "logs/stream.md": "# 流水\n\n> 最新在上 · `[动作 | 认知 | 效力]`\n\n",
            ".gitignore": ".jiacong/cache/\n.jiacong/dashboard/\n.jiacong/round_*.json*\n.jiacong/watcher.*\n",
            "base/perspectives/_index.md": "# 视角库\n\n| 视角 | 场景 | 创建日期 |\n|:---|:---|:---|\n",
            "base/resources/_index.md": "# 资源总览\n\n> 记录项目可复用的素材矿与参考材料，兼容外部检索线索、即时新闻与多媒介知识载体：经典、专著、博论、期刊、智库、新闻、视频、音频等。\n> 外部检索与即时新闻可先进入本库；被用于论证、方案或布局时，再归入 `topics/`、`doc/` 或 `base/disposition/`。\n\n",
            "base/disposition/_index.md": "# 布局总览\n\n> 记录项目的布阵逻辑：行动者、资源、机会、渠道如何被配置成推进项目的整体态势。\n> 原始素材仍进入 `base/resources/`；本页只说明布局层的用途与边界。\n\n",
        },
    },
    "实证": {
        "dirs": [
            "topics",
            "logs",
            "doc",
            "base",
            "base/perspectives",
            "base/resources",
            "base/tools",
            "base/disposition",
            "draft",
            "data",
            "models",
            "results",
            "notebooks",
        ],
        "roots": DEFAULT_ROOTS_EMPIRICAL,
        "base_topics": BASE_TOPICS_EMPIRICAL,
        "files": {
            "logs/stream.md": "# 流水\n\n> 最新在上 · `[动作 | 认知 | 效力]`\n\n",
            ".gitignore": ".jiacong/cache/\n.jiacong/dashboard/\n.jiacong/round_*.json*\n.jiacong/watcher.*\n",
            "base/perspectives/_index.md": "# 视角库\n\n",
            "base/resources/_index.md": "# 资源总览\n\n> 记录项目可复用的素材矿与参考材料，兼容外部检索线索、即时新闻与多媒介知识载体：经典、专著、博论、期刊、智库、新闻、视频、音频等。\n> 外部检索与即时新闻可先进入本库；被用于论证、方案或布局时，再归入 `topics/`、`doc/` 或 `base/disposition/`。\n\n",
            "base/disposition/_index.md": "# 布局总览\n\n> 记录项目的布阵逻辑：行动者、资源、机会、渠道如何被配置成推进项目的整体态势。\n> 原始素材仍进入 `base/resources/`；本页只说明布局层的用途与边界。\n\n",
        },
    },
    "代码": {
        "dirs": [
            "topics",
            "logs",
            "doc",
            "base",
            "base/perspectives",
            "base/resources",
            "base/tools",
            "base/disposition",
            "draft",
            "src",
        ],
        "roots": [
            ("001_架构", "🏗️架构"),
            ("002_设计", "🧠设计"),
            ("003_工具", "🛠️工具"),
        ],
        "base_topics": BASE_TOPICS_CODE,
        "files": {
            "logs/stream.md": "# 流水\n\n",
            ".gitignore": ".jiacong/cache/\n.jiacong/dashboard/\n.jiacong/round_*.json*\n.jiacong/watcher.*\n",
            "base/perspectives/_index.md": "# 视角库\n\n",
            "base/resources/_index.md": "# 资源总览\n\n> 记录项目可复用的素材矿与参考材料，兼容外部检索线索、即时新闻与多媒介知识载体：经典、专著、博论、期刊、智库、新闻、视频、音频等。\n> 外部检索与即时新闻可先进入本库；被用于论证、方案或布局时，再归入 `topics/`、`doc/` 或 `base/disposition/`。\n\n",
            "base/disposition/_index.md": "# 布局总览\n\n> 记录项目的布阵逻辑：行动者、资源、机会、渠道如何被配置成推进项目的整体态势。\n> 原始素材仍进入 `base/resources/`；本页只说明布局层的用途与边界。\n\n",
        },
    },
    "短平快": {
        "dirs": ["logs", "doc", "draft"],
        "roots": [],
        "base_topics": [],
        "files": {
            "logs/stream.md": "# 流水\n\n",
            ".gitignore": ".jiacong/cache/\n.jiacong/dashboard/\n.jiacong/round_*.json*\n.jiacong/watcher.*\n",
        },
    },
}


def load_architecture(pkg: str, templates_dir: Path | None = None) -> dict:
    """读取架构套餐定义（hardcoded fallback）。"""
    if pkg not in ARCHITECTURE_PACKAGES:
        raise SystemExit(
            f"[错误] 未知套餐：{pkg}，可选：{list(ARCHITECTURE_PACKAGES)}"
        )
    return _attach_template_profiles(pkg, ARCHITECTURE_PACKAGES[pkg])


# --------------------------------------------------------------------------- #
# 模板渲染
# --------------------------------------------------------------------------- #

def render_template(tmpl_text: str, context: dict) -> str:
    """渲染 Jinja2 模板。缺 jinja2 时用 str.format_map 降级。"""
    try:
        from jinja2 import Template  # type: ignore
        return Template(tmpl_text, keep_trailing_newline=True).render(**context)
    except ImportError:
        converted = re.sub(
            r"\{\{\s*(\w+)(?:\s*\|\s*default\([^)]+\))?\s*\}\}",
            r"{\1}", tmpl_text,
        )
        try:
            return converted.format_map({k: str(v) for k, v in context.items()})
        except (KeyError, IndexError):
            return tmpl_text


def find_templates_dir(script_file: str) -> Path:
    """从脚本文件位置推断 templates/ 目录。"""
    script_path = Path(script_file).resolve()
    return script_path.parent.parent / "templates"
