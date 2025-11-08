"""
FastAPI Dependencies
Odpowiedzialność: Dependency injection dla routerów
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, AsyncGenerator

from services.redis_service import RedisService, get_redis_client
from services.auth_service import AuthService
from database import async_sessionmaker, User

# ============================================
# SECURITY
# ============================================

security = HTTPBearer()
auth_service = AuthService()

# ============================================
# REDIS DEPENDENCY
# ============================================

async def get_redis() -> RedisService:
    """
    Dependency dla Redis service
    
    Returns:
        RedisService: Redis service instance
    
    Usage:
        @app.get("/endpoint")
        async def endpoint(redis: RedisService = Depends(get_redis)):
            await redis.get_lobby("123")
    """
    return RedisService()

# ============================================
# DATABASE DEPENDENCY
# ============================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency dla database session
    
    Yields:
        AsyncSession: SQLAlchemy async session
    
    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
    """
    async with async_sessionmaker() as session:
        try:
            yield session
        finally:
            await session.close()

# ============================================
# AUTH DEPENDENCIES
# ============================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Pobierz zalogowanego użytkownika z tokena
    
    Args:
        credentials: HTTP Bearer token
        db: Database session
    
    Returns:
        Dict: User info {'id': int, 'username': str, 'email': str, 'is_guest': bool}
    
    Raises:
        HTTPException: 401 jeśli token nieprawidłowy
    
    Usage:
        @app.get("/protected")
        async def protected(user: Dict = Depends(get_current_user)):
            return {"message": f"Hello {user['username']}"}
    """
    token = credentials.credentials
    
    # Pobierz user_id z Redis
    redis_client = get_redis_client()
    user_id_bytes = await redis_client.get(f"token:{token}")
    
    if not user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub wygasły token"
        )
    
    try:
        user_id = int(user_id_bytes.decode('utf-8'))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy token"
        )
    
    # Pobierz użytkownika z bazy
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Użytkownik nie znaleziony"
            )
        
        # Sprawdź czy to gość (goście nie mają hasła)
        is_guest = user.hashed_password is None
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email if hasattr(user, 'email') else None,
            "is_guest": is_guest
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Błąd autentykacji"
        )

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[Dict]:
    """
    Opcjonalna autoryzacja (nie wyrzuca błędu jeśli brak tokena)
    
    Args:
        credentials: HTTP Bearer token (opcjonalny)
        db: Database session
    
    Returns:
        Optional[Dict]: User dict lub None
    
    Usage:
        @app.get("/public-but-can-be-authenticated")
        async def endpoint(user: Optional[Dict] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user['username']}"}
            else:
                return {"message": "Hello guest"}
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

# ============================================
# ROLE-BASED DEPENDENCIES
# ============================================

def require_not_guest(user: Dict = Depends(get_current_user)) -> Dict:
    """
    Wymaga użytkownika który NIE jest gościem
    
    Args:
        user: Current user
    
    Returns:
        Dict: User dict
    
    Raises:
        HTTPException: 403 jeśli gość
    
    Usage:
        @app.post("/ranked-game")
        async def create_ranked(user: Dict = Depends(require_not_guest)):
            # Tylko zarejestrowani użytkownicy
            pass
    """
    if user.get("is_guest", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Goście nie mają dostępu do tej funkcji"
        )
    return user

# ============================================
# LOBBY/GAME OWNERSHIP DEPENDENCIES
# ============================================

async def verify_lobby_host(
    lobby_id: str,
    user: Dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
) -> Dict:
    """
    Sprawdź czy użytkownik jest hostem lobby
    
    Args:
        lobby_id: ID lobby
        user: Current user
        redis: Redis service
    
    Returns:
        Dict: User dict
    
    Raises:
        HTTPException: 403 jeśli nie jest hostem, 404 jeśli lobby nie istnieje
    
    Usage:
        @app.post("/lobby/{lobby_id}/start")
        async def start_game(
            lobby_id: str,
            user: Dict = Depends(verify_lobby_host)
        ):
            # Tylko host może rozpocząć grę
            pass
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    if lobby_data.get("host") != user["username"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko host może wykonać tę akcję"
        )
    
    return user

# ============================================
# HELPERS
# ============================================

def get_user_id(user: Dict = Depends(get_current_user)) -> int:
    """
    Pobierz tylko user_id (helper)
    
    Args:
        user: Current user
    
    Returns:
        int: User ID
    
    Usage:
        @app.get("/my-stats")
        async def my_stats(user_id: int = Depends(get_user_id)):
            return {"user_id": user_id}
    """
    return user["id"]

def get_username(user: Dict = Depends(get_current_user)) -> str:
    """
    Pobierz tylko username (helper)
    
    Args:
        user: Current user
    
    Returns:
        str: Username
    
    Usage:
        @app.get("/my-profile")
        async def my_profile(username: str = Depends(get_username)):
            return {"username": username}
    """
    return user["username"]