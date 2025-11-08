"""
Service: Boty
Odpowiedzialność: Automatyczne wykonywanie akcji botów
"""
import asyncio
import traceback
from typing import Any

from services.redis_service import RedisService
from routers.websocket_router import manager

# Import funkcji z boty.py (istniejący plik)
from boty import wybierz_akcje_dla_bota_testowego

class BotService:
    """Service do obsługi botów"""
    
    def __init__(self):
        self.max_iterations = 20  # Zabezpieczenie przed nieskończoną pętlą
        self.bot_delay = 0.5  # Opóźnienie między ruchami botów (sekundy)
    
    async def process_bot_actions(
        self,
        game_id: str,
        engine: Any,
        redis: RedisService
    ) -> None:
        """
        Automatycznie wykonuje akcje botów dopóki jest ich kolej.
        Obsługuje wszystkie fazy gry: DEKLARACJA, MELDUNEK, ROZGRYWKA.
        
        Args:
            game_id: ID gry
            engine: Silnik gry (SixtySixEngine)
            redis: Redis service
        """
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Pobierz aktualny stan
            state = engine.game_state
            
            # Sprawdź czyja kolej
            kolej_idx = state.kolej_gracza_idx
            if kolej_idx is None:
                print("[Bot] Brak kolejki - koniec automatycznych ruchów")
                break
            
            current_player = state.gracze[kolej_idx]
            player_id = str(current_player.nazwa).strip()
            
            # Jeśli to nie bot - zakończ
            if not player_id.startswith('Bot'):
                print(f"[Bot] Kolej gracza {player_id} - koniec automatycznych ruchów")
                break
            
            print(f"[Bot] Kolej bota {player_id}, faza: {state.faza.name}")
            
            # Pobierz dozwolone akcje
            try:
                allowed_actions = engine.get_legal_actions(player_id)
                current_player_from_engine = engine.get_current_player()
            except Exception as e:
                print(f"[Bot] Błąd pobierania akcji: {e}")
                traceback.print_exc()
                break
            
            if not allowed_actions:
                print(f"[Bot] Brak dostępnych akcji dla {player_id}")
                print(f"[Bot] Faza: {state.faza.name}, Kolej: {engine.get_current_player()}")
                break
            
            # Bot wybiera akcję
            try:
                typ_akcji, parametry = wybierz_akcje_dla_bota_testowego(
                    current_player,
                    state
                )
                
                # Obsługa różnych typów akcji
                if typ_akcji == 'karta':
                    # W fazie ROZGRYWKA zwraca obiekt Karta
                    from silnik_gry import Karta
                    if isinstance(parametry, Karta):
                        bot_action = {
                            'typ': 'zagraj_karte',
                            'karta': str(parametry)  # Zamień Karta na string
                        }
                    else:
                        bot_action = {
                            'typ': 'zagraj_karte',
                            'karta': parametry
                        }
                elif typ_akcji == 'licytacja':
                    # W fazie licytacji zwraca dict akcji
                    bot_action = parametry
                elif typ_akcji == 'brak':
                    print(f"[Bot] Bot {player_id} nie ma akcji")
                    break
                else:
                    # Fallback - użyj jako dict
                    bot_action = {
                        'typ': typ_akcji,
                        **parametry
                    }
                
                print(f"[Bot] Bot {player_id} wykonuje: {bot_action}")
                
                # Wykonaj akcję bota
                engine.perform_action(player_id, bot_action)
                
                # Zapisz silnik
                await redis.save_game_engine(game_id, engine)
                
                # Broadcast przez WebSocket
                await manager.broadcast(game_id, {
                    'type': 'bot_action',
                    'player': player_id,
                    'action': bot_action
                })
                
                # Małe opóźnienie dla płynności
                await asyncio.sleep(self.bot_delay)
                
            except Exception as e:
                print(f"[Bot] Błąd wykonywania akcji bota: {e}")
                traceback.print_exc()
                break
        
        if iteration >= self.max_iterations:
            print(f"[Bot] UWAGA: Osiągnięto limit iteracji ({self.max_iterations})")
    
    async def is_bot_turn(self, engine: Any) -> bool:
        """
        Sprawdź czy jest kolej bota
        
        Args:
            engine: Silnik gry
        
        Returns:
            bool: True jeśli kolej bota
        """
        try:
            state = engine.game_state
            kolej_idx = state.kolej_gracza_idx
            
            if kolej_idx is None:
                return False
            
            current_player = state.gracze[kolej_idx]
            player_id = str(current_player.nazwa).strip()
            
            return player_id.startswith('Bot')
        except:
            return False
    
    def get_bot_difficulty(self, bot_name: str) -> str:
        """
        Pobierz poziom trudności bota (na przyszłość)
        
        Args:
            bot_name: Nazwa bota
        
        Returns:
            str: Poziom trudności ('easy', 'medium', 'hard')
        """
        # Na razie wszyscy boci są 'easy' (testowy bot)
        # W przyszłości można dodać Bot #1 (easy), Bot #2 (medium), etc.
        return 'easy'
    
    async def replace_player_with_bot(
        self,
        game_id: str,
        player_name: str,
        redis: RedisService
    ) -> bool:
        """
        Zamień gracza na bota (gdy gracz się rozłączy)
        
        Args:
            game_id: ID gry
            player_name: Nazwa gracza do zamiany
            redis: Redis service
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            # Pobierz lobby
            lobby_data = await redis.get_lobby(game_id)
            if not lobby_data:
                return False
            
            # Znajdź slot gracza
            slots = lobby_data.get('slots', [])
            for slot in slots:
                if slot.get('nazwa') == player_name and slot.get('typ') == 'gracz':
                    # Zamień na bota
                    bot_num = 1
                    existing_bots = [
                        s for s in slots 
                        if s.get('typ') == 'bot' and s.get('nazwa', '').startswith('Bot #')
                    ]
                    if existing_bots:
                        bot_nums = []
                        for bot in existing_bots:
                            try:
                                num = int(bot['nazwa'].split('#')[1])
                                bot_nums.append(num)
                            except:
                                pass
                        bot_num = max(bot_nums) + 1 if bot_nums else 1
                    
                    slot['typ'] = 'bot'
                    slot['nazwa'] = f"Bot #{bot_num}"
                    slot['id_uzytkownika'] = None
                    slot['ready'] = True
                    slot['avatar_url'] = 'bot_avatar.png'
                    
                    # Zapisz
                    await redis.save_lobby(game_id, lobby_data)
                    
                    print(f"✅ Gracz {player_name} zamieniony na {slot['nazwa']}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error replacing player with bot: {e}")
            return False