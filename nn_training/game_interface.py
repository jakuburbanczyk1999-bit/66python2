# nn_training/game_interface.py
"""
Interfejs do silnika gry 66 dla treningu sieci neuronowej.
Wrapper wokół SixtySixEngine zapewniający prostsze API.
"""

import sys
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Dodaj ścieżki do importów - NN_DIR musi być PRZED PROJECT_ROOT
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from engines.sixtysix_engine import SixtySixEngine
from silnik_gry import Kontrakt, FazaGry, Kolor

try:
    from .config import ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX
except ImportError:
    from config import ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX


class GameResult(Enum):
    """Wynik gry z perspektywy gracza."""
    WIN = 1
    LOSS = -1
    DRAW = 0


@dataclass
class GameOutcome:
    """Wynik zakończonej gry."""
    winner_team: Optional[str]  # Nazwa wygrywającej drużyny/gracza
    points_awarded: int  # Punkty meczowe
    contract: Optional[str]  # Kontrakt
    is_win: Dict[str, bool]  # Czy dany gracz wygrał
    rewards: Dict[str, float]  # Nagrody dla każdego gracza


class GameInterface:
    """
    Prosty interfejs do gry 66 dla treningu NN.
    
    Zapewnia:
    - Łatwe tworzenie nowych gier
    - Wykonywanie akcji przez indeks
    - Pobieranie stanu w formacie dla enkodera
    - Obsługę końca gry i nagród
    """
    
    def __init__(self, 
                 player_ids: List[str],
                 mode: str = '4p'):
        """
        Tworzy nową grę.
        
        Args:
            player_ids: Lista ID graczy (4 dla 4p, 3 dla 3p)
            mode: Tryb gry ('4p' lub '3p')
        """
        self.player_ids = player_ids
        self.mode = mode
        
        # Ustawienia gry
        settings = {
            'tryb': mode,
            'rozdajacy_idx': random.randint(0, len(player_ids) - 1),
        }
        
        if mode == '4p':
            settings['nazwy_druzyn'] = {
                'My': f"Team_{player_ids[0]}_{player_ids[2]}",
                'Oni': f"Team_{player_ids[1]}_{player_ids[3]}",
            }
        
        # Stwórz silnik gry
        self.engine = SixtySixEngine(player_ids, settings)
        
        # Cache dla drużyn (4p)
        self._team_members = {}
        if mode == '4p':
            self._team_members[player_ids[0]] = [player_ids[0], player_ids[2]]
            self._team_members[player_ids[2]] = [player_ids[0], player_ids[2]]
            self._team_members[player_ids[1]] = [player_ids[1], player_ids[3]]
            self._team_members[player_ids[3]] = [player_ids[1], player_ids[3]]
    
    def get_state(self, player_id: str) -> Dict[str, Any]:
        """
        Pobiera stan gry dla gracza.
        
        Returns:
            Słownik stanu kompatybilny z StateEncoder
        """
        return self.engine.get_state_for_player(player_id)
    
    def get_current_player(self) -> Optional[str]:
        """Zwraca ID gracza, którego jest tura."""
        return self.engine.get_current_player()
    
    def get_legal_actions(self, player_id: str) -> List[Dict[str, Any]]:
        """Zwraca listę legalnych akcji dla gracza."""
        return self.engine.get_legal_actions(player_id)
    
    def get_legal_action_indices(self, player_id: str) -> List[int]:
        """
        Zwraca listę indeksów legalnych akcji.
        
        Returns:
            Lista indeksów akcji (do użycia z ACTION_INDEX_TO_DICT)
        """
        legal_actions = self.get_legal_actions(player_id)
        state = self.get_state(player_id)
        grywalne_karty = state.get('grywalne_karty', [])
        
        indices = []
        
        # Mapuj akcje licytacyjne
        for action in legal_actions:
            idx = self._action_to_index(action)
            if idx is not None:
                indices.append(idx)
        
        # Mapuj grywalne karty
        for karta_str in grywalne_karty:
            idx = self._card_to_action_index(karta_str)
            if idx is not None:
                indices.append(idx)
        
        return indices
    
    def perform_action_by_index(self, player_id: str, action_idx: int) -> bool:
        """
        Wykonuje akcję po indeksie.
        
        Args:
            player_id: ID gracza
            action_idx: Indeks akcji (0 do TOTAL_ACTIONS-1)
            
        Returns:
            True jeśli akcja została wykonana
        """
        if action_idx not in ACTION_INDEX_TO_DICT:
            print(f"Nieznany indeks akcji: {action_idx}")
            return False
        
        action = ACTION_INDEX_TO_DICT[action_idx].copy()
        return self.perform_action(player_id, action)
    
    def perform_action(self, player_id: str, action: Dict[str, Any]) -> bool:
        """
        Wykonuje akcję.
        
        Args:
            player_id: ID gracza
            action: Słownik akcji
            
        Returns:
            True jeśli akcja została wykonana
        """
        try:
            self.engine.perform_action(player_id, action)
            
            # Automatyczna finalizacja lewy
            if self.engine.game_state.lewa_do_zamkniecia:
                self.engine.perform_action(player_id, {'typ': 'finalizuj_lewe'})
            
            return True
        except Exception as e:
            print(f"Błąd wykonania akcji: {e}")
            return False
    
    def is_terminal(self) -> bool:
        """Sprawdza czy gra się zakończyła."""
        return self.engine.is_terminal()
    
    def get_outcome(self) -> Optional[GameOutcome]:
        """
        Zwraca wynik zakończonej gry.
        
        Returns:
            GameOutcome lub None jeśli gra nie zakończona
        """
        if not self.is_terminal():
            return None
        
        podsumowanie = self.engine.game_state.podsumowanie
        if not podsumowanie:
            return None
        
        # Ustal zwycięzcę
        if self.mode == '4p':
            winner = podsumowanie.get('wygrana_druzyna')
        else:
            winners = podsumowanie.get('wygrani_gracze', [])
            winner = winners[0] if winners else None
        
        points = podsumowanie.get('przyznane_punkty', 0)
        contract = podsumowanie.get('kontrakt')
        
        # Oblicz czy każdy gracz wygrał
        is_win = {}
        rewards = {}
        
        for pid in self.player_ids:
            if self.mode == '4p':
                # Sprawdź drużynę
                player_obj = self.engine._map_player_id_to_obj(pid)
                if player_obj and player_obj.druzyna:
                    is_win[pid] = player_obj.druzyna.nazwa == winner
                else:
                    is_win[pid] = False
            else:
                # 3p - sprawdź czy gracz jest wśród zwycięzców
                winners = podsumowanie.get('wygrani_gracze', [])
                is_win[pid] = pid in winners
            
            # Nagroda: +points za wygraną, -points za przegraną
            rewards[pid] = float(points) if is_win[pid] else float(-points)
        
        return GameOutcome(
            winner_team=winner,
            points_awarded=points,
            contract=contract,
            is_win=is_win,
            rewards=rewards,
        )
    
    def get_phase(self) -> str:
        """Zwraca aktualną fazę gry."""
        return self.engine.game_state.faza.name
    
    def get_contract(self) -> Optional[str]:
        """Zwraca aktualny kontrakt."""
        if self.engine.game_state.kontrakt:
            return self.engine.game_state.kontrakt.name
        return None
    
    def get_trump(self) -> Optional[str]:
        """Zwraca aktualny atut."""
        if self.engine.game_state.atut:
            return self.engine.game_state.atut.name
        return None
    
    def clone(self) -> 'GameInterface':
        """Tworzy kopię gry (dla symulacji)."""
        import copy
        new_game = GameInterface.__new__(GameInterface)
        new_game.player_ids = self.player_ids.copy()
        new_game.mode = self.mode
        new_game.engine = self.engine.clone()
        new_game._team_members = self._team_members.copy()
        return new_game
    
    # === Metody pomocnicze ===
    
    def _action_to_index(self, action: Dict[str, Any]) -> Optional[int]:
        """Konwertuje słownik akcji na indeks."""
        typ = action.get('typ', '')
        
        if typ == 'deklaracja':
            kontrakt = action.get('kontrakt', '')
            if hasattr(kontrakt, 'name'):
                kontrakt = kontrakt.name
            
            atut = action.get('atut')
            if atut and hasattr(atut, 'name'):
                atut = atut.name
            
            key = (typ, kontrakt, atut)
            return DICT_TO_ACTION_INDEX.get(key)
        
        elif typ == 'przebicie':
            kontrakt = action.get('kontrakt', '')
            if hasattr(kontrakt, 'name'):
                kontrakt = kontrakt.name
            key = (typ, kontrakt)
            return DICT_TO_ACTION_INDEX.get(key)
        
        elif typ in ['pas', 'pas_lufa', 'lufa', 'kontra', 'do_konca', 
                     'pytanie', 'nie_pytam', 'graj_normalnie']:
            key = (typ, None)
            return DICT_TO_ACTION_INDEX.get(key)
        
        elif typ == 'zagraj_karte':
            karta = action.get('karta', {})
            if isinstance(karta, dict):
                ranga = karta.get('ranga', '').upper()
                kolor = karta.get('kolor', '').upper()
                key = ('zagraj_karte', ranga, kolor)
                return DICT_TO_ACTION_INDEX.get(key)
        
        return None
    
    def _card_to_action_index(self, card_str: str) -> Optional[int]:
        """Konwertuje string karty na indeks akcji."""
        try:
            parts = card_str.split()
            if len(parts) >= 2:
                ranga = parts[0].upper()
                kolor = parts[1].upper()
                key = ('zagraj_karte', ranga, kolor)
                return DICT_TO_ACTION_INDEX.get(key)
        except:
            pass
        return None


def play_random_game(player_ids: List[str] = None, 
                     mode: str = '4p',
                     verbose: bool = False) -> GameOutcome:
    """
    Rozgrywa losową grę.
    
    Args:
        player_ids: Lista ID graczy
        mode: Tryb gry
        verbose: Czy wypisywać logi
        
    Returns:
        GameOutcome z wynikiem
    """
    if player_ids is None:
        if mode == '4p':
            player_ids = ['P1', 'P2', 'P3', 'P4']
        else:
            player_ids = ['P1', 'P2', 'P3']
    
    game = GameInterface(player_ids, mode)
    
    move_count = 0
    max_moves = 200  # Bezpiecznik
    
    while not game.is_terminal() and move_count < max_moves:
        current = game.get_current_player()
        
        if current is None:
            if verbose:
                print(f"Brak gracza w turze, faza: {game.get_phase()}")
            break
        
        legal_indices = game.get_legal_action_indices(current)
        
        if not legal_indices:
            if verbose:
                print(f"Brak legalnych akcji dla {current}, faza: {game.get_phase()}")
            break
        
        # Wybierz losową akcję
        action_idx = random.choice(legal_indices)
        
        if verbose:
            action = ACTION_INDEX_TO_DICT[action_idx]
            print(f"[{move_count}] {current}: {action}")
        
        game.perform_action_by_index(current, action_idx)
        move_count += 1
    
    outcome = game.get_outcome()
    
    if verbose and outcome:
        print(f"\n=== Game Over ===")
        print(f"Winner: {outcome.winner_team}")
        print(f"Points: {outcome.points_awarded}")
        print(f"Contract: {outcome.contract}")
    
    return outcome


if __name__ == "__main__":
    # Test interfejsu
    print("=== Test GameInterface ===\n")
    
    # Rozegraj kilka losowych gier
    wins = {'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0}
    
    for i in range(10):
        outcome = play_random_game(verbose=(i == 0))  # Verbose tylko dla pierwszej
        
        if outcome:
            for pid, won in outcome.is_win.items():
                if won:
                    wins[pid] += 1
    
    print(f"\n=== Results after 10 games ===")
    print(f"Wins: {wins}")
    
    # Test pojedynczej gry z więcej szczegółami
    print("\n=== Detailed single game test ===")
    game = GameInterface(['A', 'B', 'C', 'D'], '4p')
    
    print(f"Phase: {game.get_phase()}")
    print(f"Current player: {game.get_current_player()}")
    
    state = game.get_state('A')
    print(f"Player A hand: {state['rece_graczy'].get('A', [])}")
    
    legal = game.get_legal_action_indices('A')
    print(f"Legal actions for A: {len(legal)} options")
    
    if legal:
        print(f"First few actions:")
        for idx in legal[:5]:
            print(f"  {idx}: {ACTION_INDEX_TO_DICT[idx]}")
