# NJ 本地资源 + Care2Caregivers 视频 — 设计与实施记录（M4）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[agent-orchestration.md](agent-orchestration.md)。

---

## 1. 目的

补齐 proposal 的"社会支持与可用资源"：
1. **NJ 本地资源**：权威求助热线/机构（可核实电话）+ 清洗后的 NJ 设施列表（按县浏览）。
2. **Care2Caregivers 视频**：12 个 COPSA 官方视频，按主题相关地推荐给用户观看。

---

## 2. 数据现实（抓取后确认，务必记住）

### 2.1 设施列表（carenewjersey `list02_...facilities.htm`）
- 105 条，格式：`<City> NJ - New Jersey <type> facilities -- <Facility Name>, <County> County`。
- ✅ 可解析出：**城市 / 机构名 / 县**。
- ⚠️ **问题①（无联系方式）**：源站明确"we do not provide contact information"——无电话/地址/网站。
- ⚠️ **问题②（噪声）**：混入非照护机构，如 `Airmark Facility Services`、`Apex Facilities Srvs Corp`（物业/保洁公司）→ 需清洗剔除。
- ⚠️ **问题③（类型标签不可信）**：`Alzheimer's / dementia / short-term memory` 标签是**按行轮换套用**的，非真实分类 → **清洗时丢弃此字段**。

### 2.2 资源页（carenewjersey `a4_...resources.htm`）
- 非清单，是**分类导航门户**（~22 类）+ 一个总线 `(800) 989-8137`。
- → **不结构化爬取**；改为**手工 curate 少而准的权威资源**。

### 2.3 视频（care2caregivers `/videos/`）
- 12 个 YouTube 嵌入（`youtube.com/embed/<id>`），有标题；含英/西/俄三版 Bridges。
- v1 只surface 英文（`language="en"`）；西/俄保留在数据里备用。

---

## 3. 数据准确性红线

健康类应用**绝不编造电话号码**。`nj_resources.json` 只放**可核实的官方号码**，
并整体**标记 `"validation": "pending_advisory_review"`**，交顾问团/临床上线前核验、扩充
（尤其 NJ 州级机构联系方式）。设施因源站无电话，仅给 名称/城市/县 + "请经助线转介"。

---

## 4. 数据模型

### 4.1 `backend/app/tools/data/nj_facilities.json`
```json
{ "source": "carenewjersey.org/list02_...", "fetched": "2026-07-01",
  "note": "no contact info at source; type label unreliable/dropped; cleaned",
  "facilities": [ {"name": "...", "city": "...", "county": "Bergen"} ] }
```

### 4.2 `backend/app/tools/data/nj_resources.json`（手工 curate）
```json
{ "validation": "pending_advisory_review",
  "resources": [
    {"name":"Care2Caregivers Helpline","phone":"1-800-424-2494",
     "url":"https://care2caregivers.com","category":"helpline","statewide":true,
     "description":"Peer support helpline for NJ dementia caregivers."} ] }
```
仅收录高置信度号码：Care2Caregivers 助线、Alzheimer's Association 24/7、
Eldercare Locator、988、carenewjersey 总线。NJ 州级机构待顾问补充。

### 4.3 `backend/app/tools/data/videos.json`
```json
{ "source":"care2caregivers.com/help-for-caregivers/videos/","fetched":"2026-07-01",
  "videos":[ {"title":"...","youtube_id":"...","url":"https://youtu.be/...",
              "category":"sleep","language":"en"} ] }
```
类别对齐 KB 分类（sleep / challenging_behaviors / caregiver_selfcare / understanding_dementia …）。

---

## 5. 工具与接入

### 5.1 工具 `find_local_resources`
- 位置：`backend/app/tools/resources.py`，注册进现有 `ToolRegistry`。
- 签名参数：`county?`、`resource_type?`。
- 行为：返回 statewide 权威资源 + （给了 county 则）该县设施若干 + 提示"设施无联系方式，请经助线转介"。

### 5.2 视频推荐
- 不进 RAG（首版不转录）；按**主题相关**推荐：Education 检索后取命中 chunk 的主
  导 `category` → 匹配 `videos.json` 中同类英文视频，取 1–2 个。

### 5.3 接入编排（高效、仍流式）
- **资源**：扩展 Coordinator 路由 `ROUTE_SPEC`，加 `needs_resources`(bool) + `county`(string?)。
  命中则 Coordinator **确定性调用** `find_local_resources`，结果放 `ctx.flags["resources"]`。
- **视频**：Education 依据检索类别自行挑选。
- Education 汇总后发**一个** `("resources", {facilities, helplines, videos})` 事件；
  正文里点一句"下面附了本地资源/相关视频"。
- `chat.py` 透传该事件（沿用现有通用 signal/事件转发）。

### 5.4 前端（已定：结构化卡片）
回答下方一张卡片，分区展示：
- **☎ Helplines**：`tel:` 可拨打 + 网址可点。
- **🏢 NJ facilities（county）**：名称+城市（标注"无直接联系方式，请拨助线转介"）。
- **📺 Related videos**：标题 → YouTube 链接。

---

## 6. 逐文件实施计划

> 状态：⏳ 计划 / ✅ 完成（实施时回填）

- ✅ **新增** `scripts/build_nj_facilities.py`：抓取+解析+清洗；扩展了噪声正则
  （facility/facilities + service/srvs/integ/manage/mangement、magazine、jrnl、
  airmark/aramark、janitorial/cleaning/staffing）+ 剥离导航文字前缀。
- ✅ **新增** `backend/app/tools/data/nj_facilities.json`：**95 家 / 20 县**（脚本产出，含 `removed_log`）。
- ✅ **新增** `backend/app/tools/data/nj_resources.json`：5 条权威热线（`validation: pending_advisory_review`）。
- ✅ **新增** `backend/app/tools/data/videos.json`：12 个视频（10 en / 1 es / 1 ru）。
- ✅ **新增** `backend/app/tools/resources.py`：数据加载 + `get_local_resources()` +
  `find_local_resources` 工具注册 + `pick_videos(category)`。
- ✅ **改** `backend/app/agents/coordinator.py`：`ROUTE_SPEC` 加 `needs_resources/county`；
  命中即 `get_local_resources()` 入 `ctx.flags["resources"]`（无额外 LLM 调用）。
- ✅ **改** `backend/app/agents/education.py`：`_resources_payload()` 合并 flags 资源 +
  按命中主导 `category` 挑视频 → 发 `("resources", …)` 事件；提示词条件性提一句。
- ✅ **改** `backend/app/api/chat.py`：透传 `resources` 事件。
- ✅ **改** `frontend/lib/api.ts`：`onResources` + `ResourcesPayload/Helpline/Facility/VideoLink` 类型 + SSE 解析。
- ✅ **新增** `frontend/components/ResourceCard.tsx`：热线(tel: 可拨) / 设施(county) / 视频(YouTube) 分区卡片。
- ✅ **改** `frontend/components/Chat.tsx` + `globals.css`：捕获 resources → 回答下方渲染卡片 + `.resource-card` 样式。

## 6b. 验证结果（真实 GPT，端到端）

- `get_local_resources("Bergen County")` → 5 热线 + 7 设施；无 county → 仅热线。
- 路由：「find memory care near Bergen County」→ needs_resources + county=Bergen → 卡片含设施+热线 ✅。
- 视频：「up all night」→ 附 Sleep 视频；「repeat the same question」→ 附行为类视频 ✅。
- 代理链路：Essex County 请求经 3000→8000 返回 6 设施 + 5 热线 + note ✅。
- 前端 `npm run build` 通过；卡片实际渲染建议浏览器目视确认（tel: 拨号、YouTube 链接）。

---

## 7. 验证计划
1. `find_local_resources(county="Bergen")` 返回该县设施 + statewide 助线。
2. 问"How do I find memory care near Bergen County?" → 路由 needs_resources+county=Bergen → 卡片含设施+助线。
3. 问睡眠/行为类问题 → 卡片含对应主题的相关视频。
4. 前端卡片：tel: 可拨、YouTube 可点；无资源时不显示卡片。

## 8. 记录：数据清洗问题（供复核）

源列表 105 条 → 清洗后 **95 条**，**剔除 10 条**（`removed_log` 亦存于 json）：

| 剔除项 | 城市/县 | 原因 |
|---|---|---|
| Airmark Facility Services | Atlantic City / Atlantic | 物业保洁公司 |
| Airmark Facility Services | Pleasantville / Atlantic | 物业保洁公司 |
| Apex Facilities Srvs Corp | Barnegat / Ocean | 物业服务公司 |
| Crs Facility Service | Elmwood Park / Bergen | 物业服务公司 |
| Crs Facility Service | Jersey City / Hudson | 物业服务公司 |
| Crs Facility Service | Elizabeth / Union | 物业服务公司 |
| Ccg Facilities Integartion | Jersey City / Hudson | 设施集成公司 |
| Ambrose Facilities Mangement Incorporated | Westville / Gloucester | 设施管理公司 |
| Business Facilities Magazine | Eatontown / Monmouth | 杂志（非机构） |
| Mainland Jrnl … Mainland Manor C | Pleasantville / Atlantic | 源数据garbled、不可信 |

**其他已知问题 / 维护备注**：
- 源站**无任何联系方式**；设施仅 名称/城市/县，卡片已标注"请经助线转介"。
- 源站"Alzheimer's/dementia/short-term memory"类型标签**轮换套用、不可信**，已丢弃。
- 保留但属边缘：`Alzheimers Association Delaware Valley Chapter`（其实是协会分部，非住养机构，但有用）；`Synergy HomeCare`、`Compassionate Reach Senior Care Services`（居家照护，保留）。
- 覆盖 20 县，缺 Hunterdon（源站本身无）。
- **视频推荐**目前每次命中相关类别就展示，长对话可能重复；将来可"每会话每类别只提示一次"。
- `nj_resources.json` 仅收录高置信度号码，**上线前需顾问团核验并补充 NJ 州级机构联系方式**。
