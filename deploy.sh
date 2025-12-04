#!/bin/bash
# ============================================
# Miedziowe Karty - Skrypt wdrożeniowy
# ============================================
# Użycie: ./deploy.sh [opcja]
# Opcje:
#   build   - Buduje frontend i backend
#   start   - Uruchamia kontenery
#   stop    - Zatrzymuje kontenery
#   restart - Restartuje kontenery
#   logs    - Pokazuje logi
#   update  - Pobiera zmiany z git i restartuje
# ============================================

set -e

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funkcje pomocnicze
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Sprawdź czy .env istnieje
check_env() {
    if [ ! -f ".env" ]; then
        log_warn "Brak pliku .env - kopiuję z .env.example"
        cp .env.example .env
        log_warn "WAŻNE: Edytuj plik .env i ustaw SECRET_KEY!"
        exit 1
    fi
}

# Buduj frontend
build_frontend() {
    log_info "Budowanie frontendu..."
    cd frontend
    npm install
    npm run build
    cd ..
    log_info "Frontend zbudowany!"
}

# Buduj backend (Docker)
build_backend() {
    log_info "Budowanie backendu..."
    docker compose -f docker-compose.prod.yml build backend
    log_info "Backend zbudowany!"
}

# Uruchom kontenery
start() {
    check_env
    log_info "Uruchamianie kontenerów..."
    docker compose -f docker-compose.prod.yml up -d
    log_info "Kontenery uruchomione!"
    docker compose -f docker-compose.prod.yml ps
}

# Zatrzymaj kontenery
stop() {
    log_info "Zatrzymywanie kontenerów..."
    docker compose -f docker-compose.prod.yml down
    log_info "Kontenery zatrzymane!"
}

# Restartuj kontenery
restart() {
    log_info "Restartowanie kontenerów..."
    docker compose -f docker-compose.prod.yml restart
    log_info "Kontenery zrestartowane!"
}

# Pokaż logi
logs() {
    docker compose -f docker-compose.prod.yml logs -f
}

# Pełna aktualizacja
update() {
    log_info "Pobieranie zmian z git..."
    git pull origin main
    
    log_info "Budowanie frontendu..."
    build_frontend
    
    log_info "Restartowanie backendu..."
    docker compose -f docker-compose.prod.yml up -d --build backend
    
    log_info "Restartowanie nginx..."
    docker compose -f docker-compose.prod.yml restart nginx
    
    log_info "Aktualizacja zakończona!"
    docker compose -f docker-compose.prod.yml ps
}

# Główna logika
case "$1" in
    build)
        build_frontend
        build_backend
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    update)
        update
        ;;
    *)
        echo "Użycie: $0 {build|start|stop|restart|logs|update}"
        echo ""
        echo "Opcje:"
        echo "  build   - Buduje frontend i backend"
        echo "  start   - Uruchamia kontenery"
        echo "  stop    - Zatrzymuje kontenery"
        echo "  restart - Restartuje kontenery"
        echo "  logs    - Pokazuje logi"
        echo "  update  - Pobiera zmiany z git i restartuje"
        exit 1
        ;;
esac
