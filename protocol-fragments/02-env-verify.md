# §1.2 环境验证

> 会话开始时一次性执行；用中转站 / 远程 / 切换机器时尤为关键。

身份查验通过后，进入 §1.3 启动对齐前，AI 自检并向用户报告：

- **cwd**：当前工作目录（对照用户预期）
- **平台**：Windows / Mac / Linux（决定路径分隔符）
- **git**：当前分支 + 是否有未提交改动（仅在 git 项目内）
- **关键工具**：Python 路径（见"环境规则"）/ 持久记忆机制（报告具体名称，如 memorix MCP、hermes memory、项目 Memory.md 等；无则标 ○）

推荐报告格式（一行扫完）：

`✅ cwd: <路径> · 平台: Windows · git: main (clean) · Python: ✓ · 记忆: ✓ memorix MCP`
`✅ cwd: <路径> · 平台: Linux · git: feat/x (dirty) · Python: ✓ · 记忆: ○`

**异常处理（soft warn）**：任一项与预期不符 → 标 ⚠️ 报告异常，继续等用户指令；不自动继续任务，不擅自重置。
