"""
Utils: Cleanup
Odpowiedzialność: Garbage collector - czyszczenie starych lobby/gier
"""
import asyncio
import time
from typing import Optional

from services.redis_service import RedisService
from config import settings

# ============================================
# CLEANUP TASK
# ============================================

cleanup_task: Optional[asyncio.Task] = None

async def cleanup_old_games():
    """
    Periodic task - czyści stare gry/lobby
    Uruchamiany co 2 minuty
    """
    redis = RedisService()
    
    while True:
        try:
            await asyncio.sleep(120)  # 2 minuty
            
            print("[Cleanup] Rozpoczynam czyszczenie starych gier...")
            
            # Pobierz wszystkie lobby
            lobbies = await redis.list_lobbies()
            
            current_time = time.time()
            max_age = settings.MAX_LOBBY_AGE_HOURS * 3600  # Godziny -> sekundy
            lobby_idle_timeout = 1800  # 30 minut bez aktywności dla LOBBY
            game_idle_timeout = 3600   # 1 godzina dla gier W_GRZE
            
            cleaned = 0
            inactive_kicked = 0
            
            for lobby in lobbies:
                lobby_id = lobby.get('id_gry')
                created_at = lobby.get('created_at', 0)
                status = lobby.get('status_partii', 'UNKNOWN')
                last_activity = lobby.get('last_activity', created_at)
                slots = lobby.get('slots', [])
                
                # Oblicz wiek lobby i czas nieaktywności
                age = current_time - created_at
                idle_time = current_time - last_activity
                
                # Sprawdź czy są prawdziwi gracze (nie boty)
                real_players = sum(1 for s in slots if s.get('typ') == 'gracz' and s.get('nazwa'))
                
                # Usuń jeśli:
                should_delete = False
                reason = ""
                
                # 1. Starsze niż MAX_LOBBY_AGE_HOURS
                if age > max_age:
                    should_delete = True
                    reason = f"stare ({age/3600:.1f}h)"
                
                # 2. Status ZAKONCZONA i starsze niż 10 min
                elif status == 'ZAKONCZONA' and age > 600:
                    should_delete = True
                    reason = "zakończone > 10min"
                
                # 3. LOBBY bez graczy (same boty lub puste) przez 5 min
                elif status == 'LOBBY' and real_players == 0 and idle_time > 300:
                    should_delete = True
                    reason = "puste lobby > 5min"
                
                # 4. LOBBY nieaktywne przez 30 min
                elif status == 'LOBBY' and idle_time > lobby_idle_timeout:
                    should_delete = True
                    reason = f"nieaktywne lobby ({idle_time/60:.0f}min)"
                
                # 5. Gra W_GRZE nieaktywna przez 1h (prawdopodobnie bug)
                elif status in ['W_GRZE', 'W_TRAKCIE'] and idle_time > game_idle_timeout:
                    should_delete = True
                    reason = f"nieaktywna gra ({idle_time/60:.0f}min)"
                
                if should_delete:
                    # Usuń lobby i silnik
                    await redis.delete_game(lobby_id)
                    cleaned += 1
                    print(f"[Cleanup] Usunięto lobby {lobby_id} ({reason})")
            
            if cleaned > 0:
                print(f"[Cleanup] Wyczyszczono {cleaned} starych gier")
            else:
                print("[Cleanup] Brak gier do wyczyszczenia")
        
        except Exception as e:
            print(f"[Cleanup] Błąd: {e}")
            import traceback
            traceback.print_exc()

def setup_periodic_cleanup():
    """
    Uruchom periodic cleanup task
    Wywoływane w main.py przy startup
    """
    global cleanup_task
    
    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(cleanup_old_games())
        print("✅ Cleanup task uruchomiony")
    else:
        print("⚠️ Cleanup task już działa")

async def stop_cleanup():
    """
    Zatrzymaj cleanup task
    Wywoływane w main.py przy shutdown
    """
    global cleanup_task
    
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        print("👋 Cleanup task zatrzymany")

# ============================================
# CLEANUP INACTIVE USERS
# ============================================

inactive_users_task: Optional[asyncio.Task] = None

async def cleanup_inactive_users():
    """
    Periodic task - ustawia offline użytkowników bez heartbeat
    Uruchamiany co 2 minuty
    """
    from services.redis_service import RedisService
    from database import async_sessionmaker, User
    from sqlalchemy import select, update
    
    while True:
        try:
            await asyncio.sleep(120)  # 2 minuty
            
            redis = RedisService()
            
            async with async_sessionmaker() as session:
                # Pobierz wszystkich online userów
                result = await session.execute(
                    select(User).where(User.status == 'online')
                )
                online_users = result.scalars().all()
                
                offline_count = 0
                
                for user in online_users:
                    # Sprawdź czy ma aktywny heartbeat w Redis
                    heartbeat = await redis.redis.get(f"heartbeat:{user.id}")
                    
                    if not heartbeat:
                        # Brak heartbeat - ustaw offline
                        user.status = 'offline'
                        offline_count += 1
                
                if offline_count > 0:
                    await session.commit()
                    print(f"[📴 Cleanup] Ustawiono {offline_count} użytkowników na offline")
        
        except Exception as e:
            print(f"[Cleanup Users] Błąd: {e}")
            import traceback
            traceback.print_exc()

def setup_inactive_users_cleanup():
    """
    Uruchom cleanup inactive users task
    """
    global inactive_users_task
    
    if inactive_users_task is None or inactive_users_task.done():
        inactive_users_task = asyncio.create_task(cleanup_inactive_users())
        print("✅ Inactive users cleanup task uruchomiony")

async def stop_inactive_users_cleanup():
    """
    Zatrzymaj inactive users cleanup task
    """
    global inactive_users_task
    
    if inactive_users_task and not inactive_users_task.done():
        inactive_users_task.cancel()
        try:
            await inactive_users_task
        except asyncio.CancelledError:
            pass
        print("👋 Inactive users cleanup task zatrzymany")

# ============================================
# MANUAL CLEANUP
# ============================================

async def cleanup_specific_game(game_id: str) -> bool:
    """
    Ręcznie wyczyść konkretną grę
    
    Args:
        game_id: ID gry do usunięcia
    
    Returns:
        bool: True jeśli sukces
    """
    try:
        redis = RedisService()
        await redis.delete_game(game_id)
        print(f"[Cleanup] Ręcznie usunięto grę {game_id}")
        return True
    except Exception as e:
        print(f"[Cleanup] Błąd usuwania gry {game_id}: {e}")
        return False

async def cleanup_disconnected_players():
    """
    Znajdź i zamień rozłączonych graczy na boty
    (Opcjonalna funkcja - do rozszerzenia)
    """
    # TODO: Implementacja jeśli potrzebna
    pass

# ============================================
# STATS
# ============================================

async def get_cleanup_stats() -> dict:
    """
    Statystyki cleanup
    
    Returns:
        dict: Statystyki
    """
    redis = RedisService()
    lobbies = await redis.list_lobbies()
    
    current_time = time.time()
    
    stats = {
        'total_lobbies': len(lobbies),
        'by_status': {},
        'old_lobbies': 0,
        'active_games': 0
    }
    
    for lobby in lobbies:
        status = lobby.get('status_partii', 'UNKNOWN')
        created_at = lobby.get('created_at', 0)
        age_hours = (current_time - created_at) / 3600
        
        # Count by status
        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        # Count old
        if age_hours > settings.MAX_LOBBY_AGE_HOURS:
            stats['old_lobbies'] += 1
        
        # Count active
        if status in ['W_GRZE', 'W_TRAKCIE', 'IN_PROGRESS']:
            stats['active_games'] += 1
    
    return stats