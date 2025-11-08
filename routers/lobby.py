"""
Router: Lobby
Odpowiedzialność: Tworzenie, join, ready, kick, start gry
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import time

from services.redis_service import RedisService
from services.game_service import GameService
from dependencies import get_current_user, get_redis

# ============================================
# PYDANTIC MODELS
# ============================================

class LobbyCreateRequest(BaseModel):
    """Request do stworzenia lobby"""
    lobby_type: str = "66"
    player_count: int = 4
    ranked: bool = False
    password: Optional[str] = None

# ============================================
# ROUTER
# ============================================

router = APIRouter()
game_service = GameService()

# ============================================
# LIST LOBBIES
# ============================================

@router.get("/list")
async def list_lobbies(redis: RedisService = Depends(get_redis)):
    """
    Lista wszystkich dostępnych lobby
    
    Returns:
        dict: Lista lobby
    """
    lobbies = await redis.list_lobbies()
    
    # Filtruj tylko lobby w statusie LOBBY (nie w grze)
    available_lobbies = [
        lobby for lobby in lobbies
        if lobby.get("status_partii") == "LOBBY"
    ]
    
    # Zwróć listę bezpośrednio (kompatybilność z frontendem)
    return available_lobbies

# ============================================
# CREATE LOBBY
# ============================================

@router.post("/create")
async def create_lobby(
    request: LobbyCreateRequest,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Stwórz nowe lobby
    
    Args:
        request: Parametry lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Dane lobby
    
    Raises:
        HTTPException: 400 jeśli nieprawidłowe parametry
    """
    # Walidacja
    if request.player_count not in [3, 4]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liczba graczy musi być 3 lub 4"
        )
    
    # Wygeneruj ID
    game_id = str(uuid.uuid4())[:8]
    
    # Stwórz sloty
    slots = []
    for i in range(request.player_count):
        if i == 0:
            # Pierwszy slot = Host
            slots.append({
                'numer_gracza': i,
                'typ': 'gracz',
                'id_uzytkownika': current_user['id'],
                'nazwa': current_user['username'],
                'is_host': True,
                'ready': False,
                'avatar_url': 'default_avatar.png'
            })
        else:
            # Pozostałe = puste
            slots.append({
                'numer_gracza': i,
                'typ': 'pusty',
                'id_uzytkownika': None,
                'nazwa': None,
                'is_host': False,
                'ready': False,
                'avatar_url': None
            })
    
    # Dane lobby
    lobby_data = {
        "id_gry": game_id,
        "id": f"Lobby_{game_id[:4]}",
        "max_graczy": request.player_count,
        "status_partii": "LOBBY",
        "slots": slots,
        "opcje": {
            "tryb_gry": f"{request.player_count}p",
            "rankingowa": request.ranked,
            "typ_gry": request.lobby_type,
            "haslo": request.password
        },
        "host_id": current_user['id'],
        "tryb_lobby": "online",
        "kicked_players": [],
        "created_at": time.time()
    }
    
    # Zapisz w Redis
    await redis.save_lobby(game_id, lobby_data)
    
    print(f"✅ Lobby utworzone: {game_id} przez {current_user['username']}")
    
    return lobby_data

# ============================================
# GET LOBBY DETAILS
# ============================================

@router.get("/{lobby_id}")
async def get_lobby_details(
    lobby_id: str,
    redis: RedisService = Depends(get_redis)
):
    """
    Pobierz szczegóły lobby
    
    Args:
        lobby_id: ID lobby
        redis: Redis service
    
    Returns:
        dict: Dane lobby
    
    Raises:
        HTTPException: 404 jeśli lobby nie istnieje
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    return lobby_data

# ============================================
# JOIN LOBBY
# ============================================

@router.post("/{lobby_id}/join")
async def join_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Dołącz do lobby
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/404 jeśli nie można dołączyć
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Sprawdź czy gracz nie jest wyrzucony
    if current_user['id'] in lobby_data.get('kicked_players', []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zostałeś wyrzucony z tego lobby"
        )
    
    # Sprawdź czy lobby jest pełne
    slots = lobby_data.get('slots', [])
    empty_slot = None
    for slot in slots:
        if slot['typ'] == 'pusty':
            empty_slot = slot
            break
    
    if not empty_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lobby jest pełne"
        )
    
    # Zajmij slot
    empty_slot['typ'] = 'gracz'
    empty_slot['id_uzytkownika'] = current_user['id']
    empty_slot['nazwa'] = current_user['username']
    empty_slot['ready'] = False
    empty_slot['avatar_url'] = 'default_avatar.png'
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    print(f"✅ {current_user['username']} dołączył do lobby {lobby_id}")
    
    return lobby_data

# ============================================
# LEAVE LOBBY
# ============================================

@router.post("/{lobby_id}/leave")
async def leave_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Opuść lobby
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: 404 jeśli lobby nie istnieje
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Znajdź slot gracza
    slots = lobby_data.get('slots', [])
    player_slot = None
    for slot in slots:
        if slot.get('id_uzytkownika') == current_user['id']:
            player_slot = slot
            break
    
    if not player_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie jesteś w tym lobby"
        )
    
    # Jeśli to host, usuń lobby
    if player_slot.get('is_host'):
        await redis.delete_lobby(lobby_id)
        print(f"✅ Host {current_user['username']} opuścił lobby {lobby_id} - lobby usunięte")
        return {"success": True, "message": "Lobby usunięte"}
    
    # Opróżnij slot
    player_slot['typ'] = 'pusty'
    player_slot['id_uzytkownika'] = None
    player_slot['nazwa'] = None
    player_slot['ready'] = False
    player_slot['avatar_url'] = None
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    print(f"✅ {current_user['username']} opuścił lobby {lobby_id}")
    
    return {"success": True, "message": "Opuszczono lobby"}

# Kontynuacja w następnym bloku...

# ============================================
# TOGGLE READY
# ============================================

@router.post("/{lobby_id}/ready")
async def toggle_ready(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Zmień status gotowości
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Znajdź slot gracza
    slots = lobby_data.get('slots', [])
    player_slot = None
    for slot in slots:
        if slot.get('id_uzytkownika') == current_user['id']:
            player_slot = slot
            break
    
    if not player_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie jesteś w tym lobby"
        )
    
    # Toggle ready
    player_slot['ready'] = not player_slot.get('ready', False)
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    print(f"✅ {current_user['username']} zmienił ready na {player_slot['ready']}")
    
    return lobby_data

# ============================================
# KICK PLAYER
# ============================================

@router.post("/{lobby_id}/kick/{user_id}")
async def kick_player(
    lobby_id: str,
    user_id: int,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Wyrzuć gracza (tylko host)
    
    Args:
        lobby_id: ID lobby
        user_id: ID gracza do wyrzucenia
        current_user: Zalogowany użytkownik (musi być hostem)
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 403 jeśli nie jesteś hostem, 404 jeśli lobby/gracz nie istnieje
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Sprawdź czy jest hostem
    if lobby_data.get('host_id') != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko host może wyrzucać graczy"
        )
    
    # Znajdź slot gracza
    slots = lobby_data.get('slots', [])
    player_slot = None
    for slot in slots:
        if slot.get('id_uzytkownika') == user_id:
            player_slot = slot
            break
    
    if not player_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gracz nie znaleziony w lobby"
        )
    
    # Dodaj do listy wyrzuconych
    if 'kicked_players' not in lobby_data:
        lobby_data['kicked_players'] = []
    lobby_data['kicked_players'].append(user_id)
    
    # Opróżnij slot
    player_name = player_slot['nazwa']
    player_slot['typ'] = 'pusty'
    player_slot['id_uzytkownika'] = None
    player_slot['nazwa'] = None
    player_slot['ready'] = False
    player_slot['avatar_url'] = None
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    print(f"✅ Host wyrzucił gracza {player_name} z lobby {lobby_id}")
    
    return lobby_data

# ============================================
# ADD BOT
# ============================================

@router.post("/{lobby_id}/add-bot")
async def add_bot(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Dodaj bota do lobby
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/404 jeśli nie można dodać bota
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Znajdź pusty slot
    slots = lobby_data.get('slots', [])
    empty_slot = None
    for slot in slots:
        if slot['typ'] == 'pusty':
            empty_slot = slot
            break
    
    if not empty_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brak wolnych slotów"
        )
    
    # Znajdź numer dla bota
    bot_numbers = []
    for slot in slots:
        if slot.get('typ') == 'bot' and slot.get('nazwa'):
            # Wyciągnij numer z "Bot #X"
            try:
                num = int(slot['nazwa'].split('#')[1])
                bot_numbers.append(num)
            except:
                pass
    
    next_bot_num = 1
    while next_bot_num in bot_numbers:
        next_bot_num += 1
    
    # Dodaj bota
    empty_slot['typ'] = 'bot'
    empty_slot['nazwa'] = f"Bot #{next_bot_num}"
    empty_slot['ready'] = True  # Boty zawsze gotowe
    empty_slot['avatar_url'] = 'bot_avatar.png'
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    print(f"✅ Dodano bota Bot #{next_bot_num} do lobby {lobby_id}")
    
    return lobby_data

# ============================================
# START GAME
# ============================================

@router.post("/{lobby_id}/start")
async def start_game(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Rozpocznij grę (tylko host)
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik (musi być hostem)
        redis: Redis service
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: 400/403 jeśli nie można rozpocząć
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Waliduj start gry
    can_start, error = await game_service.validate_game_start(lobby_data, current_user['id'])
    if not can_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Zmień status na W_GRZE
    lobby_data['status_partii'] = 'W_GRZE'
    await redis.save_lobby(lobby_id, lobby_data)
    
    # Inicjalizuj silnik gry
    engine = await game_service.initialize_game(lobby_id, lobby_data, redis)
    
    print(f"✅ Gra rozpoczęta w lobby {lobby_id}")
    
    return {
        "success": True,
        "message": "Gra rozpoczęta",
        "game_id": lobby_id,
        "phase": engine.game_state.faza.name if hasattr(engine.game_state, 'faza') else 'UNKNOWN'
    }

# ============================================
# DELETE LOBBY
# ============================================

@router.delete("/{lobby_id}")
async def delete_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Usuń lobby (tylko host)
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik (musi być hostem)
        redis: Redis service
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: 403 jeśli nie jesteś hostem, 404 jeśli lobby nie istnieje
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Sprawdź czy jest hostem
    if lobby_data.get('host_id') != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko host może usunąć lobby"
        )
    
    # Usuń
    await redis.delete_lobby(lobby_id)
    
    print(f"✅ Lobby {lobby_id} usunięte przez hosta")
    
    return {"success": True, "message": "Lobby usunięte"}

# ============================================
# CLEANUP (Internal)
# ============================================

@router.post("/{lobby_id}/cleanup")
async def cleanup_lobby(
    lobby_id: str,
    redis: RedisService = Depends(get_redis)
):
    """
    Cleanup lobby (internal endpoint)
    
    Args:
        lobby_id: ID lobby
        redis: Redis service
    
    Returns:
        dict: Success message
    """
    await redis.delete_lobby(lobby_id)
    return {"success": True, "message": "Lobby wyczyszczone"}