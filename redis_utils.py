# redis_utils.py
"""
Narzędzia do zarządzania stanem rozproszonym w Redis.
Zastępują `transient_game_state` z main.py.
"""

import uuid
import asyncio
import redis.asyncio as aioredis
from typing import Optional


class RedisLock:
    """
    Rozproszony lock używający Redis.
    Umożliwia synchronizację między wieloma serwerami/procesami.
    
    Przykład użycia:
        lock = RedisLock(redis_client, "game:123:bot_loop")
        async with lock:
            # Kod wykonywany z lockiem
            pass
    """
    
    def __init__(
        self, 
        redis_client: aioredis.Redis, 
        lock_key: str, 
        timeout: int = 30,
        retry_delay: float = 0.1
    ):
        """
        Args:
            redis_client: Klient Redis
            lock_key: Klucz dla locka (np. "game:123:bot_loop")
            timeout: Czas wygaśnięcia locka (sekundy) - zabezpieczenie przed deadlock
            retry_delay: Czas oczekiwania między próbami zdobycia locka (sekundy)
        """
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.lock_id = str(uuid.uuid4())  # Unikalny ID dla tego locka
    
    async def acquire(self, blocking: bool = True) -> bool:
        """
        Próbuje zdobyć locka.
        
        Args:
            blocking: Jeśli True, czeka aż lock będzie dostępny.
                     Jeśli False, zwraca False natychmiast jeśli lock jest zajęty.
        
        Returns:
            True jeśli udało się zdobyć locka, False w przeciwnym razie.
        """
        while True:
            # SET lock_key unique_id NX EX timeout
            # NX = set only if not exists
            # EX = expire after timeout seconds
            result = await self.redis_client.set(
                self.lock_key, 
                self.lock_id, 
                nx=True,  # Only set if key doesn't exist
                ex=self.timeout
            )
            
            if result:
                return True  # Lock zdobyty
            
            if not blocking:
                return False  # Lock zajęty, nie czekamy
            
            # Czekaj i spróbuj ponownie
            await asyncio.sleep(self.retry_delay)
    
    async def release(self):
        """
        Zwalnia locka (tylko jeśli należy do nas).
        Używa Lua script dla atomowej operacji sprawdź-i-usuń.
        """
        # Lua script: usuń klucz tylko jeśli wartość się zgadza
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis_client.eval(lua_script, 1, self.lock_key, self.lock_id)
    
    async def extend(self, additional_time: int = None):
        """
        Przedłuża czas wygaśnięcia locka.
        Przydatne dla długotrwałych operacji.
        """
        if additional_time is None:
            additional_time = self.timeout
        
        # Lua script: przedłuż tylko jeśli lock należy do nas
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        await self.redis_client.eval(
            lua_script, 
            1, 
            self.lock_key, 
            self.lock_id,
            additional_time
        )
    
    async def __aenter__(self):
        """Context manager support - acquire lock"""
        await self.acquire(blocking=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager support - release lock"""
        await self.release()


class TimerInfo:
    """
    Struktura przechowująca informacje o timerze w Redis.
    Zastępuje asyncio.Task który nie może być serializowany.
    """
    
    @staticmethod
    def create(player_id: str, remaining_time: float, move_number: int) -> dict:
        """
        Tworzy słownik z informacjami o timerze.
        
        Args:
            player_id: ID gracza, którego dotyczy timer
            remaining_time: Pozostały czas (sekundy)
            move_number: Numer ruchu (do wykrywania zmian tury)
        
        Returns:
            Słownik do zapisania w lobby_data["timer_info"]
        """
        import time
        return {
            "player_id": player_id,
            "deadline_timestamp": time.time() + remaining_time,
            "move_number": move_number,
            "started_at": time.time()
        }
    
    @staticmethod
    def is_expired(timer_info: dict) -> bool:
        """Sprawdza, czy timer wygasł"""
        import time
        if not timer_info:
            return False
        return time.time() >= timer_info.get("deadline_timestamp", float('inf'))
    
    @staticmethod
    def remaining_time(timer_info: dict) -> float:
        """Zwraca pozostały czas (sekundy)"""
        import time
        if not timer_info:
            return 0.0
        remaining = timer_info.get("deadline_timestamp", time.time()) - time.time()
        return max(0.0, remaining)


async def get_or_create_lock(redis_client: aioredis.Redis, lock_key: str) -> RedisLock:
    """
    Helper function do tworzenia locków.
    """
    return RedisLock(redis_client, lock_key, timeout=30)


# ============================================================================
# FUNKCJE POMOCNICZE DLA MIGRACJI
# ============================================================================

async def cleanup_expired_games(redis_client: aioredis.Redis, max_age_seconds: int = 21600):
    """
    Usuwa stare gry z Redis.
    
    Args:
        redis_client: Klient Redis
        max_age_seconds: Maksymalny wiek gry (domyślnie 6 godzin)
    """
    import time
    import json
    
    deleted_count = 0
    
    async for key in redis_client.scan_iter("lobby:*"):
        try:
            lobby_data_json = await redis_client.get(key)
            if not lobby_data_json:
                continue
            
            lobby_data = json.loads(lobby_data_json.decode('utf-8'))
            created_at = lobby_data.get("czas_stworzenia", time.time())
            age = time.time() - created_at
            
            if age > max_age_seconds:
                id_gry = key.decode('utf-8').split(":")[-1]
                # Usuń lobby i silnik
                await redis_client.delete(f"lobby:{id_gry}", f"engine:{id_gry}")
                deleted_count += 1
                print(f"[Cleanup] Usunięto starą grę {id_gry} (wiek: {age/3600:.1f}h)")
        
        except Exception as e:
            print(f"[Cleanup] Błąd podczas sprawdzania gry: {e}")
    
    if deleted_count > 0:
        print(f"[Cleanup] Usunięto {deleted_count} starych gier")


async def get_active_game_count(redis_client: aioredis.Redis) -> int:
    """Zwraca liczbę aktywnych gier w Redis"""
    count = 0
    async for _ in redis_client.scan_iter("lobby:*"):
        count += 1
    return count


async def compress_and_save_engine(redis_client: aioredis.Redis, id_gry: str, engine, expiration: int = 21600):
    """
    Zapisuje silnik gry z kompresją gzip (opcjonalne - dla optymalizacji).
    
    Args:
        redis_client: Klient Redis
        id_gry: ID gry
        engine: Obiekt silnika do zapisania
        expiration: Czas wygaśnięcia (sekundy)
    """
    import cloudpickle
    import gzip
    
    try:
        # Serializuj
        pickled = cloudpickle.dumps(engine)
        
        # Kompresuj (opcjonalne, ale zmniejsza rozmiar ~50%)
        compressed = gzip.compress(pickled, compresslevel=6)
        
        # Zapisz
        await redis_client.set(
            f"engine:{id_gry}",
            compressed,
            ex=expiration
        )
        
        print(f"[Redis] Zapisano silnik {id_gry} ({len(pickled)} -> {len(compressed)} bytes)")
    
    except Exception as e:
        print(f"[Redis] BŁĄD zapisu silnika {id_gry}: {e}")
        raise


async def load_compressed_engine(redis_client: aioredis.Redis, id_gry: str):
    """
    Wczytuje skompresowany silnik gry.
    
    Returns:
        Obiekt silnika lub None jeśli nie znaleziono
    """
    import cloudpickle
    import gzip
    
    try:
        compressed = await redis_client.get(f"engine:{id_gry}")
        if not compressed:
            return None
        
        # Dekompresuj
        pickled = gzip.decompress(compressed)
        
        # Deserializuj
        engine = cloudpickle.loads(pickled)
        
        return engine
    
    except Exception as e:
        print(f"[Redis] BŁĄD odczytu silnika {id_gry}: {e}")
        return None
