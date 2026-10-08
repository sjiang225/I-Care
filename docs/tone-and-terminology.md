# R06 回应语气 · R07 中性称呼：修改与情景验证

2026-09-29。对应会议纪要 R06（肯定分享与行动、减少机械道歉开场、不附加用户未表达的情绪）和 R07（使用中性照护对象称呼）。

**状态：功能已修改，自动情景检查通过；回答语气和措辞仍需 PI／团队阅读确认。** 本文的自动检查只做初筛，不能替代人工审阅。

## 1. 修改了什么

| 位置 | 修改前 | 修改后 |
|---|---|---|
| 统一回复原则（新增 `backend/app/agents/style.py`） | 各回复规则各写各的，没有语气和称呼要求 | 教育、情绪、同伴三类回答共用同一套原则（见下） |
| 情绪支持（`emotion.py`） | 以 "Lead with genuine empathy" 开头，常生成 "I'm so sorry to hear…" | 先用一句话感谢分享，只回应用户说出的感受，肯定其主动求助等行动；适合时邀请用户想一件照顾自己的小事 |
| 情绪判断（`coordinator.py`） | 只要"表达了压力、痛苦或负担"就判为需要情绪支持 | 仅当用户用自己的话说出感受才算；询问困难话题、行为问题或服务不算 |
| 知识类回答的共情句（`education.py`） | "The caregiver also sounds emotionally stressed"，由模型推测情绪 | 只在用户说出感受时加一句感谢并回应其原话；如果前面已有情绪支持段落，就直接进入实用建议，不重复感谢 |
| 走失紧急提示（`safety.py`） | "If your loved one is missing…" | "If the person you care for is missing…" |

**统一回复原则的要点**

- 用户分享感受时，先感谢分享；只回应用户实际表达的感受，不添加或标注其他情绪。
- 用户只是提问或查资料时，直接给答案，不感谢提问，也不描述或猜测用户的感受。
- 简短、具体地肯定用户的行动（主动联系、寻求帮助、查找信息、正在做的应对），不过度夸奖。
- 不用 "I'm sorry to hear…" 这类套话开头；不以空泛鼓励代替具体帮助。
- 紧急安全情况（有人走失、受伤或处于危险中）下，不感谢、不回应情绪，先给明确的行动步骤。
- 默认称 "the person you care for" 或 "the person living with dementia"，不默认关系亲密。
- 用户说了关系（my husband、my mom），就用用户的说法称呼。
- 即使参考资料写 "loved one"，回答中也改用中性说法；手册标题保持原文。

会议范围说明：这是调整默认回应方式，不是在任何场景都禁止说 sorry。危机和急症的固定安全提示保持原文，以安全优先。

## 2. 情景验证

11 条固定测试问题，涵盖：纯资源查询、困难话题的实际问题、表达感受、感受加实际问题、感到孤单、用户说明关系、走失紧急情况。使用应用实际的对话流程和模型（gpt-4o-mini），不写入任何账号或聊天记录。修改前每条跑 2 次，修改后每条跑 3 次（模型每次回答会略有不同）。

| 检查项 | 适用问题 | 修改前 | 修改后 |
|---|---|---|---|
| 情绪判断正确 | 全部 | 22/22 | 33/33 |
| 开头没有 sorry 套话 | 全部 | 15/22 | **33/33** |
| 回答中没有 "loved one" | 全部 | 11/22 | **33/33** |
| 没给用户贴未表达的情绪 | 资源查询、实际问题 | 11/12 | **18/18** |
| 直接给答案，不感谢提问 | 资源查询、实际问题 | 12/12 | 18/18 |
| 先感谢分享 | 表达感受的问题 | 0/6 | **9/9** |
| 跟随用户的称呼（如 husband、father） | 说明关系的问题 | 7/8 | 9/12 |
| 紧急情况先给行动步骤 | 走失 | 2/2 | 3/3 |

"没给用户贴未表达的情绪"只统计针对用户本人的情绪词，例如 "you're overwhelmed"。描述照护对象的情况（如 "the person became overwhelmed"）不计入。

**残留问题（称呼 9/12）**：3 次未通过都没有使用 "loved one"。其中 2 次是走失情况，回答全程用 she/her，没重复 "wife"；1 次是 "father" 问题，开头用了 "the person you care for"，后文用 he。都没有默认关系亲密，但不完全符合"跟随用户称呼"。

## 3. 回答对比（节选）

**表达感受：** "I feel so guilty and exhausted…"

- 修改前："I'm really sorry to hear that you're feeling this way. … it's okay to feel overwhelmed sometimes."（用户没说 overwhelmed）
- 修改后："Thank you for sharing how you feel. It's completely understandable to feel guilty and exhausted … Your willingness to reach out and express your feelings shows a lot of strength."

**实际问题：** "My father refuses to eat. What should I try?"

- 修改前："It's concerning when a loved one refuses to eat. …"
- 修改后：直接给出建议，并用 "he／your father" 称呼。

**资源查询：** "Where can I find adult day care in Bergen County?"

- 修改前：先说"没有具体信息"，再给泛泛建议。
- 修改后："To find adult day care in Bergen County, you can start by contacting the Care2Caregivers helpline …"

**走失：** "My wife wandered off and I can't find her."

- 修改前：固定提示用 "your loved one"，接着是 "I'm so sorry to hear that you're feeling this way… frightening and stressful"。
- 修改后：固定提示用 "the person you care for"，接着是 "It's important to act quickly. First, check…"，并再次提醒拨打 911。

## 4. 请团队审阅的问题

1. **肯定用户的表述是否自然。** 模型常用 "shows strength" 或 "takes courage" 这类说法。团队需要判断这是否符合 Mary 提出的基于个人优势的回应方式，还是会变成新的套话。
2. **结尾的自我照顾邀请。** 情绪支持回答会在适合时邀请用户想一件照顾自己的小事，需要确认是否保留。
3. **称呼原则。** 目前是用户说了关系就跟随，否则默认用 "the person you care for"。需要确认团队是否认可。
4. **Mary 提到的 character strengths and virtues 参考资料尚未取得。** 取得后可以据此细化"肯定优势"的写法。

完整回答见 `docs/evals/tone-2026-09-29-before.json` 和 `docs/evals/tone-2026-09-29-after.json`。

## 5. 如何重新运行

```bash
cd backend
.venv/bin/python -m pytest -q                 # 包含 tests/test_tone_and_terms.py，不调用模型
.venv/bin/python scripts/eval_tone.py --label after --repeats 3 --out /tmp/after.json   # 调用真实模型，会产生少量费用
```

修改任何回复规则后，建议都重新跑一次情景验证。
