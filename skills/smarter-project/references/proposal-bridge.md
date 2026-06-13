# Proposal Bridge

> **锚定**：SKILL.md §1.3 执行回复
> **定位**：连接 `smarter-project` 与并列 skill `one-turn-proposal`，不把复杂回答能力塞进项目管理 skill。

---

## 1. 分工

`smarter-project` 管项目状态：

- 焦点；
- 话题；
- scratch / card / tasks；
- 初始化；
- 角色；
- 审查；
- 脚本与 hook。

`one-turn-proposal` 管 proposal-grade 回答质量：

- 需求重构；
- 早期判断；
- 方案设计；
- 决策比较；
- 框架/方法论/协议设计；
- 证据检索与来源审查；
- 检索完备性边界；
- 可选 sidecar / schema / eval。

两个 skill 是并列关系。`one-turn-proposal` 不直接写项目文件；任何持久化仍回到 `smarter-project` 的三件套和脚本。

---

## 2. 触发

多 CLI hook 只提供增量 bridge 提示，不替代主门控。主门控仍是
`UserPromptSubmit` 每轮注入焦点、话题、最近 scratch 与流水状态，然后由模型
先判断 `延续 | 侧写 | 切焦点`。

bridge 提示分两档：

- **常驻提醒档**：每轮低噪声提醒主门控是 `smarter-project`，
  复杂回答可并用 `one-turn-proposal`，项目内产出仍回写当前话题。
- **信号提示档**：分类器只在本轮用户输入命中复杂回答、项目持久化或记录信号时
  追加一句短路由提示，提醒必要时阅读本文件和并列 skill。

最终执行仍以本 bridge 规则和当前项目事实为准。

本轮任务满足任一条件时，调用并列 skill `one-turn-proposal`：

- 用户要求提案、方案、架构、框架、方法论、路线图；
- 用户要求 skill / plugin / agent / 输出协议设计；
- 用户要求决策支持、路线比较、ADR、RFC、PRD、评审；
- 回答依赖外部事实、证据质量、来源审查或检索完备性；
- 普通回答会因缺少结构化判断而明显变弱。

不触发：

- 简单问答；
- 明确的小修小改；
- 只需执行已有脚本；
- 只需记录 scratch 的轻量讨论。

---

## 3. 回写纪律

调用 `one-turn-proposal` 后，按结果性质回写：

- 过程、分歧、用户原话 → `scratch.md`；
- 稳定结论 → `card.md`；
- 后续动作 → `tasks.md`；
- 成型提案或评审报告 → 话题内额外文件，并在 scratch 中索引。

如果 `one-turn-proposal` 不可用，简单任务继续；复杂任务先给降级版判断，并在 scratch 记录“缺少并列 skill，需修复安装”。
