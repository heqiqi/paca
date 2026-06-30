#!/usr/bin/env bash
# =============================================================================
# Paca — Bare-metal deployment with Python/FastAPI backend (no Docker)
# =============================================================================
#
# Deploys Paca using the Python/FastAPI API backend instead of Go.
# No Docker required — everything runs natively on the host.
#
# Designed for: AWS Graviton (aarch64), or any x86_64 Linux
# Tested on:    Amazon Linux 2023, Ubuntu 22.04/24.04, Debian 12
#
# Usage:
#   sudo bash deploy/install-python-bare-metal.sh
#
# Architecture:
#   ┌──────────────────────────────────────────────┐
#   │  Caddy (port 80/443)                         │
#   │  ├── /api/*      → Python FastAPI (8080)     │
#   │  ├── /ws/*       → Realtime/Bun (3001)       │
#   │  └── /*          → Static frontend files     │
#   └──────────────────────────────────────────────┘
#   │  PostgreSQL (5432)  │  Valkey/Redis (6379)   │
#   └──────────────────────────────────────────────┘
#
# =============================================================================

set -euo pipefail

# ─── Colors & helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()   { error "$*"; exit 1; }

# ─── Configuration ────────────────────────────────────────────────────────────
PACA_HOME="${PACA_HOME:-/opt/paca}"
PACA_USER="${PACA_USER:-paca}"
PACA_REPO="${PACA_REPO:-https://github.com/Paca-AI/paca.git}"
PACA_BRANCH="${PACA_BRANCH:-master}"

API_PORT=8080
REALTIME_PORT=3001
CADDY_HTTP_PORT="${CADDY_HTTP_PORT:-80}"

PG_DB="paca"
PG_USER="paca"
PG_PASSWORD=$(openssl rand -hex 16)

JWT_SECRET=$(openssl rand -hex 32)
ADMIN_USERNAME="admin"
ADMIN_PASSWORD=$(openssl rand -hex 12)
ENCRYPTION_KEY=$(openssl rand -hex 32)

PUBLIC_URL="${PUBLIC_URL:-http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)}"
PYTHON_VERSION="3.12"

# ─── Pre-flight ───────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "This script must be run as root (or with sudo)"

ARCH=$(uname -m)
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="$ID"
else
    die "Unsupported OS"
fi

info "═══════════════════════════════════════════════════════════════"
info "  Paca — Python/FastAPI Bare-metal Deployment"
info "═══════════════════════════════════════════════════════════════"
info "  OS:         $OS_ID ($ARCH)"
info "  Target:     $PACA_HOME"
info "  Backend:    Python $PYTHON_VERSION + FastAPI + uvicorn"
info "  Public URL: $PUBLIC_URL"
info "═══════════════════════════════════════════════════════════════"
echo ""

# =============================================================================
# STEP 1: Install system packages
# =============================================================================
info "[1/12] Installing system packages..."

case "$OS_ID" in
    amzn|fedora|rhel|centos)
        dnf update -y -q
        dnf install -y -q \
            git gcc make openssl openssl-devel \
            python3.12 python3.12-pip python3.12-devel \
            postgresql16-server postgresql16 \
            curl wget tar
        ;;
    ubuntu|debian)
        apt-get update -qq
        apt-get install -y -qq \
            git build-essential libssl-dev pkg-config \
            python3.12 python3.12-venv python3.12-dev python3-pip \
            postgresql postgresql-contrib libpq-dev \
            curl wget
        ;;
    *)
        die "Unsupported OS: $OS_ID. Use Amazon Linux 2023, Ubuntu 22.04+, or Debian 12+."
        ;;
esac

ok "System packages installed"

# =============================================================================
# STEP 2: Install Bun (for frontend build & realtime service)
# =============================================================================
info "[2/12] Installing Bun..."

if ! command -v bun &>/dev/null; then
    curl -fsSL https://bun.sh/install | bash
fi
export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
export PATH="$BUN_INSTALL/bin:$PATH"

ok "Bun $(bun --version) ready"

# =============================================================================
# STEP 3: Install Valkey/Redis
# =============================================================================
info "[3/12] Installing Valkey..."

case "$OS_ID" in
    amzn|fedora|rhel|centos)
        dnf install -y -q valkey 2>/dev/null || dnf install -y -q redis
        ;;
    ubuntu|debian)
        apt-get install -y -qq valkey-server 2>/dev/null || apt-get install -y -qq redis-server
        ;;
esac

# Determine service name
if systemctl list-unit-files | grep -q valkey; then
    VALKEY_SVC="valkey"
elif systemctl list-unit-files | grep -q redis-server; then
    VALKEY_SVC="redis-server"
else
    VALKEY_SVC="redis"
fi

systemctl enable "$VALKEY_SVC" --now 2>/dev/null || true
ok "Valkey/Redis running (service: $VALKEY_SVC)"

# =============================================================================
# STEP 4: Install Caddy
# =============================================================================
info "[4/12] Installing Caddy..."

if ! command -v caddy &>/dev/null; then
    case "$OS_ID" in
        amzn|fedora|rhel|centos)
            dnf install -y -q 'dnf-command(copr)' 2>/dev/null || true
            dnf copr enable -y @caddy/caddy 2>/dev/null || true
            dnf install -y -q caddy
            ;;
        ubuntu|debian)
            apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
                gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
                tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
            apt-get update -qq
            apt-get install -y -qq caddy
            ;;
    esac
fi

ok "Caddy $(caddy version 2>/dev/null || echo 'installed')"

# =============================================================================
# STEP 5: Create user, clone repository
# =============================================================================
info "[5/12] Setting up paca user and source code..."

id "$PACA_USER" &>/dev/null || useradd -r -m -d "$PACA_HOME" -s /bin/bash "$PACA_USER"

if [ ! -d "$PACA_HOME/src/.git" ]; then
    sudo -u "$PACA_USER" git clone --depth 1 -b "$PACA_BRANCH" "$PACA_REPO" "$PACA_HOME/src"
else
    sudo -u "$PACA_USER" git -C "$PACA_HOME/src" pull --ff-only 2>/dev/null || true
fi

sudo -u "$PACA_USER" mkdir -p "$PACA_HOME"/{venv,data/web-dist,logs,config,backups,plugins/{backend,frontend,mcp}}

ok "Source code at $PACA_HOME/src"

# =============================================================================
# STEP 6: Configure PostgreSQL
# =============================================================================
info "[6/12] Configuring PostgreSQL..."

case "$OS_ID" in
    amzn|fedora|rhel|centos)
        postgresql-setup --initdb 2>/dev/null || true
        systemctl enable postgresql --now
        ;;
    ubuntu|debian)
        systemctl enable postgresql --now
        ;;
esac

# Create user and database
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DB TO $PG_USER;"

# Enable password auth
PG_HBA=$(sudo -u postgres psql -t -c "SHOW hba_file;" | xargs)
if ! grep -q "$PG_USER" "$PG_HBA" 2>/dev/null; then
    echo "local   $PG_DB   $PG_USER                     md5" >> "$PG_HBA"
    echo "host    $PG_DB   $PG_USER   127.0.0.1/32      md5" >> "$PG_HBA"
    echo "host    $PG_DB   $PG_USER   ::1/128           md5" >> "$PG_HBA"
    systemctl reload postgresql
fi

ok "PostgreSQL ready (db=$PG_DB user=$PG_USER)"

# =============================================================================
# STEP 7: Setup Python virtual environment + install FastAPI backend
# =============================================================================
info "[7/12] Setting up Python FastAPI backend..."

VENV_DIR="$PACA_HOME/venv"

sudo -u "$PACA_USER" python${PYTHON_VERSION} -m venv "$VENV_DIR"

sudo -u "$PACA_USER" bash -c "
    source $VENV_DIR/bin/activate
    pip install --upgrade pip setuptools wheel -q
    pip install -r $PACA_HOME/src/services/api-python/requirements.txt -q
"

ok "Python venv ready with FastAPI + all dependencies"

# =============================================================================
# STEP 8: Build frontend
# =============================================================================
info "[8/12] Building React frontend..."

sudo -u "$PACA_USER" bash -c "
    export BUN_INSTALL=$PACA_HOME/.bun
    export PATH=\$BUN_INSTALL/bin:\$PATH

    # Install bun for paca user if needed
    if ! command -v bun &>/dev/null; then
        curl -fsSL https://bun.sh/install | bash
    fi

    cd $PACA_HOME/src/apps/web
    bun install --frozen-lockfile 2>/dev/null || bun install
    bun run build
    cp -r dist/* $PACA_HOME/data/web-dist/
"

ok "Frontend built → $PACA_HOME/data/web-dist/"

# =============================================================================
# STEP 9: Setup Realtime service
# =============================================================================
info "[9/12] Setting up Realtime service..."

sudo -u "$PACA_USER" bash -c "
    export BUN_INSTALL=$PACA_HOME/.bun
    export PATH=\$BUN_INSTALL/bin:\$PATH
    cd $PACA_HOME/src/services/realtime
    bun install --frozen-lockfile 2>/dev/null || bun install
"

ok "Realtime service ready"

# =============================================================================
# STEP 10: Write configuration
# =============================================================================
info "[10/12] Writing configuration..."

DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@localhost:5432/${PG_DB}"

sudo -u "$PACA_USER" tee "$PACA_HOME/config/paca.env" > /dev/null << EOF
# ═══════════════════════════════════════════════════════════════
# Paca Configuration (Python/FastAPI backend)
# Generated: $(date -Iseconds)
# ═══════════════════════════════════════════════════════════════

# Server
SERVER_PORT=$API_PORT
SERVER_ENV=production
PUBLIC_URL=$PUBLIC_URL
COOKIE_SECURE=false

# Database (asyncpg for FastAPI)
DATABASE_URL=$DATABASE_URL

# Redis / Valkey
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=$JWT_SECRET
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
JWT_REFRESH_SESSION_TTL_HOURS=24

# Admin credentials (SAVE THESE!)
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD

# Security
ENCRYPTION_KEY=$ENCRYPTION_KEY
AGENT_API_KEY=

# Storage (local MinIO not used — set up S3 or install MinIO separately)
STORAGE_PROVIDER=minio
STORAGE_ENDPOINT=localhost:9000
STORAGE_PUBLIC_URL=$PUBLIC_URL/storage
STORAGE_REGION=us-east-1
STORAGE_BUCKET=paca
STORAGE_ACCESS_KEY_ID=minioadmin
STORAGE_SECRET_ACCESS_KEY=minioadmin
STORAGE_USE_SSL=false

# Cache TTL (seconds)
CACHE_PROJECT_TTL=300
CACHE_CONFIG_TTL=600
CACHE_SPRINT_TTL=120

# AI Agent (disabled — use Claude Code)
AI_AGENT_URL=
EOF

chmod 600 "$PACA_HOME/config/paca.env"

ok "Config written → $PACA_HOME/config/paca.env"

# =============================================================================
# STEP 11: Write Caddyfile + systemd units
# =============================================================================
info "[11/12] Creating Caddyfile and systemd services..."

# --- Caddyfile ---
tee /etc/caddy/Caddyfile > /dev/null << EOF
# Paca Gateway (Python backend)
:${CADDY_HTTP_PORT} {
    encode gzip

    header {
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    # API → Python FastAPI (uvicorn)
    handle /api/* {
        reverse_proxy localhost:${API_PORT}
    }

    # Realtime → Socket.IO (Bun)
    handle_path /ws/* {
        reverse_proxy localhost:${REALTIME_PORT}
    }

    # Plugin frontend assets
    handle_path /plugins/* {
        root * $PACA_HOME/plugins/frontend
        file_server
    }

    # SPA frontend (React)
    handle {
        root * $PACA_HOME/data/web-dist
        try_files {path} /index.html
        file_server
    }
}
EOF

# --- paca-api.service (Python/FastAPI with uvicorn) ---
tee /etc/systemd/system/paca-api.service > /dev/null << EOF
[Unit]
Description=Paca API (Python/FastAPI)
After=network.target postgresql.service $VALKEY_SVC.service
Requires=postgresql.service

[Service]
Type=simple
User=$PACA_USER
Group=$PACA_USER
WorkingDirectory=$PACA_HOME/src/services/api-python
EnvironmentFile=$PACA_HOME/config/paca.env
ExecStart=$VENV_DIR/bin/uvicorn app.main:app \\
    --host 0.0.0.0 \\
    --port $API_PORT \\
    --workers 4 \\
    --log-level info \\
    --access-log
Restart=on-failure
RestartSec=5
StandardOutput=append:$PACA_HOME/logs/api.log
StandardError=append:$PACA_HOME/logs/api.log

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$PACA_HOME/data $PACA_HOME/logs $PACA_HOME/plugins
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

# --- paca-realtime.service ---
tee /etc/systemd/system/paca-realtime.service > /dev/null << EOF
[Unit]
Description=Paca Realtime (Socket.IO)
After=network.target $VALKEY_SVC.service paca-api.service

[Service]
Type=simple
User=$PACA_USER
Group=$PACA_USER
WorkingDirectory=$PACA_HOME/src/services/realtime
Environment=PORT=$REALTIME_PORT
Environment=NODE_ENV=production
Environment=API_URL=http://localhost:$API_PORT
Environment=REDIS_URL=redis://localhost:6379/0
Environment=CORS_ORIGINS=$PUBLIC_URL
Environment=LOG_LEVEL=info
Environment=PATH=$PACA_HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PACA_HOME/.bun/bin/bun run src/index.ts
Restart=on-failure
RestartSec=5
StandardOutput=append:$PACA_HOME/logs/realtime.log
StandardError=append:$PACA_HOME/logs/realtime.log

[Install]
WantedBy=multi-user.target
EOF

# --- paca-caddy.service ---
tee /etc/systemd/system/paca-caddy.service > /dev/null << EOF
[Unit]
Description=Paca Gateway (Caddy)
After=network.target paca-api.service paca-realtime.service

[Service]
Type=simple
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
Restart=on-failure
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

ok "Systemd services created"

# =============================================================================
# STEP 12: Run migrations + start services
# =============================================================================
info "[12/12] Running migrations and starting services..."

# Run Alembic migrations
sudo -u "$PACA_USER" bash -c "
    source $VENV_DIR/bin/activate
    export DATABASE_URL='$DATABASE_URL'
    cd $PACA_HOME/src/services/api-python
    alembic upgrade head 2>/dev/null || echo 'Migrations skipped (will auto-create on first start)'
"

# Disable default caddy if active
systemctl stop caddy 2>/dev/null || true
systemctl disable caddy 2>/dev/null || true

# Start services
systemctl enable --now paca-api
sleep 3
systemctl enable --now paca-realtime
systemctl enable --now paca-caddy

# Verify
sleep 2
if curl -sf "http://localhost:${API_PORT}/api/healthz" | grep -q "ok"; then
    ok "API health check: PASSED ✓"
else
    warn "API may still be starting — check: journalctl -u paca-api -f"
fi

# =============================================================================
# DONE
# =============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Paca deployed successfully! (Python/FastAPI backend)${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}URL:${NC}            $PUBLIC_URL"
echo -e "  ${BLUE}Admin user:${NC}     $ADMIN_USERNAME"
echo -e "  ${BLUE}Admin password:${NC}  $ADMIN_PASSWORD"
echo ""
echo -e "  ${YELLOW}⚠️  SAVE THESE CREDENTIALS — they cannot be recovered!${NC}"
echo ""
echo "  ─── Service Commands ─────────────────────────────────────────"
echo ""
echo "  Status:    systemctl status paca-api paca-realtime paca-caddy"
echo "  Logs:      tail -f $PACA_HOME/logs/api.log"
echo "  Restart:   systemctl restart paca-api"
echo "  Stop all:  systemctl stop paca-api paca-realtime paca-caddy"
echo ""
echo "  ─── Backend Info ───────────────────────────────────────────────"
echo ""
echo "  Runtime:   Python $PYTHON_VERSION + FastAPI + uvicorn (4 workers)"
echo "  Venv:      $VENV_DIR"
echo "  Source:    $PACA_HOME/src/services/api-python/"
echo "  Config:    $PACA_HOME/config/paca.env"
echo ""
echo "  ─── Upgrade ────────────────────────────────────────────────────"
echo ""
echo "  cd $PACA_HOME/src && git pull"
echo "  source $VENV_DIR/bin/activate"
echo "  pip install -r services/api-python/requirements.txt"
echo "  cd services/api-python && alembic upgrade head"
echo "  systemctl restart paca-api"
echo ""
echo "  ─── Database ───────────────────────────────────────────────────"
echo ""
echo "  Backup:    pg_dump -U $PG_USER $PG_DB | gzip > backup.sql.gz"
echo "  Restore:   gunzip -c backup.sql.gz | psql -U $PG_USER $PG_DB"
echo "  Shell:     psql -U $PG_USER -d $PG_DB"
echo ""
echo "  ─── Claude Code Integration ───────────────────────────────────"
echo ""
echo "  # After generating API key in Paca UI (Settings → API Keys):"
echo "  claude mcp add paca \\"
echo "    --env PACA_API_KEY=<your-key> \\"
echo "    --env PACA_API_URL=$PUBLIC_URL \\"
echo "    -- npx -y @paca-ai/paca-mcp"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
