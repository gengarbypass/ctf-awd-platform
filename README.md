# 塔大网安师市行 CTF-AWD 实战平台

面向授权内部训练的 CTF-AWD 攻防竞赛平台：10—15 支队伍、每队 3—4 人、最多 60 名选手；计分服务与靶机环境一体化部署在单台核心 ECS。

## 一键部署（阿里云 ECS）

```bash
git clone https://github.com/gengarbypass/ctf-awd-platform.git
sudo bash ctf-awd-platform/deploy.sh
```

脚本自动完成：Docker 安装、数据目录、密钥生成、前端镜像构建、自签名证书、容器栈启动、数据库迁移与初始管理员创建。初始管理员密码在执行时打印并写入 `deploy/.env`，首次登录后请立即修改。

> 大陆 ECS 建议在部署时填写阿里云容器镜像服务提供的加速地址（或写入 `deploy/.env` 的 `DOCKER_REGISTRY_MIRROR`），否则 Docker Hub 拉取可能失败。脚本会自动配置 Docker、PyPI 和 npm 镜像参数。
>
> 首次登录后先进入「服务模板」创建服务模板并点「预检镜像」，再初始化靶机；平台不预置靶机镜像，挑战镜像需由管理员提前构建并可从服务器拉取。

部署后请在阿里云安全组放行：TCP 443（平台）、TCP 80（跳转）、TCP 22（限管理员 IP）、实际使用的比赛端口段（默认队伍靶机 20000—21599）。

> 若服务器访问 GitHub 受限，可在本地打包后上传：`git bundle create ctf-awd.bundle --all`，上传到服务器后
> `git clone ctf-awd.bundle ctf-awd-platform && sudo bash ctf-awd-platform/deploy.sh`，部署流程完全一致。

详细操作见 `docs/选手使用说明.md` 与 `docs/管理员操作手册.md`。

## 架构速览

- 前端：Vue 3 + TypeScript + Element Plus（`frontend/`），SSE 实时计分、xterm.js Web 终端
- 后端：FastAPI + SQLAlchemy 2 + Alembic（`backend/`），HttpOnly Cookie 会话、事务化计分
- Worker：Flag 轮换（Redis 分布式锁）、健康检查、受控自动恢复
- 终端代理：WebSocket → 本队 SSH 管理网关（`app/terminal_server.py`）
- 基础设施：PostgreSQL 16 / Redis 7 / Nginx（`deploy/docker-compose.yml`）

## 核心规则

- 每队初始 1000 分；有效攻击：攻击队 +100，被攻击队 -50；重复提交不重复计分
- Flag 每 300 秒轮换，上一周期 30 秒提交宽限；比赛暂停时轮换与计时同步暂停
- 健康状态不计分，仅影响展示与同分排名（异常累计时长）
- 排名：总分 → 有效攻击数 → 服务异常时长 → 最后得分时间 → 队伍编号

## 本地开发

```bash
# 后端
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# Windows: .venv/Scripts/python -m pytest tests -q

# 前端（开发默认演示模式，VITE_USE_DEMO=false 连接真实后端）
cd frontend && npm install && npm run dev

# 种子数据（显式执行）
python scripts/seed.py
```

## 仓库结构

```
backend/    FastAPI 应用、Worker、终端代理、Alembic 迁移、测试
frontend/   Vue 3 选手端与管理端
deploy/     Compose、Nginx、前端镜像、证书目录
scripts/    种子、备份、恢复、成绩导出
systemd/    裸机部署单元文件
docs/       选手与管理员文档
deploy.sh   一键部署脚本
```
