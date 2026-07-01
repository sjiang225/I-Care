# I-Care 多智能体编排设计与实施记录（Agent-as-Tool 组合）

> 本文件是**活文档 / 维护记录**：先写计划，再随实施逐条记录每一步改了什么、为什么。
> 后期维护/修改多智能体行为时，**先读本文件**。
>
> 关联文档：整体设计见 [../DESIGN.md](../DESIGN.md)。

---

## 1. 目的

让 Coordinator 能在一轮里**组合多个专家 agent**（而不是二选一），从而正确处理
"既要知识、又带情绪"的消息：先共情、记录情绪，再给带引用的循证指导。

---

## 2. 改造前的状态（问题）

`Coordinator.stream()` 流程：安全预检 → 路由（一次 tool call 得到
`needs_education / needs_emotion / primary`）→ **只选一个** agent 执行：

```python
agent = self._emotion if route["primary"] == "emotion" else self._education
yield from agent.stream(ctx)
```

**限制**：`needs_emotion` 只被 Education 用来加一句共情语气；两个 agent 的能力
无法真正叠加；情绪只有在 primary=emotion 时才被记录。

---

## 3. 改造后的目标设计

### 3.1 编排方式：确定性"计划(Plan)"组合，而非 LLM 互相辩论

Coordinator 依据路由标记生成一个**有序执行计划**，顺序执行多个 agent，全程流式：

| 路由结果 | 执行计划(steps) |
|---|---|
| 仅知识 | `[education]` |
| 仅情绪 | `[emotion]` |
| 两者都要 | `[emotion, education]`（先共情+记录，再循证指导） |
| 都不明确(闲聊) | `[education]`（兜底） |

**为什么用确定性 Plan 而不是 LLM 自治协商**（维护者请注意）：
- 可流式：LLM 综合需要先拿到各 agent 输出再合成，破坏流式；Plan 顺序流式无此问题。
- 省成本/低延迟：只有"两者都要"时才多跑一个 agent；不做 agent 互相喊话。
- 可预测、易测试、易调试——符合健康类应用 + 试点的可靠性要求。

### 3.2 关键设计：角色分离，避免引用编号冲突

两个 agent 若都发 `sources` 事件并各自用 `[1][2]` 引用，编号会串。解决办法——
**只有 Education 发 sources / 用 `[n]` 引用**（负责"事实"）；**Emotion 只做情感
支持**：可用自我照护材料**静默**改善建议措辞，但**不发 sources、不用 `[n]`**。

这既消除冲突，也贴合角色：Emotion = 温度(affective)，Education = 循证(factual)。

### 3.3 Agent 作为可组合单元：AgentRegistry

新增 `AgentRegistry`，把 agent 变成按名注册/取用的可组合单元（"agent-as-tool"
的落地）。Coordinator 通过注册表按 Plan 取用 agent，未来加新 agent 只需注册。

### 3.4 组合执行时的衔接

- 顺序：`emotion` → 连接语 → `education`，共情先行。
- `emotion` 步跑过后，设 `ctx.flags["empathy_done"]=True`，Education 不再重复共情。
- 每当计划里含 `emotion`，情绪即被 `log_wellbeing` 记录（跨时间追踪）。

### 3.5 数据流（"两者都要"一例）

```
用户消息
  → Coordinator: 安全预检（命中则先发 988/911 提示）
  → Coordinator: 路由 tool call → {needs_education:true, needs_emotion:true}
  → 生成 Plan = [emotion, education]
  → EmotionAgent.stream:  [signal wellbeing] + [delta 共情文本]        （不发 sources）
  → Coordinator: [delta 连接语]
  → EducationAgent.stream: [sources] + [delta 循证文本(带[n]引用)]
  → [done]
```

---

## 4. 逐文件改动记录（随实施填写）

> 状态标记：⏳ 计划 / ✅ 完成

- ✅ **新增** `backend/app/agents/registry.py`：`AgentRegistry`（register/get/names）。
- ✅ **改** `backend/app/agents/emotion.py`：删除 `yield ("sources", …)`；新增
  `_plain_context()` 以无编号文本静默接地；提示词改为"weave in naturally, do NOT
  use [1]"；`_assess_and_log` + `log_wellbeing` 保留；`stream()` 现只产出
  `signal` + `delta`。
- ✅ **改** `backend/app/agents/education.py`：共情引子条件由
  `needs_emotion` 改为 `needs_emotion and not empathy_done`（避免与 Emotion 步重复）。
- ✅ **改** `backend/app/agents/coordinator.py`：`__init__` 用 `AgentRegistry` 注册两个
  agent；新增 `_build_plan(route)`（emotion 优先、education 兜底）；`stream()` 改为按
  Plan 顺序执行，步骤间插入 `CONNECTOR`，并逐步设置
  `ctx.flags["empathy_done"]`；新增 `("signal",{"plan":…})` 便于观测/调试。
- ✅ `backend/app/api/chat.py`：**未改动**——接口稳定，`signal` 事件已被通用转发；回归通过。
- ✅ 前端 **未改动**——`lib/api.ts` 对未知 `signal` 事件安全忽略；组合回答按 delta 追加到同一气泡。

## 4b. 验证结果（真实 GPT，端到端）

| 场景 | plan | sources | wellbeing signal | connector |
|---|---|---|---|---|
| 知识型「夜间游走怎么办」 | `[education]` | 3 条 | 无 | 无 |
| 情绪型「孤独又疲惫」 | `[emotion]` | 无 | 有 | 无 |
| 两者都要「夜里游走 + 我快崩溃了」 | `[emotion, education]` | 5 条（单一自洽编号） | 有 | 有 |
| 危机型「我想自杀」 | safety→`[emotion]` | 无 | 有（先 988 提示） | 无 |

---

## 5. 验证计划

端到端测试 4 类消息，确认行为：
1. **知识型** → 仅 education；有 sources/引用；无 wellbeing signal。
2. **情绪型** → 仅 emotion；有 wellbeing signal；无 sources。
3. **两者都要**（如"他晚上一直游走，我快撑不住了"）→ 先共情+记录，再带引用指导；
   sources 只出现一次、编号自洽。
4. **危机型** → 先 988/911 提示，再情绪支持。

---

## 6. 如何扩展（给维护者）

新增一个 agent（例如未来的 Peer-Support）：
1. 实现 `Agent` 协议（`name` + `stream(ctx)`，见 `agents/base.py`）。
2. 在 Coordinator 里 `self._registry.register(YourAgent())`。
3. 在路由 schema / Plan 生成逻辑里加入它的触发条件。
（功能性能力优先做成**工具**挂到已有 agent，不轻易加新 agent——见 DESIGN.md。）
