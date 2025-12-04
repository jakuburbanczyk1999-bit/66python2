"""
Service: Disconnect Handler
Odpowiedzialność: Obsługa rozłączeń graczy podczas gry
- Timer na powrót (60 sekund)
- Zakończenie gry po timeout
- Aktualizacja rankingu (przegrany traci punkty)
"""
import asyncio
import time
from typing import Dict, Optional, Callable
from dataclasses import dataclass

from services.redis_service import RedisService


@dataclass
class DisconnectInfo:
    """Info o rozłączonym graczu"""
    player_name: str
    game_id: str
    disconnect_time: float
    task: Optional[asyncio.Task] = None


class DisconnectService:
    """
    Serwis obsługujący rozłączenia graczy podczas gry.
    
    Gdy gracz się rozłączy:
    1. Uruchamia timer 60 sekund
    2. Jeśli gracz wróci - anuluje timer
    3. Jeśli nie wróci - kończy grę, gracz przegrywa
    """
    
    # Czas na powrót w sekundach
    RECONNECT_TIMEOUT = 60
    
    def __init__(self):
        # Słownik: (game_id, player_name) -> DisconnectInfo
        self.disconnected_players: Dict[tuple, DisconnectInfo] = {}
        # Callback do zakończenia gry (ustawiony przez websocket_router)
        self.on_game_forfeit: Optional[Callable] = None
    
    def set_forfeit_callback(self, callback: Callable):
        """Ustawia callback wywoływany gdy gracz przekroczy timeout"""
        self.on_game_forfeit = callback
    
    async def player_disconnected(
        self,
        game_id: str,
        player_name: str,
        redis: RedisService
    ) -> bool:
        """
        Wywoływane gdy gracz się rozłączy podczas gry.
        
        Args:
            game_id: ID gry
            player_name: Nazwa gracza
            redis: Redis service
        
        Returns:
            True jeśli gracz był w grze i uruchomiono timer
        """
        # Sprawdź czy gra jest w toku
        lobby = await redis.get_lobby(game_id)
        if not lobby:
            return False
        
        if lobby.get('status_partii') != 'W_GRZE':
            print(f"[Disconnect] {player_name} rozłączył się z lobby (nie w grze)")
            return False
        
        # Sprawdź czy gracz jest w tej grze
        slots = lobby.get('slots', [])
        player_in_game = any(
            s.get('nazwa') == player_name and s.get('typ') == 'gracz' 
            for s in slots
        )
        
        if not player_in_game:
            print(f"[Disconnect] {player_name} nie jest graczem w grze {game_id}")
            return False
        
        key = (game_id, player_name)
        
        # Jeśli już jest rozłączony (nie powinno się zdarzyć)
        if key in self.disconnected_players:
            print(f"[Disconnect] {player_name} już jest na liście rozłączonych")
            return True
        
        # Zapisz info o rozłączeniu
        disconnect_info = DisconnectInfo(
            player_name=player_name,
            game_id=game_id,
            disconnect_time=time.time()
        )
        
        # Uruchom timer
        task = asyncio.create_task(
            self._timeout_handler(game_id, player_name, redis)
        )
        disconnect_info.task = task
        
        self.disconnected_players[key] = disconnect_info
        
        # Zapisz info o rozłączeniu w Redis (dla frontendu)
        if 'disconnected_players' not in lobby:
            lobby['disconnected_players'] = {}
        lobby['disconnected_players'][player_name] = {
            'disconnect_time': disconnect_info.disconnect_time,
            'timeout_at': disconnect_info.disconnect_time + self.RECONNECT_TIMEOUT
        }
        await redis.save_lobby(game_id, lobby)
        
        print(f"⏱️ [Disconnect] {player_name} rozłączył się z gry {game_id}. Ma {self.RECONNECT_TIMEOUT}s na powrót.")
        
        return True
    
    async def player_reconnected(
        self,
        game_id: str,
        player_name: str,
        redis: RedisService
    ) -> bool:
        """
        Wywoływane gdy gracz ponownie się połączy.
        
        Args:
            game_id: ID gry
            player_name: Nazwa gracza
            redis: Redis service
        
        Returns:
            True jeśli gracz wrócił przed timeout
        """
        key = (game_id, player_name)
        
        if key not in self.disconnected_players:
            # Gracz nie był rozłączony (lub już timeout)
            return True
        
        disconnect_info = self.disconnected_players[key]
        
        # Anuluj timer
        if disconnect_info.task and not disconnect_info.task.done():
            disconnect_info.task.cancel()
            try:
                await disconnect_info.task
            except asyncio.CancelledError:
                pass
        
        # Usuń z listy rozłączonych
        del self.disconnected_players[key]
        
        # Usuń z Redis
        lobby = await redis.get_lobby(game_id)
        if lobby and 'disconnected_players' in lobby:
            lobby['disconnected_players'].pop(player_name, None)
            await redis.save_lobby(game_id, lobby)
        
        elapsed = time.time() - disconnect_info.disconnect_time
        print(f"✅ [Disconnect] {player_name} wrócił do gry {game_id} po {elapsed:.1f}s")
        
        return True
    
    async def _timeout_handler(
        self,
        game_id: str,
        player_name: str,
        redis: RedisService
    ):
        """
        Handler wywoływany po upływie czasu na powrót.
        Kończy grę - rozłączony gracz przegrywa.
        """
        try:
            # Czekaj na timeout
            await asyncio.sleep(self.RECONNECT_TIMEOUT)
            
            key = (game_id, player_name)
            
            # Sprawdź czy gracz nadal jest rozłączony
            if key not in self.disconnected_players:
                return
            
            print(f"⏰ [Disconnect] TIMEOUT! {player_name} nie wrócił do gry {game_id}")
            
            # Usuń z listy
            del self.disconnected_players[key]
            
            # Zakończ grę - gracz przegrywa
            await self._forfeit_game(game_id, player_name, redis)
            
        except asyncio.CancelledError:
            # Timer anulowany (gracz wrócił)
            pass
        except Exception as e:
            print(f"❌ [Disconnect] Błąd timeout handler: {e}")
    
    async def _forfeit_game(
        self,
        game_id: str,
        disconnected_player: str,
        redis: RedisService
    ):
        """
        Kończy grę z powodu rozłączenia gracza.
        Rozłączony gracz przegrywa, przeciwnicy wygrywają.
        
        Args:
            game_id: ID gry
            disconnected_player: Nazwa gracza który się rozłączył
            redis: Redis service
        """
        try:
            lobby = await redis.get_lobby(game_id)
            if not lobby:
                print(f"[Forfeit] Lobby {game_id} nie istnieje")
                return
            
            if lobby.get('status_partii') != 'W_GRZE':
                print(f"[Forfeit] Gra {game_id} nie jest już w toku")
                return
            
            slots = lobby.get('slots', [])
            opcje = lobby.get('opcje', {})
            is_ranked = opcje.get('rankingowa', False)
            
            # Znajdź graczy
            all_players = [s for s in slots if s.get('typ') == 'gracz']
            winners = [s for s in all_players if s.get('nazwa') != disconnected_player]
            loser = next((s for s in all_players if s.get('nazwa') == disconnected_player), None)
            
            print(f"[Forfeit] Gra {game_id} zakończona przez rozłączenie {disconnected_player}")
            print(f"[Forfeit] Zwycięzcy: {[w.get('nazwa') for w in winners]}")
            
            # Aktualizuj ranking jeśli gra rankingowa
            if is_ranked and loser:
                await self._update_ranking_forfeit(
                    winners=[w.get('nazwa') for w in winners],
                    loser=loser.get('nazwa'),
                    redis=redis
                )
            
            # Zmień status gry
            lobby['status_partii'] = 'ZAKONCZONA'
            lobby['forfeit'] = {
                'player': disconnected_player,
                'reason': 'disconnect_timeout',
                'timestamp': time.time()
            }
            lobby['winner'] = ', '.join([w.get('nazwa') for w in winners]) if winners else None
            
            # Usuń disconnected_players info
            lobby.pop('disconnected_players', None)
            
            await redis.save_lobby(game_id, lobby)
            
            # Usuń silnik gry
            await redis.delete_game_engine(game_id)
            
            # Wywołaj callback (broadcast do graczy)
            if self.on_game_forfeit:
                await self.on_game_forfeit(
                    game_id=game_id,
                    disconnected_player=disconnected_player,
                    winners=[w.get('nazwa') for w in winners]
                )
            
            print(f"✅ [Forfeit] Gra {game_id} zakończona, lobby zapisane")
            
        except Exception as e:
            print(f"❌ [Forfeit] Błąd: {e}")
            import traceback
            traceback.print_exc()
    
    async def _update_ranking_forfeit(
        self,
        winners: list,
        loser: str,
        redis: RedisService
    ):
        """
        Aktualizuje ranking po walkowerze.
        Przegrany traci punkty, zwycięzcy zyskują.
        
        Args:
            winners: Lista nazw zwycięzców
            loser: Nazwa przegranego
            redis: Redis service
        """
        try:
            from database import async_sessionmaker, User
            from sqlalchemy import select
            
            # Punkty za walkower
            FORFEIT_LOSS = -25  # Przegrany traci
            FORFEIT_WIN = 10    # Każdy zwycięzca zyskuje
            
            async with async_sessionmaker() as session:
                # Aktualizuj przegranego
                query = select(User).where(User.username == loser)
                result = await session.execute(query)
                loser_user = result.scalar_one_or_none()
                
                if loser_user:
                    current_elo = loser_user.elo or 1000
                    new_elo = max(0, current_elo + FORFEIT_LOSS)
                    loser_user.elo = new_elo
                    print(f"[Ranking] {loser}: {current_elo} → {new_elo} (walkower)")
                
                # Aktualizuj zwycięzców
                for winner_name in winners:
                    query = select(User).where(User.username == winner_name)
                    result = await session.execute(query)
                    winner_user = result.scalar_one_or_none()
                    
                    if winner_user:
                        current_elo = winner_user.elo or 1000
                        new_elo = current_elo + FORFEIT_WIN
                        winner_user.elo = new_elo
                        print(f"[Ranking] {winner_name}: {current_elo} → {new_elo} (walkower)")
                
                await session.commit()
                
        except Exception as e:
            print(f"❌ [Ranking] Błąd aktualizacji rankingu: {e}")
    
    def is_player_disconnected(self, game_id: str, player_name: str) -> bool:
        """Sprawdź czy gracz jest rozłączony"""
        return (game_id, player_name) in self.disconnected_players
    
    def get_disconnect_info(self, game_id: str, player_name: str) -> Optional[DisconnectInfo]:
        """Pobierz info o rozłączeniu gracza"""
        return self.disconnected_players.get((game_id, player_name))
    
    def get_time_remaining(self, game_id: str, player_name: str) -> Optional[float]:
        """Ile sekund zostało graczowi na powrót"""
        info = self.get_disconnect_info(game_id, player_name)
        if not info:
            return None
        
        elapsed = time.time() - info.disconnect_time
        remaining = self.RECONNECT_TIMEOUT - elapsed
        return max(0, remaining)
    
    async def cleanup_game(self, game_id: str):
        """Wyczyść wszystkie timery dla danej gry"""
        keys_to_remove = [
            key for key in self.disconnected_players 
            if key[0] == game_id
        ]
        
        for key in keys_to_remove:
            info = self.disconnected_players[key]
            if info.task and not info.task.done():
                info.task.cancel()
                try:
                    await info.task
                except asyncio.CancelledError:
                    pass
            del self.disconnected_players[key]
        
        if keys_to_remove:
            print(f"[Disconnect] Wyczyszczono {len(keys_to_remove)} timerów dla gry {game_id}")


# Singleton instance
disconnect_service = DisconnectService()
