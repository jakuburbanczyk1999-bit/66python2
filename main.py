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

# Import bot matchmaking
from bot_matchmaking import bot_matchmaking

# ============================================
# STARTUP CLEANUP FUNCTIONS
# ============================================

async def cleanup_stale_bot_games(redis_service):
    """
    Czyści stare gry botów po restarcie serwera.
    Gry W_GRZE bez silnika są usuwane.
    """
    import json
    from database import async_sessionmaker, User
    from sqlalchemy import select
    
    try:
        # Pobierz wszystkie lobby
        lobbies = await redis_service.list_lobbies()
        removed_count = 0
        
        for lobby in lobbies:
            lobby_id = lobby.get('id')
            status = lobby.get('status_partii', 'LOBBY')
            
            # Sprawdź tylko gry W_GRZE
            if status != 'W_GRZE':
                continue
            
            # Sprawdź czy silnik gry istnieje
            engine = await redis_service.get_game_engine(lobby_id)
            
            if not engine:
                # Brak silnika = gra zombie, usuń
                print(f"   [Cleanup] Usuwam grę zombie: {lobby_id} (brak silnika)")
                await redis_service.delete_game(lobby_id)
                removed_count += 1
                continue
            
            # Sprawdź czy wszyscy gracze to boty
            slots = lobby.get('slots', [])
            all_bots = True
            
            for slot in slots:
                if slot.get('typ') not in ['gracz', 'bot']:
                    continue
                    
                player_name = slot.get('nazwa')
                if not player_name:
                    continue
                
                # Sprawdź czy to bot
                is_bot = False
                
                # Wzorzec "Bot #X"
                if player_name.startswith('Bot #'):
                    is_bot = True
                else:
                    # Sprawdź w bazie danych
                    try:
                        async with async_sessionmaker() as session:
                            query = select(User).where(User.username == player_name)
                            result = await session.execute(query)
                            user = result.scalar_one_or_none()
                            
                            if user and user.settings:
                                settings = json.loads(user.settings)
                                is_bot = settings.get('jest_botem', False)
                    except:
                        pass
                
                if not is_bot:
                    all_bots = False
                    break
            
            # Jeśli wszyscy gracze to boty, usuń grę (po restarcie nie ma sensu kontynuować)
            if all_bots:
                print(f"   [Cleanup] Usuwam grę botów: {lobby_id} (tylko boty, restart serwera)")
                await redis_service.delete_game(lobby_id)
                removed_count += 1
        
        if removed_count > 0:
            print(f"   [Cleanup] Usunięto {removed_count} starych gier")
        else:
            print("   [Cleanup] Brak starych gier do usunięcia")
            
    except Exception as e:
        print(f"   [Cleanup] Błąd: {e}")
        import traceback
        traceback.print_exc()

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
    print("\n🧹 [3/4] Uruchamianie garbage collector...")
    try:
        setup_periodic_cleanup()
        print("✅ Cleanup task uruchomiony!")
    except Exception as e:
        print(f"⚠️ OSTRZEŻENIE cleanup: {e}")
        # Nie przerywaj startu jeśli cleanup nie działa
    
    # 4. Czyszczenie starych gier botów po restarcie serwera
    print("\n🧹 [4/5] Czyszczenie starych gier botów...")
    try:
        from services.redis_service import RedisService
        redis_service = RedisService()
        await cleanup_stale_bot_games(redis_service)
        print("✅ Stare gry botów wyczyszczone!")
    except Exception as e:
        print(f"⚠️ OSTRZEŻENIE czyszczenie gier: {e}")
    
    # 5. Uruchomienie bot matchmaking
    print("\n🤖 [5/5] Uruchamianie bot matchmaking...")
    try:
        await bot_matchmaking.initialize(redis_service)
        await bot_matchmaking.start()
        print("✅ Bot matchmaking uruchomiony!")
    except Exception as e:
        print(f"⚠️ OSTRZEŻENIE bot matchmaking: {e}")
        # Nie przerywaj startu jeśli bot matchmaking nie działa
    
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
    
    # 1. Zatrzymaj bot matchmaking
    print("\n🤖 [1/3] Zatrzymywanie bot matchmaking...")
    try:
        await bot_matchmaking.stop()
        print("✅ Bot matchmaking zatrzymany!")
    except Exception as e:
        print(f"⚠️ Błąd zatrzymywania bot matchmaking: {e}")
    
    # 2. Zatrzymaj cleanup task
    print("\n🧹 [2/3] Zatrzymywanie cleanup task...")
    try:
        await stop_cleanup()
        print("✅ Cleanup zatrzymany!")
    except Exception as e:
        print(f"⚠️ Błąd zatrzymywania cleanup: {e}")
    
    # 3. Zamknij Redis
    print("\n🔴 [3/3] Zamykanie Redis...")
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
import os
cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
# Dodaj domenę produkcyjną jeśli ustawiona
if os.getenv("CORS_ORIGIN"):
    cors_origins.append(os.getenv("CORS_ORIGIN"))
if os.getenv("CORS_ORIGINS"):  # Wiele domen oddzielonych przecinkiem
    cors_origins.extend(os.getenv("CORS_ORIGINS").split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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

@app.get("/api/health", tags=["🏥 Health"])
@app.get("/health", tags=["🏥 Health"], include_in_schema=False)  # alias
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

@app.get("/api/stats", tags=["📊 Stats"])
async def get_public_stats():
    """
    Publiczne statystyki dla strony głównej
    """
    from services.redis_service import get_redis_client
    from database import async_sessionmaker, User
    from sqlalchemy import select, func
    
    try:
        # Liczba zarejestrowanych użytkowników (bez gości)
        active_players = 0
        total_games = 0
        
        async with async_sessionmaker() as session:
            # Policz użytkowników (nie-gości)
            query = select(func.count()).select_from(User).where(
                ~User.username.like('Guest_%')
            )
            result = await session.execute(query)
            active_players = result.scalar() or 0
        
        # Policz aktywne lobby w Redis
        try:
            redis = get_redis_client()
            # Policz gry zakończone (można też dodać counter w Redis)
            lobby_keys = await redis.keys("lobby:*")
            active_lobbies = len(lobby_keys)
            
            # Total games - można przechowywać w Redis jako counter
            total_games_str = await redis.get("stats:total_games")
            total_games = int(total_games_str) if total_games_str else active_lobbies * 2  # Szacunek
        except:
            total_games = 0
        
        return {
            "activePlayers": active_players,
            "totalGames": total_games,
            "availableGames": 1  # Na razie tylko 66
        }
    except Exception as e:
        return {
            "activePlayers": 0,
            "totalGames": 0,
            "availableGames": 1
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