"""
Router: Lobby
Odpowiedzialność: Tworzenie, join, ready, kick, start gry, change slot, chat
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import time
import json
import asyncio
import random

from services.redis_service import RedisService
from services.game_service import GameService
from dependencies import get_current_user, get_redis
from database import async_sessionmaker, User
from sqlalchemy import select

# ============================================
# PYDANTIC MODELS
# ============================================

class LobbyCreateRequest(BaseModel):
    """Request do stworzenia lobby"""
    nazwa: str = "Unnamed Game"      
    typ_gry: str = "66"              # "66" lub "tysiac"
    max_graczy: int = 4              # 2, 3 lub 4 (dla tysiąca też 2, 3, 4)
    rankingowa: bool = False         
    haslo: Optional[str] = None      

class ChatMessageRequest(BaseModel):
    """Request do wysłania wiadomości"""
    message: str

# ============================================
# ROUTER
# ============================================

router = APIRouter()
game_service = GameService()

# ============================================
# HELPER - Delayed Bot Ready (background task)
# ============================================

async def _delayed_bot_ready(lobby_id: str, bot_name: str, redis: RedisService):
    """
    Po opóźnieniu 2-5s, daj gotowość botowi.
    Uruchamiane w tle.
    """
    delay = random.uniform(2.0, 5.0)
    await asyncio.sleep(delay)
    
    try:
        # Pobierz świeże dane lobby
        lobby_data = await redis.get_lobby(lobby_id)
        if not lobby_data or lobby_data.get('status_partii') != 'LOBBY':
            return  # Lobby zniknęło lub gra wystartowała
        
        # Znajdź slot bota i daj gotowość
        for slot in lobby_data.get('slots', []):
            if slot.get('nazwa') == bot_name:
                slot['ready'] = True
                break
        else:
            return  # Bot nie znaleziony (został usunięty?)
        
        # Zapisz
        await redis.save_lobby(lobby_id, lobby_data)
        
        # System message
        await send_system_message(lobby_id, f"{bot_name} jest gotowy", redis)
        
        print(f"✅ Bot {bot_name} jest gotowy w lobby {lobby_id}")
        
    except Exception as e:
        print(f"❌ Błąd delayed_bot_ready: {e}")

# ============================================
# HELPER - Update Last Activity
# ============================================

async def update_last_activity(lobby_id: str, lobby_data: dict, redis: RedisService):
    """
    Aktualizuj timestamp ostatniej aktywności w lobby
    
    Args:
        lobby_id: ID lobby
        lobby_data: Dane lobby
        redis: Redis service
    """
    lobby_data['last_activity'] = time.time()
    await redis.save_lobby(lobby_id, lobby_data)

# ============================================
# HELPER - Send System Message
# ============================================

async def send_system_message(lobby_id: str, message: str, redis: RedisService):
    """
    Wyślij wiadomość systemową do czatu
    
    Args:
        lobby_id: ID lobby
        message: Treść wiadomości systemowej
        redis: Redis service
    """
    chat_message = {
        "id": int(time.time() * 1000),
        "user_id": None,
        "username": "System",
        "message": message,
        "timestamp": time.time(),
        "is_system": True
    }
    
    chat_key = f"lobby:{lobby_id}:chat"
    await redis.redis.rpush(chat_key, json.dumps(chat_message))
    await redis.redis.ltrim(chat_key, -100, -1)
    await redis.redis.expire(chat_key, 86400)
    
    print(f"📢 [SYSTEM] [{lobby_id}] {message}")

# ============================================
# LIST LOBBIES
# ============================================

@router.get("/list")
async def list_lobbies(redis: RedisService = Depends(get_redis)):
    """
    Lista wszystkich dostępnych lobby (w lobby i w grze)
    
    Returns:
        dict: Lista lobby
    """
    lobbies = await redis.list_lobbies()
    
    # Filtruj lobby w statusie LOBBY lub W_GRZE (nie zakończone)
    available_lobbies = [
        lobby for lobby in lobbies
        if lobby.get("status_partii") in ["LOBBY", "W_GRZE", "W_TRAKCIE"]
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
    if request.typ_gry == 'tysiac':
        if request.max_graczy not in [2, 3, 4]:  
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Liczba graczy w Tysiącu musi być 2, 3 lub 4"
            )
    else:  # 66
        if request.max_graczy not in [3, 4]:  
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Liczba graczy w 66 musi być 3 lub 4"
            )
    
    # Wygeneruj ID
    game_id = str(uuid.uuid4())[:8]
    
    # Stwórz sloty
    slots = []
    for i in range(request.max_graczy):  
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
        "nazwa": request.nazwa,          
        "max_graczy": request.max_graczy,
        "status_partii": "LOBBY",
        "slots": slots,
        "opcje": {
            "tryb_gry": f"{request.max_graczy}p",
            "rankingowa": request.rankingowa,  
            "typ_gry": request.typ_gry,        
            "haslo": request.haslo             
        },
        "host_id": current_user['id'],
        "tryb_lobby": "online",
        "kicked_players": [],
        "created_at": time.time()
    }
    
    # Zapisz w Redis
    await redis.save_lobby(game_id, lobby_data)
    
    # System message
    await send_system_message(game_id, f"Lobby utworzone przez {current_user['username']}", redis)
    
    # Aktualizuj last_activity
    lobby_data['last_activity'] = time.time()
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
    
    # System message
    await send_system_message(lobby_id, f"{current_user['username']} dołączył do lobby", redis)
    
    # Aktualizuj last_activity
    await update_last_activity(lobby_id, lobby_data, redis)
    
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
    
    # System message
    await send_system_message(lobby_id, f"{current_user['username']} opuścił lobby", redis)
    
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
    Toggle ready status
    
    Args:
        lobby_id: ID lobby
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/404 jeśli błąd
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
    
    # System message
    status_text = "gotowy" if player_slot['ready'] else "nie gotowy"
    await send_system_message(lobby_id, f"{current_user['username']} jest {status_text}", redis)
    
    # Aktualizuj last_activity
    await update_last_activity(lobby_id, lobby_data, redis)
    
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
    
    # System message
    await send_system_message(lobby_id, f"{player_name} został wyrzucony", redis)
    
    print(f"✅ Host wyrzucił gracza {player_name} z lobby {lobby_id}")
    
    return lobby_data

# ============================================
# ADD BOT
# ============================================

@router.post("/{lobby_id}/add-bot")
async def add_bot(
    lobby_id: str,
    slot_number: Optional[int] = Query(None, description="Numer slotu (0-3), jeśli None to pierwszy wolny"),
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Dodaj bota do lobby
    
    Args:
        lobby_id: ID lobby
        slot_number: Opcjonalny numer slotu (0-3)
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
    
    slots = lobby_data.get('slots', [])
    
    # Znajdź slot do dodania bota
    empty_slot = None
    
    if slot_number is not None:
        # Konkretny slot
        if slot_number < 0 or slot_number >= len(slots):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nieprawidłowy numer slotu"
            )
        
        if slots[slot_number]['typ'] != 'pusty':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ten slot jest zajęty"
            )
        
        empty_slot = slots[slot_number]
    else:
        # Pierwszy wolny slot
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
    
    # Dodaj bota (jeszcze NIE GOTOWY)
    empty_slot['typ'] = 'bot'
    empty_slot['nazwa'] = f"Bot #{next_bot_num}"
    empty_slot['ready'] = False  # Bot NIE jest jeszcze gotowy
    empty_slot['avatar_url'] = 'bot_avatar.png'
    
    bot_name = f"Bot #{next_bot_num}"
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # System message - dołączenie
    await send_system_message(lobby_id, f"{bot_name} dołączył do lobby", redis)
    
    print(f"✅ Dodano bota {bot_name} do lobby {lobby_id}")
    
    # Uruchom task w tle który da ready po 2-5s
    asyncio.create_task(_delayed_bot_ready(lobby_id, bot_name, redis))
    
    return lobby_data

# ============================================
# LIST AVAILABLE BOTS - NOWE!
# ============================================

@router.get("/bots/available")
async def list_available_bots():
    """
    Lista dostępnych botów z osobowościami
    
    Returns:
        List[dict]: Lista botów z ich algorytmami/osobowościami
    """
    async with async_sessionmaker() as session:
        query = select(User)
        result = await session.execute(query)
        users = result.scalars().all()
        
        bots = []
        for user in users:
            try:
                settings = json.loads(user.settings) if user.settings else {}
                if settings.get('jest_botem'):
                    algorytm = settings.get('algorytm', 'topplayer')
                    bots.append({
                        'id': user.id,
                        'username': user.username,
                        'algorytm': algorytm,
                        'avatar_url': user.avatar_url or 'bot_avatar.png'
                    })
            except:
                pass
        
        return bots

# ============================================
# ADD NAMED BOT - NOWE!
# ============================================

class AddNamedBotRequest(BaseModel):
    """Request do dodania konkretnego bota"""
    bot_username: str

@router.post("/{lobby_id}/add-named-bot")
async def add_named_bot(
    lobby_id: str,
    request: AddNamedBotRequest,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Dodaj konkretnego bota (z osobowością) do lobby
    
    Args:
        lobby_id: ID lobby
        request: {"bot_username": "nazwa_bota"}
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
    
    # Znajdź bota w bazie danych
    async with async_sessionmaker() as session:
        query = select(User).where(User.username == request.bot_username)
        result = await session.execute(query)
        bot_user = result.scalar_one_or_none()
        
        if not bot_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot '{request.bot_username}' nie znaleziony"
            )
        
        # Sprawdź czy to naprawdę bot
        try:
            settings = json.loads(bot_user.settings) if bot_user.settings else {}
            if not settings.get('jest_botem'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="To konto nie jest botem"
                )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Błędne ustawienia bota"
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
    
    # Sprawdź czy ten bot nie jest już w lobby
    for slot in slots:
        if slot.get('nazwa') == request.bot_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bot '{request.bot_username}' jest już w lobby"
            )
    
    # Dodaj bota (jeszcze NIE GOTOWY)
    empty_slot['typ'] = 'bot'
    empty_slot['id_uzytkownika'] = bot_user.id
    empty_slot['nazwa'] = bot_user.username
    empty_slot['ready'] = False  # Bot NIE jest jeszcze gotowy
    empty_slot['avatar_url'] = bot_user.avatar_url or 'bot_avatar.png'
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # Pobierz algorytm dla wiadomości
    algorytm = settings.get('algorytm', 'topplayer')
    
    # System message - dołączenie
    await send_system_message(lobby_id, f"🤖 {bot_user.username} ({algorytm}) dołączył do lobby", redis)
    
    print(f"✅ Dodano bota {bot_user.username} ({algorytm}) do lobby {lobby_id}")
    
    # Uruchom task w tle który da ready po 2-5s
    asyncio.create_task(_delayed_bot_ready(lobby_id, bot_user.username, redis))
    
    return lobby_data

# ============================================
# CHANGE SLOT - NOWE!
# ============================================

@router.post("/{lobby_id}/change-slot/{target_slot}")
async def change_slot(
    lobby_id: str,
    target_slot: int,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Gracz zmienia swój slot na inny (pusty)
    
    Args:
        lobby_id: ID lobby
        target_slot: Numer docelowego slotu (0-3)
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/404 jeśli błąd
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Sprawdź czy gra nie rozpoczęta
    if lobby_data.get('status_partii') == 'W_GRZE':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można zmieniać slotów podczas gry"
        )
    
    slots = lobby_data.get('slots', [])
    
    # Znajdź obecny slot gracza
    current_slot = None
    current_slot_index = None
    for i, slot in enumerate(slots):
        if slot.get('id_uzytkownika') == current_user['id']:
            current_slot = slot
            current_slot_index = i
            break
    
    if not current_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie jesteś w tym lobby"
        )
    
    # Sprawdź czy to nie ten sam slot
    if current_slot_index == target_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Już jesteś na tym slocie"
        )
    
    # Sprawdź czy target slot istnieje i jest pusty
    if target_slot < 0 or target_slot >= len(slots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy numer slotu"
        )
    
    target_slot_data = slots[target_slot]
    
    if target_slot_data['typ'] != 'pusty':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ten slot jest zajęty"
        )
    
    # Zamień sloty
    # Skopiuj dane gracza do target slotu
    target_slot_data['typ'] = current_slot['typ']
    target_slot_data['id_uzytkownika'] = current_slot['id_uzytkownika']
    target_slot_data['nazwa'] = current_slot['nazwa']
    target_slot_data['is_host'] = current_slot['is_host']
    target_slot_data['ready'] = current_slot['ready']
    target_slot_data['avatar_url'] = current_slot['avatar_url']
    
    # Opróżnij stary slot
    current_slot['typ'] = 'pusty'
    current_slot['id_uzytkownika'] = None
    current_slot['nazwa'] = None
    current_slot['is_host'] = False
    current_slot['ready'] = False
    current_slot['avatar_url'] = None
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # System message
    await send_system_message(lobby_id, f"{current_user['username']} zmienił miejsce", redis)
    
    print(f"🔄 {current_user['username']} zmienił slot na {target_slot} w lobby {lobby_id}")
    
    return lobby_data

# ============================================
# KICK BOT - NOWE!
# ============================================

@router.post("/{lobby_id}/kick-bot/{slot_number}")
async def kick_bot(
    lobby_id: str,
    slot_number: int,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Host wyrzuca bota z danego slotu
    
    Args:
        lobby_id: ID lobby
        slot_number: Numer slotu z botem (0-3)
        current_user: Zalogowany użytkownik (musi być hostem)
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/403/404 jeśli błąd
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
            detail="Tylko host może wyrzucać boty"
        )
    
    slots = lobby_data.get('slots', [])
    
    # Sprawdź czy slot istnieje
    if slot_number < 0 or slot_number >= len(slots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy numer slotu"
        )
    
    slot = slots[slot_number]
    
    # Sprawdź czy to bot
    if slot.get('typ') != 'bot':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="W tym slocie nie ma bota"
        )
    
    # Opróżnij slot
    bot_name = slot['nazwa']
    slot['typ'] = 'pusty'
    slot['nazwa'] = None
    slot['ready'] = False
    slot['avatar_url'] = None
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # System message
    await send_system_message(lobby_id, f"{bot_name} został usunięty", redis)
    
    print(f"🤖❌ Host wyrzucił bota {bot_name} ze slotu {slot_number} w lobby {lobby_id}")
    
    return lobby_data

# ============================================
# CHAT - GET MESSAGES - NOWE!
# ============================================

@router.get("/{lobby_id}/chat")
async def get_chat_messages(
    lobby_id: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Pobierz historię czatu w lobby
    
    Args:
        lobby_id: ID lobby
        limit: Max liczba wiadomości (default 50)
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        List[dict]: Lista wiadomości
    """
    # Sprawdź czy lobby istnieje
    lobby_data = await redis.get_lobby(lobby_id)
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Pobierz wiadomości z Redis
    chat_key = f"lobby:{lobby_id}:chat"
    messages = await redis.redis.lrange(chat_key, -limit, -1)
    
    # Parse JSON messages
    parsed_messages = []
    for msg in messages:
        try:
            parsed_messages.append(json.loads(msg))
        except:
            pass
    
    return parsed_messages

# ============================================
# CHAT - SEND MESSAGE - NOWE!
# ============================================

@router.post("/{lobby_id}/chat")
async def send_chat_message(
    lobby_id: str,
    message: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Wyślij wiadomość na czat lobby
    
    Args:
        lobby_id: ID lobby
        message: {"message": "treść"}
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Wysłana wiadomość
    
    Raises:
        HTTPException: 400/404 jeśli błąd
    """
    # Sprawdź czy lobby istnieje
    lobby_data = await redis.get_lobby(lobby_id)
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Walidacja wiadomości
    msg_text = message.message.strip()
    
    if not msg_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wiadomość nie może być pusta"
        )
    
    if len(msg_text) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wiadomość za długa (max 500 znaków)"
        )
    
    # Sprawdź czy użytkownik jest w lobby
    slots = lobby_data.get('slots', [])
    is_in_lobby = any(slot.get('id_uzytkownika') == current_user['id'] for slot in slots)
    
    if not is_in_lobby:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Musisz być w lobby aby wysyłać wiadomości"
        )
    
    # Stwórz wiadomość
    chat_message = {
        "id": int(time.time() * 1000),  # Timestamp jako ID
        "user_id": current_user['id'],
        "username": current_user['username'],
        "message": msg_text,
        "timestamp": time.time(),
        "is_system": False
    }
    
    # Zapisz w Redis (lista)
    chat_key = f"lobby:{lobby_id}:chat"
    await redis.redis.rpush(chat_key, json.dumps(chat_message))
    await redis.redis.ltrim(chat_key, -100, -1)
    await redis.redis.expire(chat_key, 86400)
    
    # Aktualizuj last_activity
    await update_last_activity(lobby_id, lobby_data, redis)
    
    print(f"💬 [{lobby_id}] {current_user['username']}: {msg_text}")
    
    return chat_message

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
    
    # System message
    await send_system_message(lobby_id, "Gra rozpoczęta!", redis)
    
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
# SWAP SLOTS
# ============================================

@router.post("/{lobby_id}/swap-slots")
async def swap_slots(
    lobby_id: str,
    slot_a: int,
    slot_b: int,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Zamień miejscami 2 sloty (tylko host)
    
    Args:
        lobby_id: ID lobby
        slot_a: Numer pierwszego slotu (0-3)
        slot_b: Numer drugiego slotu (0-3)
        current_user: Zalogowany użytkownik (musi być hostem)
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/403/404 jeśli błąd
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
            detail="Tylko host może zamieniać sloty"
        )
    
    # Sprawdź czy gra nie rozpoczęta
    if lobby_data.get('status_partii') == 'W_GRZE':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można zamieniać slotów podczas gry"
        )
    
    slots = lobby_data.get('slots', [])
    
    # Walidacja numerów slotów
    if slot_a < 0 or slot_a >= len(slots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieprawidłowy numer slotu A: {slot_a}"
        )
    
    if slot_b < 0 or slot_b >= len(slots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieprawidłowy numer slotu B: {slot_b}"
        )
    
    if slot_a == slot_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można zamienić slotu samego ze sobą"
        )
    
    # Pobierz dane slotów
    slot_a_data = slots[slot_a]
    slot_b_data = slots[slot_b]
    
    # Zamień zawartość (ale nie numery!)
    # Zapisz numer_gracza przed zamianą
    temp_numer_a = slot_a_data['numer_gracza']
    temp_numer_b = slot_b_data['numer_gracza']
    
    # Zamień wszystkie pola OPRÓCZ numer_gracza
    temp = {
        'typ': slot_a_data['typ'],
        'id_uzytkownika': slot_a_data.get('id_uzytkownika'),
        'nazwa': slot_a_data.get('nazwa'),
        'is_host': slot_a_data.get('is_host', False),
        'ready': slot_a_data.get('ready', False),
        'avatar_url': slot_a_data.get('avatar_url')
    }
    
    slot_a_data['typ'] = slot_b_data['typ']
    slot_a_data['id_uzytkownika'] = slot_b_data.get('id_uzytkownika')
    slot_a_data['nazwa'] = slot_b_data.get('nazwa')
    slot_a_data['is_host'] = slot_b_data.get('is_host', False)
    slot_a_data['ready'] = slot_b_data.get('ready', False)
    slot_a_data['avatar_url'] = slot_b_data.get('avatar_url')
    
    slot_b_data['typ'] = temp['typ']
    slot_b_data['id_uzytkownika'] = temp['id_uzytkownika']
    slot_b_data['nazwa'] = temp['nazwa']
    slot_b_data['is_host'] = temp['is_host']
    slot_b_data['ready'] = temp['ready']
    slot_b_data['avatar_url'] = temp['avatar_url']
    
    # Zachowaj oryginalne numery slotów
    slot_a_data['numer_gracza'] = temp_numer_a
    slot_b_data['numer_gracza'] = temp_numer_b
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # System message
    names = []
    if slot_a_data.get('nazwa'):
        names.append(slot_a_data['nazwa'])
    if slot_b_data.get('nazwa'):
        names.append(slot_b_data['nazwa'])
    
    if len(names) == 2:
        msg = f"{names[0]} i {names[1]} zamienili się miejscami"
    elif len(names) == 1:
        msg = f"{names[0]} zmienił pozycję"
    else:
        msg = "Host zamienił sloty"
    
    await send_system_message(lobby_id, msg, redis)
    
    print(f"🔄 Host zamienił sloty {slot_a} ↔ {slot_b} w lobby {lobby_id}")
    
    return lobby_data


# ============================================
# TRANSFER HOST
# ============================================

@router.post("/{lobby_id}/transfer-host/{new_host_user_id}")
async def transfer_host(
    lobby_id: str,
    new_host_user_id: int,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Przekaż hosta innemu graczowi (tylko obecny host)
    
    Args:
        lobby_id: ID lobby
        new_host_user_id: ID nowego hosta
        current_user: Zalogowany użytkownik (musi być obecnym hostem)
        redis: Redis service
    
    Returns:
        dict: Zaktualizowane dane lobby
    
    Raises:
        HTTPException: 400/403/404 jeśli błąd
    """
    lobby_data = await redis.get_lobby(lobby_id)
    
    if not lobby_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby nie znalezione"
        )
    
    # Sprawdź czy jest obecnym hostem
    if lobby_data.get('host_id') != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko host może przekazać role hosta"
        )
    
    # Sprawdź czy próbuje przekazać samemu sobie
    if new_host_user_id == current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Już jesteś hostem"
        )
    
    slots = lobby_data.get('slots', [])
    
    # Znajdź obecnego hosta i nowego hosta
    old_host_slot = None
    new_host_slot = None
    
    for slot in slots:
        if slot.get('id_uzytkownika') == current_user['id']:
            old_host_slot = slot
        if slot.get('id_uzytkownika') == new_host_user_id:
            new_host_slot = slot
    
    if not old_host_slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie jesteś w lobby"
        )
    
    if not new_host_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nowy host nie znaleziony w lobby"
        )
    
    # Sprawdź czy nowy host to gracz (nie bot)
    if new_host_slot.get('typ') != 'gracz':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można przekazać hosta botowi"
        )
    
    # Przekaż role
    old_host_slot['is_host'] = False
    new_host_slot['is_host'] = True
    
    # Zaktualizuj host_id w lobby
    lobby_data['host_id'] = new_host_user_id
    
    # Zapisz
    await redis.save_lobby(lobby_id, lobby_data)
    
    # System message
    await send_system_message(
        lobby_id, 
        f"{new_host_slot['nazwa']} jest teraz hostem! 👑", 
        redis
    )
    
    print(f"👑 Host przekazany: {current_user['username']} → {new_host_slot['nazwa']} w lobby {lobby_id}")
    
    return lobby_data

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