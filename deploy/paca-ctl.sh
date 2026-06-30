#!/usr/bin/env bash
# =============================================================================
# paca-ctl — Management utility for bare-metal Litchi deployment
# =============================================================================
#
# Usage:
#   paca-ctl status          Show service status
#   paca-ctl start           Start all services
#   paca-ctl stop            Stop all services
#   paca-ctl restart         Restart all services
#   paca-ctl logs [service]  Tail logs (api|realtime|caddy|all)
#   paca-ctl upgrade         Pull latest code and rebuild
#   paca-ctl backup          Create a database backup
#   paca-ctl restore <file>  Restore from a backup file
#
# =============================================================================

set -euo pipefail

PACA_HOME="${PACA_HOME:-/opt/paca}"
SERVICES=(paca-api paca-realtime paca-caddy)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

case "${1:-help}" in

    status)
        echo -e "${BLUE}═══ Litchi Service Status ═══${NC}"
        for svc in "${SERVICES[@]}"; do
            STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
            if [ "$STATUS" = "active" ]; then
                echo -e "  ${GREEN}●${NC} $svc: ${GREEN}running${NC}"
            else
                echo -e "  ${RED}●${NC} $svc: ${RED}$STATUS${NC}"
            fi
        done
        echo ""
        echo -e "${BLUE}═══ Resource Usage ═══${NC}"
        echo "  API:      $(ps -o rss= -C paca-api 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo 'N/A')"
        echo "  Realtime: $(ps aux | grep 'bun.*realtime' | grep -v grep | awk '{printf "%.1f MB", $6/1024}' || echo 'N/A')"
        echo ""
        echo -e "${BLUE}═══ Connections ═══${NC}"
        echo "  PostgreSQL: $(pg_isready -q && echo -e "${GREEN}OK${NC}" || echo -e "${RED}DOWN${NC}")"
        echo "  Valkey:     $((redis-cli ping 2>/dev/null || valkey-cli ping 2>/dev/null) | grep -q PONG && echo -e "${GREEN}OK${NC}" || echo -e "${RED}DOWN${NC}")"
        echo "  API:        $(curl -sf http://localhost:8080/api/healthz >/dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}DOWN${NC}")"
        ;;

    start)
        echo "Starting Litchi services..."
        for svc in "${SERVICES[@]}"; do
            sudo systemctl start "$svc"
            echo "  Started $svc"
        done
        echo -e "${GREEN}All services started.${NC}"
        ;;

    stop)
        echo "Stopping Litchi services..."
        for svc in $(echo "${SERVICES[@]}" | tr ' ' '\n' | tac); do
            sudo systemctl stop "$svc"
            echo "  Stopped $svc"
        done
        echo -e "${YELLOW}All services stopped.${NC}"
        ;;

    restart)
        echo "Restarting Litchi services..."
        for svc in "${SERVICES[@]}"; do
            sudo systemctl restart "$svc"
            echo "  Restarted $svc"
        done
        echo -e "${GREEN}All services restarted.${NC}"
        ;;

    logs)
        SERVICE="${2:-all}"
        case "$SERVICE" in
            api)      tail -f "$PACA_HOME/logs/api.log" ;;
            realtime) tail -f "$PACA_HOME/logs/realtime.log" ;;
            caddy)    journalctl -u paca-caddy -f ;;
            all)      tail -f "$PACA_HOME/logs/"*.log ;;
            *)        echo "Unknown service: $SERVICE. Use: api|realtime|caddy|all" ;;
        esac
        ;;

    upgrade)
        echo -e "${BLUE}═══ Upgrading Litchi ═══${NC}"

        echo "  Pulling latest source..."
        sudo -u paca git -C "$PACA_HOME/src" pull --ff-only

        echo "  Building API..."
        sudo -u paca bash -c "
            export PATH=\$PATH:/usr/local/go/bin
            export GOPATH=$PACA_HOME/.go
            export GOCACHE=$PACA_HOME/.go/cache
            cd $PACA_HOME/src/services/api
            CGO_ENABLED=0 go build -ldflags='-s -w' -o $PACA_HOME/bin/paca-api ./cmd/api
        "

        echo "  Building frontend..."
        sudo -u paca bash -c "
            export PATH=$PACA_HOME/.bun/bin:\$PATH
            cd $PACA_HOME/src/apps/web
            bun install --frozen-lockfile
            bun run build
            cp -r dist/* $PACA_HOME/data/web-dist/
        "

        echo "  Updating realtime deps..."
        sudo -u paca bash -c "
            export PATH=$PACA_HOME/.bun/bin:\$PATH
            cd $PACA_HOME/src/services/realtime
            bun install --frozen-lockfile
        "

        echo "  Restarting services..."
        for svc in "${SERVICES[@]}"; do
            sudo systemctl restart "$svc"
        done

        echo -e "${GREEN}Upgrade complete!${NC}"
        ;;

    backup)
        BACKUP_DIR="$PACA_HOME/backups"
        mkdir -p "$BACKUP_DIR"
        TIMESTAMP=$(date +%Y%m%d-%H%M%S)
        BACKUP_FILE="$BACKUP_DIR/paca-$TIMESTAMP.sql.gz"

        source "$PACA_HOME/config/paca.env"
        echo "Creating database backup..."
        pg_dump "$DATABASE_URL" --no-owner | gzip > "$BACKUP_FILE"
        echo -e "${GREEN}Backup saved: $BACKUP_FILE${NC}"

        # Cleanup old backups (keep last 7 days)
        find "$BACKUP_DIR" -name "paca-*.sql.gz" -mtime +7 -delete
        ;;

    restore)
        BACKUP_FILE="${2:-}"
        if [ -z "$BACKUP_FILE" ]; then
            echo "Usage: paca-ctl restore <backup-file.sql.gz>"
            echo ""
            echo "Available backups:"
            ls -lh "$PACA_HOME/backups/"*.sql.gz 2>/dev/null || echo "  (none)"
            exit 1
        fi

        source "$PACA_HOME/config/paca.env"
        echo -e "${YELLOW}WARNING: This will overwrite the current database!${NC}"
        read -p "Continue? (yes/no): " CONFIRM
        if [ "$CONFIRM" = "yes" ]; then
            echo "Stopping API..."
            sudo systemctl stop paca-api
            echo "Restoring..."
            gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
            echo "Starting API..."
            sudo systemctl start paca-api
            echo -e "${GREEN}Restore complete.${NC}"
        else
            echo "Aborted."
        fi
        ;;

    help|*)
        echo "paca-ctl — Litchi bare-metal management"
        echo ""
        echo "Usage: paca-ctl <command>"
        echo ""
        echo "Commands:"
        echo "  status          Show service status"
        echo "  start           Start all services"
        echo "  stop            Stop all services"
        echo "  restart         Restart all services"
        echo "  logs [service]  Tail logs (api|realtime|caddy|all)"
        echo "  upgrade         Pull latest and rebuild all"
        echo "  backup          Create database backup"
        echo "  restore <file>  Restore from backup"
        echo ""
        ;;
esac
