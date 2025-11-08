"""
Pydantic models dla API
Odpowiedzialność: Request/Response schemas
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# ============================================
# AUTH MODELS
# ============================================

class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    token_type: str = "bearer"

class AuthResponse(BaseModel):
    """Odpowiedź po logowaniu/rejestracji"""
    access_token: str
    token_type: str = "bearer"
    username: str
    email: Optional[str] = None
    is_guest: bool = False

class UserRegister(BaseModel):
    """Request do rejestracji"""
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    """Request do logowania"""
    username: str
    password: str

class GuestLogin(BaseModel):
    """Request do logowania jako gość"""
    guest_name: str

# ============================================
# LOBBY MODELS
# ============================================

class LobbyCreate(BaseModel):
    """Request do stworzenia lobby"""
    max_players: int = 4
    is_ranked: bool = False

class LobbyInfo(BaseModel):
    """Informacje o lobby"""
    lobby_id: str
    host: str
    players: List[Dict[str, Any]]
    max_players: int
    is_ranked: bool
    created_at: datetime
    status: str

class LobbyList(BaseModel):
    """Lista dostępnych lobby"""
    lobbies: List[LobbyInfo]

# ============================================
# GAME MODELS
# ============================================

class GameState(BaseModel):
    """Stan gry (uproszczony dla API)"""
    faza: str
    kolej_gracza: Optional[str]
    gracz_grajacy: Optional[str]
    kontrakt: Optional[Dict[str, Any]]
    punkty_meczu: Dict[str, int]
    # ... więcej pól według potrzeb

class GameAction(BaseModel):
    """Akcja gracza"""
    typ: str
    # Dynamiczne pola zależne od typu akcji
    # np. karta, kontrakt, atut, etc.
    
    class Config:
        extra = "allow"  # Pozwól na dodatkowe pola

# ============================================
# WEBSOCKET MODELS
# ============================================

class WSMessage(BaseModel):
    """Wiadomość WebSocket"""
    type: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
