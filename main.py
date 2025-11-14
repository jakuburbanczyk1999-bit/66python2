"""
Główny plik aplikacji FastAPI
Odpowiedzialność: Inicjalizacja app, routing, startup/shutdown
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import routerów
from routers import auth, lobby, game, pages, websocket_router, admin

# Import services
from services.redis_service import init_redis, close_redis
from database import init_db

# Import utils
from utils.cleanup import setup_periodic_cleanup, stop_cleanup

# Import logging config
from logging_config import setup_logging

# ============================================
# LIFESPAN - Startup/Shutdown
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Zarządza cyklem życia aplikacji (startup/shutdown)
    """
    # ============================================
    # STARTUP
    # ============================================
    print("=" * 60)
    print("🚀 URUCHAMIANIE APLIKACJI: Miedziowe Karty - Gra w 66")
    print("=" * 60)
    
    # 0. Konfiguracja logowania
    print("\n📋 [0/3] Konfiguracja logowania...")
    try:
        setup_logging()
    except Exception as e:
        print(f"⚠️ OSTRZEŻENIE logging: {e}")
    
    # 1. Inicjalizacja bazy danych
    print("\n📦 [1/3] Inicjalizacja bazy danych...")
    try:
        await init_db()
        print("✅ Baza danych gotowa!")
    except Exception as e:
        print(f"❌ BŁĄD bazy danych: {e}")
        raise
    
    # 2. Inicjalizacja Redis
    print("\n🔴 [2/3] Inicjalizacja Redis...")
    try:
        await init_redis()
        print("✅ Redis gotowy!")
    except Exception as e:
        print(f"❌ BŁĄD Redis: {e}")
        raise
    
    # 3. Uruchomienie cleanup task
    print("\n🧹 [3/3] Uruchamianie garbage collector...")
    try:
        setup_periodic_cleanup()
        print("✅ Cleanup task uruchomiony!")
    except Exception as e:
        print(f"⚠️ OSTRZEŻENIE cleanup: {e}")
        # Nie przerywaj startu jeśli cleanup nie działa
    
    print("\n" + "=" * 60)
    print("✅ APLIKACJA URUCHOMIONA POMYŚLNIE!")
    print("=" * 60)
    print("\n📍 Dostępne endpointy:")
    print("   • http://localhost:8000/          - Strona główna")
    print("   • http://localhost:8000/docs      - API dokumentacja")
    print("   • http://localhost:8000/api/auth  - Autentykacja")
    print("   • http://localhost:8000/api/lobby - Lobby")
    print("   • http://localhost:8000/api/game  - Gra")
    print("   • http://localhost:8000/ws        - WebSocket")
    print("\n")
    
    # Yield - aplikacja działa
    yield
    
    # ============================================
    # SHUTDOWN
    # ============================================
    print("\n" + "=" * 60)
    print("👋 ZAMYKANIE APLIKACJI...")
    print("=" * 60)
    
    # 1. Zatrzymaj cleanup task
    print("\n🧹 [1/2] Zatrzymywanie cleanup task...")
    try:
        await stop_cleanup()
        print("✅ Cleanup zatrzymany!")
    except Exception as e:
        print(f"⚠️ Błąd zatrzymywania cleanup: {e}")
    
    # 2. Zamknij Redis
    print("\n🔴 [2/2] Zamykanie Redis...")
    try:
        await close_redis()
        print("✅ Redis zamknięty!")
    except Exception as e:
        print(f"⚠️ Błąd zamykania Redis: {e}")
    
    print("\n" + "=" * 60)
    print("✅ APLIKACJA ZAMKNIĘTA POMYŚLNIE!")
    print("=" * 60 + "\n")

# ============================================
# INICJALIZACJA FASTAPI
# ============================================

app = FastAPI(
    title="Miedziowe Karty - Gra w 66",
    description="Backend API dla gry w 66 (Sixty-Six card game)",
    version="2.0.0",
    lifespan=lifespan  # <-- NOWY SPOSÓB (FastAPI 0.93+)
)



# ============================================
# MIDDLEWARE
# ============================================

# CORS - pozwól na requesty z frontendu
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# STATIC FILES
# ============================================

# Serwuj pliki statyczne (HTML, CSS, JS)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("✅ Static files mounted: /static")
except Exception as e:
    print(f"⚠️ OSTRZEŻENIE: Nie można zamontować /static: {e}")
    print("   (To normalne jeśli folder 'static' nie istnieje w dev)")

# ============================================
# ROUTING - API ENDPOINTS
# ============================================

# Auth endpoints: /api/auth/*
app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["🔐 Authentication"]
)

# Lobby endpoints: /api/lobby/*
app.include_router(
    lobby.router,
    prefix="/api/lobby",
    tags=["🎮 Lobby"]
)

# Game endpoints: /api/game/*
app.include_router(
    game.router,
    prefix="/api/game",
    tags=["🃏 Game"]
)

# WebSocket: /ws/*
app.include_router(
    websocket_router.router,
    tags=["🔌 WebSocket"]
)

# Pages (HTML): /*
app.include_router(
    pages.router,
    tags=["📄 Pages"]
)
# Pages (Admin): /admin/*
app.include_router(
    admin.router,
    prefix="/api/admin", 
    tags=["👑 Admin"]
)

# ============================================
# ROOT ENDPOINT
# ============================================

@app.get("/api", tags=["🏠 Root"])
async def api_root():
    """
    API Root endpoint - informacje o API
    """
    return {
        "status": "ok",
        "message": "Miedziowe Karty API",
        "version": "2.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "lobby": "/api/lobby",
            "game": "/api/game",
            "websocket": "/ws",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.get("/health", tags=["🏥 Health"])
async def health_check():
    """
    Health check endpoint - sprawdź czy serwer działa
    """
    from services.redis_service import get_redis_client
    
    health = {
        "status": "healthy",
        "services": {}
    }
    
    # Sprawdź Redis
    try:
        redis = get_redis_client()
        await redis.ping()
        health["services"]["redis"] = "✅ online"
    except Exception as e:
        health["services"]["redis"] = f"❌ offline: {e}"
        health["status"] = "unhealthy"
    
    # Sprawdź Database (opcjonalnie)
    try:
        from database import async_sessionmaker
        async with async_sessionmaker() as session:
            await session.execute("SELECT 1")
        health["services"]["database"] = "✅ online"
    except Exception as e:
        health["services"]["database"] = f"⚠️ warning: {e}"
    
    return health

# ============================================
# ADMIN ENDPOINTS (opcjonalnie)
# ============================================

@app.get("/api/stats", tags=["📊 Admin"])
async def get_stats():
    """
    Statystyki serwera (liczba gier, graczy, etc.)
    """
    from utils.cleanup import get_cleanup_stats
    from routers.websocket_router import manager
    
    try:
        cleanup_stats = await get_cleanup_stats()
        ws_stats = {
            'connected_games': len(manager.get_all_games()),
            'total_connections': sum(
                manager.get_connections_count(game_id)
                for game_id in manager.get_all_games()
            )
        }
        
        return {
            "status": "ok",
            "cleanup": cleanup_stats,
            "websocket": ws_stats
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# ============================================
# MAIN - Uruchomienie serwera
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("🎮 MIEDZIOWE KARTY - GRA W 66")
    print("=" * 60)
    print("\n▶️  Uruchamianie serwera deweloperskiego...\n")
    
    # Uruchom serwer deweloperski
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload w dev mode
        log_level="info"
    )