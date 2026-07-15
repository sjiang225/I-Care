# I-Care 问答质量评测（82 题，Care2Caregivers 语料）

> 内部技术评测（非人类受试研究）。日期：2026-07。
> 数据源：`I-Care questions(1).docx` 的 82 个真实照护者问题（9 类）。

## 方法
- 逐题过**真实多智能体流水线**（Coordinator→Education/RAG…），记录答案 + 引用来源 + plan。
- **客观指标**：检索命中主题 = 引用来源的分类是否包含该题所属类别。
- **LLM 评审**（gpt-4o-mini）：verdict(GOOD/OK/WEAK) + grounded + safe + 理由。
- **人工复核**被标记项（局限：LLM 评审与被测同模型，偏宽松；已辅以人工抽查）。

## 结果（n=82）
- **安全**：0 unsafe（0/82）✅ — 健康场景关键。
- **合理性**：LLM 评审 82/82 GOOD（偏宽松，仅作参考）。
- **检索命中正确主题**：**71/82（87%）**。
- **答案带 Care2Caregivers 引用**：**63/82（77%）**。
- 分类命中：nutrition/recognition/sleep/care_options 全中；communication 4/8、
  understanding_dementia 4/7 偏低（见下）。

## 人工复核结论（被标记的 11 条主题不匹配）
- **多数是"相邻但合理"或分类界定本身模糊**：如"如何让他冷静/是否该争辩/如何转移注意"
  归在 communication，但检索到 challenging_behaviors 的 Calming/Behaviors 文档——**内容确实覆盖**，答案 GOOD。
- **真实语料缺口（少数）**：
  - "痴呆混乱 vs 谵妄(delirium)的区别"——语料**无谵妄内容**。系统**如实说明**"reference
    material does not specifically explain…"，再给安全的通用说明 + 建议就医。**处理得当、未编造**。
  - 记忆机制类("为何记得30年前却忘了早上")——语料对机制解释较薄，检索分散；答案准确但少引用。
- **轻微检索瑕疵**：个别本应命中专属文档（如"想上厕所的迹象"→ 应命中 incontinence）未干净命中。

## 结论
系统在这 82 题上**回答合理、零不安全**，且**遇到语料缺口会诚实说明、不编造引用**（重要的可信特性）。
主要可改进项是**检索精度/覆盖**：communication 与 understanding_dementia 类可加重排或补充语料；
delirium 等缺口可考虑扩充知识库。

## 局限（写论文需注意）
- LLM-as-judge 与被测同模型，非独立、偏宽松 → **需临床专家(顾问团)独立评审答案准确性**。
- 非人类受试评测；**usability(SUS/满意度/焦点小组，Step 3)尚未开展**。
