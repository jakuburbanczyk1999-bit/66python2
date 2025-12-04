# ============================================
# Miedziowe Karty - Backend Dockerfile
# ============================================

FROM python:3.11-slim

# Ustaw katalog roboczy
WORKDIR /app

# Zainstaluj zależności systemowe
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Kopiuj requirements i zainstaluj zależności Pythona
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj kod aplikacji
COPY . .

# Usuń niepotrzebne pliki
RUN rm -rf frontend/ backup/ postgres-data/ __pycache__/ .git/ .vscode/ *.db

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Uruchom serwer
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
