"""
Bot Matchmaking Worker
Odpowiedzialność: Autonomiczne zarządzanie botami - tworzenie/dołączanie do lobby
"""
import asyncio
import random
import json
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from database import async_sessionmaker, User
from sqlalchemy import select


# ===========================================
# KONFIGURACJA HARMONOGRAMU BOTÓW
# ===========================================

# Liczba aktywnych botów w zależności od pory dnia
BOT_SCHEDULE = {
    # Godzina (0-23): liczba aktywnych botów
    0: 4,   # Północ - 4 boty
    1: 4,
    2: 4,
    3: 4,
    4: 4,
    5: 4,
    6: 8,   # Rano - 8 botów
    7: 8,
    8: 8,
    9: 8,
    10: 8,
    11: 8,
    12: 12,  # Po południu - 12 botów
    13: 12,
    14: 12,
    15: 12,
    16: 12,
    17: 12,
    18: 18,  # Wieczór - 18 botów (maksimum)
    19: 18,
    20: 18,
    21: 18,
    22: 12,  # Późny wieczór - 12 botów
    23: 8,
}

# Interwał rotacji botów (w sekundach) - co 3 godziny
ROTATION_INTERVAL = 3 * 60 * 60  # 3 godziny

# Minimalna liczba botów zawsze aktywnych (nigdy nie wyłączaj wszystkich)
MIN_ALWAYS_ACTIVE = 2


@dataclass
class BotConfig:
    """Konfiguracja pojedynczego bota"""
    user_id: int
    username: str
    algorytm: str
    avatar_url: str
    
    # Interwały (w sekundach) - każdy bot ma swoje losowe wartości
    min_interval: float = field(default_factory=lambda: random.uniform(20.0, 40.0))
    max_interval: float = field(default_factory=lambda: random.uniform(60.0, 120.0))
    
    # Stan
    is_active: bool = True
    current_lobby_id: Optional[str] = None
    in_game: bool = False


class BotMatchmakingWorker:
    """
    Worker zarządzający autonomicznymi botami.
    Każdy bot działa jako osobny task z losowym interwałem.
    Obsługuje harmonogram godzinowy i rotację botów.
    """
    
    def __init__(self):
        self.bots: Dict[int, BotConfig] = {}
        self.bot_tasks: Dict[int, asyncio.Task] = {}
        self.is_running: bool = False
        self.redis = None
        
        self.matchmaking_enabled: bool = True
        self.min_interval: float = 30.0
        self.max_interval: float = 120.0
        
        self.preferred_game_type: str = "66"
        self.preferred_players: int = 4
        
        # Harmonogram i rotacja
        self.active_bot_ids: Set[int] = set()  # Aktualnie aktywne boty
        self.rotation_task: Optional[asyncio.Task] = None
        self.last_rotation_time: float = 0
    
    async def initialize(self, redis_service):
        """Inicjalizuj worker z Redis service"""
        self.redis = redis_service
        await self._load_bots_from_db()
    
    async def _load_bots_from_db(self):
        """Załaduj wszystkie boty z bazy danych"""
        async with async_sessionmaker() as session:
            query = select(User)
            result = await session.execute(query)
            users = result.scalars().all()
            
            for user in users:
                try:
                    settings = json.loads(user.settings) if user.settings else {}
                    if settings.get('jest_botem'):
                        self.bots[user.id] = BotConfig(
                            user_id=user.id,
                            username=user.username,
                            algorytm=settings.get('algorytm', 'topplayer'),
                            avatar_url=user.avatar_url or 'default_avatar.png'
                        )
                except:
                    pass
    
    # ===========================================
    # HARMONOGRAM I ROTACJA BOTÓW
    # ===========================================
    
    def _get_target_bot_count(self) -> int:
        """Pobierz docelową liczbę botów na podstawie aktualnej godziny"""
        current_hour = datetime.now().hour
        target = BOT_SCHEDULE.get(current_hour, 8)
        # Nie więcej niż mamy botów
        return min(target, len(self.bots))
    
    def _select_bots_to_activate(self, count: int) -> List[int]:
        """
        Wybierz boty do aktywacji.
        Priorytetyzuje boty, które nie są w grze.
        Dodaje losowość dla różnorodności.
        """
        all_bot_ids = list(self.bots.keys())
        
        # Najpierw boty które NIE są w grze (można je wyłączyć/włączyć)
        not_in_game = [bid for bid in all_bot_ids if not self.bots[bid].in_game]
        in_game = [bid for bid in all_bot_ids if self.bots[bid].in_game]
        
        # Losowo przetasuj
        random.shuffle(not_in_game)
        random.shuffle(in_game)
        
        # Wybierz: najpierw te w grze (muszą być aktywne), potem losowe
        selected = in_game.copy()
        
        # Dodaj z puli "nie w grze" aż do osiągnięcia limitu
        for bid in not_in_game:
            if len(selected) >= count:
                break
            selected.append(bid)
        
        return selected[:count]
    
    async def _apply_bot_schedule(self):
        """
        Zastosuj harmonogram - aktywuj/dezaktywuj boty.
        Wywoływane przy starcie i co ROTATION_INTERVAL.
        """
        target_count = self._get_target_bot_count()
        current_hour = datetime.now().hour
        
        # Wybierz boty do aktywacji
        bots_to_activate = set(self._select_bots_to_activate(target_count))
        
        # Znajdź zmiany
        to_start = bots_to_activate - self.active_bot_ids
        to_stop = self.active_bot_ids - bots_to_activate
        
        # Nie zatrzymuj botów które są w grze
        to_stop = {bid for bid in to_stop if not self.bots[bid].in_game}
        
        # Zatrzymaj nadmiarowe boty
        for bot_id in to_stop:
            if bot_id in self.bot_tasks:
                self.bot_tasks[bot_id].cancel()
                try:
                    await self.bot_tasks[bot_id]
                except asyncio.CancelledError:
                    pass
                del self.bot_tasks[bot_id]
                self.bots[bot_id].is_active = False
                print(f"🔴 [{self.bots[bot_id].username}] Dezaktywowany (harmonogram: {target_count} botów o {current_hour}:00)")
        
        # Uruchom nowe boty
        for bot_id in to_start:
            if bot_id not in self.bot_tasks:
                bot = self.bots[bot_id]
                bot.is_active = True
                task = asyncio.create_task(self._bot_loop(bot))
                self.bot_tasks[bot_id] = task
                print(f"🟢 [{bot.username}] Aktywowany (harmonogram: {target_count} botów o {current_hour}:00)")
        
        # Aktualizuj set aktywnych
        self.active_bot_ids = set(self.bot_tasks.keys())
        self.last_rotation_time = time.time()
        
        print(f"📅 Harmonogram: {len(self.active_bot_ids)}/{len(self.bots)} botów aktywnych (cel: {target_count}, godzina: {current_hour}:00)")
    
    async def _rotation_loop(self):
        """Pętla rotacji botów - wywoływana co ROTATION_INTERVAL"""
        while self.is_running:
            try:
                # Czekaj do następnej rotacji
                await asyncio.sleep(ROTATION_INTERVAL)
                
                if not self.is_running:
                    break
                
                print(f"\n🔄 === ROTACJA BOTÓW ===")
                await self._apply_bot_schedule()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Błąd rotacji botów: {e}")
                await asyncio.sleep(60)  # Czekaj minutę przed ponowną próbą
    
    async def _sync_bot_lobby_states(self):
        """Synchronizuj stan botów z Redis"""
        if not self.redis:
            return
        
        try:
            lobbies = await self.redis.list_lobbies()
            
            for lobby in lobbies:
                lobby_id = lobby.get('id_gry')
                status = lobby.get('status_partii', '')
                
                for slot in lobby.get('slots', []):
                    user_id = slot.get('id_uzytkownika')
                    if user_id and user_id in self.bots:
                        bot = self.bots[user_id]
                        
                        if status == 'ZAKONCZONA':
                            await self._remove_bot_from_lobby(bot, lobby_id, lobby)
                        elif status in ['LOBBY', 'W_GRZE']:
                            bot.current_lobby_id = lobby_id
                            bot.in_game = (status == 'W_GRZE')
        except Exception as e:
            pass
    
    async def _remove_bot_from_lobby(self, bot: BotConfig, lobby_id: str, lobby: dict):
        """Usuń bota z lobby"""
        try:
            slots = lobby.get('slots', [])
            changed = False
            
            for slot in slots:
                if slot.get('id_uzytkownika') == bot.user_id:
                    slot['typ'] = 'pusty'
                    slot['id_uzytkownika'] = None
                    slot['nazwa'] = None
                    slot['ready'] = False
                    slot['avatar_url'] = None
                    slot['is_host'] = False
                    changed = True
                    break
            
            if changed:
                await self.redis.save_lobby(lobby_id, lobby)
            
            bot.current_lobby_id = None
            bot.in_game = False
        except:
            pass
    
    async def start(self):
        """Uruchom system botów z harmonogramem"""
        if self.is_running:
            return
        
        await self._sync_bot_lobby_states()
        
        self.is_running = True
        
        # Zastosuj harmonogram zamiast uruchamiać wszystkie boty
        print(f"\n🤖 === START SYSTEMU BOTÓW ===")
        print(f"🤖 Załadowano {len(self.bots)} botów")
        await self._apply_bot_schedule()
        
        # Uruchom pętlę rotacji
        self.rotation_task = asyncio.create_task(self._rotation_loop())
    
    async def stop(self):
        """Zatrzymaj wszystkie boty i rotację"""
        self.is_running = False
        
        # Zatrzymaj rotację
        if self.rotation_task:
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass
            self.rotation_task = None
        
        # Zatrzymaj wszystkie boty
        for user_id, task in self.bot_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.bot_tasks.clear()
        self.active_bot_ids.clear()
        print("🛑 System botów zatrzymany")
    
    async def _bot_loop(self, bot: BotConfig):
        """Główna pętla pojedynczego bota"""
        initial_delay = random.uniform(5.0, 60.0)
        await asyncio.sleep(initial_delay)
        
        # LOG: Start bota
        print(f"🤖 [{bot.username}] Start (algorytm: {bot.algorytm}, interwał: {bot.min_interval:.0f}-{bot.max_interval:.0f}s)")
        
        while self.is_running and bot.is_active:
            try:
                interval = random.uniform(bot.min_interval, bot.max_interval)
                await asyncio.sleep(interval)
                
                if not self.matchmaking_enabled:
                    continue
                
                if bot.current_lobby_id:
                    lobby = await self.redis.get_lobby(bot.current_lobby_id)
                    
                    if not lobby:
                        bot.current_lobby_id = None
                        bot.in_game = False
                        continue
                    
                    status = lobby.get('status_partii', '')
                    
                    if status == 'W_GRZE':
                        bot.in_game = True
                        continue
                    elif status == 'ZAKONCZONA':
                        await self._remove_bot_from_lobby(bot, bot.current_lobby_id, lobby)
                        continue
                    elif status == 'LOBBY':
                        bot.in_game = False
                        await self._try_start_game(bot, lobby)
                        continue
                    else:
                        bot.current_lobby_id = None
                        bot.in_game = False
                        continue
                
                await self._matchmake(bot)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(10)
    
    async def _matchmake(self, bot: BotConfig):
        """Znajdź lub stwórz lobby dla bota"""
        lobbies = await self.redis.list_lobbies()
        
        # Sprawdź czy bot nie jest już gdzieś
        for lobby in lobbies:
            status = lobby.get('status_partii', '')
            if status not in ['LOBBY', 'W_GRZE']:
                continue
            
            for slot in lobby.get('slots', []):
                if slot.get('id_uzytkownika') == bot.user_id:
                    lobby_id = lobby.get('id_gry')
                    bot.current_lobby_id = lobby_id
                    bot.in_game = (status == 'W_GRZE')
                    return
        
        # Filtruj dostępne lobby
        available = []
        for lobby in lobbies:
            if lobby.get('status_partii') != 'LOBBY':
                continue
            
            opcje = lobby.get('opcje', {})
            if opcje.get('typ_gry') != self.preferred_game_type:
                continue
            
            slots = lobby.get('slots', [])
            empty_slots = [s for s in slots if s.get('typ') == 'pusty']
            if empty_slots:
                available.append(lobby)
        
        if available:
            lobby = random.choice(available)
            await self._join_lobby(bot, lobby)
        else:
            if random.random() < 0.3:
                await self._create_lobby(bot)
    
    async def _join_lobby(self, bot: BotConfig, lobby: dict):
        """Bot dołącza do istniejącego lobby"""
        lobby_id = lobby.get('id_gry')
        
        if bot.current_lobby_id and bot.current_lobby_id != lobby_id:
            return
        
        lobby = await self.redis.get_lobby(lobby_id)
        if not lobby or lobby.get('status_partii') != 'LOBBY':
            return
        
        slots = lobby.get('slots', [])
        
        for slot in slots:
            if slot.get('id_uzytkownika') == bot.user_id:
                bot.current_lobby_id = lobby_id
                return
        
        empty_slot = None
        for slot in slots:
            if slot.get('typ') == 'pusty':
                empty_slot = slot
                break
        
        if not empty_slot:
            return
        
        empty_slot['typ'] = 'gracz'
        empty_slot['id_uzytkownika'] = bot.user_id
        empty_slot['nazwa'] = bot.username
        empty_slot['ready'] = False
        empty_slot['avatar_url'] = bot.avatar_url
        
        await self.redis.save_lobby(lobby_id, lobby)
        bot.current_lobby_id = lobby_id
        
        # LOG: Dołączył do lobby
        print(f"🤖 [{bot.username}] Dołączył do lobby {lobby_id}")
        
        await self._broadcast_lobby_update(lobby_id, lobby, f"{bot.username} dołączył do lobby")
        
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)
        
        lobby = await self.redis.get_lobby(lobby_id)
        if not lobby or lobby.get('status_partii') != 'LOBBY':
            return
        
        for slot in lobby.get('slots', []):
            if slot.get('id_uzytkownika') == bot.user_id:
                slot['ready'] = True
                break
        
        await self.redis.save_lobby(lobby_id, lobby)
        
        # LOG: Jest gotowy
        print(f"🤖 [{bot.username}] Jest gotowy w lobby {lobby_id}")
        
        await self._broadcast_lobby_update(lobby_id, lobby, f"{bot.username} jest gotowy")
        await self._try_start_game(bot, lobby)
    
    async def _create_lobby(self, bot: BotConfig):
        """Bot tworzy nowe lobby"""
        if bot.current_lobby_id:
            return
        
        game_id = str(uuid.uuid4())[:8]
        
        # 10% szans na lobby 3-osobowe dla gry 66
        if self.preferred_game_type == "66" and random.random() < 0.10:
            num_players = 3
            print(f"🎲 [{bot.username}] Tworzy lobby 3-osobowe (10% szans)")
        else:
            num_players = self.preferred_players
        
        slots = []
        for i in range(num_players):
            if i == 0:
                slots.append({
                    'numer_gracza': i,
                    'typ': 'gracz',
                    'id_uzytkownika': bot.user_id,
                    'nazwa': bot.username,
                    'is_host': True,
                    'ready': False,
                    'avatar_url': bot.avatar_url
                })
            else:
                slots.append({
                    'numer_gracza': i,
                    'typ': 'pusty',
                    'id_uzytkownika': None,
                    'nazwa': None,
                    'is_host': False,
                    'ready': False,
                    'avatar_url': None
                })
        
        lobby_data = {
            "id_gry": game_id,
            "id": f"Lobby_{game_id[:4]}",
            "nazwa": f"Gra {bot.username}",
            "max_graczy": num_players,
            "status_partii": "LOBBY",
            "slots": slots,
            "opcje": {
                "tryb_gry": f"{num_players}p",
                "rankingowa": True,
                "typ_gry": self.preferred_game_type,
                "haslo": None
            },
            "host_id": bot.user_id,
            "tryb_lobby": "online",
            "kicked_players": [],
            "created_at": time.time()
        }
        
        await self.redis.save_lobby(game_id, lobby_data)
        bot.current_lobby_id = game_id
        
        # LOG: Stworzył lobby
        print(f"🤖 [{bot.username}] Stworzył lobby {game_id}")
        
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)
        
        lobby_data = await self.redis.get_lobby(game_id)
        if not lobby_data or lobby_data.get('status_partii') != 'LOBBY':
            return
        
        for slot in lobby_data.get('slots', []):
            if slot.get('id_uzytkownika') == bot.user_id:
                slot['ready'] = True
                break
        
        await self.redis.save_lobby(game_id, lobby_data)
        
        # LOG: Jest gotowy
        print(f"🤖 [{bot.username}] Jest gotowy w lobby {game_id}")
    
    async def _try_start_game(self, bot: BotConfig, lobby: dict):
        """Sprawdź czy lobby jest pełne i wystartuj grę"""
        slots = lobby.get('slots', [])
        lobby_id = lobby.get('id_gry')
        
        occupied_slots = [s for s in slots if s.get('typ') in ['gracz', 'bot']]
        max_players = lobby.get('max_graczy', 4)
        
        if len(occupied_slots) < max_players:
            return
        
        all_ready = all(s.get('ready', False) for s in occupied_slots)
        if not all_ready:
            return
        
        is_host = False
        for slot in slots:
            if slot.get('id_uzytkownika') == bot.user_id and slot.get('is_host'):
                is_host = True
                break
        
        if not is_host:
            return
        
        delay = random.uniform(2.0, 5.0)
        print(f"🤖 [{bot.username}] Wszyscy gotowi - start za {delay:.1f}s")
        await asyncio.sleep(delay)
        
        lobby = await self.redis.get_lobby(lobby_id)
        if not lobby or lobby.get('status_partii') != 'LOBBY':
            return
        
        slots = lobby.get('slots', [])
        occupied_slots = [s for s in slots if s.get('typ') in ['gracz', 'bot']]
        if len(occupied_slots) < max_players:
            return
        
        all_ready = all(s.get('ready', False) for s in occupied_slots)
        if not all_ready:
            return
        
        # LOG: Startuje grę
        print(f"🤖 [{bot.username}] Startuje grę w lobby {lobby_id}")
        
        lobby['status_partii'] = 'W_GRZE'
        await self.redis.save_lobby(lobby_id, lobby)
        
        await self._broadcast_game_start(lobby_id, lobby)
        
        try:
            from services.game_service import GameService
            game_service = GameService()
            await game_service.initialize_game(lobby_id, lobby, self.redis)
            bot.in_game = True
        except Exception as e:
            lobby['status_partii'] = 'LOBBY'
            await self.redis.save_lobby(lobby_id, lobby)
    
    async def _broadcast_lobby_update(self, lobby_id: str, lobby: dict, message: str):
        """Wyślij aktualizację lobby przez WebSocket"""
        try:
            from routers.websocket_router import manager
            await manager.broadcast(lobby_id, {
                'type': 'lobby_update',
                'lobby': lobby,
                'message': message
            })
        except:
            pass
    
    async def _broadcast_game_start(self, lobby_id: str, lobby: dict):
        """Wyślij informację o starcie gry przez WebSocket"""
        try:
            from routers.websocket_router import manager
            await manager.broadcast(lobby_id, {
                'type': 'game_start',
                'lobby_id': lobby_id,
                'players': [s['nazwa'] for s in lobby['slots'] if s['typ'] != 'pusty']
            })
        except:
            pass
    
    # ==========================================
    # PUBLIC METHODS
    # ==========================================
    
    def mark_bot_game_ended(self, username: str):
        """Oznacz że gra bota się zakończyła"""
        for bot in self.bots.values():
            if bot.username == username:
                bot.current_lobby_id = None
                bot.in_game = False
                return True
        return False
    
    def is_bot(self, username: str) -> bool:
        """Sprawdź czy gracz o danej nazwie jest botem"""
        for bot in self.bots.values():
            if bot.username == username:
                return True
        return False
    
    def get_bot_algorithm(self, username: str) -> Optional[str]:
        """Pobierz algorytm bota"""
        for bot in self.bots.values():
            if bot.username == username:
                return bot.algorytm
        return None
    
    # ==========================================
    # ADMIN API
    # ==========================================
    
    async def force_bot_to_lobby(self, bot_username: str, lobby_id: str) -> bool:
        """Admin: Wymuś dołączenie bota do konkretnego lobby"""
        bot = None
        for b in self.bots.values():
            if b.username == bot_username:
                bot = b
                break
        
        if not bot:
            return False
        
        if bot.in_game:
            return False
        
        lobby = await self.redis.get_lobby(lobby_id)
        if not lobby:
            return False
        
        if bot.current_lobby_id and bot.current_lobby_id != lobby_id:
            await self._leave_lobby(bot)
        
        await self._join_lobby(bot, lobby)
        return True
    
    async def _leave_lobby(self, bot: BotConfig):
        """Bot opuszcza lobby"""
        if not bot.current_lobby_id:
            return
        
        lobby = await self.redis.get_lobby(bot.current_lobby_id)
        if not lobby:
            bot.current_lobby_id = None
            return
        
        for slot in lobby.get('slots', []):
            if slot.get('id_uzytkownika') == bot.user_id:
                slot['typ'] = 'pusty'
                slot['id_uzytkownika'] = None
                slot['nazwa'] = None
                slot['ready'] = False
                slot['avatar_url'] = None
                break
        
        await self.redis.save_lobby(bot.current_lobby_id, lobby)
        bot.current_lobby_id = None
    
    def set_matchmaking_enabled(self, enabled: bool):
        """Admin: Włącz/wyłącz matchmaking"""
        self.matchmaking_enabled = enabled
    
    def set_bot_active(self, bot_username: str, active: bool) -> bool:
        """Admin: Włącz/wyłącz konkretnego bota (nie można wyłączyć podczas gry)"""
        for bot in self.bots.values():
            if bot.username == bot_username:
                # Zabezpieczenie: nie wyłączaj bota który jest w grze
                if not active and bot.in_game:
                    print(f"⚠️ Nie można wyłączyć bota {bot_username} - jest w grze")
                    return False
                bot.is_active = active
                return True
        return False
    
    def get_status(self) -> dict:
        """Admin: Pobierz status wszystkich botów"""
        current_hour = datetime.now().hour
        target_count = self._get_target_bot_count()
        next_rotation = ROTATION_INTERVAL - (time.time() - self.last_rotation_time) if self.last_rotation_time else 0
        
        return {
            "matchmaking_enabled": self.matchmaking_enabled,
            "is_running": self.is_running,
            "total_bots": len(self.bots),
            "active_bots": len(self.active_bot_ids),
            "active_tasks": len(self.bot_tasks),
            "schedule": {
                "current_hour": current_hour,
                "target_bots": target_count,
                "next_rotation_in": f"{int(next_rotation // 60)}m {int(next_rotation % 60)}s" if next_rotation > 0 else "now",
                "rotation_interval": f"{ROTATION_INTERVAL // 3600}h"
            },
            "config": {
                "min_interval": self.min_interval,
                "max_interval": self.max_interval,
                "preferred_game_type": self.preferred_game_type,
                "preferred_players": self.preferred_players
            },
            "bots": [
                {
                    "username": bot.username,
                    "algorytm": bot.algorytm,
                    "is_active": bot.user_id in self.active_bot_ids,
                    "in_game": bot.in_game,
                    "current_lobby": bot.current_lobby_id,
                    "interval": f"{bot.min_interval:.0f}-{bot.max_interval:.0f}s"
                }
                for bot in self.bots.values()
            ]
        }


# Singleton instance
bot_matchmaking = BotMatchmakingWorker()
