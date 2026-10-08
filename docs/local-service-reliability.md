# 本机 ngrok 预览的稳定运行

2026-09-30。

## 已确认的原因与边界

本次故障时 ngrok 隧道和 8000 后端仍运行，但 3000 前端没有进程监听，公网返回 502 / ERR_NGROK_8012。旧前端缺少足够退出记录，无法断定具体退出原因。当前原始启动方式是 `next dev` 与独立的 uvicorn/ngrok 进程，没有 launchd 托管；进程退出后无人重启。

ngrok 只是把公网请求转发给电脑，并不替电脑运行应用。即使自动恢复配置完成，关机、退出当前 macOS 用户、休眠、合盖或断网时仍可能不可用。当前机器接电的空闲睡眠设置为 0，电池模式为 1；本轮没有修改电源设置，也没有设置常驻防休眠。

要消除对这台 Mac 的依赖，应部署到持续在线的学校/实验室服务器或云服务器，使用正式构建、进程管理、持久磁盘、备份与监测。仍不能承诺任何服务永不故障。本地自动恢复解决的是常见进程退出与卡住，不能替代服务器部署。

## 当前实施状态

- 已新增 `scripts/local_services.py`，构建与启动过程不改业务逻辑、不改 `.env` 或已有数据库。
- 已完成隔离正式构建及临时端口的首页/后端代理检查。
- 已生成 4 份 launchd 配置，保存在 `.runtime/launchagents/`，尚未正式安装和切换。
- macOS 托管预检被 Python 访问桌面目录的系统权限提示阻塞。系统日志明确记录 `kTCCServiceSystemPolicyDesktopFolder` 授权请求；正在等待用户决定。现有临时服务保持运行。
- 云服务器/托管平台信息尚待用户提供。

这不是“自动恢复已完成”的验收记录。授权后需安装、切换、验证实际进程退出恢复，再更新本节。

## 托管设计

| 服务 | 启动方式 | 恢复机制 |
| --- | --- | --- |
| frontend | 隔离快照中的 `next start`，127.0.0.1:3000 | launchd KeepAlive，退出后重新启动 |
| backend | 原项目虚拟环境 uvicorn，127.0.0.1:8000，沿用原 `.env` 和数据路径 | launchd KeepAlive，退出后重新启动 |
| ngrok | 沿用已有 ngrok 配置与认证，固定原域名，转发 127.0.0.1:3000 | launchd KeepAlive；网络重连由 ngrok 自身处理 |
| watchdog | 每 60 秒检查本机首页、后端 `/health`、ngrok 本机管理接口 | 连续 3 次失败后，只重启对应已托管服务；不恢复被主动停止的服务 |

使用用户级 LaunchAgents，在登录当前 macOS 用户时加载，**不代表机器重启后未登录也会运行**。异常退出有 10 秒的重启节流，因此恢复不是零中断。健康检查不调用模型、不读取聊天记录、不反复访问公网占用 ngrok 配额，也不代表对模型输出或所有数据库功能做了检查。

所有运行文件都在被 git 忽略的 `.runtime/` 内：隔离前端版本、独立依赖副本、服务配置、健康状态与日志。日志超过 10 MB 时保留一份副本并截断原文件。ngrok 认证仅引用已有配置文件路径，没有抄入 plist。构建失败不切换当前版本。

## 授权后的操作命令

在项目根目录执行：

```bash
# 构建不影响现有开发 .next 或当前线上快照
python3 scripts/local_services.py build
python3 scripts/local_services.py prepare --url https://guise-explore-emit.ngrok-free.dev

# 安装前必须核对并关闭占用 3000/8000/4040 的旧 I-Care 进程，
# 不要使用通杀 node/python/ngrok 的命令。
python3 scripts/local_services.py install
python3 scripts/local_services.py status
```

管理与更新：

```bash
python3 scripts/local_services.py status
python3 scripts/local_services.py restart frontend
python3 scripts/local_services.py restart backend
python3 scripts/local_services.py update
python3 scripts/local_services.py stop
python3 scripts/local_services.py start
python3 scripts/local_services.py uninstall
```

`update` 重新构建并验证前端后切换；启动失败会恢复上一版本。修改前端源代码不会自动影响公网正式快照，必须执行 update。后端源代码和模型配置更新后执行 restart backend。日常开发使用另一个端口，如在 frontend 中运行 `npm run dev -- --port 3001`，避免与正式服务抢占 3000。

`stop` 是本次登录期间的暂停；下次登录会按已安装 plist 再加载。`uninstall` 停止并移除本工具的 4 个自动启动配置，保留发布快照和日志，不动数据库和认证文件。项目路径、Python/Node/ngrok 安装路径发生变化时需要重新生成配置。定期清理不再使用的旧发布快照，保留 current/previous 指向的版本。

## 验证

执行 `python3 -m unittest discover -s scripts/tests -v` 检查三次连续失败、成功后重置、主动停止后不被重新拉起。正式安装后，需验证首页、静态脚本、资料与问卷公开接口，以及受控终止前端进程后自动恢复。不得把仅生成配置当作完成。

参考：[ngrok ERR_NGROK_8012](https://ngrok.com/docs/errors/err_ngrok_8012)、[Apple launchd 用户服务](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)、[Next.js 正式运行方式](https://nextjs.org/docs/pages/getting-started/deploying)。
