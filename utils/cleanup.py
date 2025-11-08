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
    Uruchamiany co 5 minut
    """
    redis = RedisService()
    
    while True:
        try:
            await asyncio.sleep(300)  # 5 minut
            
            print("[Cleanup] Rozpoczynam czyszczenie starych gier...")
            
            # Pobierz wszystkie lobby
            lobbies = await redis.list_lobbies()
            
            current_time = time.time()
            max_age = settings.MAX_LOBBY_AGE_HOURS * 3600  # Godziny -> sekundy
            
            cleaned = 0
            
            for lobby in lobbies:
                lobby_id = lobby.get('id_gry')
                created_at = lobby.get('created_at', 0)
                status = lobby.get('status_partii', 'UNKNOWN')
                
                # Oblicz wiek lobby
                age = current_time - created_at
                
                # Usuń jeśli:
                # 1. Starsze niż MAX_LOBBY_AGE_HOURS
                # 2. Status ZAKONCZONA i starsze niż 1h
                should_delete = False
                
                if age > max_age:
                    should_delete = True
                    reason = f"stare ({age/3600:.1f}h)"
                elif status == 'ZAKONCZONA' and age > 3600:
                    should_delete = True
                    reason = "zakończone > 1h"
                
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