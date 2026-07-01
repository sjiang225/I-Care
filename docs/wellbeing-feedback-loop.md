# 情绪趋势回喂对话闭环 — 设计与实施记录（M6）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[wellbeing-visualization.md](wellbeing-visualization.md)、[agent-orchestration.md](agent-orchestration.md)。

---

## 1. 目的

闭合 proposal Step 2 的要求——"context-aware dialogue management for tracking
caregiver stress patterns and emotional well-being **over time**"。现在我们只
**记录+展示**情绪趋势；本轮让趋势**回喂对话**：当压力持续偏高/上升时，系统主动
用更温暖的语气回应、并温和地引导自我照护资源——而不是等用户开口。

---

## 2. 现状（已有基础，复用）

- `db.wellbeing_summary(session_id)` → `{count, avg_stress, latest_stress, trend, top_emotions}`（已实现）。
- Coordinator 已有 `ctx.flags` 机制向下传递上下文。
- 已有资源工具 `get_local_resources()` 与视频挑选（可复用于"引导减压"）。

**缺**：没人去读这个 summary 来影响当轮回答。

---

## 3. 目标设计

### 3.1 触发阈值（threshold-gated，避免过度触发）
在 Coordinator 每轮开始时取 `wellbeing_summary`。判定 `high_stress` 为真当：
`count >= 3` 且（`avg_stress >= 3.5` 或（`latest_stress >= 4` 且 `trend == "up"`)）。
数据不足（count<3）一律视为不触发。

### 3.2 高压力时的三个动作（都要"轻"，不喧宾夺主）
1. **温度**：给当轮 agent 注入一句 `caregiver_state` 上下文提示（不逐字引用日志），
   让回答**先温柔承接**近期状态。
2. **语气**：即便本轮是纯知识问题，也让 Education 带一句共情引子
   （复用现有 `needs_emotion` tone 机制）。
3. **引导**：确保**自我照护**资源出现——附 helplines（复用 `get_local_resources()`
   只取 helplines）+ 一个 `caregiver_selfcare` 视频（复用 `pick_videos`）。

### 3.3 设计原则（务必遵守，写进代码注释）
- **克制**：只在跨过阈值时触发；语气自然，不每轮反复念叨压力。
- **不监控感**：绝不逐字复述日志、不列举"你上次说…"；只做温柔承接。
- **支持而非评判**：目的是减负和求助引导，不是提醒他"你压力很大"。

### 3.4 数据流
```
用户消息
 → Coordinator: summary = wellbeing_summary(session)
 → 若 high_stress: flags["caregiver_state"]=温和提示; flags["high_stress"]=True;
                   flags["needs_emotion"]=True(语气); flags["resources"]+=自我照护helpline/视频
 → 正常路由/组合执行；agent 读 flags 调整语气 + 卡片带自我照护
```

---

## 4. 逐文件实施计划

> 状态：⏳ 计划 / ✅ 完成

- ✅ **新增** `backend/app/agents/state.py`：`assess_caregiver_state(summary)` →
  `CaregiverState{high_stress, note}`；阈值 `count>=3 且 (avg>=3.5 或 latest>=4且trend=up)`；
  高压力提示语单一事实源（明确"勿逐字引用、勿提追踪"）。
- ✅ **改** `backend/app/agents/coordinator.py`：路由后取 `wellbeing_summary` → `assess_caregiver_state`；
  高压力时设 `high_stress / caregiver_state / extra_video_category=caregiver_selfcare`，并
  `setdefault("resources", get_local_resources())` 补热线（无额外 LLM 调用）。
- ✅ **改** `backend/app/agents/education.py`：共情引子条件改为 `(needs_emotion 或 high_stress)
  且 not empathy_done`；有 `caregiver_state` 则注入语气；`_resources_payload` 依
  `extra_video_category` 追加一个自我照护视频（按 url 去重）。
- ✅ **改** `backend/app/agents/emotion.py`：有 `caregiver_state` 则追加到 system 提示。
- ✅ 前端：未改动（走现有资源卡片/共情通道）。

## 4b. 验证结果（真实 GPT，同一中性问题 "What is vascular dementia?"）

| 场景（seed 情绪） | 自我照护热线 | 视频 | 回答开头 |
|---|---|---|---|
| 高压力 [4,5,5] | 5 条 | +Compassion Fatigue（自我照护） | "I can see how stressful things have been for you lately…" 后接正文 ✅ |
| 低压力 [1,2,2] | 0 | 仅主题视频 | 直接答正文 ✅ |
| 数据不足 count=1 | 0 | 仅主题视频 | 直接答正文（count<3 不触发）✅ |

## 5. 验证计划
1. 给某 session 造"高且上升"的情绪历史（seed 多条 stress 4–5）。
2. 发一个**中性知识问题**（如"What is vascular dementia?"）→ 回答应**先温柔承接** +
   附**自我照护 helpline/视频**卡片。
3. 对照：低压力 session 同样问题 → 正常回答、不触发关怀。
4. 数据不足（count<3）→ 不触发。

## 6. 将来
- 阈值/触发频率可调（每会话最多主动关怀 N 次）。
- 结合长期记忆做更个性化的承接。
