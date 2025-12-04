"""
Admin routes - zarządzanie platformą
FIXED: Dostosowane do rzeczywistej struktury bazy (users, is_admin)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, and_, or_
from database import User, PlayerGameStats, GameType, Friendship, Message, async_sessionmaker
from dependencies import get_current_user

router = APIRouter(tags=["admin"])


# ============================================
# ADMIN MIDDLEWARE
# ============================================

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Sprawdź czy użytkownik ma uprawnienia admina.
    Teraz sprawdzamy pole users.is_admin
    """
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(User).where(User.id == current_user['id'])
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Brak uprawnień administratora"
            )
        
        return current_user


# ============================================
# STATS - Dashboard
# ============================================

@router.get("/stats")
async def get_admin_stats(admin: dict = Depends(get_current_admin)):
    """
    Statystyki platformy dla admina
    """
    import json as json_lib
    
    async with async_sessionmaker() as session:
        # Liczba użytkowników
        total_users_result = await session.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar()
        
        # Policz użytkowników online (włącznie z botami)
        all_users_result = await session.execute(select(User))
        all_users = all_users_result.scalars().all()
        
        online_users = 0
        bots_count = 0
        for user in all_users:
            is_bot = False
            try:
                if user.settings:
                    settings = json_lib.loads(user.settings)
                    is_bot = settings.get('jest_botem', False)
            except:
                pass
            
            if is_bot:
                bots_count += 1
                online_users += 1  # Boty zawsze online
            elif user.status == 'online':
                online_users += 1
        
        # Użytkownicy zarejestrowani dzisiaj
        today_users_result = await session.execute(
            select(func.count(User.id)).where(
                func.date(User.created_at) == func.current_date()
            )
        )
        users_today = today_users_result.scalar()
        
        # Liczba adminów
        admins_result = await session.execute(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        total_admins = admins_result.scalar()
        
        # Liczba znajomości
        friendships_result = await session.execute(select(func.count(Friendship.user_id_1)))
        total_friendships = friendships_result.scalar()
        
        # Liczba wiadomości
        messages_result = await session.execute(select(func.count(Message.id)))
        total_messages = messages_result.scalar()
        
        # Nieprzeczytane wiadomości
        unread_messages_result = await session.execute(
            select(func.count(Message.id)).where(Message.is_read == False)
        )
        unread_messages = unread_messages_result.scalar()
        
        return {
            "users": {
                "total": total_users,
                "online": online_users,
                "bots": bots_count,
                "today": users_today,
                "admins": total_admins
            },
            "social": {
                "friendships": total_friendships,
                "messages": total_messages,
                "unread_messages": unread_messages
            }
        }


# ============================================
# USER MANAGEMENT
# ============================================

@router.get("/users")
async def get_all_users(
    search: str = None,
    status: str = None,  # 'online', 'offline', 'in_game'
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(get_current_admin)
):
    """
    Lista wszystkich użytkowników z możliwością filtrowania
    """
    import json as json_lib
    
    async with async_sessionmaker() as session:
        # Build query
        query = select(User)
        
        # Filters
        filters = []
        if search:
            filters.append(or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            ))
        
        # Status filter - obsługiwany po pobraniu danych (boty zawsze online)
        # Nie filtrujemy tu, bo musimy sprawdzić settings
        
        if filters:
            query = query.where(and_(*filters))
        
        # Get all results first (potrzebne do sprawdzenia botów)
        query = query.order_by(User.created_at.desc())
        result = await session.execute(query)
        all_users = result.scalars().all()
        
        # Format response i filtruj po statusie
        users_data = []
        for user in all_users:
            # Sprawdź czy to bot
            is_bot = False
            try:
                if user.settings:
                    settings = json_lib.loads(user.settings)
                    is_bot = settings.get('jest_botem', False)
            except:
                pass
            
            # Boty zawsze online
            effective_status = 'online' if is_bot else user.status
            
            # Filtruj po statusie
            if status:
                if status == 'online' and effective_status != 'online':
                    continue
                elif status == 'offline' and effective_status != 'offline':
                    continue
                elif status == 'in_game' and effective_status != 'in_game':
                    continue
            
            # Get games stats for this user
            stats_result = await session.execute(
                select(func.sum(PlayerGameStats.games_played))
                .where(PlayerGameStats.user_id == user.id)
            )
            games_played = stats_result.scalar() or 0
            
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "status": effective_status,
                "is_admin": user.is_admin,
                "is_bot": is_bot,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "games_played": games_played
            })
        
        # Paginacja
        total = len(users_data)
        users_data = users_data[offset:offset + limit]
        
        return {
            "users": users_data,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Szczegóły konkretnego użytkownika
    """
    async with async_sessionmaker() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
        
        # Get game stats
        stats_result = await session.execute(
            select(PlayerGameStats, GameType)
            .join(GameType, PlayerGameStats.game_type_id == GameType.id)
            .where(PlayerGameStats.user_id == user_id)
        )
        stats_rows = stats_result.all()
        
        game_stats = []
        for stat, game_type in stats_rows:
            game_stats.append({
                "game_name": game_type.name,
                "elo_rating": stat.elo_rating,
                "games_played": stat.games_played,
                "games_won": stat.games_won,
                "win_rate": (stat.games_won / stat.games_played * 100) if stat.games_played > 0 else 0
            })
        
        # Get friendships count
        friendships_result = await session.execute(
            select(func.count(Friendship.user_id_1))
            .where(or_(
                Friendship.user_id_1 == user_id,
                Friendship.user_id_2 == user_id
            ))
            .where(Friendship.status == 'accepted')
        )
        friends_count = friendships_result.scalar()
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "status": user.status,
            "is_admin": user.is_admin,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "game_stats": game_stats,
            "friends_count": friends_count
        }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Usuń użytkownika (hard delete)
    """
    async with async_sessionmaker() as session:
        # Don't delete yourself
        if user_id == admin['id']:
            raise HTTPException(
                status_code=400, 
                detail="Nie możesz usunąć sam siebie!"
            )
        
        # Check if user exists
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
        
        # Delete related data
        # 1. Player game stats
        await session.execute(
            delete(PlayerGameStats).where(PlayerGameStats.user_id == user_id)
        )
        
        # 2. Friendships
        await session.execute(
            delete(Friendship).where(or_(
                Friendship.user_id_1 == user_id,
                Friendship.user_id_2 == user_id
            ))
        )
        
        # 3. Messages
        await session.execute(
            delete(Message).where(or_(
                Message.sender_id == user_id,
                Message.receiver_id == user_id
            ))
        )
        
        # 4. Delete user
        await session.delete(user)
        
        await session.commit()
        
        return {
            "message": "Użytkownik usunięty pomyślnie",
            "deleted_id": user_id,
            "deleted_username": user.username
        }


@router.patch("/users/{user_id}/admin")
async def toggle_admin(
    user_id: int,
    grant: bool,  # True = nadaj, False = zabierz
    admin: dict = Depends(get_current_admin)
):
    """
    Nadaj lub zabierz uprawnienia admina
    """
    async with async_sessionmaker() as session:
        # Don't modify yourself
        if user_id == admin['id']:
            raise HTTPException(
                status_code=400,
                detail="Nie możesz modyfikować swoich uprawnień!"
            )
        
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
        
        # Update is_admin
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_admin=grant)
        )
        
        await session.commit()
        
        return {
            "message": f"Uprawnienia admina {'nadane' if grant else 'odebrane'}",
            "user_id": user_id,
            "username": user.username,
            "is_admin": grant
        }


@router.patch("/users/{user_id}/status")
async def change_user_status(
    user_id: int,
    status: str,  # 'online', 'offline', 'in_game'
    admin: dict = Depends(get_current_admin)
):
    """
    Zmień status użytkownika (force)
    """
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
        
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(status=status)
        )
        
        await session.commit()
        
        return {
            "message": "Status zmieniony",
            "user_id": user_id,
            "username": user.username,
            "new_status": status
        }


# ============================================
# GAME TYPES MANAGEMENT
# ============================================

@router.get("/game-types")
async def get_game_types(admin: dict = Depends(get_current_admin)):
    """
    Lista dostępnych typów gier
    """
    async with async_sessionmaker() as session:
        result = await session.execute(select(GameType))
        game_types = result.scalars().all()
        
        return {
            "game_types": [
                {
                    "id": gt.id,
                    "name": gt.name,
                    "rules_url": gt.rules_url
                }
                for gt in game_types
            ]
        }


@router.post("/game-types")
async def create_game_type(
    name: str,
    rules_url: str = None,
    admin: dict = Depends(get_current_admin)
):
    """
    Dodaj nowy typ gry
    """
    async with async_sessionmaker() as session:
        # Check if exists
        result = await session.execute(
            select(GameType).where(GameType.name == name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="Typ gry już istnieje")
        
        game_type = GameType(name=name, rules_url=rules_url)
        session.add(game_type)
        await session.commit()
        await session.refresh(game_type)
        
        return {
            "message": "Typ gry dodany",
            "game_type": {
                "id": game_type.id,
                "name": game_type.name,
                "rules_url": game_type.rules_url
            }
        }


# ============================================
# SOCIAL MANAGEMENT
# ============================================

@router.get("/messages")
async def get_recent_messages(
    limit: int = 50,
    admin: dict = Depends(get_current_admin)
):
    """
    Ostatnie wiadomości w systemie (monitoring)
    """
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(Message)
            .order_by(Message.sent_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        messages_data = []
        for msg in messages:
            # Get sender and receiver names
            sender_result = await session.execute(
                select(User.username).where(User.id == msg.sender_id)
            )
            sender = sender_result.scalar()
            
            receiver_result = await session.execute(
                select(User.username).where(User.id == msg.receiver_id)
            )
            receiver = receiver_result.scalar()
            
            messages_data.append({
                "id": msg.id,
                "sender": sender,
                "receiver": receiver,
                "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
                "is_read": msg.is_read
            })
        
        return {"messages": messages_data}


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Usuń wiadomość (moderacja)
    """
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(status_code=404, detail="Wiadomość nie znaleziona")
        
        await session.delete(message)
        await session.commit()
        
        return {"message": "Wiadomość usunięta"}


# ============================================
# BOT MATCHMAKING MANAGEMENT
# ============================================

@router.get("/bots/status")
async def get_bots_status(admin: dict = Depends(get_current_admin)):
    """
    Status systemu bot matchmaking
    """
    from bot_matchmaking import bot_matchmaking
    return bot_matchmaking.get_status()


@router.post("/bots/matchmaking")
async def toggle_matchmaking(
    enabled: bool,
    admin: dict = Depends(get_current_admin)
):
    """
    Włącz/wyłącz automatyczny matchmaking botów
    """
    from bot_matchmaking import bot_matchmaking
    bot_matchmaking.set_matchmaking_enabled(enabled)
    
    return {
        "message": f"Matchmaking {'włączony' if enabled else 'wyłączony'}",
        "enabled": enabled
    }


@router.post("/bots/{bot_username}/active")
async def toggle_bot_active(
    bot_username: str,
    active: bool,
    admin: dict = Depends(get_current_admin)
):
    """
    Włącz/wyłącz konkretnego bota
    """
    from bot_matchmaking import bot_matchmaking
    success = bot_matchmaking.set_bot_active(bot_username, active)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_username}' nie znaleziony")
    
    return {
        "message": f"Bot '{bot_username}' {'aktywowany' if active else 'dezaktywowany'}",
        "bot_username": bot_username,
        "active": active
    }


@router.post("/bots/{bot_username}/force-join/{lobby_id}")
async def force_bot_join(
    bot_username: str,
    lobby_id: str,
    admin: dict = Depends(get_current_admin)
):
    """
    Wymuś dołączenie bota do konkretnego lobby
    """
    from bot_matchmaking import bot_matchmaking
    success = await bot_matchmaking.force_bot_to_lobby(bot_username, lobby_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail=f"Nie udało się dodać bota '{bot_username}' do lobby '{lobby_id}'"
        )
    
    return {
        "message": f"Bot '{bot_username}' dołączył do lobby '{lobby_id}'",
        "bot_username": bot_username,
        "lobby_id": lobby_id
    }


@router.post("/bots/start")
async def start_all_bots(admin: dict = Depends(get_current_admin)):
    """
    Uruchom wszystkie boty (jeśli były zatrzymane)
    """
    from bot_matchmaking import bot_matchmaking
    await bot_matchmaking.start()
    
    return {
        "message": "Wszystkie boty uruchomione",
        "status": bot_matchmaking.get_status()
    }


@router.post("/bots/stop")
async def stop_all_bots(admin: dict = Depends(get_current_admin)):
    """
    Zatrzymaj wszystkie boty
    """
    from bot_matchmaking import bot_matchmaking
    await bot_matchmaking.stop()
    
    return {
        "message": "Wszystkie boty zatrzymane"
    }


@router.post("/bots/config")
async def configure_bots(
    min_interval: float = None,
    max_interval: float = None,
    game_type: str = None,
    players: int = None,
    admin: dict = Depends(get_current_admin)
):
    """
    Konfiguruj ustawienia bot matchmaking
    
    Args:
        min_interval: Minimalny interwał między akcjami (sekundy)
        max_interval: Maksymalny interwał między akcjami (sekundy)
        game_type: Preferowany typ gry ("66" lub "tysiac")
        players: Preferowana liczba graczy (3 lub 4)
    """
    from bot_matchmaking import bot_matchmaking
    
    if min_interval is not None:
        bot_matchmaking.min_interval = min_interval
    
    if max_interval is not None:
        bot_matchmaking.max_interval = max_interval
    
    if game_type is not None:
        if game_type not in ["66", "tysiac"]:
            raise HTTPException(status_code=400, detail="game_type musi być '66' lub 'tysiac'")
        bot_matchmaking.preferred_game_type = game_type
    
    if players is not None:
        if players not in [3, 4]:
            raise HTTPException(status_code=400, detail="players musi być 3 lub 4")
        bot_matchmaking.preferred_players = players
    
    return {
        "message": "Konfiguracja zaktualizowana",
        "config": {
            "min_interval": bot_matchmaking.min_interval,
            "max_interval": bot_matchmaking.max_interval,
            "preferred_game_type": bot_matchmaking.preferred_game_type,
            "preferred_players": bot_matchmaking.preferred_players
        }
    }


# ============================================
# GAME/LOBBY MANAGEMENT
# ============================================

@router.get("/lobbies")
async def get_all_lobbies(admin: dict = Depends(get_current_admin)):
    """
    Lista wszystkich lobby w Redis
    """
    from services.redis_service import RedisService
    
    redis = RedisService()
    lobbies = await redis.list_lobbies()
    
    return {
        "total": len(lobbies),
        "lobbies": [
            {
                "id": l.get('id_gry'),
                "nazwa": l.get('nazwa'),
                "status": l.get('status_partii'),
                "typ_gry": l.get('opcje', {}).get('typ_gry'),
                "gracze": [s.get('nazwa') for s in l.get('slots', []) if s.get('typ') != 'pusty'],
                "created_at": l.get('created_at')
            }
            for l in lobbies
        ]
    }


@router.delete("/lobbies/{lobby_id}")
async def delete_lobby(
    lobby_id: str,
    admin: dict = Depends(get_current_admin)
):
    """
    Usuń konkretne lobby (force)
    """
    from services.redis_service import RedisService
    
    redis = RedisService()
    lobby = await redis.get_lobby(lobby_id)
    
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby nie znalezione")
    
    await redis.delete_lobby(lobby_id)
    await redis.delete_game_engine(lobby_id)
    
    return {
        "message": f"Lobby {lobby_id} usunięte",
        "lobby_id": lobby_id
    }


@router.post("/lobbies/cleanup")
async def cleanup_zombie_lobbies(admin: dict = Depends(get_current_admin)):
    """
    Wyczyść wszystkie "zombie" lobby:
    - W_GRZE bez aktywnych połączeń WebSocket
    - Starsze niż 2 godziny
    - ZAKONCZONA
    """
    import time
    from services.redis_service import RedisService
    from routers.websocket_router import manager
    
    redis = RedisService()
    lobbies = await redis.list_lobbies()
    
    deleted = []
    kept = []
    now = time.time()
    max_age_hours = 2
    
    for lobby in lobbies:
        lobby_id = lobby.get('id_gry')
        status = lobby.get('status_partii')
        created_at = lobby.get('created_at', 0)
        age_hours = (now - created_at) / 3600 if created_at else 999
        
        should_delete = False
        reason = ""
        
        # 1. ZAKONCZONA - zawsze usuń
        if status == 'ZAKONCZONA':
            should_delete = True
            reason = "zakończona"
        
        # 2. Starsze niż 2 godziny
        elif age_hours > max_age_hours:
            should_delete = True
            reason = f"stara ({age_hours:.1f}h)"
        
        # 3. W_GRZE bez aktywnych połączeń
        elif status == 'W_GRZE':
            connections = manager.get_connections_count(lobby_id)
            # Sprawdź czy są jacykolwiek gracze (nie boty)
            human_players = [
                s for s in lobby.get('slots', [])
                if s.get('typ') == 'gracz'
            ]
            
            if connections == 0 and len(human_players) > 0:
                should_delete = True
                reason = "brak połączeń WS"
        
        if should_delete:
            await redis.delete_lobby(lobby_id)
            await redis.delete_game_engine(lobby_id)
            deleted.append({"id": lobby_id, "reason": reason})
        else:
            kept.append(lobby_id)
    
    return {
        "message": f"Wyczyszczono {len(deleted)} zombie lobby",
        "deleted": deleted,
        "kept_count": len(kept)
    }


@router.post("/lobbies/cleanup-all")
async def cleanup_all_lobbies(admin: dict = Depends(get_current_admin)):
    """
    Usuń WSZYSTKIE lobby (nuclear option)
    """
    from services.redis_service import RedisService
    
    redis = RedisService()
    lobbies = await redis.list_lobbies()
    
    deleted_count = 0
    for lobby in lobbies:
        lobby_id = lobby.get('id_gry')
        await redis.delete_lobby(lobby_id)
        await redis.delete_game_engine(lobby_id)
        deleted_count += 1
    
    return {
        "message": f"Usunięto wszystkie {deleted_count} lobby",
        "deleted_count": deleted_count
    }


@router.post("/users/reset-status")
async def reset_all_user_status(admin: dict = Depends(get_current_admin)):
    """
    Resetuj statusy wszystkich użytkowników na 'offline'
    (przydatne gdy statusy się rozjadą)
    """
    async with async_sessionmaker() as session:
        # Resetuj wszystkich na offline
        result = await session.execute(
            update(User)
            .where(User.status != 'offline')
            .values(status='offline')
        )
        
        await session.commit()
        
        return {
            "message": "Statusy zresetowane",
            "affected_users": result.rowcount
        }