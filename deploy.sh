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

log()  { printf '\033[1;36m[部署]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[完成]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[注意]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "请用 root 或 sudo 运行：sudo bash $0"

# ---------- 1. Docker Engine 与 Compose v2 ----------
install_docker() {
  log "安装 Docker Engine 与 Compose 插件（阿里云镜像源）…"
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y curl ca-certificates openssl git tar python3 >/dev/null
    cat > /etc/yum.repos.d/docker-ce.repo <<'REPO'
[docker-ce-stable]
name=Docker CE Stable - $basearch
baseurl=https://mirrors.aliyun.com/docker-ce/linux/centos/8/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/docker-ce/linux/centos/gpg
REPO
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null \
      || die "Docker CE 安装失败，请检查 dnf 源或系统是否为 Alibaba Cloud Linux 3"
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg openssl git python3 >/dev/null
    install -m 0755 -d /etc/apt/keyrings >/dev/null
    curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
      || die "下载 Docker 软件源密钥失败"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null \
      || die "Docker CE 安装失败，请检查 apt 源"
  else
    die "仅支持 dnf（Alibaba Cloud Linux 3）或 apt（Ubuntu 22.04/24.04）"
  fi
  systemctl enable --now docker >/dev/null 2>&1 || die "Docker 服务启动失败"
  ok "Docker 安装完成"
}

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "Docker 与 Compose 插件已安装"
else
  install_docker
fi

command -v docker >/dev/null 2>&1 || die "未找到 docker 命令"
docker compose version >/dev/null 2>&1 || die "未找到 docker compose 插件，请安装 docker-compose-plugin"
if ! docker info >/dev/null 2>&1; then
  systemctl start docker >/dev/null 2>&1 || true
  sleep 2
fi
docker info >/dev/null 2>&1 || die "Docker daemon 未运行，请检查 systemctl status docker"

# Docker 已预装时安装脚本可能被跳过，这里补齐部署所需的基础工具。
ensure_base_tools() {
  local missing=()
  local tool
  for tool in curl openssl python3; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  [[ ${#missing[@]} -eq 0 ]] && return 0
  log "补齐基础工具：${missing[*]} …"
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y "${missing[@]}" >/dev/null
  else
    apt-get update -qq
    apt-get install -y -qq "${missing[@]}" >/dev/null
  fi
}

ensure_base_tools

# ---------- 2. 目录结构 ----------
log "准备数据目录 $DATA_DIR …"
mkdir -p "$DATA_DIR"/{postgres,redis,targets,logs,backups}
ok "数据目录就绪"

# ---------- 3. 配置文件 ----------
generate_secret() { head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 44; }

ensure_env_default() {
  local key="$1" value="$2"
  grep -q "^${key}=" "$ENV_FILE" || printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

if [[ -f "$ENV_FILE" ]]; then
  ok "复用已有配置 $ENV_FILE"
else
  log "生成部署配置 …"
  read -r -p "绑定域名（直接回车则用服务器公网 IP）: " TARC_DOMAIN_INPUT
  TARC_DOMAIN="${TARC_DOMAIN:-${TARC_DOMAIN_INPUT:-}}"
  read -r -p "平台对外端口，HTTPS 默认 443: " TARC_PORT_INPUT
  TARC_PORT="${TARC_PORT:-${TARC_PORT_INPUT:-443}}"
  TARC_PORT="${TARC_PORT:-443}"

  if [[ -z "${DOCKER_REGISTRY_MIRROR:-}" ]]; then
    read -r -p "Docker 镜像加速地址（阿里云容器镜像服务控制台获取，大陆 ECS 建议填写，可回车跳过）: " DOCKER_REGISTRY_MIRROR_INPUT
    DOCKER_REGISTRY_MIRROR="${DOCKER_REGISTRY_MIRROR_INPUT:-}"
  fi
  NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
  PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
  GATEWAY_IMAGE="${GATEWAY_IMAGE:-linuxserver/openssh-server:latest}"
  GATEWAY_PORT="${GATEWAY_PORT:-2222}"

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
GATEWAY_IMAGE=$GATEWAY_IMAGE
GATEWAY_PORT=$GATEWAY_PORT
# 构建与拉取镜像时使用；大陆 ECS 建议填写阿里云镜像加速器
DOCKER_REGISTRY_MIRROR=$DOCKER_REGISTRY_MIRROR
NPM_REGISTRY=$NPM_REGISTRY
PIP_INDEX_URL=$PIP_INDEX_URL
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

# 兼容旧版 .env，并在部署时记录 Docker socket 的组 ID，供容器内 Docker SDK 使用。
ensure_env_default DOCKER_REGISTRY_MIRROR "${DOCKER_REGISTRY_MIRROR:-}"
ensure_env_default NPM_REGISTRY "${NPM_REGISTRY:-https://registry.npmmirror.com}"
ensure_env_default PIP_INDEX_URL "${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
ensure_env_default GATEWAY_IMAGE "${GATEWAY_IMAGE:-linuxserver/openssh-server:latest}"
ensure_env_default GATEWAY_PORT "${GATEWAY_PORT:-2222}"

DOCKER_GID="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || true)"
if [[ -n "$DOCKER_GID" ]]; then
  if grep -q '^DOCKER_GID=' "$ENV_FILE"; then
    sed -i "s/^DOCKER_GID=.*/DOCKER_GID=$DOCKER_GID/" "$ENV_FILE"
  else
    printf 'DOCKER_GID=%s\n' "$DOCKER_GID" >> "$ENV_FILE"
  fi
else
  warn "无法读取 /var/run/docker.sock 的组 ID；若容器无法访问 Docker，请检查 socket 权限。"
fi

set -a; source "$ENV_FILE"; set +a
: "${POSTGRES_PASSWORD:?}"; : "${REDIS_PASSWORD:?}"; : "${SESSION_SECRET:?}"; : "${FLAG_HMAC_SECRET:?}"; : "${TERMINAL_SSH_PASSWORD:?}"
: "${TARC_PORT:=443}"; : "${TARC_DOMAIN:=}"; : "${DOCKER_REGISTRY_MIRROR:=}"; : "${GATEWAY_IMAGE:=linuxserver/openssh-server:latest}"; : "${GATEWAY_PORT:=2222}"

# ---------- 4. Docker 镜像加速 ----------
configure_docker_mirror() {
  if [[ -z "${DOCKER_REGISTRY_MIRROR:-}" ]]; then
    warn "未配置 Docker 镜像加速地址；大陆 ECS 拉取 Docker Hub 可能失败。可在 deploy/.env 设置 DOCKER_REGISTRY_MIRROR 后重跑。"
    return 0
  fi
  command -v python3 >/dev/null 2>&1 || die "缺少 python3，无法写入 Docker 镜像配置"
  mkdir -p /etc/docker
  local before after
  before="$(sha256sum /etc/docker/daemon.json 2>/dev/null | awk '{print $1}' || true)"
  if [[ -f /etc/docker/daemon.json ]]; then
    cp "/etc/docker/daemon.json" "/etc/docker/daemon.json.bak.$(date +%s)"
  fi
  python3 - "$DOCKER_REGISTRY_MIRROR" <<'PY' || die "写入 Docker 镜像配置失败（请检查 /etc/docker/daemon.json）"
import json
import pathlib
import sys

path = pathlib.Path("/etc/docker/daemon.json")
data = {}
if path.exists() and path.read_text(encoding="utf-8").strip():
    data = json.loads(path.read_text(encoding="utf-8"))
data["registry-mirrors"] = [sys.argv[1]]
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  after="$(sha256sum /etc/docker/daemon.json 2>/dev/null | awk '{print $1}' || true)"
  if [[ "$before" != "$after" ]]; then
    systemctl restart docker
    sleep 2
    docker info >/dev/null 2>&1 || die "Docker 重启后不可用，请检查 systemctl status docker"
  fi
  ok "Docker 镜像加速已配置"
}

configure_docker_mirror

log "预拉取终端网关镜像 $GATEWAY_IMAGE …"
docker pull "$GATEWAY_IMAGE" || die "网关镜像拉取失败。请配置 DOCKER_REGISTRY_MIRROR，或手动 docker pull $GATEWAY_IMAGE 后重跑。"
ok "网关镜像就绪"

# ---------- 5. TLS 证书 ----------
CERT_DIR="$ROOT/deploy/certs"
mkdir -p "$CERT_DIR"
if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  ok "复用已有 TLS 证书 deploy/certs"
else
  CERT_CN="${TARC_DOMAIN:-$(curl -fsS --max-time 5 http://100.100.100.200/latest/meta-data/eipv4 2>/dev/null || hostname -I | awk '{print $1}')}"
  CERT_CN="${CERT_CN:-localhost}"
  log "生成自签名证书（CN=$CERT_CN），浏览器首次访问需手动信任…"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$CERT_CN" >/dev/null 2>&1 || die "自签名证书生成失败"
  chmod 600 "$CERT_DIR/privkey.pem"
  ok "自签名证书已生成（正式训练建议替换为域名证书）"
fi

# ---------- 6. 构建并启动容器栈 ----------
log "构建镜像并启动容器栈（前端在 Docker 内构建，首次会下载 npm 依赖）…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
ok "容器栈已启动"

log "等待服务健康检查 …"
for i in $(seq 1 90); do
  if curl -fkS -o /dev/null --max-time 3 "https://127.0.0.1:$TARC_PORT/api/v1/health" 2>/dev/null; then
    ok "API 健康检查通过"; break
  fi
  [[ $i -eq 90 ]] && { docker compose -f "$COMPOSE_FILE" ps; die "健康检查超时，请查看日志：docker compose -f $COMPOSE_FILE logs --tail=100"; }
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
  赛前流程   ：管理后台建队伍/选手 → 服务模板配置并预拉镜像 → 靶机初始化 → 赛前检查 → 开始比赛
\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
BANNER
