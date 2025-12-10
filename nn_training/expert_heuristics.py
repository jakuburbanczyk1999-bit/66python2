# nn_training/expert_heuristics.py
"""
Heurystyczny ekspert do deklaracji w grze 66.
Używany jako "nauczyciel" dla sieci neuronowej.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Ścieżki
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import CARD_VALUES, SUIT_ORDER, RANK_ORDER


@dataclass
class HandAnalysis:
    """Analiza ręki gracza."""
    # Per kolor
    suit_lengths: Dict[str, int]
    suit_points: Dict[str, int]
    suit_high_cards: Dict[str, int]  # A + 10
    marriages: Dict[str, bool]  # K+Q w kolorze
    
    # Globalne
    total_points: int
    total_high_cards: int
    num_marriages: int
    longest_suit: str
    longest_suit_length: int
    strongest_suit: str  # Najsilniejszy pod względem punktów
    
    # Specjalne
    has_void: bool  # Czy jest renons
    is_balanced: bool  # Czy zbalansowana (max różnica 2)


def analyze_hand(cards: List[Dict[str, str]]) -> HandAnalysis:
    """
    Analizuje rękę gracza.
    
    Args:
        cards: Lista kart jako słowniki {'ranga': ..., 'kolor': ...}
    """
    suit_lengths = {suit: 0 for suit in SUIT_ORDER}
    suit_points = {suit: 0 for suit in SUIT_ORDER}
    suit_high_cards = {suit: 0 for suit in SUIT_ORDER}
    suit_ranks = {suit: set() for suit in SUIT_ORDER}
    
    for card in cards:
        kolor = card.get('kolor', '').upper()
        ranga = card.get('ranga', '').upper()
        
        if kolor in suit_lengths:
            suit_lengths[kolor] += 1
            suit_points[kolor] += CARD_VALUES.get(ranga, 0)
            suit_ranks[kolor].add(ranga)
            
            if ranga in ['AS', 'DZIESIATKA']:
                suit_high_cards[kolor] += 1
    
    # Meldunki
    marriages = {}
    for suit in SUIT_ORDER:
        marriages[suit] = 'KROL' in suit_ranks[suit] and 'DAMA' in suit_ranks[suit]
    
    # Globalne
    total_points = sum(suit_points.values())
    total_high_cards = sum(suit_high_cards.values())
    num_marriages = sum(marriages.values())
    
    # Najdłuższy kolor
    longest_suit = max(SUIT_ORDER, key=lambda s: suit_lengths[s])
    longest_suit_length = suit_lengths[longest_suit]
    
    # Najsilniejszy kolor (punkty + długość)
    def suit_strength(s):
        return suit_points[s] + suit_lengths[s] * 3 + (20 if marriages[s] else 0)
    
    strongest_suit = max(SUIT_ORDER, key=suit_strength)
    
    # Specjalne
    has_void = any(length == 0 for length in suit_lengths.values())
    lengths = list(suit_lengths.values())
    is_balanced = max(lengths) - min(lengths) <= 2
    
    return HandAnalysis(
        suit_lengths=suit_lengths,
        suit_points=suit_points,
        suit_high_cards=suit_high_cards,
        marriages=marriages,
        total_points=total_points,
        total_high_cards=total_high_cards,
        num_marriages=num_marriages,
        longest_suit=longest_suit,
        longest_suit_length=longest_suit_length,
        strongest_suit=strongest_suit,
        has_void=has_void,
        is_balanced=is_balanced,
    )


def expert_declaration(hand: HandAnalysis, legal_actions: List[Dict]) -> Dict[str, Any]:
    """
    Heurystyczny ekspert wybiera najlepszą deklarację.
    
    Zasady:
    1. NORMALNA z najsilniejszym kolorem - domyślna bezpieczna opcja
    2. BEZ_PYTANIA - tylko z bardzo silnym kolorem (4+ karty, A+10+K lub meldunek)
    3. GORSZA - tylko z bardzo słabą ręką (mało punktów, bez wysokich kart)
    4. LEPSZA - prawie nigdy (potrzeba 6 kart w kolorze z A+10+K+Q lub podobne)
    
    Returns:
        Akcja do wykonania
    """
    # Filtruj tylko deklaracje
    declarations = [a for a in legal_actions if a.get('typ') == 'deklaracja']
    
    if not declarations:
        return legal_actions[0] if legal_actions else {}
    
    # Sprawdź czy LEPSZA jest możliwa (bardzo rzadko)
    # Potrzeba: 5+ kart w jednym kolorze z A+10 lub bardzo silna ręka
    if hand.longest_suit_length >= 5 and hand.total_high_cards >= 3:
        for action in declarations:
            if action.get('kontrakt') == 'LEPSZA':
                return action
    
    # Sprawdź czy GORSZA jest dobra
    # Potrzeba: słaba ręka (<=15 pkt), bez wysokich kart, zbalansowana
    if hand.total_points <= 15 and hand.total_high_cards <= 1 and hand.is_balanced:
        for action in declarations:
            if action.get('kontrakt') == 'GORSZA':
                return action
    
    # Sprawdź czy BEZ_PYTANIA jest możliwe
    # Potrzeba: silny kolor (4+ karty z A+10 lub meldunek + A)
    for suit in SUIT_ORDER:
        if hand.suit_lengths[suit] >= 4:
            has_top_cards = hand.suit_high_cards[suit] >= 2
            has_marriage_and_high = hand.marriages[suit] and hand.suit_high_cards[suit] >= 1
            
            if has_top_cards or has_marriage_and_high:
                for action in declarations:
                    if action.get('kontrakt') == 'BEZ_PYTANIA':
                        atut = action.get('atut')
                        if atut and (isinstance(atut, str) and atut.upper() == suit or 
                                    hasattr(atut, 'name') and atut.name == suit):
                            return action
    
    # Domyślnie: NORMALNA z najsilniejszym kolorem
    best_suit = hand.strongest_suit
    
    # Preferuj kolor z meldunkiem
    for suit in SUIT_ORDER:
        if hand.marriages[suit] and hand.suit_lengths[suit] >= 2:
            best_suit = suit
            break
    
    # Znajdź NORMALNA z tym kolorem
    for action in declarations:
        if action.get('kontrakt') == 'NORMALNA':
            atut = action.get('atut')
            if atut:
                atut_str = atut.upper() if isinstance(atut, str) else (atut.name if hasattr(atut, 'name') else str(atut))
                if atut_str == best_suit:
                    return action
    
    # Fallback: pierwsza NORMALNA
    for action in declarations:
        if action.get('kontrakt') == 'NORMALNA':
            return action
    
    return declarations[0]


def expert_bidding(hand: HandAnalysis, game_state: Dict, legal_actions: List[Dict]) -> Dict[str, Any]:
    """
    Heurystyczny ekspert dla fazy licytacji (LUFA).
    
    Zasady:
    1. Jeśli mamy silną rękę i ktoś zadeklarował słaby kontrakt -> LUFA
    2. Jeśli ktoś dał LUFA a my mamy silną rękę -> KONTRA
    3. Domyślnie -> PAS
    """
    action_types = {a.get('typ') for a in legal_actions}
    
    # Sprawdź aktualny kontrakt
    kontrakt = game_state.get('kontrakt', {})
    kontrakt_typ = None
    if kontrakt:
        kontrakt_typ = kontrakt.get('typ')
        if hasattr(kontrakt_typ, 'name'):
            kontrakt_typ = kontrakt_typ.name
    
    # Silna ręka = dużo punktów i wysokie karty
    strong_hand = hand.total_points >= 25 and hand.total_high_cards >= 2
    very_strong_hand = hand.total_points >= 30 and hand.total_high_cards >= 3
    
    # Jeśli możemy dać KONTRA i mamy bardzo silną rękę
    if 'kontra' in action_types and very_strong_hand:
        for action in legal_actions:
            if action.get('typ') == 'kontra':
                return action
    
    # Jeśli możemy dać LUFA i mamy silną rękę + przeciwnik ma słaby kontrakt
    if 'lufa' in action_types and strong_hand:
        # LUFA tylko jeśli przeciwnik zadeklarował NORMALNA
        if kontrakt_typ == 'NORMALNA':
            for action in legal_actions:
                if action.get('typ') == 'lufa':
                    return action
    
    # Domyślnie PAS lub PAS_LUFA
    for action in legal_actions:
        if action.get('typ') in ['pas', 'pas_lufa']:
            return action
    
    return legal_actions[0] if legal_actions else {}


def expert_question_phase(hand: HandAnalysis, game_state: Dict, legal_actions: List[Dict]) -> Dict[str, Any]:
    """
    Ekspert dla fazy pytania (po NORMALNA).
    
    Zasady:
    - Pytaj jeśli masz meldunek atutowy (40 pkt!)
    - Pytaj jeśli masz słabą rękę i potrzebujesz info
    - Nie pytaj jeśli masz silną rękę
    """
    action_types = {a.get('typ') for a in legal_actions}
    
    # Sprawdź czy mamy meldunek atutowy
    kontrakt = game_state.get('kontrakt', {})
    atut = kontrakt.get('atut') if kontrakt else None
    if atut:
        atut_str = atut.upper() if isinstance(atut, str) else (atut.name if hasattr(atut, 'name') else None)
        if atut_str and hand.marriages.get(atut_str, False):
            # Mamy meldunek atutowy - zdecydowanie pytaj!
            for action in legal_actions:
                if action.get('typ') == 'pytanie':
                    return action
    
    # Silna ręka - nie pytaj
    if hand.total_points >= 25 and hand.total_high_cards >= 2:
        for action in legal_actions:
            if action.get('typ') == 'nie_pytam':
                return action
    
    # Słaba ręka - pytaj
    for action in legal_actions:
        if action.get('typ') == 'pytanie':
            return action
    
    return legal_actions[0] if legal_actions else {}


def expert_play_card(hand_cards: List[str], game_state: Dict, legal_cards: List[str]) -> str:
    """
    Ekspert do grania kart.
    
    Proste zasady:
    1. Jeśli wygrywamy lewę - zagraj najniższą kartę która wygrywa
    2. Jeśli przegrywamy - zagraj najniższą kartę
    3. Jeśli prowadzimy - zagraj z najsilniejszego koloru
    """
    if not legal_cards:
        return ""
    
    # Parsuj karty
    def parse_card(card_str):
        parts = card_str.split()
        if len(parts) >= 2:
            return {'ranga': parts[0].upper(), 'kolor': parts[1].upper()}
        return None
    
    def card_value(card_str):
        card = parse_card(card_str)
        if card:
            return CARD_VALUES.get(card['ranga'], 0)
        return 0
    
    # Posortuj od najniższej
    sorted_cards = sorted(legal_cards, key=card_value)
    
    # Sprawdź czy to początek lewy
    karty_na_stole = game_state.get('karty_na_stole', [])
    
    if not karty_na_stole:
        # Prowadzimy - zagraj najwyższą z najdłuższego koloru
        # Uproszczenie: zagraj najwyższą
        return sorted_cards[-1]
    
    # Nie prowadzimy - zagraj najniższą legalną
    return sorted_cards[0]


class ExpertBot:
    """
    Bot heurystyczny używający reguł eksperckich.
    Służy jako "nauczyciel" dla sieci neuronowej.
    """
    
    def __init__(self):
        pass
    
    def get_action(self, game_state: Dict, player_id: str) -> Dict[str, Any]:
        """
        Zwraca akcję eksperta.
        
        Args:
            game_state: Stan gry z get_state_for_player
            player_id: ID gracza
            
        Returns:
            Akcja do wykonania
        """
        # Pobierz rękę
        rece = game_state.get('rece_graczy', {})
        reka_raw = rece.get(player_id, [])
        
        # Parsuj karty
        cards = []
        for item in reka_raw:
            if isinstance(item, str):
                parts = item.split()
                if len(parts) >= 2:
                    cards.append({'ranga': parts[0].upper(), 'kolor': parts[1].upper()})
            elif isinstance(item, dict):
                cards.append({
                    'ranga': item.get('ranga', '').upper(),
                    'kolor': item.get('kolor', '').upper()
                })
        
        # Analizuj rękę
        hand = analyze_hand(cards)
        
        # Pobierz legalne akcje
        legal_actions = game_state.get('mozliwe_akcje', [])
        grywalne_karty = game_state.get('grywalne_karty', [])
        
        # Faza gry
        faza = game_state.get('faza', '')
        
        # Wybierz akcję w zależności od fazy
        if faza == 'DEKLARACJA_1':
            return expert_declaration(hand, legal_actions)
        
        elif faza in ['LUFA', 'LICYTACJA']:
            return expert_bidding(hand, game_state, legal_actions)
        
        elif faza in ['FAZA_PYTANIA_START', 'FAZA_DECYZJI_PO_PASACH']:
            return expert_question_phase(hand, game_state, legal_actions)
        
        elif faza == 'ROZGRYWKA':
            if grywalne_karty:
                card_str = expert_play_card(reka_raw, game_state, grywalne_karty)
                if card_str:
                    parts = card_str.split()
                    if len(parts) >= 2:
                        return {
                            'typ': 'zagraj_karte',
                            'karta': {'ranga': parts[0], 'kolor': parts[1]}
                        }
            # Fallback
            if grywalne_karty:
                parts = grywalne_karty[0].split()
                if len(parts) >= 2:
                    return {
                        'typ': 'zagraj_karte', 
                        'karta': {'ranga': parts[0], 'kolor': parts[1]}
                    }
        
        # Fallback: pierwsza legalna akcja
        if legal_actions:
            return legal_actions[0]
        
        return {}


# Globalna instancja
EXPERT = ExpertBot()


if __name__ == "__main__":
    # Test eksperta
    print("=== Test Expert Heuristics ===\n")
    
    # Test analizy ręki
    test_cards = [
        {'ranga': 'AS', 'kolor': 'CZERWIEN'},
        {'ranga': 'KROL', 'kolor': 'CZERWIEN'},
        {'ranga': 'DAMA', 'kolor': 'CZERWIEN'},
        {'ranga': 'DZIESIATKA', 'kolor': 'DZWONEK'},
        {'ranga': 'WALET', 'kolor': 'ZOLADZ'},
        {'ranga': 'DZIEWIATKA', 'kolor': 'WINO'},
    ]
    
    hand = analyze_hand(test_cards)
    print(f"Hand analysis:")
    print(f"  Total points: {hand.total_points}")
    print(f"  High cards: {hand.total_high_cards}")
    print(f"  Marriages: {hand.marriages}")
    print(f"  Longest suit: {hand.longest_suit} ({hand.longest_suit_length})")
    print(f"  Strongest suit: {hand.strongest_suit}")
    
    # Test deklaracji
    test_actions = [
        {'typ': 'deklaracja', 'kontrakt': 'NORMALNA', 'atut': 'CZERWIEN'},
        {'typ': 'deklaracja', 'kontrakt': 'NORMALNA', 'atut': 'DZWONEK'},
        {'typ': 'deklaracja', 'kontrakt': 'BEZ_PYTANIA', 'atut': 'CZERWIEN'},
        {'typ': 'deklaracja', 'kontrakt': 'GORSZA', 'atut': None},
        {'typ': 'deklaracja', 'kontrakt': 'LEPSZA', 'atut': None},
    ]
    
    action = expert_declaration(hand, test_actions)
    print(f"\nExpert declaration: {action}")
    
    # Powinno wybrać NORMALNA CZERWIEN (bo ma A+K+Q - meldunek!)
