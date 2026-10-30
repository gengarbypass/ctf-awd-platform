#!/usr/bin/env bash
# 塔大网安师市行 CTF-AWD 实战平台一键部署脚本
# 适用：干净的阿里云 ECS（Ubuntu 22.04/24.04 或 Alibaba Cloud Linux 3）
# 用法：
#   git clone https://github.com/gengarbypass/ctf-awd-platform.git
#   sudo bash ctf-awd-platform/deploy.sh            # 交互式引导部署
#   sudo TARC_DOMAIN=ctf.example.com bash deploy.sh  # 非交互式
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="/data/awd"
ENV_FILE="$ROOT/deploy/.env"
COMPOSE_FILE="$ROOT/deploy/docker-compose.yml"
CLOCK_SKEW_MSG=""

log()  { printf '\033[1;36m[部署]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[完成]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[注意]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "请用 root 或 sudo 运行：sudo bash $0"

# ---------- 1. 系统依赖 ----------
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "Docker 与 Compose 插件已安装"
else
  log "安装 Docker Engine 与 Compose 插件（阿里云镜像源）…"
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y dnf-plugin-release-utils >/dev/null 2>&1 || true
    dnf install -y docker-cli containerd >/dev/null 2>&1 || dnf install -y docker >/dev/null 2>&1 || true
    dnf install -y python3-pip >/dev/null 2>&1 || true
    pip3 install -U pip >/dev/null 2>&1 || true
    pip3 install docker-compose >/dev/null 2>&1 || true
  else
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg >/dev/null
    install -m 0755 -d /etc/apt/keyrings >/dev/null
    curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
  fi
  systemctl enable --now docker
  ok "Docker 安装完成"
fi

# ---------- 2. 目录结构 ----------
log "准备数据目录 $DATA_DIR …"
mkdir -p "$DATA_DIR"/{postgres,redis,targets,logs,backups}
ok "数据目录就绪"

# ---------- 3. 配置文件 ----------
generate_secret() { head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 44; }

if [[ -f "$ENV_FILE" ]]; then
  ok "复用已有配置 $ENV_FILE"
else
  log "生成部署配置 …"
  read -r -p "绑定域名（直接回车则用服务器公网 IP）: " TARC_DOMAIN_INPUT
  TARC_DOMAIN="${TARC_DOMAIN:-${TARC_DOMAIN_INPUT:-}}"
  read -r -p "平台对外端口，HTTPS 默认 443: " TARC_PORT_INPUT
  TARC_PORT="${TARC_PORT:-${TARC_PORT_INPUT:-443}}"
  TARC_PORT="${TARC_PORT:-443}"

  POSTGRES_PASSWORD="$(generate_secret)"
  REDIS_PASSWORD="$(generate_secret)"
  SESSION_SECRET="$(generate_secret)$(generate_secret)"
  FLAG_HMAC_SECRET="$(generate_secret)$(generate_secret)"
  TERMINAL_SSH_PASSWORD="$(generate_secret)"
  ADMIN_PASSWORD="$(generate_secret | head -c 16)!"

  cat > "$ENV_FILE" <<ENV
# 塔大网安师市行 CTF-AWD 平台部署配置（由 deploy.sh 生成，含密钥，勿提交仓库）
ENVIRONMENT=production
POSTGRES_DB=awd
POSTGRES_USER=awd
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD
SESSION_SECRET=$SESSION_SECRET
FLAG_HMAC_SECRET=$FLAG_HMAC_SECRET
TERMINAL_SSH_USERNAME=player
TERMINAL_SSH_PASSWORD=$TERMINAL_SSH_PASSWORD
# 初始管理员（部署后请立即登录并修改密码）
TARC_ADMIN_USERNAME=admin
TARC_ADMIN_PASSWORD=$ADMIN_PASSWORD
# 入口
TARC_DOMAIN=$TARC_DOMAIN
TARC_PORT=$TARC_PORT
# 竞赛参数（与设计文档一致）
MATCH_ROUND_SECONDS=300
FLAG_GRACE_SECONDS=30
INITIAL_TEAM_SCORE=1000
ATTACK_REWARD=100
VICTIM_PENALTY=50
HEALTH_INTERVAL_SECONDS=30
MAX_AUTO_RESTARTS=2
ENV
  chmod 600 "$ENV_FILE"
  ok "配置已写入 $ENV_FILE（含密钥）"
  printf '\n'
  printf '\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n'
  printf '  初始管理员账号已写入 deploy/.env：\n'
  printf '    用户名：admin\n    密码：\033[1;37m%s\033[0m\n' "$ADMIN_PASSWORD"
  printf '  请立即抄录并在首次登录后修改密码。\n'
  printf '\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n'
  printf '\n'
fi

set -a; source "$ENV_FILE"; set +a
: "${POSTGRES_PASSWORD:?}"; : "${REDIS_PASSWORD:?}"; : "${SESSION_SECRET:?}"; : "${FLAG_HMAC_SECRET:?}"; : "${TERMINAL_SSH_PASSWORD:?}"

# ---------- 4. 前端生产构建 ----------
if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  log "本地未发现前端构建产物，开始构建（需要 Node.js 20+）…"
  if ! command -v node >/dev/null 2>&1; then
    warn "未检测到 Node.js，安装 Node.js 22 LTS …"
    if command -v dnf >/dev/null 2>&1; then
      dnf install -y nodejs npm >/dev/null 2>&1 || die "Node.js 安装失败，请手动安装 Node 20+ 后重跑"
    else
      curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1
      apt-get install -y -qq nodejs >/dev/null
    fi
  fi
  (cd "$ROOT/frontend" && npm install --no-audit --no-fund >/dev/null && npm run build >/dev/null)
  ok "前端构建完成"
else
  ok "复用已有前端构建产物 frontend/dist"
fi

# ---------- 5. TLS 证书 ----------
CERT_DIR="$ROOT/deploy/certs"
mkdir -p "$CERT_DIR"
if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  ok "复用已有 TLS 证书 deploy/certs"
else
  CERT_CN="${TARC_DOMAIN:-$(curl -fsS --max-time 5 http://100.100.100.200/latest/meta-data/eipv4 2>/dev/null || hostname -I | awk '{print $1}')}"
  log "生成自签名证书（CN=$CERT_CN），浏览器首次访问需手动信任…"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$CERT_CN" >/dev/null 2>&1
  ok "自签名证书已生成（正式训练建议替换为域名证书）"
fi

# ---------- 6. 启动容器栈 ----------
log "构建镜像并启动容器栈 …"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
ok "容器栈已启动"

log "等待服务健康检查 …"
for i in $(seq 1 60); do
  if curl -fkS -o /dev/null --max-time 3 "https://127.0.0.1:$TARC_PORT/api/v1/health" 2>/dev/null; then
    ok "API 健康检查通过"; break
  fi
  [[ $i -eq 60 ]] && { docker compose -f "$COMPOSE_FILE" ps; die "健康检查超时，请查看日志：docker compose -f $COMPOSE_FILE logs --tail=100"; }
  sleep 2
done

# ---------- 7. 初始化管理员 ----------
if [[ -n "${TARC_ADMIN_USERNAME:-}" && -n "${TARC_ADMIN_PASSWORD:-}" ]]; then
  log "创建初始管理员 …"
  docker compose -f "$COMPOSE_FILE" exec -T api python - <<PY
import asyncio
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password

async def main():
    async with SessionLocal() as db:
        exists = await db.scalar(select(User.id).where(User.username == "admin"))
        if not exists:
            db.add(User(username="admin", password_hash=hash_password("${TARC_ADMIN_PASSWORD}"), role=Role.ADMIN))
            await db.commit()
            print("admin created")
        else:
            print("admin already exists")

asyncio.run(main())
PY
  ok "管理员账号就绪"
fi

# ---------- 8. 安全组提示 ----------
PUBLIC_IP="$(curl -fsS --max-time 5 http://100.100.100.200/latest/meta-data/eipv4 2>/dev/null || echo 服务器公网IP)"
cat <<BANNER

\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
\033[1;37m  部署完成\033[0m
\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
  平台入口   ：https://${TARC_DOMAIN:-$PUBLIC_IP}${TARC_PORT:+:$TARC_PORT}
  管理入口   ：同域名，使用 admin 账号登录后自动进入 /admin
  配置文件   ：$ENV_FILE
  常用命令   ：
    docker compose -f $COMPOSE_FILE ps
    docker compose -f $COMPOSE_FILE logs -f api worker
    docker compose -f $COMPOSE_FILE restart api worker terminal
  阿里云安全组还需放行（入方向）：
    TCP 443    0.0.0.0/0    平台与 Web 终端
    TCP 80     0.0.0.0/0    跳转 HTTPS
    TCP 22     管理员 IP     服务器运维
    TCP 20000-21599  0.0.0.0/0   队伍靶机比赛端口
  赛前流程   ：管理后台建队伍/选手 → 靶机初始化 → 赛前检查 → 开始比赛
\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
BANNER
