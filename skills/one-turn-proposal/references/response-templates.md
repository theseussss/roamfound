# Response Templates

Use these as flexible starting points. Remove sections that do not help. Rename headings to match the user's language and context.

## Template A: lightweight direct answer

Use for Level 1 requests.

```text
[direct answer]

原因是：[one short reason]

[optional next step, only if useful]
```

## Template B: standard structured answer

Use for Level 2 requests.

```text
我理解你的需求是：[reconstruct the real need in 1-2 sentences]

我的判断是：[clear recommendation / position]

可以拆成 [number] 个部分：
1. [dimension 1]
2. [dimension 2]
3. [dimension 3]

我建议：[proposal or path]

需要注意：[assumptions, risks, limits]

下一步最适合：[one concrete next step]
```

## Template C: formal general proposal

Use for Level 3 cross-domain deliverables.

```text
# [proposal title]

## 1. 需求理解
[what the user is really trying to achieve]

## 2. 核心判断
[the main recommendation and why]

## 3. 设计原则 / 决策原则
[principles that guide the proposal]

## 4. 总体架构
[main layers, modules, or components]

## 5. 具体方案
[the proposed structure, workflow, or implementation]

## 6. 执行路径
[steps, phases, deliverables, acceptance criteria]

## 7. 风险与边界
[risks, assumptions, non-goals, when not to use]

## 8. 下一步
[one best next move or small choice set]
```

## Template D: framework design proposal

Use when the user is designing a reusable intellectual framework, operating model, answer protocol, or Skill architecture.

```text
# [framework name]

## 1. 定位
这个框架用于：[scope]
不用于：[non-scope]

## 2. 核心判断
[what the framework should optimize for and what it should avoid]

## 3. 设计原则
- [principle 1]
- [principle 2]
- [principle 3]

## 4. 总体架构
架构示意：
core protocol
  - [module]
  - [module]
  - [module]
scenario adapters
  - [adapter]
  - [adapter]
hidden mechanisms
  - [mechanism]
  - [mechanism]

## 5. 模块归位
| 模块 | 作用 | 是否核心 | 何时调用 |
|---|---|---:|---|
| [module] | [role] | [yes/no] | [trigger] |

## 6. 使用流程
1. [step]
2. [step]
3. [step]

## 7. 反模式
- [what not to do]

## 8. 示例
[user input → output shape]
```

## Template E: decision memo

Use when the answer is mainly a choice.

```text
## 决策问题
[what is being decided]

## 建议
我建议：[option]

## 判断依据
- [criterion 1]
- [criterion 2]
- [criterion 3]

## 备选项比较
| 选项 | 优点 | 代价 | 适合条件 |
|---|---|---|---|

## 后果与风险
[what this choice implies]

## 重新评估条件
如果出现 [condition]，应重新判断。

## 下一步
[next action]
```

## Template F: product proposal

Use for product, MVP, PRD, or feature work.

```text
## 目标用户
[user segment]

## 用户问题
[pain point / job to be done]

## 核心价值
[why the product should exist]

## 方案
[product shape and key flows]

## MVP 范围
必须有：
- [must-have]

暂不做：
- [non-goal]

## 成功指标
[metrics]

## 风险
[risks and validation needs]

## 下一步验证
[first validation step]
```

## Template G: technical proposal / RFC

Use for technical design and implementation plans.

```text
## 背景与目标
[context and goal]

## 约束
[constraints]

## 推荐方案
[the selected design]

## 备选方案
[alternatives and why they were not selected]

## 架构 / 数据流 / 接口
[design details]

## 实施计划
[steps]

## 风险、回滚与监控
[risks, rollback, observability]

## 未决问题
[open questions]
```

## Template H: review and rewrite

Use for feedback or improvement requests.

```text
总体判断：[one clear evaluation]

最需要改的是：[highest-impact issue]

具体建议：
1. [fix]
2. [fix]
3. [fix]

可直接替换版本：
[revised draft]

下一步：[one suggested refinement]
```

## Template use rules

- Do not include empty headings.
- Do not display the template name unless useful.
- Do not include every section merely because it exists.
- If the user asks for an artifact, produce the artifact rather than describing how to produce it.

## Template I: methodology system proposal

Use when the user asks to advance a framework into a methodology system.

```text
# [methodology name]

## 1. 方法论定位
[what the methodology is, what it is not, and what outcome it optimizes for]

## 2. 核心判断
[the main design judgment and the trade-off it accepts]

## 3. 系统架构
- core protocol
- complexity regulator
- task adapters
- hidden mechanisms
- output contracts
- evaluation layer

## 4. 既有框架归位
| 框架 | 归位 | 操作角色 | 是否保留语义 |
|---|---|---|---|

## 5. 运行流程
[how the method is applied to a user request]

## 6. 质量标准
[acceptance criteria and failure modes]

## 7. 边界与不纳入项
[what the system intentionally avoids]

## 8. 下一版路线
[the next changes to make it more productized, testable, or maintainable]
```

## Template J: semantic loss audit

Use when the user asks whether integration has lost meaning.

```text
## 总体判断
[semantic preservation / compression / loss judgment]

## 归位表
| 来源框架 | 原始作用 | 当前归位 | 保留了什么 | 压缩了什么 | 是否有丢失 |
|---|---|---|---|---|---|

## 真正保留的核心语义
[what operations remain]

## 有意压缩的部分
[labels, rituals, full formats, or visible process removed]

## 需要补强的部分
[where real semantic loss or weak integration exists]

## 结论
[what to change next]
```

## Template K: evaluation plan

Use when the user wants to test or publish the methodology.

```text
## 评测目标
[what the evaluation should prove]

## 测试集
| 用例 | 期望复杂度 | 期望适配器 | 必须出现 | 必须避免 |
|---|---|---|---|---|

## 评分标准
[dimensions and pass threshold]

## 失败模式
[common failures and repair actions]

## 发布门槛
[minimum acceptable performance]
```
