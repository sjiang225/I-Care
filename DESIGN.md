# I-Care 技术设计方案（Web / PWA 版）

> Development of an Intelligence Care (I-Care) Program for Dementia Caregivers
> ©2026 Rutgers, The State University of New Jersey, All rights reserved.

本方案按"先做网页应用（PWA），后续可平滑扩展到 App Store"的策略设计。

---

## 1. 设计目标与约束

- **用户**：痴呆症家庭照护者，多为中老年，需极简、大字体、易上手的界面。
- **核心能力**：多智能体对话 + Care2Caregivers 知识库 RAG + 语音交互 + 长期情绪/压力追踪。
- **首版规模**：6 人可用性测试（Step 3），重点是"能用、可靠、可迭代"，不是高并发。
- **零苹果费用**：Web/PWA，受试者用手机浏览器打开链接即可"添加到主屏幕"使用。
- **可扩展**：前后端分离，将来用同一套后端 + 壳（Capacitor/原生 WebView）即可上架 App Store。

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | **Next.js (React) + TypeScript**，PWA | 移动端友好、可装到主屏幕、将来易转原生壳 |
| UI | Tailwind CSS + 无障碍组件 | 大字体/高对比/简单布局，适配老年用户 |
| 语音 | **Web Speech API**（浏览器内置 STT + TTS） | 免费、无需原生、PWA 直接可用 |
| 后端 | **Python + FastAPI** | AI/RAG 生态最成熟，开发快 |
| LLM | **GPT（首版）**，封装成可切换接口 | 见 §4 说明；后续可换成自研小模型 |
| 向量/数据库 | **PostgreSQL + pgvector** | 一个库同时存业务数据和向量，省运维 |
| 部署 | 前端 Vercel + 后端/DB Render 或 Railway | 便宜、上线快 |

---

## 3. 系统架构

```
  手机浏览器 (PWA)
  ┌─────────────────────────────┐
  │  Next.js 前端                │
  │  · 聊天界面 (文字/语音)      │
  │  · 主题学习入口              │
  │  · 资源/设施查询            │
  │  · 情绪自评 & 趋势图        │
  └──────────────┬──────────────┘
                 │ HTTPS / SSE(流式)
  ┌──────────────▼──────────────┐
  │  FastAPI 后端                │
  │  ┌───────────────────────┐  │
  │  │  Coordinator Agent     │  │ ← 路由 & 上下文管理
  │  └───┬───────────┬────────┘  │
  │      │           │           │
  │  ┌───▼───┐   ┌───▼────────┐  │
  │  │Education│  │Emotion-    │  │
  │  │ Agent  │   │Support Agent│  │
  │  └───┬───┘   └────────────┘  │
  │      │ RAG 检索               │
  │  ┌───▼─────────────────────┐ │
  │  │ 检索层 (pgvector)        │ │
  │  └─────────────────────────┘ │
  └──────────────┬──────────────┘
                 │
  ┌──────────────▼──────────────┐
  │ PostgreSQL + pgvector        │
  │ · 知识库向量 (Care2Caregivers)│
  │ · 用户/会话/消息             │
  │ · 情绪压力时间序列           │
  └─────────────────────────────┘
```

---

## 4. 多智能体设计（对应 proposal Step 2）

- **Coordinator Agent（协调）**：判断用户意图，路由到合适子智能体；维护跨轮、跨会话上下文；处理安全/急症升级。
- **Education Agent（教育）**：基于 RAG 检索 Care2Caregivers 知识库，给出循证、可引用的照护指导。
- **Emotion-Support Agent（情绪支持）**：共情对话，识别压力/负面情绪信号，必要时引导减压资源或自评。

> 实现方式：用 LLM 的 function/tool calling 做轻量编排（Coordinator 决定调用哪个 agent + 是否检索），不引入重型框架，保证可控、可调试。

### LLM 抽象层（关键设计）

首版用 **GPT**，但代码**不直接依赖 OpenAI SDK**，而是封装一层统一接口 `LLMProvider`，将来无缝换成**自研小模型**：

```python
class LLMProvider(Protocol):
    def chat(self, messages, tools=None, **opts) -> Message: ...
    def stream_chat(self, messages, tools=None, **opts): ...   # 流式
    def embed(self, texts: list[str]) -> list[Vector]: ...      # RAG 用
```

- **实现类**：`OpenAIProvider`（首版）、将来加 `SelfHostedProvider`。
- **切换方式**：只改配置（`.env` 里的 `LLM_PROVIDER` + `base_url` + `model`），**业务代码零改动**。
- **推荐做法**：自研小模型用 **OpenAI 兼容接口**部署（vLLM / Ollama / TGI 都支持），这样连实现类都几乎不用改，改个 `base_url` 指向自己的服务即可。也可用 LiteLLM 统一网关进一步解耦。
- **覆盖范围**：抽象层同时管 **对话** 和 **embedding**，所以将来对话和向量化都能换成自研模型。
- **配套**：把各 agent 的 **prompt/参数外置成配置**，换模型时方便针对小模型重新调优。
- **回归保障**：§5 的 ~100 问题评估集在换模型后直接重跑，量化对比新旧模型质量。

---

## 5. RAG 知识库管线（对应 proposal Step 1）

1. **采集**：抓取 Care2Caregivers 教育指南/手册 + carenewjersey.org 的 NJ 设施与资源列表。
2. **清洗 & 结构化**：按 5 大主题 + 9 类 FAQ（来自 questions 文档）打标签。
3. **切块 + 向量化**：分段、生成 embedding 存入 pgvector，保留来源元数据（用于引用）。
4. **检索**：用户提问 → 向量检索 Top-K → 重排 → 交给 Education Agent 合成答案并附来源。
5. **离线评估**：用 questions 文档里约 100 个真实问题做回归测试集，保证答案准确、可追溯。

---

## 6. 数据模型（核心表）

- `users`：受试者基本信息（去标识化）。
- `sessions`：会话。
- `messages`：每轮对话（角色、内容、命中的知识来源、调用的 agent）。
- `kb_chunks`：知识库切块 + embedding + 来源元数据。
- `wellbeing_logs`：情绪/压力自评与系统推断的时间序列（用于趋势图）。

---

## 7. 功能 ↔ Proposal 对照

| Proposal 要求 | 本方案落点 |
|---|---|
| 多智能体（Education/Emotion/Coordinator） | §4 |
| RAG + Care2Caregivers 知识库 | §5 |
| 自然语言 + 语音界面 | Web Speech API |
| 上下文感知 + 长期压力追踪 | `wellbeing_logs` + 趋势图 |
| 智能手机可下载使用 | PWA"添加到主屏幕" |
| 版权声明展示 | 全站页脚固定显示 |
| NJ 资源整合 | 知识库 + 资源查询页 |
| SUS 可用性测试 | §10 测试阶段 |

---

## 8. 无障碍 / 老年友好 UX

- 默认大字体、可一键放大；高对比配色。
- 语音输入/朗读，降低打字门槛。
- 界面层级浅、按钮大、文案简单。
- 急症提示醒目（如行为突变、攻击升级时引导就医/求助）。

---

## 9. 安全与合规

- **医疗免责声明** + 紧急情况升级引导（非诊断工具）。
- **隐私**：受试者数据去标识化，传输加密；按 IRB/HIPAA 标准评估存储。
- **版权声明**（每页页脚）：
  `©2026 Rutgers, The State University of New Jersey, All rights reserved. Do not copy or reproduce without permission.`
- **IRB 伦理审批**：涉及人类受试者，开发并行推进、测试前必须获批。

---

## 10. 分阶段实施计划

**M0 — 项目脚手架**：前后端工程初始化、部署打通、版权页脚、基础聊天 UI。
**M1 — 知识库**：采集 + 清洗 Care2Caregivers/NJ 资源，建 RAG 管线，离线评估集跑通。
**M2 — 多智能体核心**：Coordinator + Education + Emotion 三 agent，流式对话，附来源。
**M3 — 语音 & 情绪追踪**：Web Speech 语音输入/朗读，情绪自评 + 趋势图。
**M4 — 打磨**：老年无障碍优化、PWA 安装体验、急症/安全提示、稳定性。
**M5 — 可用性测试支持**：SUS + 满意度问卷、任务脚本、数据导出，配合 6 人测试与迭代。

---

## 11. 将来上架 App Store 的路径

- 后端不变；前端用 **Capacitor** 把现有 Web 应用打包成原生壳 → 同一套代码即可上架 iOS/Android。
- 届时再付 Apple Developer Program（$99/年，建议走 Rutgers 机构账号）。

---

## 12. 待确认决策

1. ~~**LLM**：用 GPT，封装成可切换接口，后续可换自研小模型。~~ ✅ 已定
2. ~~**语音**：语音 + 文字首版都做。~~ ✅ 已定（语音提前到与文字同步开发）
3. ~~**语言**：首版只做英文，架构预留多语言扩展位。~~ ✅ 已定
4. ~~**数据托管 / 合规**：暂缓——首版聚焦系统开发，用测试数据/测试 key，部署与合规等 IRB/IT 答复后再切。~~ ⏸️ 暂缓
