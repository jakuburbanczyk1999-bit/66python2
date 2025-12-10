# nn_training/config.py
"""
Konfiguracja dla treningu sieci neuronowej do gry 66.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from pathlib import Path

# =============================================================================
# ŚCIEŻKI
# =============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHECKPOINTS_DIR = BASE_DIR / "checkpoints"
LOGS_DIR = BASE_DIR / "logs"

# Utwórz foldery jeśli nie istnieją
DATA_DIR.mkdir(exist_ok=True)
CHECKPOINTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# =============================================================================
# WYMIARY SIECI
# =============================================================================

@dataclass
class NetworkConfig:
    """Konfiguracja wymiarów sieci neuronowej."""
    
    # --- Wymiary stanu (input) ---
    # Ręka gracza - per kolor (4 kolory)
    CARDS_PER_SUIT: int = 6  # 9, J, Q, K, 10, A
    NUM_SUITS: int = 4
    
    # Features per kolor (11 features × 4 kolory = 44)
    SUIT_FEATURES: int = 11  # num_cards, has_A, has_10, has_K, has_Q, has_J, has_9, has_marriage, suit_points, is_longest, is_trump_marriage
    
    # Features globalne ręki (12)
    GLOBAL_HAND_FEATURES: int = 12  # total_points, high_cards, marriages, trump_marriage_points, longest, shortest, voids, singletons, balance, position, cards_in_hand, is_dealer
    
    # Stan gry (24)
    PHASE_DIM: int = 8  # one-hot fazy
    CONTRACT_DIM: int = 5  # one-hot kontraktu (4 + brak)
    TRUMP_DIM: int = 5  # one-hot atutu (4 + brak)
    GAME_STATE_FEATURES: int = 6  # multiplier, points_us, points_them, is_playing, is_defending, cards_played_count
    
    # Rozgrywka - karty zagrane (24) + aktualna lewa (12)
    CARDS_PLAYED_DIM: int = 24  # one-hot wszystkich kart
    CURRENT_TRICK_DIM: int = 16  # 4 pozycje × 4 features (karta zagrana, kolor, ranga, czy wygrywa)
    
    @property
    def HAND_STATE_DIM(self) -> int:
        """Wymiar stanu ręki."""
        return self.SUIT_FEATURES * self.NUM_SUITS + self.GLOBAL_HAND_FEATURES
    
    @property
    def GAME_STATE_DIM(self) -> int:
        """Wymiar stanu gry."""
        return self.PHASE_DIM + self.CONTRACT_DIM + self.TRUMP_DIM + self.GAME_STATE_FEATURES
    
    @property
    def PLAY_STATE_DIM(self) -> int:
        """Wymiar stanu rozgrywki."""
        return self.CARDS_PLAYED_DIM + self.CURRENT_TRICK_DIM
    
    @property
    def TOTAL_STATE_DIM(self) -> int:
        """Całkowity wymiar stanu."""
        return self.HAND_STATE_DIM + self.GAME_STATE_DIM + self.PLAY_STATE_DIM
    
    # --- Wymiary akcji (output) ---
    # Deklaracje: 4 kontrakty × 4 kolory dla NORMALNA/BEZ_PYTANIA + 2 dla GORSZA/LEPSZA = 10
    # Ale GORSZA/LEPSZA nie mają atutu, więc:
    # NORMALNA: 4 kolory = 4
    # BEZ_PYTANIA: 4 kolory = 4  
    # GORSZA: 1
    # LEPSZA: 1
    # = 10 deklaracji
    
    DECLARATION_ACTIONS: int = 10
    
    # Akcje licytacyjne: pas, pas_lufa, lufa, kontra, do_konca, przebicie_gorsza, przebicie_lepsza, pytanie, nie_pytam, graj_normalnie
    BIDDING_ACTIONS: int = 10
    
    # Akcje rozgrywki: 24 karty (indeks w talii)
    PLAY_ACTIONS: int = 24
    
    @property
    def TOTAL_ACTIONS(self) -> int:
        """Całkowita liczba akcji."""
        return self.DECLARATION_ACTIONS + self.BIDDING_ACTIONS + self.PLAY_ACTIONS
    
    # --- Architektura sieci ---
    HIDDEN_DIM: int = 256
    NUM_HIDDEN_LAYERS: int = 3
    DROPOUT: float = 0.1


# =============================================================================
# KONFIGURACJA TRENINGU
# =============================================================================

@dataclass
class TrainingConfig:
    """Konfiguracja procesu treningu."""
    
    # Self-play
    GAMES_PER_ITERATION: int = 500
    MCTS_SIMULATIONS: int = 100  # Dla AlphaZero-style (opcjonalne)
    TEMPERATURE: float = 1.0  # Eksploracja w self-play
    TEMPERATURE_DECAY: float = 0.99
    MIN_TEMPERATURE: float = 0.1
    
    # Training
    BATCH_SIZE: int = 256
    LEARNING_RATE: float = 0.001
    WEIGHT_DECAY: float = 1e-4
    EPOCHS_PER_ITERATION: int = 10
    
    # Loss weights
    POLICY_LOSS_WEIGHT: float = 1.0
    VALUE_LOSS_WEIGHT: float = 1.0
    ENTROPY_BONUS: float = 0.01  # Zachęta do eksploracji
    
    # Evaluation
    EVAL_GAMES: int = 100
    WIN_RATE_THRESHOLD: float = 0.55  # Minimum do zapisania modelu
    
    # Checkpointing
    SAVE_EVERY_N_ITERATIONS: int = 10
    KEEP_LAST_N_CHECKPOINTS: int = 5
    
    # Hardware
    USE_GPU: bool = True
    NUM_WORKERS: int = 4  # Dla dataloadera
    
    # Totals
    TOTAL_ITERATIONS: int = 100


# =============================================================================
# MAPOWANIA AKCJI
# =============================================================================

# Mapowanie indeksu akcji na słownik akcji (dla silnika gry)
ACTION_INDEX_TO_DICT = {}
DICT_TO_ACTION_INDEX = {}

def _build_action_mappings():
    """Buduje mapowania akcji."""
    global ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX
    
    idx = 0
    
    # --- Deklaracje (0-9) ---
    # NORMALNA z 4 kolorami (0-3)
    for kolor in ['CZERWIEN', 'DZWONEK', 'ZOLADZ', 'WINO']:
        action = {'typ': 'deklaracja', 'kontrakt': 'NORMALNA', 'atut': kolor}
        ACTION_INDEX_TO_DICT[idx] = action
        DICT_TO_ACTION_INDEX[(action['typ'], action['kontrakt'], action.get('atut'))] = idx
        idx += 1
    
    # BEZ_PYTANIA z 4 kolorami (4-7)
    for kolor in ['CZERWIEN', 'DZWONEK', 'ZOLADZ', 'WINO']:
        action = {'typ': 'deklaracja', 'kontrakt': 'BEZ_PYTANIA', 'atut': kolor}
        ACTION_INDEX_TO_DICT[idx] = action
        DICT_TO_ACTION_INDEX[(action['typ'], action['kontrakt'], action.get('atut'))] = idx
        idx += 1
    
    # GORSZA (8)
    action = {'typ': 'deklaracja', 'kontrakt': 'GORSZA', 'atut': None}
    ACTION_INDEX_TO_DICT[idx] = action
    DICT_TO_ACTION_INDEX[(action['typ'], action['kontrakt'], None)] = idx
    idx += 1
    
    # LEPSZA (9)
    action = {'typ': 'deklaracja', 'kontrakt': 'LEPSZA', 'atut': None}
    ACTION_INDEX_TO_DICT[idx] = action
    DICT_TO_ACTION_INDEX[(action['typ'], action['kontrakt'], None)] = idx
    idx += 1
    
    # --- Akcje licytacyjne (10-19) ---
    bidding_actions = [
        {'typ': 'pas'},
        {'typ': 'pas_lufa'},
        {'typ': 'lufa'},
        {'typ': 'kontra'},
        {'typ': 'do_konca'},
        {'typ': 'przebicie', 'kontrakt': 'GORSZA'},
        {'typ': 'przebicie', 'kontrakt': 'LEPSZA'},
        {'typ': 'pytanie'},
        {'typ': 'nie_pytam'},
        {'typ': 'graj_normalnie'},
    ]
    
    for action in bidding_actions:
        ACTION_INDEX_TO_DICT[idx] = action
        key = (action['typ'], action.get('kontrakt'))
        DICT_TO_ACTION_INDEX[key] = idx
        idx += 1
    
    # --- Akcje rozgrywki (20-43) ---
    # Karty w kolejności: 4 kolory × 6 rang
    kolory = ['CZERWIEN', 'DZWONEK', 'ZOLADZ', 'WINO']
    rangi = ['DZIEWIATKA', 'WALET', 'DAMA', 'KROL', 'DZIESIATKA', 'AS']
    
    for kolor in kolory:
        for ranga in rangi:
            action = {'typ': 'zagraj_karte', 'karta': {'ranga': ranga, 'kolor': kolor}}
            ACTION_INDEX_TO_DICT[idx] = action
            DICT_TO_ACTION_INDEX[('zagraj_karte', ranga, kolor)] = idx
            idx += 1

# Zbuduj mapowania przy imporcie
_build_action_mappings()


# =============================================================================
# POMOCNICZE STAŁE
# =============================================================================

# Wartości punktowe kart
CARD_VALUES = {
    'AS': 11,
    'DZIESIATKA': 10,
    'KROL': 4,
    'DAMA': 3,
    'WALET': 2,
    'DZIEWIATKA': 0,
}

# Kolejność rang (dla sortowania)
RANK_ORDER = ['DZIEWIATKA', 'WALET', 'DAMA', 'KROL', 'DZIESIATKA', 'AS']

# Kolejność kolorów (dla sortowania)
SUIT_ORDER = ['CZERWIEN', 'ZOLADZ', 'DZWONEK', 'WINO']

# Indeksy faz gry
PHASE_INDICES = {
    'PRZED_ROZDANIEM': 0,
    'DEKLARACJA_1': 1,
    'LICYTACJA': 2,
    'LUFA': 3,
    'ROZGRYWKA': 4,
    'PODSUMOWANIE_ROZDANIA': 5,
    'ZAKONCZONE': 6,
    'FAZA_PYTANIA_START': 7,
    'FAZA_DECYZJI_PO_PASACH': 7,  # Mapujemy na to samo co FAZA_PYTANIA (uproszczenie)
}

# Indeksy kontraktów
CONTRACT_INDICES = {
    None: 0,
    'NORMALNA': 1,
    'BEZ_PYTANIA': 2,
    'GORSZA': 3,
    'LEPSZA': 4,
}

# Indeksy kolorów
SUIT_INDICES = {
    None: 0,
    'CZERWIEN': 1,
    'DZWONEK': 2,
    'ZOLADZ': 3,
    'WINO': 4,
}

# Indeksy rang
RANK_INDICES = {
    'DZIEWIATKA': 0,
    'WALET': 1,
    'DAMA': 2,
    'KROL': 3,
    'DZIESIATKA': 4,
    'AS': 5,
}


# =============================================================================
# GLOBALNE INSTANCJE KONFIGURACJI
# =============================================================================

NETWORK_CONFIG = NetworkConfig()
TRAINING_CONFIG = TrainingConfig()


if __name__ == "__main__":
    # Test konfiguracji
    print(f"=== Network Config ===")
    print(f"Hand state dim: {NETWORK_CONFIG.HAND_STATE_DIM}")
    print(f"Game state dim: {NETWORK_CONFIG.GAME_STATE_DIM}")
    print(f"Play state dim: {NETWORK_CONFIG.PLAY_STATE_DIM}")
    print(f"Total state dim: {NETWORK_CONFIG.TOTAL_STATE_DIM}")
    print(f"Total actions: {NETWORK_CONFIG.TOTAL_ACTIONS}")
    
    print(f"\n=== Action Mappings ===")
    print(f"Total mapped actions: {len(ACTION_INDEX_TO_DICT)}")
    for i in range(min(10, len(ACTION_INDEX_TO_DICT))):
        print(f"  {i}: {ACTION_INDEX_TO_DICT[i]}")
    print("  ...")
    for i in range(40, 44):
        print(f"  {i}: {ACTION_INDEX_TO_DICT[i]}")
