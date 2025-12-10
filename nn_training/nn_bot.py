# nn_training/nn_bot.py
"""
Bot używający sieci neuronowej do gry w 66.
Może być użyty jako zamiennik dla MCTS_Bot.
"""

import torch
import random
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Dodaj ścieżki do importów - NN_DIR musi być PRZED PROJECT_ROOT
import sys
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from engines.abstract_game_engine import AbstractGameEngine
from engines.sixtysix_engine import SixtySixEngine

try:
    from .config import CHECKPOINTS_DIR, ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX
    from .state_encoder import StateEncoder, ENCODER
    from .network import CardGameNetwork, LightweightNetwork
except ImportError:
    from config import CHECKPOINTS_DIR, ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX
    from state_encoder import StateEncoder, ENCODER
    from network import CardGameNetwork, LightweightNetwork


class NeuralNetworkBot:
    """
    Bot używający sieci neuronowej.
    
    API kompatybilne z MCTS_Bot z boty.py:
    - znajdz_najlepszy_ruch(stan_gry, nazwa_gracza, limit_czasu_s)
    
    Główne zalety nad MCTS:
    - ~100x szybszy (5-10ms vs 1000ms)
    - ~5x mniej pamięci (współdzielony model)
    - Skaluje się do 100+ botów
    """
    
    def __init__(self,
                 model_path: Optional[str] = None,
                 model: Optional[CardGameNetwork] = None,
                 temperature: float = 0.5,
                 greedy: bool = False,
                 device: str = None,
                 personality: Optional[str] = None):
        """
        Args:
            model_path: Ścieżka do zapisanego modelu
            model: Gotowy model (alternatywnie do model_path)
            temperature: Temperatura dla eksploracji (wyższa = bardziej losowy)
            greedy: Jeśli True, zawsze wybiera najlepszą akcję
            device: Urządzenie ('cuda' lub 'cpu')
            personality: Nazwa osobowości (wpływa na temperaturę i biasy)
        """
        # Urządzenie
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        
        # Model
        if model is not None:
            self.model = model
        elif model_path is not None:
            self.model = CardGameNetwork.load(model_path)
        else:
            # Spróbuj załadować domyślny model
            default_path = CHECKPOINTS_DIR / "best_model.pt"
            if default_path.exists():
                self.model = CardGameNetwork.load(str(default_path))
            else:
                raise ValueError("Nie podano modelu i nie znaleziono domyślnego!")
        
        self.model.to(self.device)
        self.model.eval()
        
        # Parametry
        self.temperature = temperature
        self.greedy = greedy
        self.personality = personality
        
        # Enkoder
        self.encoder = ENCODER
        
        # Osobowości (biasy temperaturowe i akcji)
        self._setup_personality()
    
    def _setup_personality(self):
        """Konfiguruje parametry osobowości."""
        self.action_biases = {}  # Biasy dla określonych akcji
        
        if self.personality == 'aggressive':
            # Bardziej agresywny - preferuje lufy i wysokie kontrakty
            self.temperature = 0.8
            self.action_biases = {
                'lufa': 0.3,
                'kontra': 0.3,
                'LEPSZA': 0.2,
                'BEZ_PYTANIA': 0.2,
            }
        
        elif self.personality == 'cautious':
            # Ostrożny - preferuje pasy i normalną
            self.temperature = 0.3
            self.action_biases = {
                'pas': 0.2,
                'pas_lufa': 0.3,
                'NORMALNA': 0.2,
            }
        
        elif self.personality == 'chaotic':
            # Chaotyczny - wysoka temperatura, mniejsze preferencje
            self.temperature = 1.5
        
        elif self.personality == 'calculated':
            # Kalkulujący - niska temperatura, dokładniejszy
            self.temperature = 0.2
            self.greedy = True
        
        elif self.personality == 'gorsza_enjoyer':
            # Lubi grać Gorszą
            self.temperature = 0.5
            self.action_biases = {'GORSZA': 0.5}
        
        elif self.personality == 'lepsza_enjoyer':
            # Lubi grać Lepszą
            self.temperature = 0.5
            self.action_biases = {'LEPSZA': 0.5}
    
    def znajdz_najlepszy_ruch(self,
                              poczatkowy_stan_gry: AbstractGameEngine,
                              nazwa_gracza_bota: str,
                              limit_czasu_s: float = 0.0) -> Dict[str, Any]:
        """
        Znajduje najlepszy ruch używając sieci neuronowej.
        
        API kompatybilne z MCTS_Bot.
        
        Args:
            poczatkowy_stan_gry: Silnik gry (AbstractGameEngine)
            nazwa_gracza_bota: Nazwa gracza bota
            limit_czasu_s: Ignorowany (NN jest bardzo szybka)
            
        Returns:
            Słownik akcji do wykonania
        """
        # Sprawdź typ silnika
        if not isinstance(poczatkowy_stan_gry, SixtySixEngine):
            print(f"BŁĄD: NeuralNetworkBot obsługuje tylko SixtySixEngine")
            return {}
        
        # Pobierz stan gry
        state_dict = poczatkowy_stan_gry.get_state_for_player(nazwa_gracza_bota)
        
        # Sprawdź czy to nasza tura
        if state_dict.get('kolej_gracza') != nazwa_gracza_bota:
            return {}
        
        # Pobierz legalne akcje
        legal_actions = poczatkowy_stan_gry.get_legal_actions(nazwa_gracza_bota)
        grywalne_karty = state_dict.get('grywalne_karty', [])
        
        # Mapuj na indeksy
        legal_indices = []
        for action in legal_actions:
            idx = self._action_to_index(action)
            if idx is not None:
                legal_indices.append(idx)
        
        for karta_str in grywalne_karty:
            idx = self._card_to_action_index(karta_str)
            if idx is not None:
                legal_indices.append(idx)
        
        if not legal_indices:
            print(f"OSTRZEŻENIE: Brak legalnych akcji dla {nazwa_gracza_bota}")
            return {}
        
        # Jeśli tylko jedna opcja, wybierz ją
        if len(legal_indices) == 1:
            return ACTION_INDEX_TO_DICT[legal_indices[0]].copy()
        
        # Enkoduj stan
        state_tensor = self.encoder.encode_state(state_dict, nazwa_gracza_bota)
        action_mask = self.encoder.get_action_mask(state_dict, nazwa_gracza_bota)
        
        # Przenieś na urządzenie
        state_tensor = state_tensor.to(self.device)
        action_mask = action_mask.to(self.device)
        
        # Wybierz akcję
        with torch.no_grad():
            action_idx = self._select_action(state_tensor, action_mask, legal_indices)
        
        # Konwertuj na słownik akcji
        action = ACTION_INDEX_TO_DICT[action_idx].copy()
        
        return action
    
    def _select_action(self,
                       state: torch.Tensor,
                       action_mask: torch.Tensor,
                       legal_indices: List[int]) -> int:
        """Wybiera akcję używając modelu i parametrów osobowości."""
        # Forward pass
        if state.dim() == 1:
            state = state.unsqueeze(0)
        if action_mask.dim() == 1:
            action_mask = action_mask.unsqueeze(0)
        
        policy, _ = self.model(state, action_mask)
        policy = policy.squeeze(0)
        
        # Zastosuj biasy osobowości
        if self.action_biases:
            policy = self._apply_biases(policy, legal_indices)
        
        # Wybór akcji
        if self.greedy:
            # Wybierz najlepszą legalną akcję
            legal_mask = torch.zeros_like(policy, dtype=torch.bool)
            for idx in legal_indices:
                legal_mask[idx] = True
            
            masked_policy = policy.clone()
            masked_policy[~legal_mask] = float('-inf')
            action_idx = masked_policy.argmax().item()
        else:
            # Zastosuj temperaturę i sampluj
            log_policy = torch.log(policy + 1e-10) / self.temperature
            
            # Maskuj nielegalne
            legal_mask = torch.zeros_like(log_policy, dtype=torch.bool)
            for idx in legal_indices:
                legal_mask[idx] = True
            log_policy[~legal_mask] = float('-inf')
            
            # Softmax
            probs = torch.softmax(log_policy, dim=-1)
            
            # Sampluj
            try:
                action_idx = torch.multinomial(probs, 1).item()
            except RuntimeError:
                # Fallback jeśli wszystkie prawdopodobieństwa są 0
                action_idx = random.choice(legal_indices)
        
        # Upewnij się, że akcja jest legalna
        if action_idx not in legal_indices:
            action_idx = random.choice(legal_indices)
        
        return action_idx
    
    def _apply_biases(self, 
                      policy: torch.Tensor, 
                      legal_indices: List[int]) -> torch.Tensor:
        """Zastosowuje biasy osobowości do policy."""
        biased_policy = policy.clone()
        
        for idx in legal_indices:
            action = ACTION_INDEX_TO_DICT.get(idx, {})
            
            # Sprawdź biasy
            for bias_key, bias_value in self.action_biases.items():
                should_apply = False
                
                # Sprawdź typ akcji
                if action.get('typ') == bias_key:
                    should_apply = True
                # Sprawdź kontrakt
                elif action.get('kontrakt') == bias_key:
                    should_apply = True
                
                if should_apply:
                    # Dodaj bias (mnożąc prawdopodobieństwo)
                    biased_policy[idx] = biased_policy[idx] * (1.0 + bias_value)
        
        # Renormalizuj
        total = biased_policy[legal_indices].sum()
        if total > 0:
            for idx in legal_indices:
                biased_policy[idx] = biased_policy[idx] / total
        
        return biased_policy
    
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


# === Fabryka botów ===

def create_nn_bot(personality: str = None,
                  model_path: str = None,
                  temperature: float = 0.5) -> NeuralNetworkBot:
    """
    Tworzy bota NN z określoną osobowością.
    
    Args:
        personality: Nazwa osobowości ('aggressive', 'cautious', 'chaotic', etc.)
        model_path: Ścieżka do modelu (domyślny jeśli None)
        temperature: Bazowa temperatura
        
    Returns:
        Skonfigurowany NeuralNetworkBot
    """
    return NeuralNetworkBot(
        model_path=model_path,
        temperature=temperature,
        personality=personality
    )


# === Predefiniowane osobowości (kompatybilne z boty.py) ===

NN_BOT_PERSONALITIES = {
    'topplayer': {'temperature': 0.3, 'greedy': True},
    'szaleniec': {'temperature': 1.2, 'personality': 'aggressive'},
    'gorsza_enjoyer': {'temperature': 0.5, 'personality': 'gorsza_enjoyer'},
    'lepsza_enjoyer': {'temperature': 0.5, 'personality': 'lepsza_enjoyer'},
    'beginner': {'temperature': 0.8, 'personality': 'cautious'},
    'chaotic': {'temperature': 1.5, 'personality': 'chaotic'},
    'counter': {'temperature': 0.4, 'personality': 'aggressive'},
    'nie_lubie_pytac': {'temperature': 0.5},
}


def create_nn_bot_by_name(name: str, model_path: str = None) -> NeuralNetworkBot:
    """
    Tworzy bota NN po nazwie (kompatybilne z BOT_PERSONALITIES z boty.py).
    
    Args:
        name: Nazwa osobowości z NN_BOT_PERSONALITIES
        model_path: Ścieżka do modelu
        
    Returns:
        NeuralNetworkBot
    """
    config = NN_BOT_PERSONALITIES.get(name, {})
    
    return NeuralNetworkBot(
        model_path=model_path,
        temperature=config.get('temperature', 0.5),
        greedy=config.get('greedy', False),
        personality=config.get('personality'),
    )


if __name__ == "__main__":
    print("=== Test NeuralNetworkBot ===\n")
    
    # Sprawdź czy istnieje model
    default_model = CHECKPOINTS_DIR / "best_model.pt"
    
    if not default_model.exists():
        print("Brak wytrenowanego modelu. Tworzę nowy dla testów...")
        
        # Stwórz prosty model
        model = CardGameNetwork()
        model.save(name="best_model")
        print(f"Zapisano testowy model: {default_model}")
    
    # Test tworzenia bota
    print("\nTworzenie botów...")
    
    try:
        bot_default = NeuralNetworkBot()
        print("✓ Bot domyślny utworzony")
        
        bot_aggressive = create_nn_bot(personality='aggressive')
        print("✓ Bot agresywny utworzony")
        
        bot_cautious = create_nn_bot_by_name('beginner')
        print("✓ Bot ostrożny utworzony")
        
        print(f"\nUrządzenie: {bot_default.device}")
        print(f"Temperatura (domyślny): {bot_default.temperature}")
        print(f"Temperatura (agresywny): {bot_aggressive.temperature}")
        
    except Exception as e:
        print(f"✗ Błąd: {e}")
    
    # Test z prostą grą
    print("\n=== Test z grą ===")
    
    try:
        from engines.sixtysix_engine import SixtySixEngine
        
        # Stwórz grę
        players = ['Bot1', 'Bot2', 'Bot3', 'Bot4']
        settings = {
            'tryb': '4p',
            'rozdajacy_idx': 0,
            'nazwy_druzyn': {'My': 'Team1', 'Oni': 'Team2'}
        }
        
        engine = SixtySixEngine(players, settings)
        
        # Pobierz akcję od bota
        current = engine.get_current_player()
        if current:
            bot = NeuralNetworkBot()
            action = bot.znajdz_najlepszy_ruch(engine, current)
            print(f"Gracz {current}, wybrana akcja: {action}")
        
        print("✓ Test z grą zakończony pomyślnie")
        
    except Exception as e:
        print(f"✗ Błąd testu: {e}")
        import traceback
        traceback.print_exc()
