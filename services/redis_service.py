"""
Service: Redis
Odpowiedzialność: Wszystkie operacje na Redis (save/load game, lobby, etc.)
"""
import json
import cloudpickle
from redis.asyncio import Redis, from_url
from typing import Optional, Dict, Any, List
from config import settings, REDIS_PREFIX_LOBBY, REDIS_PREFIX_GAME, REDIS_PREFIX_USER

# Singleton Redis client
_redis_client: Optional[Redis] = None

async def init_redis() -> Redis:
    """
    Inicjalizuj Redis client (wywoływane przy starcie app)
    
    Returns:
        Redis: Zainicjalizowany client
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            password=settings.REDIS_PASSWORD,
            decode_responses=False  # Dla pickle (binarny)
        )
        await _redis_client.ping()
        print("✅ Redis połączony")
    return _redis_client

def get_redis_client() -> Redis:
    """
    Pobierz Redis client (singleton)
    
    Returns:
        Redis: Redis client
    
    Raises:
        RuntimeError: Jeśli Redis nie został zainicjalizowany
    """
    if _redis_client is None:
        raise RuntimeError("Redis nie został zainicjalizowany. Wywołaj init_redis() przy starcie.")
    return _redis_client

async def close_redis():
    """Zamknij połączenie Redis (wywoływane przy shutdown)"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        print("👋 Redis zamknięty")

# ============================================
# KEY HELPERS
# ============================================

def lobby_key(lobby_id: str) -> str:
    """Klucz Redis dla lobby"""
    return f"{REDIS_PREFIX_LOBBY}{lobby_id}"

def engine_key(game_id: str) -> str:
    """Klucz Redis dla silnika gry"""
    return f"{REDIS_PREFIX_GAME}{game_id}"

def user_key(username: str) -> str:
    """Klucz Redis dla użytkownika"""
    return f"{REDIS_PREFIX_USER}{username}"

# ============================================
# REDIS SERVICE CLASS
# ============================================

class RedisService:
    """Service do operacji Redis"""
    
    def __init__(self):
        self.redis = get_redis_client()
        self.expiration = 86400  # 24 godziny (domyślnie)
    
    # ============================================
    # LOBBY OPERATIONS
    # ============================================
    
    async def save_lobby(self, lobby_id: str, lobby_data: dict) -> bool:
        """
        Zapisz lobby do Redis
        
        Args:
            lobby_id: ID lobby
            lobby_data: Dane lobby (dict)
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            # Usuwamy klucze przejściowe przed zapisem
            clean_data = lobby_data.copy()
            clean_data.pop("timer_task", None)
            clean_data.pop("bot_loop_lock", None)
            
            json_data = json.dumps(clean_data)
            await self.redis.set(
                lobby_key(lobby_id),
                json_data,
                ex=self.expiration
            )
            return True
        except Exception as e:
            print(f"❌ Redis save_lobby error [{lobby_id}]: {e}")
            return False
    
    async def get_lobby(self, lobby_id: str) -> Optional[dict]:
        """
        Pobierz lobby z Redis
        
        Args:
            lobby_id: ID lobby
        
        Returns:
            Optional[dict]: Dane lobby lub None
        """
        try:
            json_data = await self.redis.get(lobby_key(lobby_id))
            if json_data:
                return json.loads(json_data.decode('utf-8'))
            return None
        except Exception as e:
            print(f"❌ Redis get_lobby error [{lobby_id}]: {e}")
            return None
    
    async def list_lobbies(self) -> List[dict]:
        """
        Lista wszystkich lobby
        
        Returns:
            List[dict]: Lista lobby
        """
        try:
            # Pobierz wszystkie klucze lobby:*
            pattern = f"{REDIS_PREFIX_LOBBY}*"
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            # Pobierz dane dla każdego lobby
            lobbies = []
            for key in keys:
                json_data = await self.redis.get(key)
                if json_data:
                    lobby_data = json.loads(json_data.decode('utf-8'))
                    lobbies.append(lobby_data)
            
            return lobbies
        except Exception as e:
            print(f"❌ Redis list_lobbies error: {e}")
            return []
    
    async def delete_lobby(self, lobby_id: str) -> bool:
        """
        Usuń lobby
        
        Args:
            lobby_id: ID lobby
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            await self.redis.delete(lobby_key(lobby_id))
            return True
        except Exception as e:
            print(f"❌ Redis delete_lobby error [{lobby_id}]: {e}")
            return False
    
    # ============================================
    # GAME OPERATIONS
    # ============================================
    
    async def save_game_engine(self, game_id: str, engine: Any) -> bool:
        """
        Zapisz silnik gry do Redis (pickle)
        
        Args:
            game_id: ID gry
            engine: Obiekt silnika gry
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            # Serializacja za pomocą cloudpickle
            pickled_engine = cloudpickle.dumps(engine)
            await self.redis.set(
                engine_key(game_id),
                pickled_engine,
                ex=self.expiration
            )
            return True
        except Exception as e:
            print(f"❌ Redis save_game_engine error [{game_id}]: {e}")
            return False
    
    async def get_game_engine(self, game_id: str) -> Optional[Any]:
        """
        Pobierz silnik gry z Redis
        
        Args:
            game_id: ID gry
        
        Returns:
            Optional[Any]: Engine lub None
        """
        try:
            pickled_engine = await self.redis.get(engine_key(game_id))
            if pickled_engine:
                # Deserializacja za pomocą cloudpickle
                return cloudpickle.loads(pickled_engine)
            return None
        except Exception as e:
            print(f"❌ Redis get_game_engine error [{game_id}]: {e}")
            return None
    
    async def delete_game(self, game_id: str) -> bool:
        """
        Usuń grę (lobby + engine)
        
        Args:
            game_id: ID gry
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            await self.redis.delete(
                lobby_key(game_id),
                engine_key(game_id)
            )
            print(f"🗑️ Usunięto grę {game_id} z Redis")
            return True
        except Exception as e:
            print(f"❌ Redis delete_game error [{game_id}]: {e}")
            return False
    
    # ============================================
    # USER OPERATIONS
    # ============================================
    
    async def save_user(self, username: str, user_data: dict) -> bool:
        """
        Zapisz dane użytkownika
        
        Args:
            username: Username
            user_data: Dane użytkownika (dict)
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            json_data = json.dumps(user_data)
            await self.redis.set(
                user_key(username),
                json_data,
                ex=self.expiration
            )
            return True
        except Exception as e:
            print(f"❌ Redis save_user error [{username}]: {e}")
            return False
    
    async def get_user(self, username: str) -> Optional[dict]:
        """
        Pobierz dane użytkownika
        
        Args:
            username: Username
        
        Returns:
            Optional[dict]: Dane użytkownika lub None
        """
        try:
            json_data = await self.redis.get(user_key(username))
            if json_data:
                return json.loads(json_data.decode('utf-8'))
            return None
        except Exception as e:
            print(f"❌ Redis get_user error [{username}]: {e}")
            return None
    
    async def user_exists(self, username: str) -> bool:
        """
        Sprawdź czy użytkownik istnieje
        
        Args:
            username: Username
        
        Returns:
            bool: True jeśli istnieje
        """
        try:
            return await self.redis.exists(user_key(username)) > 0
        except Exception as e:
            print(f"❌ Redis user_exists error [{username}]: {e}")
            return False
    
    # ============================================
    # RANKING OPERATIONS
    # ============================================
    
    async def get_ranking(self, limit: int = 100) -> List[dict]:
        """
        Pobierz ranking (sorted set)
        
        Args:
            limit: Maksymalna liczba wyników
        
        Returns:
            List[dict]: Lista graczy z ELO
        """
        try:
            # Pobierz top N graczy (sorted by ELO descending)
            results = await self.redis.zrevrange(
                "ranking",
                0,
                limit - 1,
                withscores=True
            )
            
            ranking = []
            for username_bytes, elo in results:
                username = username_bytes.decode('utf-8')
                ranking.append({
                    "username": username,
                    "elo": int(elo)
                })
            
            return ranking
        except Exception as e:
            print(f"❌ Redis get_ranking error: {e}")
            return []
    
    async def update_elo(self, username: str, new_elo: int) -> bool:
        """
        Aktualizuj ELO gracza
        
        Args:
            username: Username
            new_elo: Nowe ELO
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            await self.redis.zadd("ranking", {username: new_elo})
            return True
        except Exception as e:
            print(f"❌ Redis update_elo error [{username}]: {e}")
            return False
    
    async def get_player_elo(self, username: str) -> int:
        """
        Pobierz ELO gracza
        
        Args:
            username: Username
        
        Returns:
            int: ELO (domyślnie 1000 jeśli nie istnieje)
        """
        try:
            elo = await self.redis.zscore("ranking", username)
            return int(elo) if elo else settings.INITIAL_ELO
        except Exception as e:
            print(f"❌ Redis get_player_elo error [{username}]: {e}")
            return settings.INITIAL_ELO