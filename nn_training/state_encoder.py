# nn_training/state_encoder.py
"""
Enkoder stanu gry 66 na tensor dla sieci neuronowej.
Skupiony na informacjach kluczowych dla licytacji.
"""

import torch
import numpy as np
import sys
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# Dodaj ścieżki do importów - NN_DIR musi być PRZED PROJECT_ROOT
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from .config import (
        NETWORK_CONFIG, 
        CARD_VALUES, 
        RANK_ORDER, 
        SUIT_ORDER,
        PHASE_INDICES,
        CONTRACT_INDICES,
        SUIT_INDICES,
        RANK_INDICES,
        ACTION_INDEX_TO_DICT,
        DICT_TO_ACTION_INDEX,
    )
except ImportError:
    from config import (
        NETWORK_CONFIG, 
        CARD_VALUES, 
        RANK_ORDER, 
        SUIT_ORDER,
        PHASE_INDICES,
        CONTRACT_INDICES,
        SUIT_INDICES,
        RANK_INDICES,
        ACTION_INDEX_TO_DICT,
        DICT_TO_ACTION_INDEX,
    )


@dataclass
class CardInfo:
    """Informacje o karcie."""
    ranga: str
    kolor: str
    
    @property
    def value(self) -> int:
        return CARD_VALUES.get(self.ranga, 0)
    
    def __hash__(self):
        return hash((self.ranga, self.kolor))
    
    def __eq__(self, other):
        if not isinstance(other, CardInfo):
            return False
        return self.ranga == other.ranga and self.kolor == other.kolor


class StateEncoder:
    """
    Koduje stan gry 66 na tensor.
    
    Struktura tensora (NETWORK_CONFIG.TOTAL_STATE_DIM wymiarów):
    1. Hand state: informacje o ręce gracza
    2. Game state: faza, kontrakt, atut, punkty
    3. Play state: zagrane karty, aktualna lewa
    """
    
    def __init__(self):
        self.config = NETWORK_CONFIG
        
    def encode_state(self, 
                     game_state: Dict[str, Any],
                     player_id: str) -> torch.Tensor:
        """
        Koduje pełny stan gry na tensor.
        
        Args:
            game_state: Słownik stanu z silnika (get_state_for_player)
            player_id: ID gracza, dla którego kodujemy
            
        Returns:
            Tensor o wymiarze (TOTAL_STATE_DIM,)
        """
        # Zbierz wszystkie części stanu
        hand_state = self._encode_hand(game_state, player_id)
        game_info = self._encode_game_info(game_state, player_id)
        play_state = self._encode_play_state(game_state, player_id)
        
        # Połącz w jeden tensor
        full_state = torch.cat([hand_state, game_info, play_state])
        
        return full_state
    
    def _encode_hand(self, 
                     game_state: Dict[str, Any],
                     player_id: str) -> torch.Tensor:
        """
        Koduje rękę gracza.
        
        Features per kolor (11):
        - num_cards: liczba kart w kolorze (0-6, znormalizowane)
        - has_ace: czy ma Asa
        - has_ten: czy ma 10
        - has_king: czy ma Króla
        - has_queen: czy ma Damę
        - has_jack: czy ma Waleta
        - has_nine: czy ma 9
        - has_marriage: czy ma meldunek (K+Q)
        - suit_points: punkty w kolorze (znormalizowane 0-1)
        - is_longest: czy to najdłuższy kolor
        - is_trump_marriage: czy to meldunek ATUTOWY (40 pkt!)
        
        Features globalne (12):
        - total_points: suma punktów w ręce (znormalizowana)
        - high_cards: liczba wysokich kart (A, 10)
        - marriages: liczba meldunków
        - trump_marriage_points: punkty za meldunek atutowy (0 lub 40, znormalizowane)
        - longest_suit: długość najdłuższego koloru (znormalizowana)
        - shortest_suit: długość najkrótszego koloru (znormalizowana)
        - voids: liczba kolorów bez kart
        - singletons: liczba singli
        - balance: zrównoważenie ręki (0=bardzo nierówna, 1=równa)
        - position: pozycja względem rozdającego (znormalizowana 0-1)
        - cards_in_hand: liczba kart w ręce (znormalizowana)
        - is_dealer: czy gracz jest rozdającym
        """
        # Pobierz rękę gracza
        rece = game_state.get('rece_graczy', {})
        reka_raw = rece.get(player_id, [])
        
        # Parsuj karty
        cards = self._parse_hand(reka_raw)
        
        # Aktualny atut (jeśli ustalony)
        kontrakt_info = game_state.get('kontrakt', {})
        current_trump = None
        if kontrakt_info:
            current_trump = kontrakt_info.get('atut')
        
        # Grupuj karty per kolor
        suits_cards = {suit: [] for suit in SUIT_ORDER}
        for card in cards:
            if card.kolor in suits_cards:
                suits_cards[card.kolor].append(card)
        
        # Oblicz długości kolorów
        suit_lengths = {suit: len(cards_list) for suit, cards_list in suits_cards.items()}
        max_length = max(suit_lengths.values()) if suit_lengths else 0
        min_length = min(suit_lengths.values()) if suit_lengths else 0
        
        # Enkoduj per kolor
        suit_features = []
        total_points = 0
        high_cards = 0
        marriages = 0
        trump_marriage_points = 0
        
        for suit in SUIT_ORDER:
            suit_cards = suits_cards[suit]
            ranks_in_suit = {card.ranga for card in suit_cards}
            
            # Podstawowe features
            num_cards = len(suit_cards) / 6.0  # Znormalizowane
            has_ace = 1.0 if 'AS' in ranks_in_suit else 0.0
            has_ten = 1.0 if 'DZIESIATKA' in ranks_in_suit else 0.0
            has_king = 1.0 if 'KROL' in ranks_in_suit else 0.0
            has_queen = 1.0 if 'DAMA' in ranks_in_suit else 0.0
            has_jack = 1.0 if 'WALET' in ranks_in_suit else 0.0
            has_nine = 1.0 if 'DZIEWIATKA' in ranks_in_suit else 0.0
            
            # Meldunek
            has_marriage = 1.0 if ('KROL' in ranks_in_suit and 'DAMA' in ranks_in_suit) else 0.0
            
            # Czy to meldunek ATUTOWY (bardzo ważne - 40 pkt!)
            is_trump_marriage = 0.0
            if has_marriage and current_trump and suit == current_trump:
                is_trump_marriage = 1.0
                trump_marriage_points = 40
            
            # Punkty w kolorze
            suit_points = sum(card.value for card in suit_cards)
            suit_points_norm = suit_points / 24.0  # Max 11+10+4+3+2+0 = 30, używamy 24 jako aprox
            
            # Czy najdłuższy
            is_longest = 1.0 if len(suit_cards) == max_length and max_length > 0 else 0.0
            
            # Dodaj features koloru
            suit_features.extend([
                num_cards,
                has_ace,
                has_ten,
                has_king,
                has_queen,
                has_jack,
                has_nine,
                has_marriage,
                suit_points_norm,
                is_longest,
                is_trump_marriage,
            ])
            
            # Aktualizuj globalne
            total_points += suit_points
            high_cards += (1 if has_ace else 0) + (1 if has_ten else 0)
            marriages += int(has_marriage)
        
        # Features globalne
        total_cards = len(cards)
        voids = sum(1 for length in suit_lengths.values() if length == 0)
        singletons = sum(1 for length in suit_lengths.values() if length == 1)
        
        # Zrównoważenie (variance długości kolorów)
        if total_cards > 0:
            avg_length = total_cards / 4.0
            variance = sum((length - avg_length) ** 2 for length in suit_lengths.values()) / 4.0
            balance = 1.0 - min(variance / 4.0, 1.0)  # 0 = nierówna, 1 = równa
        else:
            balance = 0.5
        
        # Pozycja (TODO: potrzebujemy info o rozdającym)
        position = 0.0  # Na razie placeholder
        
        # Czy rozdający
        is_dealer = 0.0  # Na razie placeholder
        
        global_features = [
            total_points / 120.0,  # Znormalizowane (max możliwe)
            high_cards / 8.0,  # Max 8 wysokich kart
            marriages / 4.0,  # Max 4 meldunki
            trump_marriage_points / 40.0,  # 0 lub 1
            max_length / 6.0,
            min_length / 6.0,
            voids / 4.0,
            singletons / 4.0,
            balance,
            position,
            total_cards / 6.0,
            is_dealer,
        ]
        
        # Połącz
        all_features = suit_features + global_features
        return torch.tensor(all_features, dtype=torch.float32)
    
    def _encode_game_info(self,
                          game_state: Dict[str, Any],
                          player_id: str) -> torch.Tensor:
        """
        Koduje informacje o stanie gry.
        
        Features (8 + 5 + 5 + 6 = 24):
        - phase: one-hot fazy gry (8)
        - contract: one-hot kontraktu (5)
        - trump: one-hot atutu (5)
        - game_features: (6)
            - multiplier (znormalizowany)
            - points_us (znormalizowane)
            - points_them (znormalizowane)
            - is_playing (czy jesteśmy grającym)
            - is_defending (czy jesteśmy obrońcą)
            - cards_played_count (znormalizowane)
        """
        features = []
        
        # Faza (one-hot, 8 dim)
        phase_str = game_state.get('faza', 'PRZED_ROZDANIEM')
        phase_idx = PHASE_INDICES.get(phase_str, 0)
        phase_onehot = [0.0] * 8
        if 0 <= phase_idx < 8:
            phase_onehot[phase_idx] = 1.0
        features.extend(phase_onehot)
        
        # Kontrakt (one-hot, 5 dim)
        kontrakt_info = game_state.get('kontrakt', {})
        contract_str = kontrakt_info.get('typ') if kontrakt_info else None
        contract_idx = CONTRACT_INDICES.get(contract_str, 0)
        contract_onehot = [0.0] * 5
        if 0 <= contract_idx < 5:
            contract_onehot[contract_idx] = 1.0
        features.extend(contract_onehot)
        
        # Atut (one-hot, 5 dim)
        trump_str = kontrakt_info.get('atut') if kontrakt_info else None
        trump_idx = SUIT_INDICES.get(trump_str, 0)
        trump_onehot = [0.0] * 5
        if 0 <= trump_idx < 5:
            trump_onehot[trump_idx] = 1.0
        features.extend(trump_onehot)
        
        # Mnożnik
        multiplier = game_state.get('mnoznik_lufy', 1)
        multiplier_norm = min(multiplier / 16.0, 1.0)  # Max 16 (teoretycznie)
        features.append(multiplier_norm)
        
        # Punkty w rozdaniu
        punkty = game_state.get('punkty_w_rozdaniu', {})
        
        # Musimy określić "nas" i "ich" - zależy od trybu gry
        # Na razie uproszczenie: suma punktów dla gracza
        points_us = 0.0
        points_them = 0.0
        
        # Sprawdź czy mamy punkty_meczowe (dla określenia drużyn)
        punkty_meczowe = game_state.get('punkty_meczowe', {})
        
        # Uproszczone: weź punkty gracza jako "us"
        if player_id in punkty:
            points_us = punkty.get(player_id, 0) / 120.0
        
        # Reszta jako "them"
        for pid, pts in punkty.items():
            if pid != player_id:
                points_them += pts
        points_them = min(points_them / 120.0, 1.0)
        
        features.append(points_us)
        features.append(points_them)
        
        # Czy grający/obrońca
        gracz_grajacy = game_state.get('gracz_grajacy')
        is_playing = 1.0 if gracz_grajacy == player_id else 0.0
        is_defending = 1.0 if gracz_grajacy and gracz_grajacy != player_id else 0.0
        features.append(is_playing)
        features.append(is_defending)
        
        # Liczba zagranych kart (aproksymacja postępu gry)
        historia = game_state.get('historia_rozdania', [])
        cards_played = sum(1 for log in historia if log.get('typ') == 'zagranie_karty')
        cards_played_norm = cards_played / 24.0  # Max 24 karty
        features.append(cards_played_norm)
        
        return torch.tensor(features, dtype=torch.float32)
    
    def _encode_play_state(self,
                           game_state: Dict[str, Any],
                           player_id: str) -> torch.Tensor:
        """
        Koduje stan rozgrywki (zagrane karty, aktualna lewa).
        
        Features (24 + 16 = 40):
        - cards_played: one-hot zagranych kart (24)
        - current_trick: 4 pozycje × 4 features (16)
        """
        features = []
        
        # Zagrane karty (one-hot, 24 dim)
        cards_played = [0.0] * 24
        historia = game_state.get('historia_rozdania', [])
        
        for log in historia:
            if log.get('typ') == 'zagranie_karty':
                karta_str = log.get('karta', '')
                card_idx = self._card_to_index(karta_str)
                if card_idx is not None and 0 <= card_idx < 24:
                    cards_played[card_idx] = 1.0
        
        features.extend(cards_played)
        
        # Aktualna lewa (16 dim = 4 pozycje × 4 features)
        karty_na_stole = game_state.get('karty_na_stole', [])
        
        for i in range(4):  # 4 możliwe pozycje w lewie
            if i < len(karty_na_stole):
                karta_info = karty_na_stole[i]
                karta_str = karta_info.get('karta', '')
                gracz = karta_info.get('gracz', '')
                
                # Feature 1: czy pozycja zajęta
                features.append(1.0)
                
                # Feature 2: czy to nasza karta
                features.append(1.0 if gracz == player_id else 0.0)
                
                # Feature 3: wartość karty (znormalizowana)
                card = self._parse_card_string(karta_str)
                if card:
                    features.append(card.value / 11.0)
                else:
                    features.append(0.0)
                
                # Feature 4: czy to kolor wiodący
                # Uproszczenie: pierwsza karta = wiodąca
                if i == 0:
                    features.append(1.0)  # Pierwsza zawsze wiodąca
                else:
                    first_card_str = karty_na_stole[0].get('karta', '') if karty_na_stole else ''
                    first_card = self._parse_card_string(first_card_str)
                    if card and first_card and card.kolor == first_card.kolor:
                        features.append(1.0)
                    else:
                        features.append(0.0)
            else:
                # Pusta pozycja
                features.extend([0.0, 0.0, 0.0, 0.0])
        
        return torch.tensor(features, dtype=torch.float32)
    
    def get_action_mask(self,
                        game_state: Dict[str, Any],
                        player_id: str) -> torch.Tensor:
        """
        Zwraca maskę legalnych akcji.
        
        Returns:
            Tensor bool o wymiarze (TOTAL_ACTIONS,)
        """
        mask = torch.zeros(self.config.TOTAL_ACTIONS, dtype=torch.bool)
        
        # Pobierz możliwe akcje
        mozliwe_akcje = game_state.get('mozliwe_akcje', [])
        grywalne_karty = game_state.get('grywalne_karty', [])
        
        # Mapuj akcje licytacyjne
        for action in mozliwe_akcje:
            idx = self._action_to_index(action)
            if idx is not None and 0 <= idx < len(mask):
                mask[idx] = True
        
        # Mapuj grywalne karty
        for karta_str in grywalne_karty:
            idx = self._card_action_to_index(karta_str)
            if idx is not None and 0 <= idx < len(mask):
                mask[idx] = True
        
        return mask
    
    def decode_action(self, action_idx: int) -> Dict[str, Any]:
        """
        Dekoduje indeks akcji na słownik akcji dla silnika.
        
        Args:
            action_idx: Indeks akcji (0 do TOTAL_ACTIONS-1)
            
        Returns:
            Słownik akcji kompatybilny z silnikiem gry
        """
        if action_idx in ACTION_INDEX_TO_DICT:
            return ACTION_INDEX_TO_DICT[action_idx].copy()
        else:
            raise ValueError(f"Nieznany indeks akcji: {action_idx}")
    
    # === Metody pomocnicze ===
    
    def _parse_hand(self, reka_raw) -> List[CardInfo]:
        """Parsuje rękę z różnych formatów."""
        cards = []
        
        if isinstance(reka_raw, list):
            for item in reka_raw:
                if isinstance(item, str):
                    card = self._parse_card_string(item)
                    if card:
                        cards.append(card)
                elif isinstance(item, dict):
                    ranga = item.get('ranga', '')
                    kolor = item.get('kolor', '')
                    if ranga and kolor:
                        cards.append(CardInfo(ranga=ranga.upper(), kolor=kolor.upper()))
        
        return cards
    
    def _parse_card_string(self, card_str: str) -> Optional[CardInfo]:
        """Parsuje string karty (np. 'As Czerwien') na CardInfo."""
        if not card_str:
            return None
        
        try:
            parts = card_str.split()
            if len(parts) >= 2:
                ranga = parts[0].upper()
                kolor = parts[1].upper()
                return CardInfo(ranga=ranga, kolor=kolor)
        except:
            pass
        
        return None
    
    def _card_to_index(self, card_str: str) -> Optional[int]:
        """Konwertuje string karty na indeks (0-23)."""
        card = self._parse_card_string(card_str)
        if not card:
            return None
        
        try:
            suit_idx = SUIT_ORDER.index(card.kolor)
            rank_idx = RANK_ORDER.index(card.ranga)
            return suit_idx * 6 + rank_idx
        except ValueError:
            return None
    
    def _action_to_index(self, action: Dict[str, Any]) -> Optional[int]:
        """Konwertuje słownik akcji na indeks."""
        typ = action.get('typ', '')
        
        if typ == 'deklaracja':
            kontrakt = action.get('kontrakt', '')
            if isinstance(kontrakt, str):
                kontrakt_str = kontrakt
            else:
                kontrakt_str = kontrakt.name if hasattr(kontrakt, 'name') else str(kontrakt)
            
            atut = action.get('atut')
            if atut:
                if isinstance(atut, str):
                    atut_str = atut
                else:
                    atut_str = atut.name if hasattr(atut, 'name') else str(atut)
            else:
                atut_str = None
            
            key = (typ, kontrakt_str, atut_str)
            return DICT_TO_ACTION_INDEX.get(key)
        
        elif typ == 'przebicie':
            kontrakt = action.get('kontrakt', '')
            if isinstance(kontrakt, str):
                kontrakt_str = kontrakt
            else:
                kontrakt_str = kontrakt.name if hasattr(kontrakt, 'name') else str(kontrakt)
            key = (typ, kontrakt_str)
            return DICT_TO_ACTION_INDEX.get(key)
        
        elif typ in ['pas', 'pas_lufa', 'lufa', 'kontra', 'do_konca', 'pytanie', 'nie_pytam', 'graj_normalnie']:
            key = (typ, None)
            return DICT_TO_ACTION_INDEX.get(key)
        
        return None
    
    def _card_action_to_index(self, card_str: str) -> Optional[int]:
        """Konwertuje string karty na indeks akcji zagrania."""
        card = self._parse_card_string(card_str)
        if not card:
            return None
        
        key = ('zagraj_karte', card.ranga, card.kolor)
        return DICT_TO_ACTION_INDEX.get(key)


# === Globalna instancja ===
ENCODER = StateEncoder()


if __name__ == "__main__":
    # Test enkodera
    encoder = StateEncoder()
    
    # Przykładowy stan gry
    test_state = {
        'faza': 'DEKLARACJA_1',
        'kolej_gracza': 'TestPlayer',
        'gracz_grajacy': None,
        'kontrakt': None,
        'rece_graczy': {
            'TestPlayer': ['As Czerwien', 'Krol Czerwien', 'Dama Czerwien', 'Dziesiatka Dzwonek', 'Walet Zoladz', 'Dziewiatka Wino'],
        },
        'karty_na_stole': [],
        'mozliwe_akcje': [
            {'typ': 'deklaracja', 'kontrakt': 'NORMALNA', 'atut': 'CZERWIEN'},
            {'typ': 'deklaracja', 'kontrakt': 'GORSZA', 'atut': None},
        ],
        'grywalne_karty': [],
        'historia_rozdania': [],
        'punkty_w_rozdaniu': {},
        'punkty_meczowe': {},
        'mnoznik_lufy': 1,
    }
    
    # Test enkodowania
    state_tensor = encoder.encode_state(test_state, 'TestPlayer')
    print(f"State tensor shape: {state_tensor.shape}")
    print(f"Expected: {NETWORK_CONFIG.TOTAL_STATE_DIM}")
    
    # Test maski akcji
    action_mask = encoder.get_action_mask(test_state, 'TestPlayer')
    print(f"\nAction mask shape: {action_mask.shape}")
    print(f"Legal actions: {action_mask.sum().item()}")
    
    # Pokaż legalne akcje
    legal_indices = torch.where(action_mask)[0].tolist()
    print(f"Legal action indices: {legal_indices}")
    for idx in legal_indices:
        print(f"  {idx}: {ACTION_INDEX_TO_DICT[idx]}")
