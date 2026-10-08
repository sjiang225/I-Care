# R09 紧急求助提示

2026-09-29。对应会议纪要 R09 / N8。**状态：已实施；新增的聊天触发关键词和 988 行仍需团队审阅。**

## 设计原则

提示分三层：首页常驻，每个页面的页脚都能一点拨号，聊天里按内容触发。**不在每条 AI 回复里重复**，这是会议讨论的方向：避免照护者看腻、避免普通提问被吓到，与 R06 "不给用户贴没表达过的情绪"一致。

## 三层提示

| 层级 | 位置 | 内容 | 出现规则 |
|---|---|---|---|
| 1 | 首页最底部，常见主题下方（按设计稿） | **Need urgent help?** 左栏 "In immediate danger?"＋〔Call 911〕按钮；右栏 "Emotional crisis support"＋可点击的 "Call or text 988"（24/7）；下面是首页页脚（免责声明、版权） | 一直显示，但需要滚动到首页底部才能看到。样式平静，不用读屏软件的警报方式，打开首页时不会打断朗读 |
| 2 | 其他页面（聊天、资料库、自评）的页脚 | "In an emergency, call 911."，其中 911 可以点击拨号 | 一直显示 |
| 3 | 聊天回复最前面 | 固定提示，号码可以点击拨号 | 规则判断到以下内容时出现：自伤（988 和 911）、急症（911）、走失（911），以及本次**新增的照护者安全（会议原句，911）** |

## 新增：照护者安全

失智症照护中，被照护者可能出现攻击行为，这正是会议原句中 "feel in danger" 的情形。判断规则在 `backend/app/agents/safety.py`，只匹配具体的说法，例如 "hit me"、"threatened me"、"scared of him"、"I don't feel safe"、"fear for her safety"、"has a knife"。以下这类普通内容不会触发：

- "It really hurt me when she forgot my name."
- "How do I handle aggression during bathing?"
- "Is my mom in danger of falling at night?"

触发固定提示后，后面的 AI 回复第一段必须先给两三条立即可做的安全步骤，比如去安全的地方、有危险时拨 911；不能先感谢、夸奖或描述感受。这条规则同样适用于走失和急症。用真实模型测试：照护者遇险和走失两个场景各跑 3 次，6/6 的回复都先给行动步骤。

## 2026-09-29 版面调整

按设计稿，首页提示从主按钮下方移到页面最底部，改为简洁的两栏样式，不再展示会议原句全文。会议原句仍用于聊天中"照护者安全"的触发提示。

需要团队留意：
- 首页提示现在要滚动到底部才能看到，不如原来醒目；
- "In immediate danger?" 没有明确写出"照护对象处于危险"的情况。

如果团队认为应更突出，可以把它移回主按钮下方，或在 "In immediate danger?" 下补一行小字 "For you or the person you are supporting"。

## 请团队审阅

1. 首页的 988 那一行是否保留。会议提到过 988，但没有形成完整的展示方案。
2. 照护者安全的判断关键词是否需要增减。可以参考 `backend/tests/test_emergency_help.py` 里会触发和不会触发的例句。
3. 首页改用设计稿的简短文案后，是否仍符合会议"本人或照护对象处于危险"的要求。

## 相关文件

`frontend/components/HomeView.tsx`（首页提示）、`frontend/components/Chat.tsx`（页脚）、`backend/app/agents/safety.py`（判断规则）、`backend/app/agents/style.py`（`safety_instruction`，紧急情况下先给行动步骤）。
