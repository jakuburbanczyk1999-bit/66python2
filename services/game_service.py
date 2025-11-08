"""
Service: Game
Odpowiedzialność: Inicjalizacja gry, zarządzanie stanem gry
"""
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status

from services.redis_service import RedisService
from services.bot_service import BotService
from engines.sixtysix_engine import SixtySixEngine

class GameService:
    """Service do zarządzania grami"""
    
    def __init__(self):
        self.bot_service = BotService()
    
    async def initialize_game(
        self,
        lobby_id: str,
        lobby_data: dict,
        redis: RedisService
    ) -> SixtySixEngine:
        """
        Inicjalizuj nową grę (utwórz silnik)
        
        Args:
            lobby_id: ID lobby/gry
            lobby_data: Dane lobby z Redis
            redis: Redis service
        
        Returns:
            SixtySixEngine: Zainicjalizowany silnik gry
        
        Raises:
            ValueError: Jeśli nieprawidłowe dane
        """
        print(f"[GameService] Tworzenie silnika gry dla lobby {lobby_id}")
        
        # Przygotuj listę ID graczy (w kolejności slotów)
        player_ids = []
        for slot in lobby_data.get('slots', []):
            if slot['typ'] != 'pusty':
                # Dla botów i graczy używamy nazwy jako ID
                player_ids.append(slot['nazwa'])
        
        if len(player_ids) < 2:
            raise ValueError("Potrzeba minimum 2 graczy do rozpoczęcia gry")
        
        # Ustawienia gry
        max_players = lobby_data.get('max_graczy', 4)
        game_settings = {
            'tryb': f'{max_players}p',
            'rozdajacy_idx': 0,  # Pierwszy gracz rozdaje
            'nazwy_druzyn': {
                'My': 'Drużyna 1',
                'Oni': 'Drużyna 2'
            }
        }
        
        # Utwórz instancję silnika
        engine = SixtySixEngine(player_ids, game_settings)
        
        # Zapisz silnik do Redis
        await redis.save_game_engine(lobby_id, engine)
        
        print(f"[GameService] Silnik utworzony, faza: {engine.game_state.faza}")
        
        # Auto-wykonaj akcje botów jeśli bot ma turę
        await self.bot_service.process_bot_actions(lobby_id, engine, redis)
        
        return engine
    
    async def validate_game_start(
        self,
        lobby_data: dict,
        user_id: int
    ) -> tuple[bool, str]:
        """
        Waliduj czy można rozpocząć grę
        
        Args:
            lobby_data: Dane lobby
            user_id: ID użytkownika próbującego rozpocząć
        
        Returns:
            tuple[bool, str]: (can_start, error_message)
        """
        # Sprawdź czy użytkownik jest hostem
        host_slot = next((s for s in lobby_data['slots'] if s.get('is_host')), None)
        if not host_slot or host_slot.get('id_uzytkownika') != user_id:
            return False, "Tylko host może rozpocząć grę"
        
        # Sprawdź liczbę graczy
        player_count = sum(1 for s in lobby_data['slots'] if s['typ'] != 'pusty')
        max_players = lobby_data.get('max_graczy', 4)
        
        if player_count < max_players:
            return False, f"Potrzeba {max_players} graczy (masz {player_count})"
        
        # Sprawdź czy wszyscy gotowi (poza hostem i botami)
        not_ready = [
            s['nazwa'] for s in lobby_data['slots']
            if s['typ'] == 'gracz' 
            and not s.get('ready', False)
            and not s.get('is_host', False)  # Host nie musi być ready
        ]
        
        if not_ready:
            return False, f"Nie wszyscy gracze są gotowi: {', '.join(not_ready)}"
        
        return True, ""
    
    async def get_game_status(
        self,
        game_id: str,
        redis: RedisService
    ) -> Dict[str, Any]:
        """
        Pobierz status gry
        
        Args:
            game_id: ID gry
            redis: Redis service
        
        Returns:
            Dict: Status gry
        """
        lobby_data = await redis.get_lobby(game_id)
        engine = await redis.get_game_engine(game_id)
        
        if not lobby_data:
            return {'exists': False}
        
        status = {
            'exists': True,
            'game_id': game_id,
            'status': lobby_data.get('status_partii', 'UNKNOWN'),
            'max_players': lobby_data.get('max_graczy', 4),
            'players': []
        }
        
        # Dodaj graczy
        for slot in lobby_data.get('slots', []):
            if slot['typ'] != 'pusty':
                status['players'].append({
                    'name': slot['nazwa'],
                    'is_bot': slot['typ'] == 'bot',
                    'is_host': slot.get('is_host', False),
                    'ready': slot.get('ready', False)
                })
        
        # Dodaj info z silnika jeśli gra w trakcie
        if engine and lobby_data.get('status_partii') in ['W_GRZE', 'W_TRAKCIE', 'IN_PROGRESS']:
            try:
                status['phase'] = engine.game_state.faza.name if hasattr(engine.game_state, 'faza') else 'UNKNOWN'
                status['current_player'] = (
                    engine.game_state.gracze[engine.game_state.kolej_gracza_idx].nazwa
                    if hasattr(engine.game_state, 'kolej_gracza_idx') 
                    and engine.game_state.kolej_gracza_idx is not None
                    else None
                )
            except:
                pass
        
        return status
    
    async def end_game(
        self,
        game_id: str,
        winner: Optional[str],
        redis: RedisService
    ) -> bool:
        """
        Zakończ grę
        
        Args:
            game_id: ID gry
            winner: Zwycięzca (opcjonalnie)
            redis: Redis service
        
        Returns:
            bool: True jeśli sukces
        """
        try:
            # Pobierz lobby
            lobby_data = await redis.get_lobby(game_id)
            if not lobby_data:
                return False
            
            # Zmień status
            lobby_data['status_partii'] = 'ZAKONCZONA'
            if winner:
                lobby_data['winner'] = winner
            
            # Zapisz
            await redis.save_lobby(game_id, lobby_data)
            
            # Opcjonalnie: usuń silnik (oszczędność pamięci)
            # await redis.delete_game(game_id)
            
            print(f"✅ Gra {game_id} zakończona. Zwycięzca: {winner}")
            
            return True
        except Exception as e:
            print(f"❌ Błąd kończenia gry: {e}")
            return False
    
    def calculate_team_assignment(self, player_count: int) -> Dict[str, List[int]]:
        """
        Oblicz przydział graczy do drużyn
        
        Args:
            player_count: Liczba graczy (3 lub 4)
        
        Returns:
            Dict: Przydział {'My': [0, 2], 'Oni': [1, 3]}
        """
        if player_count == 4:
            return {
                'My': [0, 2],   # Gracz 0 i 2
                'Oni': [1, 3]   # Gracz 1 i 3
            }
        elif player_count == 3:
            return {
                'My': [0],      # Solo
                'Oni': [1, 2]   # Para
            }
        else:
            raise ValueError(f"Nieprawidłowa liczba graczy: {player_count}")
    
    async def check_and_finalize_round(
        self,
        game_id: str,
        engine: Any,
        redis: RedisService
    ) -> bool:
        """
        Sprawdź czy runda się skończyła i finalizuj jeśli tak
        
        Args:
            game_id: ID gry
            engine: Silnik gry
            redis: Redis service
        
        Returns:
            bool: True jeśli runda zakończona
        """
        try:
            state = engine.game_state
            
            # Sprawdź czy rozdanie zakończone
            if hasattr(state, 'rozdanie_zakonczone') and state.rozdanie_zakonczone:
                print(f"[GameService] Rozdanie zakończone w grze {game_id}")
                
                # Sprawdź czy gra zakończona (ktoś osiągnął limit punktów)
                if hasattr(state, 'partia_zakonczona') and state.partia_zakonczona:
                    # Pobierz zwycięzcę
                    winner = None
                    if hasattr(state, 'zwyciezca_partii'):
                        winner = state.zwyciezca_partii
                    
                    # Zakończ grę
                    await self.end_game(game_id, winner, redis)
                    return True
                
                return True
            
            return False
        except Exception as e:
            print(f"❌ Błąd check_and_finalize_round: {e}")
            return False
    
    def get_player_index(self, lobby_data: dict, player_name: str) -> Optional[int]:
        """
        Pobierz indeks gracza w slots
        
        Args:
            lobby_data: Dane lobby
            player_name: Nazwa gracza
        
        Returns:
            Optional[int]: Indeks lub None
        """
        for idx, slot in enumerate(lobby_data.get('slots', [])):
            if slot.get('nazwa') == player_name:
                return idx
        return None