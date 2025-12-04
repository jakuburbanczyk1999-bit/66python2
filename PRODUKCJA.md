# 🚀 Miedziowe Karty - Przewodnik Produkcyjny

## 📋 Spis treści
1. [Przygotowanie projektu](#1-przygotowanie-projektu)
2. [Wybór hostingu](#2-wybór-hostingu)
3. [Wdrożenie na VPS](#3-wdrożenie-na-vps)
4. [Konfiguracja domeny i SSL](#4-konfiguracja-domeny-i-ssl)
5. [Zarządzanie zmianami](#5-zarządzanie-zmianami)
6. [Monitoring i backup](#6-monitoring-i-backup)

---

## 1. Przygotowanie projektu

### 1.1 Zmienne środowiskowe (.env)

Utwórz plik `.env` w głównym katalogu:

```env
# === PRODUKCJA ===
ENVIRONMENT=production

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=silne_haslo_redis_123

# JWT - ZMIEŃ NA LOSOWY STRING!
SECRET_KEY=wygeneruj_losowy_64_znakowy_string_tutaj_abcdefgh12345678

# Database (jeśli używasz PostgreSQL)
DATABASE_URL=postgresql://mkuser:mkpassword@db:5432/mkdb
```

### 1.2 Wygeneruj bezpieczny SECRET_KEY

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# Lub online: https://randomkeygen.com/
```

### 1.3 Zbuduj frontend

```bash
cd frontend
npm run build
```

To stworzy folder `frontend/dist/` z gotowymi plikami statycznymi.

---

## 2. Wybór hostingu

### Opcja A: VPS (Rekomendowane) - ~20-40 zł/mies
**Zalety:** Pełna kontrola, najtańszy, WebSocket działa idealnie

| Provider | Cena | RAM | Lokalizacja |
|----------|------|-----|-------------|
| **Hetzner** | ~18 zł | 2GB | Niemcy (szybki dla PL) |
| **DigitalOcean** | ~24 zł | 1GB | Amsterdam |
| **OVH** | ~20 zł | 2GB | Polska! |
| **Mikr.us** | ~15 zł | 2GB | Polska! |

### Opcja B: Railway / Render - ~40-80 zł/mies
**Zalety:** Łatwe wdrożenie, auto-deploy z GitHub
**Wady:** Droższe, ograniczenia WebSocket

### Opcja C: Fly.io - ~30-50 zł/mies
**Zalety:** Dobre dla WebSocket, global edge
**Wady:** Bardziej skomplikowana konfiguracja

**📌 REKOMENDACJA: Hetzner VPS (CX11) za ~18 zł/mies**

---

## 3. Wdrożenie na VPS

### 3.1 Zamów VPS

1. Zarejestruj się na https://hetzner.cloud lub https://mikr.us
2. Zamów najtańszy VPS z Ubuntu 22.04
3. Zapisz IP serwera i hasło root

### 3.2 Połącz się z serwerem

```bash
ssh root@TWOJE_IP_SERWERA
```

### 3.3 Zainstaluj Docker

```bash
# Aktualizacja systemu
apt update && apt upgrade -y

# Instalacja Docker
curl -fsSL https://get.docker.com | sh

# Instalacja Docker Compose
apt install docker-compose-plugin -y

# Sprawdź instalację
docker --version
docker compose version
```

### 3.4 Sklonuj projekt

```bash
# Zainstaluj git
apt install git -y

# Sklonuj repozytorium
cd /opt
git clone https://github.com/TWOJ_USERNAME/miedziowe-karty.git
cd miedziowe-karty
```

### 3.5 Utwórz plik produkcyjny docker-compose

```bash
nano docker-compose.prod.yml
```

Wklej:

```yaml
version: '3.8'

services:
  # Redis
  redis:
    image: redis:7-alpine
    container_name: mk_redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: always

  # Backend FastAPI
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mk_backend
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - redis
    ports:
      - "8000:8000"
    volumes:
      - ./gra66.db:/app/gra66.db
    restart: always

  # Frontend Nginx
  frontend:
    image: nginx:alpine
    container_name: mk_frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - backend
    restart: always

volumes:
  redis_data:
```

### 3.6 Utwórz Dockerfile dla backendu

```bash
nano Dockerfile
```

Wklej:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Zainstaluj zależności systemowe
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Kopiuj requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj kod aplikacji
COPY . .

# Uruchom serwer
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.7 Utwórz requirements.txt (jeśli nie istnieje)

```bash
nano requirements.txt
```

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
redis>=4.5.0
cloudpickle>=2.2.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
python-multipart>=0.0.6
```

### 3.8 Utwórz nginx.conf

```bash
nano nginx.conf
```

Wklej:

```nginx
server {
    listen 80;
    server_name _;
    
    # Frontend - pliki statyczne
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # WebSocket
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### 3.9 Utwórz plik .env na serwerze

```bash
nano .env
```

```env
REDIS_PASSWORD=wygeneruj_silne_haslo
SECRET_KEY=wygeneruj_64_znakowy_token
```

### 3.10 Zbuduj frontend (na serwerze lub lokalnie)

```bash
# Na serwerze (wymaga Node.js)
apt install nodejs npm -y
cd frontend
npm install
npm run build
cd ..
```

Lub zbuduj lokalnie i skopiuj:
```bash
# Lokalnie
cd frontend
npm run build

# Skopiuj na serwer
scp -r dist/ root@TWOJE_IP:/opt/miedziowe-karty/frontend/
```

### 3.11 Uruchom aplikację

```bash
cd /opt/miedziowe-karty
docker compose -f docker-compose.prod.yml up -d
```

### 3.12 Sprawdź czy działa

```bash
# Logi
docker compose -f docker-compose.prod.yml logs -f

# Status
docker ps
```

Aplikacja powinna być dostępna na: `http://TWOJE_IP`

---

## 4. Konfiguracja domeny i SSL

### 4.1 Kup domenę

- https://ovh.pl (~30 zł/rok za .pl)
- https://nazwa.pl
- https://home.pl

### 4.2 Skonfiguruj DNS

W panelu rejestratora dodaj rekord A:
```
Typ: A
Nazwa: @ (lub pusta)
Wartość: TWOJE_IP_SERWERA
TTL: 3600
```

Dla www:
```
Typ: CNAME
Nazwa: www
Wartość: twojadomena.pl
TTL: 3600
```

### 4.3 Zainstaluj certyfikat SSL (Let's Encrypt)

```bash
# Zainstaluj Certbot
apt install certbot python3-certbot-nginx -y

# Zatrzymaj nginx z Dockera
docker compose -f docker-compose.prod.yml stop frontend

# Uzyskaj certyfikat
certbot certonly --standalone -d twojadomena.pl -d www.twojadomena.pl

# Uruchom ponownie
docker compose -f docker-compose.prod.yml up -d
```

### 4.4 Zaktualizuj nginx.conf dla HTTPS

```nginx
server {
    listen 80;
    server_name twojadomena.pl www.twojadomena.pl;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name twojadomena.pl www.twojadomena.pl;
    
    ssl_certificate /etc/letsencrypt/live/twojadomena.pl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/twojadomena.pl/privkey.pem;
    
    # Frontend
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

## 5. Zarządzanie zmianami

### 5.1 Workflow aktualizacji

```bash
# 1. Wprowadź zmiany lokalnie
# 2. Przetestuj lokalnie
# 3. Commit i push do GitHub
git add .
git commit -m "Opis zmian"
git push origin main

# 4. Na serwerze - pobierz zmiany
ssh root@TWOJE_IP
cd /opt/miedziowe-karty
git pull origin main

# 5. Przebuduj frontend (jeśli zmiany)
cd frontend
npm run build
cd ..

# 6. Zrestartuj backend (jeśli zmiany)
docker compose -f docker-compose.prod.yml up -d --build backend

# 7. Sprawdź logi
docker compose -f docker-compose.prod.yml logs -f backend
```

### 5.2 Szybka aktualizacja (tylko backend)

```bash
ssh root@TWOJE_IP
cd /opt/miedziowe-karty
git pull
docker compose -f docker-compose.prod.yml restart backend
```

### 5.3 Szybka aktualizacja (tylko frontend)

```bash
# Lokalnie - zbuduj
cd frontend
npm run build

# Skopiuj na serwer
scp -r dist/* root@TWOJE_IP:/opt/miedziowe-karty/frontend/dist/

# Na serwerze - restart nginx
ssh root@TWOJE_IP
docker compose -f docker-compose.prod.yml restart frontend
```

### 5.4 Automatyczny deploy (opcjonalnie)

Możesz skonfigurować GitHub Actions dla auto-deploy:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_IP }}
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/miedziowe-karty
            git pull origin main
            cd frontend && npm install && npm run build && cd ..
            docker compose -f docker-compose.prod.yml up -d --build
```

---

## 6. Monitoring i backup

### 6.1 Podstawowe komendy

```bash
# Status kontenerów
docker ps

# Logi w czasie rzeczywistym
docker compose -f docker-compose.prod.yml logs -f

# Logi konkretnego serwisu
docker compose -f docker-compose.prod.yml logs -f backend

# Restart wszystkiego
docker compose -f docker-compose.prod.yml restart

# Zatrzymaj
docker compose -f docker-compose.prod.yml down

# Uruchom
docker compose -f docker-compose.prod.yml up -d
```

### 6.2 Backup bazy danych

```bash
# Backup SQLite
cp /opt/miedziowe-karty/gra66.db /opt/backups/gra66_$(date +%Y%m%d).db

# Automatyczny backup (cron)
crontab -e
# Dodaj:
0 3 * * * cp /opt/miedziowe-karty/gra66.db /opt/backups/gra66_$(date +\%Y\%m\%d).db
```

### 6.3 Backup Redis

```bash
# Redis zapisuje dane w volume, ale możesz wyeksportować
docker exec mk_redis redis-cli -a $REDIS_PASSWORD BGSAVE
```

### 6.4 Monitoring (opcjonalnie)

Możesz dodać Uptime Kuma dla monitoringu:

```bash
docker run -d \
  --name uptime-kuma \
  -p 3001:3001 \
  -v uptime-kuma:/app/data \
  --restart always \
  louislam/uptime-kuma
```

---

## 📝 Checklist przed produkcją

- [ ] Zmień SECRET_KEY na losowy string
- [ ] Ustaw silne hasło Redis
- [ ] Zbuduj frontend (`npm run build`)
- [ ] Przetestuj lokalnie z docker-compose
- [ ] Zamów VPS
- [ ] Skonfiguruj domenę i DNS
- [ ] Zainstaluj certyfikat SSL
- [ ] Skonfiguruj backup
- [ ] Przetestuj WebSocket
- [ ] Sprawdź logi na błędy

---

## 🆘 Troubleshooting

### WebSocket nie działa
- Sprawdź nginx.conf - sekcja `/ws`
- Sprawdź czy `proxy_read_timeout` jest ustawiony

### CORS błędy
- Dodaj domenę do `allow_origins` w `main.py`

### 502 Bad Gateway
- Backend nie wystartował - sprawdź logi: `docker logs mk_backend`

### Brak dostępu do strony
- Sprawdź czy porty 80/443 są otwarte w firewall
- `ufw allow 80 && ufw allow 443`

---

## 💰 Szacunkowe koszty

| Element | Koszt miesięczny |
|---------|------------------|
| VPS (Hetzner CX11) | ~18 zł |
| Domena .pl (rocznie/12) | ~3 zł |
| SSL (Let's Encrypt) | 0 zł |
| **RAZEM** | **~21 zł/mies** |

---

*Ostatnia aktualizacja: Grudzień 2024*
