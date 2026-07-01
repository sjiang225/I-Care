# 部署 — 让 I-Care 有可访问网址（M7）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[README.md](../README.md)。

---

## 1. 目的

把本地系统变成"别人能打开的网址"，用于演示 / 引导式可用性测试。
**注意**：这是**演示/测试部署**，用测试数据；**不是**合规生产环境（HIPAA/IRB 相关
托管仍待 Rutgers/NJIT IT 与 IRB 明确，见 DESIGN.md 决策 4）。

---

## 2. 两种方案（可先后进行）

### Tier 1 —— 隧道（最快，几分钟出网址）
在你的 Mac 上跑起前后端，用 **Cloudflare Quick Tunnel**（无需账号）把本地 `:3000`
暴露成一个 `https://xxx.trycloudflare.com` 公网地址。
- 优点：即刻可用、零云配置、用你本地的 KB 和 key。
- 缺点：**Mac 开着才在线**，URL 每次重启会变；仅适合有人陪同的演示/测试时段。
- 适用：马上要给人看 / 约时间做 6 人测试。

### Tier 2 —— 云托管（长期在线）
- **前端** → Vercel（Next.js 原生支持，免费）。
- **后端** → Render Web Service（Python，免费档含持久磁盘）。
- 优点：7×24 在线、固定网址。
- 缺点：要建账号、把仓库推到 GitHub、配密钥与持久化。

---

## 3. 部署前的通用准备（代码侧，我来做）

1. **随包携带知识库**：`kb.sqlite3`（175 块，含向量）目前被 `.gitignore` 忽略。
   加例外提交它，部署端无需重跑入库（省 key、确定性）。`app.sqlite3`（用户数据）保持忽略。
2. **后端可配置化**：`uvicorn` 监听 `$PORT`；`CORS_ORIGINS` 从环境读（设为前端域名）；
   `APP_DB_PATH` 从环境读（已支持）→ 生产指向持久磁盘。
3. **前端**：`BACKEND_URL` 环境变量指向后端地址（`next.config.mjs` 的 rewrite 已用它）。
4. **健康检查**：`/health` 已有。
5. **产物文件**：`Procfile` / `render.yaml`（后端启动）、`.env` 模板、部署指南。

---

## 4. 逐步实施

### 4.1 通用准备（Tier 1/2 都需要）
- ⏳ `.gitignore`：为 `backend/app/.../kb.sqlite3`（或 data 下）加例外并提交 KB。
  （若不想入库大文件，则改为部署时运行 `python -m app.kb.ingest`，但需 key。）
- ⏳ 后端 `CORS_ORIGINS`/`$PORT` 收尾（`$PORT` 由启动命令传入）。

### 4.2 Tier 1（隧道）
- ⏳ 下载 `cloudflared` 二进制（无需账号）。
- ⏳ 跑后端(8000)+前端(3000，`BACKEND_URL=http://localhost:8000`)。
- ⏳ `cloudflared tunnel --url http://localhost:3000` → 得到公网 https 网址。
- 说明：前端 Next 服务端 rewrite 会把 `/api` 转发到本地后端，故只需暴露 :3000。

### 4.3 Tier 2（云）
- ⏳ **新增** `backend/render.yaml` 或 `Procfile`：`uvicorn app.main:app --host 0.0.0.0 --port $PORT`。
- ⏳ **文档** `docs/deploy-guide.md`：一步步（推 GitHub → Render 建 Web Service、挂持久盘
  `/data`、设 `OPENAI_API_KEY`/`CORS_ORIGINS`/`APP_DB_PATH=/data/app.sqlite3` → Vercel 建
  前端、设 `BACKEND_URL` → 互填域名到 CORS）。

---

## 5. 分工（重要）

**我能做**：所有代码/配置就绪（提交 KB、Procfile/render.yaml、CORS/PORT/env 收尾、
部署指南）；Tier 1 隧道也可当场帮你跑起来给出网址（需你同意暴露本机）。

**需要你做**（像 IRB 一样，属账号/权限）：
- Tier 1：同意把本机暴露成公网（安全考量）。
- Tier 2：注册 Vercel/Render 账号、把仓库推到**你的 GitHub**、在平台上设密钥、点部署。
  （我可提供每一步命令与截图级指引，但不能用你的账号代操作。）

---

## 6. 注意事项 / 风险
- **成本**：公网可访问意味着任何人都能触发 GPT 调用 → 烧你的 OpenAI 额度。Tier 1 只在
  测试时段开、Tier 2 建议加简单口令/限流。上线前评估。
- **密钥**：`OPENAI_API_KEY` 只作为平台密钥，绝不进仓库。
- **数据持久化**：`app.sqlite3`（情绪/用户数据）在云上必须挂**持久磁盘**，否则重启即丢。
- **隐私合规**：演示部署仅用测试数据；真实受试数据须等合规托管明确。

## 7. 决策（实施前确认）
1. **先做哪一档**：Tier 1 隧道（马上有网址） / 直接 Tier 2 云 / 两个都要（先1后2）。
2. **KB 处理**：提交 `kb.sqlite3` 进仓库（推荐、简单） vs 部署时重跑入库（需 key）。
3. **Tier 2 主机**：Render（推荐，Python 免 Docker） vs 其他（Fly/Railway）。
