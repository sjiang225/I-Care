# 用户账户 + 按用户历史 — 设计与实施记录（M9）

> 活文档 / 维护记录：先写计划，实施时逐条回填"改动记录"。
> 关联：[DESIGN.md](../DESIGN.md)、[deployment.md](deployment.md)、[wellbeing-visualization.md](wellbeing-visualization.md)。

---

## 1. 目的

让 I-Care 支持**正式账户（邮箱+密码）**，从而：
- 多用户互不混淆（后端按认证身份分数据）。
- 按用户**追踪情绪趋势 + 提问/对话历史**。
- 跨设备登录看到自己的历史。

替代现有的匿名 `session_id`（localStorage 随机 UUID）方案。

---

## 2. 安全边界（⚠️ 必须遵守，写进代码注释）

- 密码**PBKDF2-HMAC-SHA256 + 每用户随机盐**哈希存储（stdlib，无明文、无新依赖）。
- 登录发**随机会话令牌**（`secrets.token_urlsafe`），存 `auth_tokens` 表，可撤销、可过期。
- 鉴权：请求带 `Authorization: Bearer <token>`；后端**从令牌解析 user_id**，
  **绝不信任前端传来的用户 id**（防止改 id 看他人数据）。
- **原型级鉴权**：未经安全审计、**非 HIPAA 合规**。真实照护者数据上线前需专门安全/合规评审
  + HTTPS + 持久化与备份策略（配合 deployment.md / IRB）。测试勿用真实常用密码。

---

## 3. 数据模型（SQLite，沿用 app.sqlite3）

- `users(id, email UNIQUE, password_hash, salt, display_name, created_at)`
- `auth_tokens(token PRIMARY KEY, user_id, created_at, expires_at)`
- `conversations(id, user_id, created_at, title)`
- `messages(id, conversation_id, user_id, role, content, created_at)`
- `wellbeing_logs`：改为按 **user_id** 关联（新增列；旧的 session_id 保留兼容/可空）。

## 4. 后端

- **新增** `app/auth/security.py`：`hash_password/verify_password`（PBKDF2）、`new_token`。
- **改** `app/db.py`：users/auth_tokens/conversations/messages 表 + 读写方法；wellbeing 按 user。
- **新增** `app/api/auth.py`：
  - `POST /api/auth/register {email,password,display_name}` → 建用户 + 返令牌
  - `POST /api/auth/login {email,password}` → 校验 + 返令牌 + 用户信息
  - `POST /api/auth/logout` → 撤销令牌
  - `GET  /api/auth/me` → 当前用户（校验令牌）
- **新增** `app/api/deps.py`：`current_user`（FastAPI 依赖，从 Bearer 令牌解析用户；失败 401）。
- **改** `app/api/chat.py`：改为**需要登录**；用认证用户 id 作为会话键（替代前端 session_id）；
  **持久化每条消息**（user + assistant）到 messages（按当前 conversation）。
- **改** `app/api/wellbeing.py`：改为按认证用户返趋势（去掉 session_id 参数）。
- **新增** `app/api/history.py`：`GET /api/history` 返回该用户的对话/消息，供"历史"查看与续聊。

## 5. 前端

- **新增** `lib/auth.ts`：register/login/logout/me + 令牌存取（localStorage）+ 带 Auth 头的 fetch 封装。
- **新增** `components/AuthGate.tsx`：无有效令牌 → 显示登录/注册页；否则渲染 App。
- **新增** `components/auth/LoginRegister.tsx`：登录/注册切换表单（邮箱、密码、昵称）。
- **改** `components/Chat.tsx`：不再自造 session_id；请求带令牌；头部显示用户名 + **退出**；
  "New conversation" 新建 conversation；进入时可载入最近对话。
- **改** `lib/api.ts`：所有请求走带 Auth 头的封装；`streamChat`/`getWellbeing` 去掉 session_id。
- **新增（可选）** `components/History.tsx`：历史对话列表，点开续聊。

## 6. 验证结果（真实 GPT，端到端）

- 注册 A/B ✅；重复邮箱 → 409 ✅；密码错误 → 401 ✅；`/me` 无令牌 → 401 ✅。
- A、B **各自独立**：不同 conversation、history 互不可见、wellbeing 各算（A=1、B=0）✅。
- 后端只认令牌解析身份（前端改 id 无效）✅。
- 代理链路：注册 → 认证聊天写入 conversation #3 → `/history` 返回 user+assistant 两条 ✅。
- 游客（无令牌）仍可聊天、按匿名 session 记情绪 ✅。

### 实施改动记录
- ✅ **新增** `backend/app/auth/security.py`（PBKDF2 + token）。
- ✅ **改** `backend/app/db.py`：users/auth_tokens/conversations/messages 表 + 方法（`User`/`MessageRow`）。
- ✅ **新增** `backend/app/api/auth.py`（register/login/logout/me）+ `backend/app/api/deps.py`（`current_user[_optional]`）。
- ✅ **改** `backend/app/api/chat.py`：可选鉴权；登录→`owner_key="u:<id>"` + 建/续 conversation + 持久化 user/assistant 消息 + emit `meta{conversation_id}`；游客→session_id、不落库。
- ✅ **改** `backend/app/api/wellbeing.py`：登录按用户键、游客按 session。
- ✅ **新增** `backend/app/api/history.py`（`GET /api/history` 返回最近对话供续聊）。
- ✅ **改** `backend/app/main.py`：注册 auth/history 路由。
- ✅ **新增** `frontend/lib/auth.ts`（token 存取 + register/login/logout/me/getHistory）。
- ✅ **改** `frontend/lib/api.ts`：请求带 Auth 头；`streamChat` 传 conversation_id + `onMeta`；`getWellbeing` 带 Auth 头。
- ✅ **新增** `frontend/components/auth/LoginRegister.tsx`（登录/注册弹窗）。
- ✅ **改** `frontend/components/Chat.tsx`：me 恢复登录 + 载历史；头部登录/退出；conversationId 跟踪；新对话重置。
- ✅ **改** `frontend/app/globals.css`：`.signin-btn` + `.auth-*` 样式。

## 7. 决策
- 账户形式：✅ 正式账户（邮箱+密码）。
- 历史：✅ 按用户存对话/提问历史。
- 登录门槛：✅ **允许游客试用**（不强制登录）。
  - **游客**：照常聊天；情绪按前端匿名 `session_id` 临时记录；**对话不入库、无跨设备历史**。
  - **登录用户**：情绪 + 对话历史按账户持久化，可跨设备。
- 邮箱验证 / 找回密码 / 频率限制：原型**暂不做**，列入将来（真部署再加）。

### 实现方式：可选鉴权 + 统一 owner key（避免 wellbeing 迁移）
- 依赖 `current_user_optional`：有令牌→用户；无→游客。
- 情绪 owner key：登录用户 = `"u:<id>"`；游客 = 前端 `session_id`（复用现有列，不改表）。
- 消息入库：**仅登录用户**写 `messages`（按当前 conversation）。
- 前端不做硬门：头部给"登录/注册"入口；游客直接用。

## 8. 将来
- 邮箱验证、找回密码、登录限流/锁定。
- 与合规托管对接（加密存储、审计、备份、数据删除权）。
- 历史检索/导出（也可支撑研究分析）。
