"""
Router: Stats (ranking i statystyki)
Odpowiedzialność: Ranking graczy, statystyki, system ELO
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
import json

from database import async_sessionmaker, User, PlayerGameStats, GameType
from dependencies import get_current_user, get_redis
from services.redis_service import RedisService

router = APIRouter()

# ============================================
# HELPER DO POBIERANIA RANG (używany w innych modułach)
# ============================================

async def get_ranks_for_usernames(usernames: list) -> dict:
    """
    Pobiera rangi dla listy użytkowników.
    Zwraca dict {username: rank_info}
    """
    if not usernames:
        return {}
    
    ranks = {}
    try:
        async with async_sessionmaker() as session:
            # Pobierz najwyższe ELO dla każdego użytkownika
            users_query = select(User).where(User.username.in_(usernames))
            users_result = await session.execute(users_query)
            users = {u.username: u.id for u in users_result.scalars().all()}
            
            for username in usernames:
                if username not in users:
                    # Nowy gracz bez statystyk - domyślna ranga
                    ranks[username] = get_rank_for_elo(1200)
                    continue
                
                user_id = users[username]
                
                # Pobierz najwyższe ELO
                stats_query = select(func.max(PlayerGameStats.elo_rating)).where(
                    PlayerGameStats.user_id == user_id
                )
                stats_result = await session.execute(stats_query)
                max_elo = stats_result.scalar() or 1200
                
                ranks[username] = get_rank_for_elo(max_elo)
    except Exception as e:
        print(f"[⚠️ Stats] Błąd pobierania rang: {e}")
        # Fallback - domyślna ranga dla wszystkich
        for username in usernames:
            if username not in ranks:
                ranks[username] = get_rank_for_elo(1200)
    
    return ranks

# ============================================
# SYSTEM RANG
# ============================================

# Próg dla rangi Mistrz - punkty powyżej tego są wyświetlane jako "Mistrz X"
MISTRZ_THRESHOLD = 1350

RANKS = [
    {'name': 'Klasa 3', 'emoji': '3️⃣', 'min_elo': 0, 'max_elo': 1099, 'color': '#8B7355'},
    {'name': 'Klasa 2', 'emoji': '2️⃣', 'min_elo': 1100, 'max_elo': 1249, 'color': '#C0C0C0'},
    {'name': 'Klasa 1', 'emoji': '1️⃣', 'min_elo': 1250, 'max_elo': 1349, 'color': '#FFD700'},
    {'name': 'Mistrz', 'emoji': 'Ⓜ️', 'min_elo': 1350, 'max_elo': 9999, 'color': '#FF4500'},
]

def get_rank_for_elo(elo: float) -> dict:
    """Zwraca rangę dla danego ELO."""
    for rank in RANKS:
        if rank['min_elo'] <= elo <= rank['max_elo']:
            result = rank.copy()
            # Dla Mistrza dodaj punkty ponad próg
            if rank['name'] == 'Mistrz':
                result['master_points'] = int(elo - MISTRZ_THRESHOLD)
            return result
    return RANKS[0]  # Domyślnie Klasa 3

def calculate_elo_change(winner_elo: float, loser_elo: float, k_factor: int = 32) -> tuple:
    """
    Oblicza zmianę ELO po meczu.
    Zwraca (winner_change, loser_change).
    """
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 - expected_winner
    
    winner_change = k_factor * (1 - expected_winner)
    loser_change = k_factor * (0 - expected_loser)
    
    return round(winner_change, 1), round(loser_change, 1)

# ============================================
# ENDPOINTS
# ============================================

@router.get("/ranking")
async def get_ranking(
    game_type: Optional[str] = Query(None, description="Typ gry: '66' lub 'tysiac'"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Pobierz ranking graczy.
    
    Args:
        game_type: Opcjonalnie filtruj po typie gry
        limit: Liczba wyników (max 100)
        offset: Offset dla paginacji
    
    Returns:
        Lista graczy z ich statystykami i rangami
    """
    try:
        async with async_sessionmaker() as session:
            # Pobierz typ gry jeśli podany
            game_type_id = None
            if game_type:
                game_type_query = select(GameType).where(GameType.name.ilike(f"%{game_type}%"))
                result = await session.execute(game_type_query)
                gt = result.scalar_one_or_none()
                if gt:
                    game_type_id = gt.id
            
            # Buduj query
            if game_type_id:
                # Ranking dla konkretnej gry
                query = (
                    select(User, PlayerGameStats)
                    .join(PlayerGameStats, User.id == PlayerGameStats.user_id)
                    .where(PlayerGameStats.game_type_id == game_type_id)
                    .where(PlayerGameStats.games_played > 0)
                    .order_by(PlayerGameStats.elo_rating.desc())
                    .offset(offset)
                    .limit(limit)
                )
            else:
                # Ranking globalny - użyj najwyższego ELO gracza
                # Subquery: max ELO dla każdego użytkownika
                subq = (
                    select(
                        PlayerGameStats.user_id,
                        func.max(PlayerGameStats.elo_rating).label('max_elo'),
                        func.sum(PlayerGameStats.games_played).label('total_games'),
                        func.sum(PlayerGameStats.games_won).label('total_wins')
                    )
                    .group_by(PlayerGameStats.user_id)
                    .subquery()
                )
                
                query = (
                    select(User, subq.c.max_elo, subq.c.total_games, subq.c.total_wins)
                    .join(subq, User.id == subq.c.user_id)
                    .where(subq.c.total_games > 0)
                    .order_by(subq.c.max_elo.desc())
                    .offset(offset)
                    .limit(limit)
                )
            
            result = await session.execute(query)
            rows = result.all()
            
            ranking = []
            for i, row in enumerate(rows):
                if game_type_id:
                    user, stats = row
                    elo = stats.elo_rating
                    games = stats.games_played
                    wins = stats.games_won
                else:
                    user, elo, games, wins = row
                    elo = elo or 1200
                    games = games or 0
                    wins = wins or 0
                
                rank_info = get_rank_for_elo(elo)
                win_rate = round((wins / games * 100), 1) if games > 0 else 0
                
                # Sprawdź czy to bot
                is_bot = False
                if user.settings:
                    try:
                        settings = json.loads(user.settings)
                        is_bot = settings.get('jest_botem', False)
                    except:
                        pass
                
                ranking.append({
                    'position': offset + i + 1,
                    'username': user.username,
                    'avatar_url': user.avatar_url or 'default_avatar.png',
                    'elo': round(elo),
                    'rank': rank_info,
                    'games_played': int(games),
                    'games_won': int(wins),
                    'win_rate': win_rate,
                    'is_bot': is_bot
                })
            
            # Policz całkowitą liczbę graczy
            if game_type_id:
                count_query = (
                    select(func.count())
                    .select_from(PlayerGameStats)
                    .where(PlayerGameStats.game_type_id == game_type_id)
                    .where(PlayerGameStats.games_played > 0)
                )
            else:
                count_query = (
                    select(func.count(func.distinct(PlayerGameStats.user_id)))
                    .where(PlayerGameStats.games_played > 0)
                )
            
            count_result = await session.execute(count_query)
            total_players = count_result.scalar() or 0
            
            return {
                'ranking': ranking,
                'total_players': total_players,
                'limit': limit,
                'offset': offset
            }
            
    except Exception as e:
        print(f"❌ Error getting ranking: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Błąd pobierania rankingu"
        )


@router.get("/player/{username}")
async def get_player_stats(username: str):
    """
    Pobierz statystyki gracza.
    
    Args:
        username: Nazwa użytkownika
    
    Returns:
        Statystyki gracza dla wszystkich gier
    """
    try:
        async with async_sessionmaker() as session:
            # Pobierz użytkownika
            user_query = select(User).where(User.username == username)
            result = await session.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Użytkownik nie znaleziony"
                )
            
            # Pobierz statystyki dla wszystkich gier
            stats_query = (
                select(PlayerGameStats, GameType)
                .join(GameType, PlayerGameStats.game_type_id == GameType.id)
                .where(PlayerGameStats.user_id == user.id)
            )
            stats_result = await session.execute(stats_query)
            stats_rows = stats_result.all()
            
            # Przygotuj dane
            game_stats = []
            total_games = 0
            total_wins = 0
            highest_elo = 1200
            
            for stats, game_type in stats_rows:
                total_games += stats.games_played
                total_wins += stats.games_won
                if stats.elo_rating > highest_elo:
                    highest_elo = stats.elo_rating
                
                rank_info = get_rank_for_elo(stats.elo_rating)
                win_rate = round((stats.games_won / stats.games_played * 100), 1) if stats.games_played > 0 else 0
                
                game_stats.append({
                    'game_type': game_type.name,
                    'elo': round(stats.elo_rating),
                    'rank': rank_info,
                    'games_played': stats.games_played,
                    'games_won': stats.games_won,
                    'games_lost': stats.games_played - stats.games_won,
                    'win_rate': win_rate
                })
            
            # Oblicz globalną rangę
            global_rank = get_rank_for_elo(highest_elo)
            global_win_rate = round((total_wins / total_games * 100), 1) if total_games > 0 else 0
            
            # Znajdź pozycję w rankingu
            position_query = (
                select(func.count())
                .select_from(PlayerGameStats)
                .where(PlayerGameStats.elo_rating > highest_elo)
            )
            pos_result = await session.execute(position_query)
            position = (pos_result.scalar() or 0) + 1
            
            # Sprawdź czy to bot
            is_bot = False
            if user.settings:
                try:
                    settings = json.loads(user.settings)
                    is_bot = settings.get('jest_botem', False)
                except:
                    pass
            
            return {
                'username': user.username,
                'avatar_url': user.avatar_url or 'default_avatar.png',
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'is_bot': is_bot,
                'global_stats': {
                    'elo': round(highest_elo),
                    'rank': global_rank,
                    'position': position,
                    'total_games': total_games,
                    'total_wins': total_wins,
                    'total_losses': total_games - total_wins,
                    'win_rate': global_win_rate
                },
                'game_stats': game_stats
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting player stats: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Błąd pobierania statystyk"
        )


@router.get("/ranks")
async def get_ranks():
    """Pobierz listę wszystkich rang."""
    return {'ranks': RANKS}


@router.post("/ranks/batch")
async def get_ranks_batch(usernames: List[str] = Body(...)):
    """
    Pobierz rangi dla listy graczy.
    Body: ["username1", "username2", ...]
    Returns: {"ranks": {"username1": {rank_info}, ...}}
    """
    ranks = await get_ranks_for_usernames(usernames)
    return {'ranks': ranks}


@router.get("/my-stats")
async def get_my_stats(current_user: dict = Depends(get_current_user)):
    """Pobierz własne statystyki (skrót)."""
    return await get_player_stats(current_user['username'])


# ============================================
# FUNKCJE POMOCNICZE (do użycia w game.py)
# ============================================

async def update_player_stats_after_game(
    winner_usernames: List[str],
    loser_usernames: List[str],
    game_type_name: str,
    is_casual: bool = False
):
    """
    Aktualizuje statystyki graczy po zakończeniu meczu.
    
    Args:
        winner_usernames: Lista nazw zwycięzców
        loser_usernames: Lista nazw przegranych
        game_type_name: Nazwa typu gry (np. "66", "Tysiąc")
        is_casual: Czy gra casual (bez wpływu na ELO)
    """
    try:
        async with async_sessionmaker() as session:
            # Pobierz typ gry (lub stwórz)
            game_type_query = select(GameType).where(GameType.name == game_type_name)
            result = await session.execute(game_type_query)
            game_type = result.scalar_one_or_none()
            
            if not game_type:
                game_type = GameType(name=game_type_name)
                session.add(game_type)
                await session.flush()
            
            # Pobierz wszystkich graczy
            all_usernames = winner_usernames + loser_usernames
            users_query = select(User).where(User.username.in_(all_usernames))
            users_result = await session.execute(users_query)
            users = {u.username: u for u in users_result.scalars().all()}
            
            # Stwórz brakujących użytkowników (np. boty które nie są jeszcze w bazie)
            for username in all_usernames:
                if username not in users:
                    print(f"[📊 Stats] Tworzę użytkownika dla: {username}")
                    new_user = User(
                        username=username,
                        hashed_password="bot_no_password",
                        settings=json.dumps({'jest_botem': True})
                    )
                    session.add(new_user)
                    await session.flush()
                    users[username] = new_user
            
            # Pobierz lub stwórz statystyki dla każdego gracza
            stats_map = {}
            for username in all_usernames:
                user = users[username]
                stats_query = select(PlayerGameStats).where(
                    and_(
                        PlayerGameStats.user_id == user.id,
                        PlayerGameStats.game_type_id == game_type.id
                    )
                )
                stats_result = await session.execute(stats_query)
                stats = stats_result.scalar_one_or_none()
                
                if not stats:
                    stats = PlayerGameStats(
                        user_id=user.id,
                        game_type_id=game_type.id,
                        elo_rating=1200.0,
                        games_played=0,
                        games_won=0
                    )
                    session.add(stats)
                    await session.flush()
                
                stats_map[username] = stats
            
            # Oblicz średnie ELO dla drużyn
            winner_elos = [stats_map[u].elo_rating for u in winner_usernames if u in stats_map]
            loser_elos = [stats_map[u].elo_rating for u in loser_usernames if u in stats_map]
            
            avg_winner_elo = sum(winner_elos) / len(winner_elos) if winner_elos else 1200
            avg_loser_elo = sum(loser_elos) / len(loser_elos) if loser_elos else 1200
            
            # Oblicz zmianę ELO
            elo_gain, elo_loss = calculate_elo_change(avg_winner_elo, avg_loser_elo)
            
            # Aktualizuj statystyki
            for username in winner_usernames:
                if username in stats_map:
                    stats = stats_map[username]
                    stats.games_played += 1
                    stats.games_won += 1
                    if not is_casual:
                        stats.elo_rating = max(100, stats.elo_rating + elo_gain)
                    print(f"📊 {username}: +1 win, ELO {'+' if elo_gain > 0 else ''}{elo_gain if not is_casual else 0}")
            
            for username in loser_usernames:
                if username in stats_map:
                    stats = stats_map[username]
                    stats.games_played += 1
                    if not is_casual:
                        stats.elo_rating = max(100, stats.elo_rating + elo_loss)
                    print(f"📊 {username}: +1 loss, ELO {elo_loss if not is_casual else 0}")
            
            await session.commit()
            print(f"✅ Statystyki zaktualizowane dla {len(all_usernames)} graczy")
            
    except Exception as e:
        print(f"❌ Błąd aktualizacji statystyk: {e}")
        import traceback
        traceback.print_exc()


async def ensure_game_types_exist():
    """Upewnia się że podstawowe typy gier istnieją w bazie."""
    try:
        async with async_sessionmaker() as session:
            # Sprawdź czy są typy gier
            query = select(func.count()).select_from(GameType)
            result = await session.execute(query)
            count = result.scalar()
            
            if count == 0:
                # Dodaj podstawowe typy
                game_types = [
                    GameType(name="66", rules_url="/rules/66"),
                    GameType(name="Tysiąc", rules_url="/rules/tysiac"),
                ]
                session.add_all(game_types)
                await session.commit()
                print("✅ Dodano podstawowe typy gier do bazy")
            
    except Exception as e:
        print(f"⚠️ Błąd inicjalizacji typów gier: {e}")
