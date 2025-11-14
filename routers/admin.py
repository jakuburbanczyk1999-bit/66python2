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
    async with async_sessionmaker() as session:
        # Liczba użytkowników
        total_users_result = await session.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar()
        
        # Użytkownicy online
        online_users_result = await session.execute(
            select(func.count(User.id)).where(User.status == 'online')
        )
        online_users = online_users_result.scalar()
        
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
                "today": users_today,
                "admins": total_admins
            },
            "social": {
                "friendships": total_friendships,
                "messages": total_messages,
                "unread_messages": unread_messages
            },
            "note": "Statystyki gier będą dostępne gdy dodasz tabele gry/gracze_lobby"
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
        
        if status:
            filters.append(User.status == status)
        
        if filters:
            query = query.where(and_(*filters))
        
        # Count total
        count_query = select(func.count(User.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Format response
        users_data = []
        for user in users:
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
                "status": user.status,
                "is_admin": user.is_admin,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "games_played": games_played
            })
        
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