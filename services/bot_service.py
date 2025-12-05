"""
Service: Boty
Odpowiedzialność: Automatyczne wykonywanie akcji botów z wykorzystaniem MCTS i osobowości
"""
import asyncio
import traceback
import json
from typing import Any, Optional, Dict
from enum import Enum

from services.redis_service import RedisService
from routers.websocket_router import manager

# Import systemu botów z nowym MCTS i osobowościami
from boty import (
    stworz_bota,
    DOSTEPNE_ALGORYTMY,
    MCTS_Bot,
    AdvancedHeuristicBot,
    RandomBot,
    wybierz_akcje_dla_bota_testowego  # Fallback dla starych botów
)
from boty_tysiac import wybierz_akcje_dla_bota_testowego_tysiac

# ============================================
# HELPER FUNCTIONS
# ============================================

def convert_enums_to_strings(obj):
    """Konwertuje wszystkie Enumy i obiekty Karta w obiekcie na stringi dla JSON serialization"""
    from silnik_gry import Karta as Karta66
    from silnik_tysiac import Karta as KartaTysiac
    
    if isinstance(obj, dict):
        return {k: convert_enums_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_enums_to_strings(item) for item in obj]
    elif isinstance(obj, Enum):
        return obj.name
    elif isinstance(obj, (Karta66, KartaTysiac)):
        return str(obj)
    else:
        return obj


# Cache botów - żeby nie tworzyć nowych instancji za każdym razem
_bot_cache: Dict[str, Any] = {}


def get_or_create_bot(algorytm: str) -> Any:
    """
    Pobiera bota z cache lub tworzy nowego.
    """
    global _bot_cache
    
    if algorytm not in _bot_cache:
        bot = stworz_bota(algorytm)
        if bot:
            _bot_cache[algorytm] = bot
        else:
            _bot_cache[algorytm] = stworz_bota('topplayer')
    
    return _bot_cache[algorytm]


class BotService:
    """Service do obsługi botów z MCTS i osobowościami"""
    
    def __init__(self):
        # Limit iteracji musi być wystarczający dla pełnego meczu:
        # - 1 runda = ~35 iteracji (deklaracje + lufy + 24 karty + 6 finalizacji)
        # - Mecz do 66 pkt = 10-15 rund = 350-500 iteracji
        self.max_iterations = 1000
        self.bot_delay = 0.8  # Opóźnienie między ruchami botów (sekundy)
        self.mcts_time_limit = 1.0  # Limit czasu dla MCTS (sekundy)
    
    def _convert_karty_w_akcji(self, akcja: Any) -> Any:
        """Konwertuje obiekty Karta na stringi w akcji (rekurencyjnie)."""
        from silnik_gry import Karta as Karta66
        from silnik_tysiac import Karta as KartaTysiac
        
        if isinstance(akcja, (Karta66, KartaTysiac)):
            return str(akcja)
        elif isinstance(akcja, dict):
            return {k: self._convert_karty_w_akcji(v) for k, v in akcja.items()}
        elif isinstance(akcja, list):
            return [self._convert_karty_w_akcji(item) for item in akcja]
        else:
            return akcja
    
    async def get_bot_algorithm(self, player_id: str, redis: RedisService) -> str:
        """Pobiera algorytm bota z bazy danych."""
        try:
            from database import async_sessionmaker, User
            from sqlalchemy import select
            
            async with async_sessionmaker() as session:
                query = select(User).where(User.username == player_id)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if user and user.settings:
                    settings = json.loads(user.settings)
                    if settings.get('jest_botem'):
                        algorytm = settings.get('algorytm', 'topplayer')
                        if algorytm in DOSTEPNE_ALGORYTMY:
                            return algorytm
        except Exception as e:
            pass
        
        return 'topplayer'
    
    def _execute_bot_action_mcts(self, bot: Any, engine: Any, player_id: str) -> Optional[dict]:
        """Wykonuje akcję bota używając MCTS lub innego algorytmu."""
        try:
            if isinstance(bot, MCTS_Bot):
                akcja = bot.znajdz_najlepszy_ruch(engine, player_id, limit_czasu_s=self.mcts_time_limit)
            elif isinstance(bot, AdvancedHeuristicBot):
                akcja = bot.znajdz_najlepszy_ruch(engine, player_id)
            elif isinstance(bot, RandomBot):
                akcja = bot.znajdz_najlepszy_ruch(engine, player_id)
            else:
                return None
            
            return akcja if akcja else None
            
        except Exception as e:
            return None
    
    async def process_bot_actions(self, game_id: str, engine: Any, redis: RedisService) -> None:
        """
        Automatycznie wykonuje akcje botów dopóki jest ich kolej.
        """
        iteration = 0
        first_action = True
        
        while iteration < self.max_iterations:
            iteration += 1
            
            state = engine.game_state
            kolej_idx = state.kolej_gracza_idx
            
            if kolej_idx is None:
                break
            
            current_player = state.gracze[kolej_idx]
            player_id = str(current_player.nazwa).strip()
            
            # Sprawdź czy to bot
            is_bot = await self._is_registered_bot_by_name(player_id)
            
            if not is_bot:
                break
            
            # Delay PRZED akcją bota
            if first_action:
                await asyncio.sleep(0.8)
                first_action = False
            else:
                await asyncio.sleep(self.bot_delay)
            
            # Pobierz algorytm bota
            algorytm = await self.get_bot_algorithm(player_id, redis)
            
            # Wykryj typ gry
            from engines.tysiac_engine import TysiacEngine
            is_tysiac = isinstance(engine, TysiacEngine)
            
            bot_action = None
            
            if is_tysiac:
                typ_akcji, parametry = wybierz_akcje_dla_bota_testowego_tysiac(current_player, state)
                bot_action = self._convert_old_bot_action(typ_akcji, parametry)
            else:
                bot = get_or_create_bot(algorytm)
                if bot:
                    bot_action = self._execute_bot_action_mcts(bot, engine, player_id)
                
                if not bot_action:
                    typ_akcji, parametry = wybierz_akcje_dla_bota_testowego(current_player, state)
                    bot_action = self._convert_old_bot_action(typ_akcji, parametry)
            
            if not bot_action:
                break
            
            # Konwertuj karty na stringi
            bot_action = self._convert_karty_w_akcji(bot_action)
            
            # LOG: Zagranie karty
            if bot_action.get('typ') == 'zagraj_karte':
                print(f"🃏 [{player_id}] gra: {bot_action.get('karta')}")
            
            try:
                # Wykonaj akcję
                action_result = engine.perform_action(player_id, bot_action)
                
                # Zapisz silnik
                await redis.save_game_engine(game_id, engine)
                
                # Przygotuj publiczny stan (bez kart) dla dymków akcji
                public_state = {
                    'faza': state.faza.name if hasattr(state.faza, 'name') else str(state.faza),
                    'rece_graczy': {g.nazwa: len(g.reka) for g in state.gracze},
                    'kolej_gracza': state.gracze[state.kolej_gracza_idx].nazwa if state.kolej_gracza_idx is not None else None
                }
                
                # Broadcast akcji bota
                await manager.broadcast(game_id, {
                    'type': 'bot_action',
                    'player': player_id,
                    'action': convert_enums_to_strings(bot_action),
                    'state': public_state
                })
                
                # Wyślij spersonalizowany stan każdemu graczowi
                await manager.broadcast_state_update(game_id)
                
                # Broadcast meldunku jeśli był
                if action_result and action_result.get('meldunek_pkt', 0) > 0:
                    meldunek_pkt = action_result.get('meldunek_pkt')
                    await manager.broadcast(game_id, {
                        'type': 'bot_action',
                        'player': player_id,
                        'action': convert_enums_to_strings({
                            'typ': 'meldunek',
                            'punkty': meldunek_pkt
                        })
                    })
                
                # Auto-finalizacja lewy
                if (hasattr(state, 'lewa_do_zamkniecia') and state.lewa_do_zamkniecia):
                    await asyncio.sleep(1.5)
                    state.finalizuj_lewe()
                    await redis.save_game_engine(game_id, engine)
                    
                    await manager.broadcast(game_id, {
                        'type': 'trick_finalized'
                    })
                    await manager.broadcast_state_update(game_id)
                
            except Exception as e:
                print(f"[Bot] Błąd akcji: {e}")
                break
        
        # === AUTOMATYCZNE PRZEJŚCIE DO NOWEJ RUNDY ===
        await self._auto_next_round_if_all_bots(game_id, engine, redis)
    
    def _convert_old_bot_action(self, typ_akcji: str, parametry: Any) -> Optional[dict]:
        """Konwertuje stary format akcji bota testowego na nowy format."""
        from silnik_gry import Karta as Karta66
        from silnik_tysiac import Karta as KartaTysiac
        
        if typ_akcji == 'karta':
            if isinstance(parametry, (Karta66, KartaTysiac)):
                return {'typ': 'zagraj_karte', 'karta': str(parametry)}
            else:
                return {'typ': 'zagraj_karte', 'karta': parametry}
        elif typ_akcji == 'licytacja':
            return self._convert_karty_w_akcji(parametry)
        elif typ_akcji == 'brak':
            return None
        else:
            return {'typ': typ_akcji, **(parametry if isinstance(parametry, dict) else {})}
    
    async def is_bot_turn(self, engine: Any) -> bool:
        """Sprawdź czy jest kolej bota"""
        try:
            state = engine.game_state
            kolej_idx = state.kolej_gracza_idx
            
            if kolej_idx is None:
                return False
            
            current_player = state.gracze[kolej_idx]
            player_id = str(current_player.nazwa).strip()
            
            return await self._is_registered_bot_by_name(player_id)
        except:
            return False
    
    async def _is_registered_bot_by_name(self, player_name: str, redis: RedisService = None, game_id: str = None) -> bool:
        """Sprawdza czy gracz o danej nazwie jest botem."""
        try:
            from database import async_sessionmaker, User
            from sqlalchemy import select
            
            async with async_sessionmaker() as session:
                query = select(User).where(User.username == player_name)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if user and user.settings:
                    settings = json.loads(user.settings)
                    if settings.get('jest_botem', False):
                        return True
        except:
            pass
        
        if player_name and player_name.startswith('Bot #'):
            return True
        
        return False
    
    def get_bot_difficulty(self, bot_name: str) -> str:
        """Pobierz poziom trudności bota"""
        return 'medium'
    
    async def _auto_next_round_if_all_bots(self, game_id: str, engine: Any, redis: RedisService) -> None:
        """Automatycznie głosuje za nową rundą gdy rozdanie jest zakończone."""
        import random
        
        try:
            state = engine.game_state
            
            # Sprawdź czy rozdanie jest zakończone
            if not getattr(state, 'rozdanie_zakonczone', False):
                return
            
            # LOG: Rozdanie zakończone
            print(f"📋 [Gra {game_id[:8]}] Rozdanie zakończone")
            
            # Sprawdź czy mecz się zakończył
            mecz_zakonczony = False
            zwyciezca = None
            
            # Dla gier z drużynami (66 4p)
            if hasattr(state, 'druzyny') and state.druzyny:
                for druzyna in state.druzyny:
                    if druzyna.punkty_meczu >= 66:
                        mecz_zakonczony = True
                        zwyciezca = f"Drużyna {druzyna.nazwa} ({druzyna.punkty_meczu} pkt)"
                        break
            else:
                # Dla gier bez drużyn
                from engines.tysiac_engine import TysiacEngine
                target_points = 1000 if isinstance(engine, TysiacEngine) else 66
                
                for gracz in state.gracze:
                    if gracz.punkty_meczu >= target_points:
                        mecz_zakonczony = True
                        zwyciezca = f"{gracz.nazwa} ({gracz.punkty_meczu} pkt)"
                        break
            
            if mecz_zakonczony:
                # LOG: Mecz zakończony
                print(f"🏆 [Gra {game_id[:8]}] MECZ ZAKOŃCZONY! Wygrywa: {zwyciezca}")
                
                lobby_data = await redis.get_lobby(game_id)
                if lobby_data:
                    lobby_data['status_partii'] = 'ZAKONCZONA'
                    await redis.save_lobby(game_id, lobby_data)
                
                # Boty głosują za powrotem do lobby
                await self._bots_vote_return_to_lobby(game_id, engine, redis)
                return
            
            # Boty głosują za następną rundą
            for gracz in state.gracze:
                is_bot = await self._is_registered_bot_by_name(gracz.nazwa)
                if is_bot:
                    delay = random.uniform(2.0, 3.0)
                    await asyncio.sleep(delay)
                    await self._bot_vote_next_round(game_id, gracz.nazwa, redis)
            
        except Exception as e:
            print(f"[Bot] Błąd _auto_next_round: {e}")
    
    async def _bot_vote_next_round(self, game_id: str, bot_name: str, redis: RedisService) -> None:
        """Bot głosuje za następną rundą."""
        import json
        
        try:
            votes_key = f"next_round_votes:{game_id}"
            votes_data = await redis.redis.get(votes_key)
            
            if votes_data:
                votes = json.loads(votes_data)
            else:
                votes = []
            
            if bot_name not in votes:
                votes.append(bot_name)
                await redis.redis.set(votes_key, json.dumps(votes), ex=3600)
                
                engine = await redis.get_game_engine(game_id)
                if engine:
                    all_players = [g.nazwa for g in engine.game_state.gracze]
                    
                    await manager.broadcast(game_id, {
                        'type': 'next_round_vote',
                        'player': bot_name,
                        'votes': votes,
                        'total_players': len(all_players),
                        'ready_players': votes
                    })
                    
                    # Sprawdź czy wszyscy zagłosowali
                    if set(votes) >= set(all_players):
                        await redis.redis.delete(votes_key)
                        await self._start_next_round_internal(game_id, engine, redis)
                        await self.process_bot_actions(game_id, engine, redis)
        except Exception as e:
            pass
    
    async def _bots_vote_return_to_lobby(self, game_id: str, engine: Any, redis: RedisService) -> None:
        """Boty głosują za powrotem do lobby (25% szans każdy)."""
        import random
        
        try:
            state = engine.game_state
            all_players = [g.nazwa for g in state.gracze]
            votes = []
            
            for gracz in state.gracze:
                is_bot = await self._is_registered_bot_by_name(gracz.nazwa)
                
                if is_bot:
                    # 25% szans na głosowanie za powrotem
                    if random.random() < 0.25:
                        delay = random.uniform(3.0, 6.0)
                        await asyncio.sleep(delay)
                        
                        votes.append(gracz.nazwa)
                        
                        await manager.broadcast(game_id, {
                            'type': 'return_to_lobby_vote',
                            'player': gracz.nazwa,
                            'votes': votes,
                            'total_players': len(all_players),
                            'ready_players': votes
                        })
            
            # Sprawdź czy wszyscy zagłosowali
            if set(votes) >= set(all_players):
                lobby_data = await redis.get_lobby(game_id)
                
                if lobby_data:
                    lobby_data['status_partii'] = 'LOBBY'
                    for slot in lobby_data.get('slots', []):
                        if slot.get('typ') in ['gracz', 'bot']:
                            slot['ready'] = False
                    
                    await redis.save_lobby(game_id, lobby_data)
                    
                    await manager.broadcast(game_id, {
                        'type': 'returned_to_lobby',
                        'lobby': lobby_data
                    })
                
                await redis.delete_game_engine(game_id)
            else:
                # Nie wszyscy zagłosowali - usuń grę
                await redis.delete_game(game_id)
                print(f"🗑️ [Gra {game_id[:8]}] Gra usunięta (boty opuściły)")
                
        except Exception as e:
            print(f"[Bot] Błąd _bots_vote_return: {e}")
    
    async def _start_next_round_internal(self, game_id: str, engine: Any, redis: RedisService) -> None:
        """Wewnętrzna metoda rozpoczynająca nową rundę."""
        state = engine.game_state
        
        # Zmień rozdającego
        if hasattr(state, 'rozdajacy_idx') and hasattr(state, 'gracze'):
            state.rozdajacy_idx = (state.rozdajacy_idx + 1) % len(state.gracze)
        
        # Wyczyść ręce i wygrane karty
        if hasattr(state, 'gracze'):
            for gracz in state.gracze:
                if hasattr(gracz, 'reka'):
                    gracz.reka.clear()
                if hasattr(gracz, 'wygrane_karty'):
                    gracz.wygrane_karty.clear()
        
        # Zresetuj talię
        from engines.tysiac_engine import TysiacEngine
        if isinstance(engine, TysiacEngine):
            from silnik_tysiac import Talia as TaliaTysiac
            if hasattr(state, 'talia'):
                state.talia = TaliaTysiac()
        else:
            from silnik_gry import Talia
            if hasattr(state, 'talia'):
                state.talia = Talia()
        
        # Zresetuj punkty w rozdaniu
        if hasattr(state, 'druzyny') and state.druzyny:
            state.punkty_w_rozdaniu = {d.nazwa: 0 for d in state.druzyny}
        elif hasattr(state, 'gracze'):
            state.punkty_w_rozdaniu = {g.nazwa: 0 for g in state.gracze}
        
        if hasattr(state, 'aktualna_lewa'):
            state.aktualna_lewa.clear()
        
        # Reset flag zakończenia
        for attr in ['rozdanie_zakonczone', 'lewa_do_zamkniecia', 'ostatnia_lewa']:
            if hasattr(state, attr):
                setattr(state, attr, False)
        
        for attr in ['podsumowanie', 'zwyciezca_rozdania', 'zwyciezca_ostatniej_lewy', 
                      'powod_zakonczenia', 'zwyciezca_lewy_tymczasowy']:
            if hasattr(state, attr):
                setattr(state, attr, None)
        
        if hasattr(state, 'karty_ostatniej_lewy'):
            state.karty_ostatniej_lewy = []
        
        # Reset kontraktu i licytacji
        for attr in ['kontrakt', 'grajacy', 'atut', 'ostatni_podbijajacy', 'lufa_challenger', 'nieaktywny_gracz']:
            if hasattr(state, attr):
                setattr(state, attr, None)
        
        if hasattr(state, 'mnoznik_lufy'):
            state.mnoznik_lufy = 1
        if hasattr(state, 'bonus_z_trzech_kart'):
            state.bonus_z_trzech_kart = False
        
        # Reset list
        for attr in ['historia_licytacji', 'pasujacy_gracze', 'oferty_przebicia', 
                      'kolejka_licytacji', 'zadeklarowane_meldunki', 'szczegolowa_historia']:
            if hasattr(state, attr):
                getattr(state, attr).clear() if hasattr(getattr(state, attr), 'clear') else setattr(state, attr, [])
        
        if hasattr(state, 'liczba_aktywnych_graczy'):
            state.liczba_aktywnych_graczy = len(state.gracze)
        
        # Reset specyficzne dla Tysiąca
        for attr in ['musik_odkryty', 'lufa_wstepna']:
            if hasattr(state, attr):
                setattr(state, attr, False)
        
        for attr in ['musik_karty', 'musik_1', 'musik_2', 'musik_1_oryginalny', 'musik_2_oryginalny']:
            if hasattr(state, attr):
                setattr(state, attr, [])
        
        for attr in ['musik_wybrany', 'licytujacy_idx', 'muzyk_idx']:
            if hasattr(state, attr):
                setattr(state, attr, None)
        
        for attr in ['aktualna_licytacja', 'kontrakt_wartosc', 'muzyk_punkty']:
            if hasattr(state, attr):
                setattr(state, attr, 0)
        
        if hasattr(state, 'bomba_uzyta'):
            state.bomba_uzyta = {g.nazwa: False for g in state.gracze}
        
        if hasattr(state, 'zwyciezca_rozdania_info'):
            state.zwyciezca_rozdania_info = {}
        
        # Rozpocznij nowe rozdanie
        if hasattr(state, 'rozpocznij_nowe_rozdanie'):
            state.rozpocznij_nowe_rozdanie()
        
        # Zapisz silnik
        await redis.save_game_engine(game_id, engine)
        
        # Broadcast info o nowej rundzie
        await manager.broadcast(game_id, {'type': 'next_round_started'})
        await manager.broadcast_state_update(game_id)
    
    async def trigger_return_to_lobby_voting(self, game_id: str, redis: RedisService) -> None:
        """Publiczna metoda wywoływana po zakończeniu meczu - boty głosują za powrotem do lobby."""
        import random
        
        try:
            lobby_data = await redis.get_lobby(game_id)
            if not lobby_data or lobby_data.get('status_partii') != 'ZAKONCZONA':
                return
            
            engine = await redis.get_game_engine(game_id)
            if not engine:
                return
            
            state = engine.game_state
            
            for gracz in state.gracze:
                is_bot = await self._is_registered_bot_by_name(gracz.nazwa)
                if is_bot:
                    # Boty zawsze głosują za powrotem do lobby
                    delay = random.uniform(2.0, 5.0)
                    await asyncio.sleep(delay)
                    
                    votes_key = f"return_to_lobby_votes:{game_id}"
                    votes_data = await redis.redis.get(votes_key)
                    
                    if votes_data:
                        votes = json.loads(votes_data)
                    else:
                        votes = {'stay': [], 'leave': []}
                    
                    if gracz.nazwa not in votes['stay']:
                        votes['stay'].append(gracz.nazwa)
                        await redis.redis.set(votes_key, json.dumps(votes), ex=120)
                        
                        all_players = [
                            s['nazwa'] for s in lobby_data.get('slots', []) 
                            if s.get('typ') in ['gracz', 'bot'] and s.get('nazwa')
                        ]
                        
                        await manager.broadcast(game_id, {
                            'type': 'return_to_lobby_vote',
                            'player': gracz.nazwa,
                            'action': 'stay',
                            'votes_stay': votes['stay'],
                            'votes_leave': votes['leave'],
                            'total_players': len(all_players)
                        })
                        
                        # Sprawdź czy wszyscy zdecydowali
                        decided = set(votes['stay'] + votes['leave'])
                        if decided >= set(all_players):
                            # Finalizuj - importuj funkcję
                            from routers.game import _finalize_lobby_return
                            await _finalize_lobby_return(game_id, lobby_data, votes, redis)
                            return
        except Exception as e:
            print(f"⚠️ Błąd trigger_return_to_lobby_voting: {e}")
            pass
