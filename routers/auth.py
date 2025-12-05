"""
Router: Autentykacja
Odpowiedzialność: Login, register, guest login, logout
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import random

from services.auth_service import AuthService
from services.redis_service import RedisService, get_redis_client
from dependencies import get_db, get_current_user
from database import User

# ============================================
# PYDANTIC MODELS
# ============================================

class LoginRequest(BaseModel):
    """Request do logowania"""
    username: str
    password: str

class RegisterRequest(BaseModel):
    """Request do rejestracji"""
    username: str
    password: str

class GuestRequest(BaseModel):
    """Request do logowania jako gość"""
    name: Optional[str] = None

class AuthResponse(BaseModel):
    """Response po logowaniu/rejestracji"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    is_guest: bool = False
    is_admin: bool = False  # ← DODANE!

# ============================================
# ROUTER
# ============================================

router = APIRouter()
auth_service = AuthService()

# ============================================
# LOGIN
# ============================================

@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Logowanie użytkownika
    
    Args:
        request: Username i password
        db: Database session
    
    Returns:
        AuthResponse: Token + user info
    
    Raises:
        HTTPException: 401 jeśli dane nieprawidłowe
    """
    # Pobierz użytkownika z bazy
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowe dane logowania"
        )
    
    # Sprawdź czy to nie jest gość (goście nie mają hasła)
    if user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Konto gościa - użyj logowania gościa"
        )
    
    # Sprawdź hasło
    if not auth_service.verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowe dane logowania"
        )
    
    # Wygeneruj token i zapisz w Redis
    token = auth_service.generate_token()
    redis_client = get_redis_client()
    await redis_client.set(f"token:{token}", str(user.id), ex=86400)  # 24h
    
    # Ustaw status na online
    user.status = 'online'
    await db.commit()
    
    print(f"✅ Login: {user.username} (ID: {user.id}, Admin: {user.is_admin})")
    
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=False,
        is_admin=user.is_admin  # ← POPRAWIONE!
    )

# ============================================
# REGISTER
# ============================================

@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Rejestracja nowego użytkownika
    
    Args:
        request: Username i password
        db: Database session
    
    Returns:
        AuthResponse: Token + user info
    
    Raises:
        HTTPException: 400 jeśli walidacja nie przeszła lub użytkownik istnieje
    """
    # Walidacja username
    is_valid, error = auth_service.validate_username(request.username)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Walidacja password
    is_valid, error = auth_service.validate_password(request.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Sprawdź czy użytkownik już istnieje
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nazwa użytkownika zajęta"
        )
    
    # Stwórz użytkownika
    user = User(
        username=request.username,
        hashed_password=auth_service.hash_password(request.password),
        status='online',
        is_admin=False  # Nowi użytkownicy nie są adminami
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Wygeneruj token i zapisz w Redis
    token = auth_service.generate_token()
    redis_client = get_redis_client()
    await redis_client.set(f"token:{token}", str(user.id), ex=86400)  # 24h
    
    print(f"✅ Rejestracja: {user.username} (ID: {user.id})")
    
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=False,
        is_admin=False  # ← DODANE!
    )

# ============================================
# GUEST LOGIN
# ============================================

@router.post("/guest", response_model=AuthResponse)
async def guest_login(
    request: GuestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Logowanie jako gość (bez hasła)
    
    Args:
        request: Opcjonalna nazwa gościa
        db: Database session
    
    Returns:
        AuthResponse: Token + guest info
    """
    # Wygeneruj nazwę gościa jeśli nie podano lub pusta
    name = (request.name and request.name.strip()) or f"Guest_{random.randint(1000, 9999)}"
    
    # Sprawdź czy nazwa jest zajęta (dla gości dodaj sufiks jeśli zajęta)
    result = await db.execute(
        select(User).where(User.username == name)
    )
    if result.scalar_one_or_none():
        name = f"{name}_{random.randint(100, 999)}"
    
    # Stwórz gościa (hashed_password = NULL oznacza gościa)
    user = User(
        username=name,
        hashed_password=None,  # NULL = gość
        status='online',
        is_admin=False  # Goście nie są adminami
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Wygeneruj token i zapisz w Redis
    token = auth_service.generate_token()
    redis_client = get_redis_client()
    await redis_client.set(f"token:{token}", str(user.id), ex=86400)  # 24h
    
    print(f"✅ Gość: {user.username} (ID: {user.id})")
    
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=True,
        is_admin=False  # ← DODANE!
    )

# ============================================
# LOGOUT
# ============================================

@router.post("/logout")
async def logout(
    user: dict = Depends(get_current_user)
):
    """
    Wylogowanie użytkownika (usunięcie tokena z Redis)
    
    Args:
        user: Current user (z dependency)
    
    Returns:
        dict: Success message
    """
    # Token jest w credentials, ale nie mamy go tutaj bezpośrednio
    # Musimy go wyciągnąć z Redis lub zapisać podczas get_current_user
    # Na razie zwróćmy sukces (token wygaśnie po 24h)
    
    print(f"✅ Logout: {user['username']} (ID: {user['id']})")
    
    return {
        "success": True,
        "message": "Wylogowano pomyślnie"
    }

# ============================================
# OFFLINE (przy zamknięciu karty)
# ============================================

class OfflineRequest(BaseModel):
    """Request do ustawienia statusu offline"""
    token: str

@router.post("/offline")
async def set_offline(
    request: OfflineRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ustaw status użytkownika na offline (wywoływane przez sendBeacon)
    
    Args:
        request: Token użytkownika
        db: Database session
    
    Returns:
        dict: Success message
    """
    try:
        # Znajdź user_id po tokenie
        redis_client = get_redis_client()
        user_id_str = await redis_client.get(f"token:{request.token}")
        
        if not user_id_str:
            return {"success": False, "message": "Token nie znaleziony"}
        
        user_id = int(user_id_str)
        
        # Ustaw status na offline
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.status = 'offline'
            await db.commit()
            print(f"📴 Offline: {user.username} (ID: {user.id})")
        
        return {"success": True, "message": "Status ustawiony na offline"}
        
    except Exception as e:
        print(f"❌ Błąd set_offline: {e}")
        return {"success": False, "message": str(e)}

# ============================================
# HEARTBEAT (utrzymanie statusu online)
# ============================================

@router.post("/heartbeat")
async def heartbeat(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Heartbeat - utrzymuje status online i aktualizuje last_seen w Redis
    
    Args:
        user: Current user (z dependency)
        db: Database session
    
    Returns:
        dict: Success message
    """
    try:
        # Zapisz timestamp heartbeat w Redis (wygasa po 3 min)
        redis_client = get_redis_client()
        await redis_client.set(f"heartbeat:{user['id']}", "1", ex=180)  # 3 minuty
        
        # Aktualizuj status w bazie na online
        result = await db.execute(
            select(User).where(User.id == user['id'])
        )
        db_user = result.scalar_one_or_none()
        
        if db_user and db_user.status != 'online':
            db_user.status = 'online'
            await db.commit()
        
        return {"success": True}
        
    except Exception as e:
        print(f"❌ Błąd heartbeat: {e}")
        return {"success": False}

# ============================================
# ME (Current user info)
# ============================================

@router.get("/me")
async def get_me(
    user: dict = Depends(get_current_user)
):
    """
    Pobierz informacje o zalogowanym użytkowniku
    
    Args:
        user: Current user (z dependency)
    
    Returns:
        dict: User info
    """
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "is_guest": user.get("is_guest", False),
        "is_admin": user.get("is_admin", False)  # ← DODANE!
    }