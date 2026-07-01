# 可用性测试脚手架 — 设计与实施记录（M5，支撑 Proposal Step 3）

> ⏸️ **状态：暂缓 / 非必需（2026-07-01 讨论后决定）。**
> Proposal 原文把"观察导航、记录系统错误、记录 time-to-task"明确交给**研究人员**，
> 并未要求 App 自行记录；SUS/满意度/人口学问卷惯例上由研究员用 Qualtrics/纸质收集。
> 因此 App 侧不实施本脚手架。以下计划保留备查，若将来决定应用内数字化收集再启用。

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)。

---

## 1. 目的

把 I-Care 从"能用的系统"变成"能开展 proposal Step 3 实验的工具"：内置量表、
问卷、任务计时与数据导出，让 6 名照护者的可用性测试可以真正跑起来、并产出可分析的量化数据。

**不做**的部分（人/流程）：招募、IRB、真人焦点小组、合规托管——本脚手架只提供工具支撑。

---

## 2. Proposal Step 3 / 评估方法的硬要求（逐条对照）

| 要求 | 本脚手架如何支撑 |
|---|---|
| 人口学问卷 | 应用内 Demographic 表单 |
| 引导式任务：①搜教育材料 ②聊天对话 ③用减压资源 | 3 个引导任务 + 计时 |
| 记录任务完成时间(time-to-task) | 每任务 Start→Done 计时 |
| 记录系统错误 | 自动累计 API 错误数 + 主持人备注 |
| 观察导航行为 | 主持人现场观察 + 备注字段（不强行自动判定"错误"） |
| **SUS 量表** | 标准 10 题 + 自动 0–100 计分 |
| 满意度问卷（准确/清晰/共情/信任） | 4+ 题 Likert + 开放意见 |
| 描述性统计 | 导出接口顺带算 SUS 均值等 |
| 焦点小组 | 线下进行；应用只做数据导出配合 |

---

## 3. 目标设计

### 3.1 研究流程（独立入口，不干扰正常使用）
通过 `?study=1` 进入 **StudySession** 引导流程：

```
① 开始：输入受试编号 + 勾选知情确认 → 建 participant
② 人口学问卷
③ 任务 A/B/C：显示任务说明 → Start(计时) → 进入聊天完成 → Done/未完成
④ SUS（10 题）
⑤ 满意度问卷（准确/清晰/共情/信任 + 开放意见）
⑥ 结束致谢
```

### 3.2 SUS（标准 10 题，5 点 Likert，自动计分）
奇数题 (分−1)、偶数题 (5−分)，求和 ×2.5 → 0–100。题目用标准英文原文。

### 3.3 满意度（对齐 proposal 的四维）
准确性 / 清晰度 / 共情 / 信任 各 1 题（Likert）+ 总体 + 开放意见。

### 3.4 任务（对齐 proposal 三类）
- A 搜教育材料：如"Find guidance on handling nighttime wandering."
- B 聊天对话：如"Ask I-Care about a challenging behavior and have a short chat."
- C 减压资源：如"Find support for your own stress or well-being."
任务中复用现有 Chat；顶部显示任务条 + "Mark done / Couldn't complete"。

### 3.5 数据与导出
后端 SQLite 新表；`GET /api/study/export` 导出 JSON/CSV（含自动 SUS 计分 + 汇总）。
（隐私合规暂缓——先用测试数据。）

---

## 4. 数据模型（SQLite，沿用 app.sqlite3）

- `study_participants(id, code, consent_ack, created_at, meta_json)`
- `study_surveys(id, participant_id, kind[demographic|sus|satisfaction], answers_json, score, created_at)`
- `study_tasks(id, participant_id, task_id, duration_ms, completed, error_count, notes, created_at)`

## 5. 后端 API
- `POST /api/study/participant` → 建受试，返回 id
- `POST /api/study/survey` → 存问卷（SUS 后端自动计分）
- `POST /api/study/task` → 存任务计时/完成/错误/备注
- `GET  /api/study/export?format=json|csv` → 研究者导出 + 描述统计

## 6. 前端
- `components/study/StudySession.tsx`：流程编排（入口 `?study=1`）
- `components/study/Likert.tsx`：通用 Likert 题组
- `components/study/Demographic.tsx` / `SUS.tsx` / `Satisfaction.tsx` / `TaskRunner.tsx`
- `lib/study.ts`：study API 封装
- 复用现有 Chat 于任务阶段

---

## 7. 逐文件实施计划

> 状态：⏳ 计划 / ✅ 完成（实施时回填）

- ⏳ **改** `backend/app/db.py`：3 张 study 表 + 读写方法 + SUS 计分。
- ⏳ **新增** `backend/app/api/study.py`：participant/survey/task/export 端点。
- ⏳ **改** `backend/app/main.py`：注册 study 路由。
- ⏳ **新增** `backend/app/study/instruments.py`：SUS/满意度/人口学题目 + 任务定义（单一事实源，前后端共用语义）。
- ⏳ **新增** `frontend/lib/study.ts` + `frontend/components/study/*`。
- ⏳ **改** `frontend/components/Chat.tsx`：识别 `?study=1` → 进入 StudySession；任务条。
- ⏳ **改** `frontend/app/globals.css`：问卷/任务样式。

## 8. 验证计划
1. 走完整流程：建受试→人口学→3 任务(计时)→SUS→满意度→结束。
2. SUS 自动计分正确（用已知答案核对 0–100）。
3. `export` 返回该受试全部数据 + SUS 分 + 汇总。
4. 任务计时、错误累计、备注落库正确。

## 9. 决策（实施前确认）
1. 任务埋点深度：务实版（计时+API错误+主持人备注） vs 全自动导航/错误捕获。
2. 首版范围：一次做全流程 vs 先问卷+导出、任务计时下一轮。
3. 研究入口：`?study=1`（推荐） vs 单独部署。

## 10. 将来
- 与合规/部署对接后真实开展；焦点小组提纲；描述统计图表；多受试对比看板。
