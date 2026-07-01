# I-Care 情绪趋势可视化 — 设计与实施记录（M3）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[agent-orchestration.md](agent-orchestration.md)。

---

## 1. 目的

把 Emotion 步已经在记录的情绪/压力数据（`wellbeing_logs` 表）**展示出来**，
实现 proposal 的核心卖点之一——"tracking caregiver stress patterns and emotional
well-being over time"。让照护者看到自己的状态趋势，并在压力偏高时被温和地引导到
自我照护资源。

---

## 2. 当前已有的基础（复用，不重造）

- `backend/app/db.py`：`wellbeing_logs` 表 + `add_wellbeing()` + `wellbeing_trend(session_id, limit)`（返回 newest-first）。
- Emotion agent 已通过 `log_wellbeing` 工具写入 `{stress_level(1-5), emotions[], note}`。
- 每次记录会发 `("signal", {"wellbeing": …})`（前端目前忽略）。
- 前端已有稳定的 `session_id`（localStorage）。

**缺什么**：一个**读接口** + 一个**可视化视图**。

---

## 3. 目标设计

### 3.1 后端：读接口 `GET /api/wellbeing`

请求：`/api/wellbeing?session_id=<sid>&limit=30`

响应（points 按时间**升序**，便于画图）：
```json
{
  "session_id": "…",
  "points": [
    {"ts": 1719800000.0, "stress_level": 4, "emotions": ["anxiety","guilt"], "note": "…"}
  ],
  "summary": {
    "count": 12,
    "avg_stress": 3.6,
    "latest_stress": 4,
    "trend": "up",                       // up | down | steady（近段 vs 前段均值）
    "top_emotions": [["guilt",5],["anxiety",3]]
  }
}
```
- 汇总逻辑放后端（一个小 `wellbeing_summary()` 函数），前端只管画。
- `db.wellbeing_trend` 返回 newest-first → 端点里反转为升序。

### 3.2 前端：应用内视图切换（不引入路由）

- 顶部栏加一个"趋势"图标按钮（📈）→ 切换到 **WellbeingView** 面板；再点返回聊天。
- 保持单页、单文件切换，最简单、老年友好。

**WellbeingView 内容**：
1. **一句话摘要**：如"你已记录 12 次。近期压力偏高，且在上升。"（据 summary 生成，语气温和）
2. **压力柱状图**：`stress_level 1–5` 随时间的柱状图，颜色按等级（绿→黄→红）。
3. **常见情绪**：`top_emotions` 做成标签 chip。
4. **温和引导**：压力偏高时，显示一句关怀 + Care2Caregivers 热线 + 指向 Self-Care 资源链接。
5. **空状态**：还没数据时——"当你和我聊天时，我会温和地留意你的感受，并在这里显示。"

### 3.3 图表实现：图表库（已定：引入 recharts）

用 **recharts**（声明式 React 图表库，响应式、移动端友好）画压力柱状图。
- 选它原因：React 生态最主流、API 简单、`ResponsiveContainer` 适配手机宽度。
- ⚠️ 兼容性：本项目是 React 19 / Next 15。安装时验证 recharts 版本兼容 React 19；
  若有 peer 依赖冲突，回退到 `chart.js + react-chartjs-2`（canvas 方案，框架无关）。
- 颜色按压力等级映射：1–2 绿、3 黄、4–5 红。

### 3.4 内联"已记录"轻提示（已定：纳入首版）

聊天里当收到 `signal.wellbeing` 时，在该条回答下方显示一个极轻的
"💚 已记录你的感受"小标记，让追踪有可见反馈。

---

## 4. 逐文件实施计划

> 状态：⏳ 计划 / ✅ 完成（实施时回填）

- ✅ **改** `backend/app/db.py`：新增 `WellbeingSummary` dataclass + `wellbeing_summary()`
  （count/avg/latest/trend/top_emotions；trend 用后半段 vs 前半段均值差 ±0.5 判定；
  数据 <4 条记 steady）。
- ✅ **新增** `backend/app/api/wellbeing.py`：`GET /api/wellbeing`（points 升序 + summary）。
- ✅ **改** `backend/app/main.py`：`include_router(wellbeing_router)`。
- ✅ **改** `frontend/package.json`：加 `recharts ^3.9.1`（React 19 安装无冲突，未回退 chart.js）。
- ✅ **改** `frontend/lib/api.ts`：`getWellbeing()` + `WellbeingData/Point` 类型；
  `StreamHandlers` 加 `onSignal`；SSE 解析新增 `signal` 事件分发。
- ✅ **新增** `frontend/components/WellbeingView.tsx`：recharts 柱状图（颜色按等级 绿/黄/红）
  + 一句话摘要 + 情绪 chip + 高压力关怀卡 + 空状态。
- ✅ **改** `frontend/components/Chat.tsx`：`view` 状态 + 顶部📈切换；`onSignal` 捕获
  `wellbeing` → 该条回答下方"💚 Noted…"提示（点按可跳趋势）。
- ✅ **改** `frontend/app/globals.css`：`.wb-*` 视图/图表/关怀卡 + `.wb-noted` 样式。

## 4b. 验证结果（真实 GPT，端到端）

- `GET /api/wellbeing`（后端直连 & 前端代理）：points 升序、summary 正确
  （seeded viz-demo：count=5, avg=3.8, latest=5, **trend=up**, top_emotions 正确）。
- **空会话**：`{count:0, latest:null, trend:"steady", top_emotions:[]}` → 前端空状态。
- **实时刷新**：`rt-check` 会话聊前 count=0；发一条情绪型消息后 count=1
  （stress=4, emotions=[hopelessness, exhaustion]）。
- 前端 `npm run build` 通过（recharts 编译无误）。图表实际渲染建议在浏览器目视确认。

---

## 5. 验证计划

1. 造几条不同时间/等级的 wellbeing 数据（或真实聊几句情绪型消息）。
2. `GET /api/wellbeing?session_id=…` 返回 points 升序 + summary 正确（趋势判断对）。
3. 前端📈切换 → 柱状图/摘要/情绪 chip/引导都正确；空状态正常。
4. 端到端：情绪型对话后，趋势视图立刻能看到新点。

---

## 6. 决策（已定）

1. **图表**：✅ 引入图表库（recharts，React 19 兼容性安装时验证，否则回退 chart.js）。
2. **UI 放置**：✅ 应用内📈切换视图（不引路由）。
3. **首版范围**：✅ 压力柱状图 + 摘要 + 情绪 chip + 高压力引导 + 内联"已记录"提示（四项全做）。

---

## 7. 将来可扩展（记录备忘）

- 把趋势**回喂给 agent**：压力持续偏高时，Coordinator 主动引导自我照护/求助。
- 时间范围切换（近 7 天/30 天）、按情绪筛选。
- **研究导出**：为可用性测试(SUS)导出 wellbeing CSV。
