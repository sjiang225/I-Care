# 主动自评：PHQ-9、GAD-7、PSS-10

实现日期：2026-09-28。承接 [升级第 1 步](upgrade-step-1.md)，以主动填写的量表替代已移除的自动推断压力图表。

## 用户流程

聊天页的 **Self-assessment** 按钮进入 **Mental Health Assessment**。引导段落和“筛查不是诊断”的提示采用 PI 提供的英文文案。除 PI 点名的 PHQ-9、GAD-7，资料目录还提供了 PSS，因此加入 PSS-10 满足压力自评需求。

1. 用户自愿选择量表。原题英文、回顾时段、选项保留，不由 AI 生成题目或解释分数。
2. 题目无默认答案，全部答完后才能提交。PHQ/GAD 有任何非零回答时，再填写原表的日常功能影响问题；该问题不计分。
3. 后端按固定规则评分，返回分数、筛查范围（PSS 显示参考分组）、说明、支持建议及原始 PDF 链接。
4. 游客可查看本次结果，答案只在提交时发送用于评分，不写入数据库。登录用户在明确标注“Submit and save my result”的按钮提交后保存答案与结果，可查看最近 20 条记录。
5. 返回量表列表可继续未提交问卷；切换到其他量表前提示是否放弃未完成内容。R01 更新后，页面顶部统一提供 Home / Chat / Self-assessment 导航，切换页面保留未提交答案、结果和滚动位置，不再因为回首页或聊天而丢失。刷新或关闭浏览器仍提示未完成内容会丢失；账号切换会重置自评组件，避免不同账号间显示前一人的结果。

本版没有趋势图、自动定期评估、自动临床诊断、自动通知研究人员、或把自评结果传给聊天 AI。英文量表没有自行翻译成其他语言。

## 资料与计分

| 量表 | 提供资料 | 回顾时段 | 计分与显示 |
| --- | --- | --- | --- |
| PHQ-9 | [PHQ - Questions.pdf](../self-assessment/PHQ%20-%20Questions.pdf) | 最近 2 周 | 9 题，每题 0–3，总分 0–27；0–4 Minimal、5–9 Mild、10–14 Moderate、15–19 Moderately severe、20–27 Severe depressive symptoms |
| GAD-7 | [Generalized-Anxiety-Scale (GAD-7).pdf](../self-assessment/Generalized-Anxiety-Scale%20(GAD-7).pdf) | 最近 2 周 | 7 题，每题 0–3，总分 0–21；0–4 Minimal、5–9 Mild、10–14 Moderate、15–21 Severe anxiety symptoms |
| PSS-10 | [PerceivedStressScale_English.pdf](../self-assessment/PerceivedStressScale_English.pdf)，第 4–5 页 | 最近 1 个月 | 10 题，每题 0–4，第 4、5、7、8 题反向计分（4−原分）；总分 0–40；0–13 Low perceived stress、14–26 Moderate perceived stress、27–40 High perceived stress（参考分组，非诊断界限） |

2026-10-02 按 PI 反馈增加 PSS 三档参考分组，范围来源为 [PI 指定的 Recallify 页面](https://recallify.ai/perceived-stress-scale/)。PSS 作者实验室明确说明该量表不是诊断工具，没有官方分数截断值，因此页面明确标注这些分类仅供一般参考，不代表诊断，也不作为自动干预或紧急风险判断依据。[CMU 量表说明](https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html)

PHQ 原附件的评分卡从 1–4 起列举；实现补全 0 分到 Minimal 区间。可参考 [PHQ-9 administration and scoring](https://projectteachny.org/app/uploads/2022/07/PHQ9-administration-and-scoring.pdf)。PHQ-9 的用途、专业解读和第 9 题后续安排参考 [University of Washington AIMS Center](https://aims.uw.edu/resource/phq-9-depression-scale/)。

原 PDF 按字节原样复制到 `frontend/public/assessments/`，页面提供来源和版权说明。网页转录仅规范换行、标点，将 PHQ 附件的“figety”拼写改为“fidgety”；PSS 的“circling”纸面作答说明改为网页选择说明。PHQ/GAD 的功能影响问题不并入 9/7 题总分；保留各附件不同的首个功能影响选项（PHQ：Not difficult at all；GAD：Not at all）。结果说明和下一步建议是应用层文案，不冒充量表原文或医疗处方。

版权：保留所提供文件的署名和版权。PHQ-9 官方页面说明无需申请复制许可；不要据此推断所有量表均为公有领域。PSS 作者当前页面将使用许可请求导向 MAPI/ePROVIDE，团队对外发布时应保留与实际用途相符的许可记录。[CMU 当前来源与许可说明](https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html)

## 第 9 题支持提示

PHQ-9 第 9 题选择任何非零答案，即在填写当下显示支持卡；提交结果和再次查看保存结果时继续显示，不因总分低而隐藏。建议及时联系合格医疗专业人员；美国即时情绪支持提供电话、短信 988 和官方网页；紧急危险提供 911/急诊说明。不将一个答案等同于临床风险诊断，也不自动联络任何第三方。[988 官方支持渠道](https://988lifeline.org/get-help/)

页面明确说明问卷没有实时人工监测，系统不会代为联系急救服务。紧急联系方式适用于当前美国/NJ 使用场景；若扩展服务地区，需要调整为当地资源。

## 接口与数据

- `GET /api/assessments/instruments`：公开量表题目、版本、选项和来源，前端按该目录渲染，避免前后端题目漂移。
- `POST /api/assessments`：接收量表 ID/版本、严格整数答案、可选功能影响选项、UUID 提交号和明确的 `save` 标志；拒绝额外分数/用户 ID 等字段，由服务器重算结果。成功响应 `Cache-Control: no-store`。
- `GET /api/assessments/history`：必须登录；仅按服务端认证用户查询最近记录，默认 20 条，最多 50 条，不接受客户端指定归属用户。响应 `Cache-Control: no-store`。

新表 `self_assessments` 独立于历史 `wellbeing_logs`，保存用户、量表版本、逐题原始答案、功能影响、结果快照及提交时间。历史页不返回逐题答案。没有删除/迁移旧压力记录。新表由现有启动初始化自动创建，无需手动 SQL。

`(user_id, submission_id)` 唯一约束让响应丢失后的相同提交重试返回原记录，避免重复保存；同提交号改答案返回 409，不覆盖记录。过期令牌返回 401，不悄悄降级为游客而丢失保存。量表版本不匹配返回 409，提示刷新页面加载最新版，再重新填写。

源代码：`backend/app/assessments/instruments.py`（定义与计分）、`backend/app/api/assessments.py`（鉴权/校验）、`backend/app/db.py`（保存/归属查询）、`frontend/components/SelfAssessment.tsx`（页面）、`frontend/lib/assessments.ts`（接口）。

## 验证

后端：`cd backend && ./.venv/bin/python -m unittest discover -s tests -v`。测试采用临时数据库和合成用户；覆盖每个 PHQ/GAD 总分和分级边界、PSS 正反计分、功能影响不计分、第 9 题低总分支持提示、非法/不完整提交、游客不落库、账号隔离、版本留存、幂等重试、旧功能停用与聊天不访问自评表。

前端：`cd frontend && npx tsc --noEmit --incremental false && npm run build`。另用临时后端数据进行实际浏览器检查：入口与三张量表、漏题校验、支持卡出现时机、结果解释、返回聊天、保存记录和窄屏布局。

本次验收结果：13 项后端测试通过，TypeScript 与生产构建通过。Chrome 实测 PHQ-9 第 9 题非零且总分 1 时仍显示支持卡；PSS 正反向题组合得到 0/40；GAD-7 得到 10/21 并成功保存、从历史重新查看。390×844 窄屏问卷和历史页无横向溢出。原始 PDF 与公开副本逐字节一致，三份文件均可通过前端访问。测试使用临时数据库与虚构账号，没有触及现有业务记录。

## 2026-10-02：PSS 参考分组更新

- 保留原题、回顾时段、反向计分及现有支持建议。应用版本更新为 `pss10-en-1994-icare-2`，题目版本本身未变。
- 结果显示总分、参考等级、简短解释及三档范围；当前档位通过边框和“Your range”文字突出，不仅依赖颜色。窄屏自动换行。
- 后端统一提供分组及来源，前端不重复定义分界。新结果保存当时的解释及分组快照。
- 旧记录保留原始总分、版本、解释和数据库快照；历史接口仅在响应中补充当前参考分组，并在详情说明旧分数按当前分组展示。无数据库迁移或旧记录重写。
- 测试覆盖 0–40 每个 PSS 总分（包含 13/14、26/27 边界）、正反计分、旧记录只读补充和用户隔离。PHQ/GAD 规则不变。

本次验证：10 项自评后端测试通过，TypeScript 检查通过。浏览器以游客身份真实提交 PSS 20 分，确认显示 Moderate perceived stress 和 14–26 当前范围；桌面、390px、320px 结果布局检查通过。后端已重启加载新版本，未使用真实账号保存测试结果。
