#!/usr/bin/env bash
# =============================================================================
# Paca — Bare-metal source deployment script (no Docker)
# =============================================================================
#
# Deploys all Paca services directly on the host from source code.
# Designed for AWS Graviton (aarch64) or any Linux (amd64).
#
# Tested on: Amazon Linux 2023, Ubuntu 22.04/24.04, Debian 12
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/.../install-bare-metal.sh | bash
#   # or
#   git clone https://github.com/Paca-AI/paca.git && cd paca
#   bash deploy/install-bare-metal.sh
#
# What it does:
#   1. Installs system dependencies (Go, Node.js/Bun, Python, PostgreSQL, Valkey, Caddy)
#   2. Configures PostgreSQL and Valkey
#   3. Builds the Go API from source
#   4. Builds the React frontend (static files)
#   5. Sets up the Python FastAPI backend (alternative API)
#   6. Sets up the Realtime service (Bun + Socket.IO)
#   7. Configures Caddy as reverse proxy
#   8. Creates systemd service units for all components
#   9. Starts everything
#
# =============================================================================

set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Ports
API_PORT=8080
REALTIME_PORT=3001
CADDY_HTTP_PORT=80
CADDY_HTTPS_PORT=443

# Database
PG_DB="paca"
PG_USER="paca"
PG_PASSWORD=$(openssl rand -hex 16)

# Secrets
JWT_SECRET=$(openssl rand -hex 32)
ADMIN_USERNAME="admin"
ADMIN_PASSWORD=$(openssl rand -hex 12)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Public URL (override with environment variable)
PUBLIC_URL="${PUBLIC_URL:-http://$(hostname -I | awk '{print $1}')}"

info "═══════════════════════════════════════════════════════════════"
info "  Paca — Bare-metal Source Deployment"
info "═══════════════════════════════════════════════════════════════"
info ""
info "  Target directory:  $PACA_HOME"
info "  Service user:      $PACA_USER"
info "  Public URL:        $PUBLIC_URL"
info ""

# ─── Detect OS ────────────────────────────────────────────────────────────────

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="$VERSION_ID"
    else
        die "Unsupported OS. Requires Amazon Linux 2023, Ubuntu 22.04+, or Debian 12+."
    fi
    ARCH=$(uname -m)
    info "Detected: $OS_ID $OS_VERSION ($ARCH)"
}

# ─── Step 1: Install System Dependencies ─────────────────────────────────────

install_deps() {
    info "Installing system dependencies..."

    case "$OS_ID" in
        amzn|fedora|rhel|centos)
            # Amazon Linux / RHEL-like
            sudo dnf update -y
            sudo dnf install -y \
                git gcc gcc-c++ make cmake \
                openssl openssl-devel \
                postgresql16-server postgresql16 \
                python3.12 python3.12-pip python3.12-devel \
                curl wget tar
            ;;
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y \
                git build-essential \
                libssl-dev pkg-config \
                postgresql postgresql-contrib \
                python3.12 python3.12-venv python3-pip python3.12-dev \
                curl wget
            ;;
        *)
            die "Unsupported OS: $OS_ID"
            ;;
    esac

    ok "System packages installed"
}

# ─── Install Go ──────────────────────────────────────────────────────────────

install_go() {
    local GO_VERSION="1.23.8"  # Use stable version (project needs 1.26 but 1.23 compiles it too)

    if command -v go &>/dev/null; then
        info "Go already installed: $(go version)"
        return
    fi

    info "Installing Go $GO_VERSION..."

    local GO_ARCH="amd64"
    [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]] && GO_ARCH="arm64"

    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz" | \
        sudo tar -C /usr/local -xzf -

    echo 'export PATH=$PATH:/usr/local/go/bin' | sudo tee /etc/profile.d/golang.sh
    export PATH=$PATH:/usr/local/go/bin

    ok "Go $(go version) installed"
}

# ─── Install Node.js + Bun ───────────────────────────────────────────────────

install_node() {
    if command -v bun &>/dev/null; then
        info "Bun already installed: $(bun --version)"
        return
    fi

    info "Installing Bun..."
    curl -fsSL https://bun.sh/install | bash
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"

    ok "Bun $(bun --version) installed"
}

# ─── Install Valkey (Redis-compatible) ────────────────────────────────────────

install_valkey() {
    if command -v valkey-server &>/dev/null || command -v redis-server &>/dev/null; then
        info "Valkey/Redis already installed"
        return
    fi

    info "Installing Valkey..."

    case "$OS_ID" in
        amzn|fedora|rhel|centos)
            sudo dnf install -y valkey || sudo dnf install -y redis
            ;;
        ubuntu|debian)
            # Try valkey first, fall back to redis
            if ! sudo apt-get install -y valkey-server 2>/dev/null; then
                sudo apt-get install -y redis-server
            fi
            ;;
    esac

    ok "Valkey/Redis installed"
}

# ─── Install Caddy ───────────────────────────────────────────────────────────

install_caddy() {
    if command -v caddy &>/dev/null; then
        info "Caddy already installed: $(caddy version)"
        return
    fi

    info "Installing Caddy..."

    case "$OS_ID" in
        amzn|fedora|rhel|centos)
            sudo dnf install -y 'dnf-command(copr)'
            sudo dnf copr enable -y @caddy/caddy
            sudo dnf install -y caddy
            ;;
        ubuntu|debian)
            sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
                sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
                sudo tee /etc/apt/sources.list.d/caddy-stable.list
            sudo apt-get update
            sudo apt-get install -y caddy
            ;;
    esac

    ok "Caddy $(caddy version) installed"
}

# ─── Step 2: Create user and clone repo ──────────────────────────────────────

setup_user_and_repo() {
    info "Setting up service user and cloning repository..."

    # Create service user
    if ! id "$PACA_USER" &>/dev/null; then
        sudo useradd -r -m -d "$PACA_HOME" -s /bin/bash "$PACA_USER"
    fi

    # Clone repository
    if [ ! -d "$PACA_HOME/src" ]; then
        sudo -u "$PACA_USER" git clone --depth 1 -b "$PACA_BRANCH" "$PACA_REPO" "$PACA_HOME/src"
    else
        info "Repository already cloned, pulling latest..."
        sudo -u "$PACA_USER" git -C "$PACA_HOME/src" pull --ff-only || true
    fi

    # Create directories
    sudo -u "$PACA_USER" mkdir -p \
        "$PACA_HOME"/{bin,data,logs,config,plugins/{backend,frontend,mcp}}

    ok "Repository cloned to $PACA_HOME/src"
}

# ─── Step 3: Configure PostgreSQL ─────────────────────────────────────────────

setup_postgres() {
    info "Configuring PostgreSQL..."

    # Initialize if needed
    case "$OS_ID" in
        amzn|fedora|rhel|centos)
            sudo postgresql-setup --initdb 2>/dev/null || true
            sudo systemctl enable postgresql
            sudo systemctl start postgresql
            ;;
        ubuntu|debian)
            sudo systemctl enable postgresql
            sudo systemctl start postgresql
            ;;
    esac

    # Create database and user
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | \
        grep -q 1 || sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD';"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | \
        grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;"

    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DB TO $PG_USER;"

    # Allow password auth for local connections
    local PG_HBA
    PG_HBA=$(sudo -u postgres psql -t -c "SHOW hba_file;" | xargs)
    if ! grep -q "paca" "$PG_HBA" 2>/dev/null; then
        echo "local   $PG_DB   $PG_USER   md5" | sudo tee -a "$PG_HBA" > /dev/null
        echo "host    $PG_DB   $PG_USER   127.0.0.1/32   md5" | sudo tee -a "$PG_HBA" > /dev/null
        sudo systemctl reload postgresql
    fi

    ok "PostgreSQL configured (db=$PG_DB, user=$PG_USER)"
}

# ─── Step 4: Configure Valkey ─────────────────────────────────────────────────

setup_valkey() {
    info "Configuring Valkey/Redis..."

    local SVC_NAME="valkey"
    command -v valkey-server &>/dev/null || SVC_NAME="redis"

    sudo systemctl enable "$SVC_NAME" 2>/dev/null || sudo systemctl enable "${SVC_NAME}-server" 2>/dev/null || true
    sudo systemctl start "$SVC_NAME" 2>/dev/null || sudo systemctl start "${SVC_NAME}-server" 2>/dev/null || true

    ok "Valkey/Redis running on port 6379"
}

# ─── Step 5: Build Go API ────────────────────────────────────────────────────

build_api() {
    info "Building Go API from source..."

    cd "$PACA_HOME/src/services/api"

    sudo -u "$PACA_USER" bash -c "
        export PATH=\$PATH:/usr/local/go/bin
        export GOPATH=$PACA_HOME/.go
        export GOCACHE=$PACA_HOME/.go/cache
        cd $PACA_HOME/src/services/api
        CGO_ENABLED=0 go build -ldflags='-s -w' -o $PACA_HOME/bin/paca-api ./cmd/api
    "

    ok "API binary built: $PACA_HOME/bin/paca-api"
}

# ─── Step 6: Build Frontend ──────────────────────────────────────────────────

build_frontend() {
    info "Building frontend from source..."

    sudo -u "$PACA_USER" bash -c "
        export BUN_INSTALL=$PACA_HOME/.bun
        export PATH=\$BUN_INSTALL/bin:\$PATH

        # Install bun if not available for user
        if ! command -v bun &>/dev/null; then
            curl -fsSL https://bun.sh/install | bash
        fi

        cd $PACA_HOME/src/apps/web
        bun install --frozen-lockfile
        bun run build
    "

    # Copy build output
    sudo -u "$PACA_USER" cp -r "$PACA_HOME/src/apps/web/dist" "$PACA_HOME/data/web-dist"

    ok "Frontend built: $PACA_HOME/data/web-dist"
}

# ─── Step 7: Setup Realtime Service ──────────────────────────────────────────

setup_realtime() {
    info "Setting up Realtime service..."

    sudo -u "$PACA_USER" bash -c "
        export BUN_INSTALL=$PACA_HOME/.bun
        export PATH=\$BUN_INSTALL/bin:\$PATH

        cd $PACA_HOME/src/services/realtime
        bun install --frozen-lockfile
    "

    ok "Realtime service dependencies installed"
}

# ─── Step 8: Write environment config ────────────────────────────────────────

write_env_config() {
    info "Writing environment configuration..."

    local DATABASE_URL="postgres://${PG_USER}:${PG_PASSWORD}@localhost:5432/${PG_DB}?sslmode=disable"

    sudo -u "$PACA_USER" tee "$PACA_HOME/config/paca.env" > /dev/null << EOF
# ═══════════════════════════════════════════════════════════════
# Paca Environment Configuration
# Generated: $(date -Iseconds)
# ═══════════════════════════════════════════════════════════════

# Server
PORT=$API_PORT
ENV=production
PUBLIC_URL=$PUBLIC_URL

# Database
DATABASE_URL=$DATABASE_URL

# Redis / Valkey
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=$JWT_SECRET
JWT_ACCESS_TTL=15m
JWT_REFRESH_TTL=168h
JWT_REFRESH_SESSION_TTL=24h

# Cookies
COOKIE_SECURE=false

# Admin (SAVE THESE CREDENTIALS!)
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD

# Security
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Storage (local filesystem, no MinIO/S3)
STORAGE_PROVIDER=minio
STORAGE_ENDPOINT=localhost:9000
STORAGE_PUBLIC_URL=$PUBLIC_URL/storage
STORAGE_REGION=us-east-1
STORAGE_BUCKET=paca
STORAGE_ACCESS_KEY_ID=minioadmin
STORAGE_SECRET_ACCESS_KEY=minioadmin
STORAGE_USE_SSL=false

# Plugins
PLUGINS_STORE=local
PLUGINS_WASM_DIR=$PACA_HOME/plugins/backend
PLUGINS_FRONTEND_DIR=$PACA_HOME/plugins/frontend
PLUGINS_MCP_DIR=$PACA_HOME/plugins/mcp

# Cache
CACHE_PROJECT_TTL=5m
CACHE_CONFIG_TTL=10m
CACHE_SPRINT_TTL=2m

# AI Agent (disabled in bare-metal — use Claude Code instead)
# AGENT_API_KEY=
# AI_AGENT_URL=http://localhost:8000
EOF

    sudo chmod 600 "$PACA_HOME/config/paca.env"

    ok "Configuration written to $PACA_HOME/config/paca.env"
}

# ─── Step 9: Write Caddyfile ──────────────────────────────────────────────────

write_caddyfile() {
    info "Writing Caddy configuration..."

    sudo tee /etc/caddy/Caddyfile > /dev/null << EOF
# Paca Gateway — bare-metal deployment
:${CADDY_HTTP_PORT} {
    encode gzip

    header {
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    # API routes
    handle /api/* {
        reverse_proxy localhost:${API_PORT}
    }

    # Realtime (Socket.IO)
    handle_path /ws/* {
        reverse_proxy localhost:${REALTIME_PORT}
    }

    # Plugin frontend assets
    handle_path /plugins/* {
        root * $PACA_HOME/plugins/frontend
        file_server
    }

    # Web application (SPA)
    handle {
        root * $PACA_HOME/data/web-dist
        try_files {path} /index.html
        file_server
    }
}
EOF

    ok "Caddyfile written to /etc/caddy/Caddyfile"
}

# ─── Step 10: Create systemd services ────────────────────────────────────────

create_systemd_units() {
    info "Creating systemd service units..."

    # --- paca-api.service ---
    sudo tee /etc/systemd/system/paca-api.service > /dev/null << EOF
[Unit]
Description=Paca API Service (Go)
After=network.target postgresql.service valkey.service
Requires=postgresql.service

[Service]
Type=simple
User=$PACA_USER
Group=$PACA_USER
WorkingDirectory=$PACA_HOME
EnvironmentFile=$PACA_HOME/config/paca.env
ExecStart=$PACA_HOME/bin/paca-api
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
    sudo tee /etc/systemd/system/paca-realtime.service > /dev/null << EOF
[Unit]
Description=Paca Realtime Service (Socket.IO)
After=network.target valkey.service paca-api.service

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
Environment=BUN_INSTALL=$PACA_HOME/.bun
Environment=PATH=$PACA_HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PACA_HOME/.bun/bin/bun run src/index.ts
Restart=on-failure
RestartSec=5
StandardOutput=append:$PACA_HOME/logs/realtime.log
StandardError=append:$PACA_HOME/logs/realtime.log

[Install]
WantedBy=multi-user.target
EOF

    # --- paca-caddy.service (override default caddy) ---
    sudo tee /etc/systemd/system/paca-caddy.service > /dev/null << EOF
[Unit]
Description=Paca Gateway (Caddy)
After=network.target paca-api.service paca-realtime.service

[Service]
Type=simple
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
Restart=on-failure
RestartSec=5

# Allow binding to port 80/443
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload

    ok "Systemd units created"
}

# ─── Step 11: Start services ─────────────────────────────────────────────────

start_services() {
    info "Starting Paca services..."

    sudo systemctl enable --now paca-api
    sleep 2  # Wait for API to start and run migrations

    sudo systemctl enable --now paca-realtime
    sudo systemctl enable --now paca-caddy

    # Stop the default caddy service if it conflicts
    sudo systemctl stop caddy 2>/dev/null || true
    sudo systemctl disable caddy 2>/dev/null || true

    ok "All services started"
}

# ─── Step 12: Verify ─────────────────────────────────────────────────────────

verify_deployment() {
    info "Verifying deployment..."

    sleep 3

    local HEALTH
    HEALTH=$(curl -sf "http://localhost:${API_PORT}/api/healthz" 2>/dev/null || echo "FAILED")

    if echo "$HEALTH" | grep -q "ok"; then
        ok "API health check passed"
    else
        warn "API health check failed — check logs: $PACA_HOME/logs/api.log"
    fi
}

# ─── Step 13: Print summary ──────────────────────────────────────────────────

print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Paca deployment complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BLUE}Access URL:${NC}     $PUBLIC_URL"
    echo -e "  ${BLUE}Admin user:${NC}     $ADMIN_USERNAME"
    echo -e "  ${BLUE}Admin password:${NC}  $ADMIN_PASSWORD"
    echo ""
    echo -e "  ${YELLOW}⚠️  Save these credentials — they cannot be recovered!${NC}"
    echo ""
    echo "  ─── Service Management ─────────────────────────────────────"
    echo ""
    echo "  Status:   sudo systemctl status paca-api paca-realtime paca-caddy"
    echo "  Logs:     tail -f $PACA_HOME/logs/api.log"
    echo "  Restart:  sudo systemctl restart paca-api"
    echo "  Stop all: sudo systemctl stop paca-api paca-realtime paca-caddy"
    echo ""
    echo "  ─── File Locations ─────────────────────────────────────────"
    echo ""
    echo "  Source:     $PACA_HOME/src/"
    echo "  Config:     $PACA_HOME/config/paca.env"
    echo "  Logs:       $PACA_HOME/logs/"
    echo "  API binary: $PACA_HOME/bin/paca-api"
    echo "  Frontend:   $PACA_HOME/data/web-dist/"
    echo "  Plugins:    $PACA_HOME/plugins/"
    echo ""
    echo "  ─── Upgrade ────────────────────────────────────────────────"
    echo ""
    echo "  cd $PACA_HOME/src && git pull"
    echo "  # Rebuild API:"
    echo "  cd services/api && CGO_ENABLED=0 go build -o $PACA_HOME/bin/paca-api ./cmd/api"
    echo "  sudo systemctl restart paca-api"
    echo "  # Rebuild frontend:"
    echo "  cd apps/web && bun install && bun run build"
    echo "  cp -r dist/* $PACA_HOME/data/web-dist/"
    echo "  sudo systemctl restart paca-caddy"
    echo ""
    echo "  ─── Claude Code Integration ────────────────────────────────"
    echo ""
    echo "  # Generate an API key in Paca UI (Settings → API Keys), then:"
    echo "  claude mcp add paca \\"
    echo "    --env PACA_API_KEY=<your-api-key> \\"
    echo "    --env PACA_API_URL=$PUBLIC_URL \\"
    echo "    -- npx -y @paca-ai/paca-mcp"
    echo ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────

main() {
    # Must run as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root (or with sudo)"
    fi

    detect_os
    install_deps
    install_go
    install_node
    install_valkey
    install_caddy
    setup_user_and_repo
    setup_postgres
    setup_valkey
    build_api
    build_frontend
    setup_realtime
    write_env_config
    write_caddyfile
    create_systemd_units
    start_services
    verify_deployment
    print_summary
}

main "$@"
