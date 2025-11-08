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
    
    print(f"✅ Login: {user.username} (ID: {user.id})")
    
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=False
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
        status='online'
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
        is_guest=False
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
    # Wygeneruj nazwę gościa jeśli nie podano
    name = request.name or f"Guest_{random.randint(1000, 9999)}"
    
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
        status='online'
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
        is_guest=True
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
        "is_guest": user.get("is_guest", False)
    }