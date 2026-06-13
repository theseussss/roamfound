# Examples

These examples calibrate style. They are intentionally shorter than full real answers.

## Example 1: framework design

User:

```text
我在思考一个大模型的输出框架，不削弱大模型的能力，但能让其回答更规范，更有架构感，更能交互，更有具体清晰的判断。
```

Good response shape:

```text
我理解你的需求不是做一个固定回答模板，而是设计一套“大模型回答协议”：让模型在保留灵活性的同时，稳定完成理解、判断、结构化、提案和交互推进。

我的判断是：这个框架应该做成动态协议，而不是固定七段式。核心应该是“理解 → 判断 → 拆解 → 提案 → 风险 → 下一步”，外层再按任务类型适配。

可以分成三层：
1. 核心协议：所有复杂回答都遵守。
2. 任务适配器：产品、技术、战略、写作等场景各自调用。
3. 隐性质量机制：复杂度调节、自检、工具验证，不必全部展示给用户。

下一步最适合把它写成一个 Skill：主文件控制触发和总流程，references 文件承载复杂度、适配器、模板和自检表。
```

Why it works:

- It reframes the user's idea.
- It gives a clear judgment.
- It proposes a Skill architecture.
- It ends with a concrete next step.

## Example 2: decision support

User:

```text
这个框架应该做成系统提示词，还是做成 skill？
```

Good response shape:

```text
我的判断是：先做成 Skill，再抽象出系统提示词版。

原因是 Skill 更适合承载多文件结构：核心协议、任务适配器、模板、质量检查可以分开维护；而系统提示词适合最终沉淀成更短的运行规范。

比较来看：
- 系统提示词：轻、直接，但长了以后难维护。
- Skill：结构清晰、可扩展、可交付，更适合你现在这个“框架化输出协议”。

建议路径：
1. 先做 Skill v0.1。
2. 用几个真实问题测试。
3. 把高频稳定规则提炼成系统提示词简版。

风险是 Skill 太重会让简单问题过度结构化，所以必须加入复杂度调节器。
```

## Example 3: product proposal

User:

```text
帮我把这个做成一个产品功能。
```

Good response shape:

```text
我理解你要做的不是“一个提示词按钮”，而是一个能把用户问题自动转成高质量结构化回答的产品功能。

我的判断是：MVP 不应该先做复杂配置台，而应该先做“回答模式选择 + 动态结构生成 + 质量自检”。

目标用户：经常让 AI 产出方案、文档、策略和决策建议的知识工作者。

核心功能：
1. 自动判断问题复杂度。
2. 选择回答协议。
3. 输出带判断的结构化答案。
4. 在结尾给出下一步推进入口。

MVP 暂不做：团队权限、模板市场、复杂工作流编排。

下一步验证：拿 20 个真实问题比较普通回答与协议化回答，评估清晰度、可执行性和用户追问次数。
```

## Example 4: lightweight rewrite

User:

```text
“回答模板”这个词是不是不够准？
```

Good response shape:

```text
是的，不够准。我建议用“回答协议”或“输出协议”。

“模板”容易让人以为是固定格式；“协议”更能表达你想要的动态行为规则：什么时候复述需求，什么时候给判断，什么时候展开提案，什么时候压缩回答。
```

Why it works:

- It does not overuse the full framework.
- It gives a direct judgment and reason.

## Example 5: review / critique

User:

```text
你看看这个输出框架是不是太复杂了？
```

Good response shape:

```text
总体判断：方向对，但需要分层，否则会显得复杂。

真正的问题不是模块太多，而是哪些模块应该用户可见、哪些应该隐藏运行、哪些只在特定场景调用。

我建议这样简化：
- 用户可见：理解、判断、方案、风险、下一步。
- 隐性运行：复杂度判断、自检、多方案比较。
- 场景调用：PRD、RFC、ADR、研究综述等专用模板。

这样用户体验是轻的，底层能力是完整的。
```

## Example 6: methodology system upgrade

User:

```text
按方法论系统推进
```

Good response shape:

```text
我的判断是：现在应该把它从“回答协议 Skill”升级为“可解释、可维护、可评估的方法论系统”。

我会补四层：
1. framework map：说明每个既有框架如何归位，避免语义丢失。
2. hidden mechanisms：定义复杂度选择、SCQA framing、多方案比较、验证和自检等隐性运行机制。
3. structured output contract：为产品化、API、Agent 和评估提供稳定字段。
4. eval cases：用代表性 prompt 测试它是否既有判断又不过度模板化。

这样用户看到的是轻量清晰的回答，维护者看到的是完整方法论系统。
```

Why it works:

- It gives a clear upgrade judgment.
- It distinguishes runtime behavior from methodology documentation.
- It names concrete deliverables instead of only discussing concepts.
- It preserves the anti-bloat principle.

## Example 6: methodology-system upgrade

User:

```text
按方法论系统推进。
```

Good response shape:

```text
我的判断是：应该在现有 Skill 之上升级，而不是重写。v0.1 已经解决“回答更有结构”，v0.2 要解决“方法论可解释、可维护、可验证”。

我会补四个层：
1. framework-map：说明 human-ai interaction、金字塔原理、scqa、adr、prd、rfc、react、tot、self-refine 等分别归位到哪里。
2. hidden-mechanisms：说明复杂度路由、多方案比较、工具验证、自检修复如何隐性运行。
3. structured-output-contract：为产品化和 agent 集成提供稳定字段。
4. eval-cases：用测试用例验证这个协议没有退化成僵硬模板。

保留不变的是：动态协议优先，不把所有理论都展示给用户；简单问题仍然压缩回答。
```

Why it works:

- It gives an upgrade judgment.
- It preserves the existing skill rather than overhauling it unnecessarily.
- It turns methodology concerns into maintainable files.
- It includes validation rather than only concepts.
