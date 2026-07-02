# Peer-Support 模块 / 虚拟同伴互动 — 设计与实施记录（M8）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[agent-orchestration.md](agent-orchestration.md)。

---

## 1. 目的与含义

补齐 proposal Abstract 明确点名、目前唯一缺失的可实现组件：
> "…and **peer-support modules**… through … and **virtual peer interactions**…"

**"peer support"在本项目的语境**：Care2Caregivers 本身就是一条 *peer support helpline*
（过来人/同路照护者提供的支持，见 proposal 参考文献 6）。所以 peer-support ≠ 临床建议，
而是"**有相似经历的人**"带来的**归属感、被理解、你不是一个人**。

**虚拟同伴**：原型阶段没有真实用户社区，故用一个 **AI 同伴伙伴（Peer Companion）** 人设——
以"过来人照护者"的口吻共情、正常化情绪、分享同伴式的过来经验。

---

## 2. 关键设计决策（含伦理红线）

### 2.1 形态：Peer Companion **对话 agent**（而非编造的"故事库"）
在现有多智能体框架里新增一个 **PeerSupportAgent**，语气区别于其它 agent：
- Education = 循证事实（带引用）
- Emotion-Support = 承接**当下**情绪 + 减压建议
- **Peer Companion = 归属与正常化**："很多照护者都经历过这些，你不是一个人"

### 2.2 伦理红线（**必须遵守**，写进代码注释与提示词）
- **透明**：明确它是"**反映照护者普遍经历的 AI 同伴**"，**不是真人**、不冒充具体某个人。
  前端为同伴消息加标识；提示词禁止编造具体虚假个人生平。
- **用集体语气**而非虚构个人传记："许多照护者会觉得…""我们不少人都有过…"，
  **不**说"我当年照顾我妈时具体做了 X"这类可能被当真的虚假个人经历。
- **不替代临床/危机**：涉及安全/危机仍走安全护栏；同伴不给医疗断言。

### 2.3 与 Emotion 的关系（避免每轮堆两段温情）
一轮最多一个"支持性声音"：**急性情绪困扰 → Emotion；孤独/自我怀疑/"这正常吗" → Peer**。

---

## 3. 架构与接入

### 3.1 路由扩展
`ROUTE_SPEC` 增加 `needs_peer`(bool)：当用户表达**孤独、觉得没人理解、自我怀疑、
想知道"别人是不是也这样"、想找人说说话**时为真。

### 3.2 计划编排（Coordinator `_build_plan`）
```
steps = []
if needs_emotion: steps.append("emotion")      # 急性情绪优先
elif needs_peer:  steps.append("peer")          # 否则同伴归属
if needs_education or not steps: steps.append("education")
```
→ 至多一个支持性声音 + 可选 education；沿用现有连接语/empathy_done 机制。

### 3.3 PeerSupportAgent
- 人设提示词：过来人照护者口吻、归属/正常化/希望、集体语气、透明是 AI 同伴。
- 可**静默**借用 `caregiver_selfcare` 知识做具体同伴式小建议（不发 sources、不用 [n]）。
- **情绪记录**：同伴对话也属情感场景 → 复用共享的 `assess_and_log_wellbeing(ctx)`
  （把 Emotion 里的该逻辑抽成共享 helper，两处复用）。
- 高压力回喂（M6）：读 `caregiver_state` 同样温柔承接。
- 发一个 `("signal", {"agent":"peer"})` 供前端加"同伴"标识。

### 3.4 透明标识（前端）
同伴消息上方显示轻标签：**🫂 Peer Companion · an AI reflecting fellow caregivers'
experiences**，并可用不同头像色调区分。

---

## 4. 数据模型
本版**不引入**编造故事库（伦理与简洁考量）。同伴发言靠人设 + 集体语气 + 可选自我照护
知识静默支撑。（将来若要"代表性反思库"，须标注 composite/representative 并经顾问核验。）

## 5. 逐文件实施计划
> 状态：⏳ 计划 / ✅ 完成

- ✅ **新增** `backend/app/agents/wellbeing_logging.py`：`assess_and_log_wellbeing(ctx)`；
  Emotion 删除内联方法、改为调用它（Peer 复用同一个）。
- ✅ **新增** `backend/app/agents/peer.py`：`PeerSupportAgent`——过来人集体语气、透明是 AI、
  禁编造个人生平、静默借用自我照护知识、复用情绪记录、读 `caregiver_state`、发 `agent:peer` 信号。
- ✅ **改** `backend/app/agents/coordinator.py`：注册 PeerSupportAgent；`ROUTE_SPEC` 加 `needs_peer`；
  `ROUTE_SYSTEM` 说明；`_build_plan` 纳入（emotion 优先、否则 peer、再 education）；
  `empathy_done` 统计 emotion|peer。
- ✅ **改** `frontend/lib/api.ts`（`onSignal` 已支持）+ `Chat.tsx`（捕获 `agent:peer` → 消息级
  `peer` 标记 + 顶部透明标签；欢迎页加 "Talk to someone who gets it" 快捷入口）+ `globals.css`（`.peer-label`）。

## 5b. 验证结果（真实 GPT）

| 消息 | plan | 同伴标识 |
|---|---|---|
| "I feel so alone… nobody understands" | `[peer]` | ✅ 集体语气"Many of us who've cared…"、无编造个人生平 |
| "I'm exhausted and can't cope" | `[emotion]` | — （急性走情绪） |
| "How do I handle nighttime wandering?" | `[education]` | — |
| 代理链路孤独消息 | `[peer]` + `agent:peer` 信号 | ✅ 前端显示透明标签 |

## 6. 验证计划
1. "Does anyone else feel this alone? I don't think anyone understands." → 路由 `needs_peer` → 同伴归属式回应 + 🫂 标识；不冒充真人、不编造个人生平。
2. "I'm completely exhausted and can't cope." → 仍走 Emotion（急性），非 peer。
3. "How do I handle wandering?" → Education（无 peer）。
4. "I feel so alone AND how do I handle wandering?" → peer + education 组合，来源引用只在 education。
5. 高压力会话下 peer 回应也温柔承接、附自我照护。

## 7. 决策（实施前确认）
1. **形态**：Peer Companion 对话 agent（推荐） / + 代表性故事库 / 仅故事库。
2. **触发**：模型自动路由（检测到孤独/正常化需求，推荐）+ 欢迎页快捷入口 / 仅用户手动开"同伴模式"。
3. **情绪记录**：同伴对话是否也记录 wellbeing（推荐记录）。

## 8. 将来
- 真实同伴：与 Care2Caregivers 助线（1-800-424-2494）预约/转接真人 peer。
- 经顾问核验的"代表性照护者反思库"。
- 同伴社区（需真实多用户，超出原型范围）。
