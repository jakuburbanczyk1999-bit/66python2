"""
Konfiguracja aplikacji
Odpowiedzialność: Wszystkie stałe, ustawienia Redis, JWT, etc.
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Ustawienia aplikacji"""
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Game settings
    MAX_PLAYERS: int = 4
    MAX_LOBBY_AGE_HOURS: int = 24
    GAME_TIMEOUT_MINUTES: int = 60
    
    # Ranking
    INITIAL_ELO: int = 1000
    K_FACTOR: int = 32
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Singleton
settings = Settings()

# Redis keys prefixes
REDIS_PREFIX_LOBBY = "lobby:"
REDIS_PREFIX_GAME = "game:"
REDIS_PREFIX_USER = "user:"
REDIS_PREFIX_RANKING = "ranking:"
