# nn_training/self_play.py
"""
Self-play do generowania danych treningowych.
Gry sieć vs sieć (lub sieć vs losowy) do zbierania (state, policy, value) tuple.
"""

import torch
import random
import numpy as np
import sys
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from tqdm import tqdm
import msgpack

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
    from .config import NETWORK_CONFIG, TRAINING_CONFIG, DATA_DIR, ACTION_INDEX_TO_DICT
    from .state_encoder import StateEncoder, ENCODER
    from .network import CardGameNetwork
    from .game_interface import GameInterface, GameOutcome
except ImportError:
    from config import NETWORK_CONFIG, TRAINING_CONFIG, DATA_DIR, ACTION_INDEX_TO_DICT
    from state_encoder import StateEncoder, ENCODER
    from network import CardGameNetwork
    from game_interface import GameInterface, GameOutcome


@dataclass
class Experience:
    """Pojedyncze doświadczenie z gry."""
    state: torch.Tensor  # Stan gry
    action_mask: torch.Tensor  # Maska legalnych akcji
    action: int  # Wybrana akcja (indeks)
    policy: torch.Tensor  # Policy z sieci (lub MCTS)
    value: float  # Outcome gry (reward)
    player_id: str  # ID gracza
    phase: str  # Faza gry


@dataclass
class GameData:
    """Dane z pojedynczej gry."""
    experiences: List[Experience] = field(default_factory=list)
    outcome: Optional[GameOutcome] = None
    
    def add_experience(self, exp: Experience):
        self.experiences.append(exp)
    
    def finalize(self, outcome: GameOutcome):
        """Ustaw outcome i zaktualizuj wartości (rewards) dla wszystkich doświadczeń."""
        self.outcome = outcome
        for exp in self.experiences:
            # Nagroda z perspektywy gracza, który podjął decyzję
            exp.value = outcome.rewards.get(exp.player_id, 0.0)


class SelfPlayWorker:
    """
    Worker do generowania danych przez self-play.
    """
    
    def __init__(self,
                 model: Optional[CardGameNetwork] = None,
                 encoder: Optional[StateEncoder] = None,
                 temperature: float = 1.0,
                 device: str = 'cpu'):
        """
        Args:
            model: Sieć neuronowa (None = losowy gracz)
            encoder: Enkoder stanu (domyślny jeśli None)
            temperature: Temperatura dla eksploracji
            device: Urządzenie dla tensora
        """
        self.model = model
        self.encoder = encoder or ENCODER
        self.temperature = temperature
        self.device = device
        
        if model:
            self.model.to(device)
            self.model.eval()
    
    def play_game(self,
                  player_ids: List[str] = None,
                  mode: str = '4p',
                  collect_data: bool = True) -> Tuple[GameOutcome, Optional[GameData]]:
        """
        Rozgrywa jedną grę i zbiera dane.
        
        Args:
            player_ids: Lista ID graczy
            mode: Tryb gry
            collect_data: Czy zbierać dane treningowe
            
        Returns:
            (outcome, game_data) - wynik gry i zebrane dane
        """
        if player_ids is None:
            if mode == '4p':
                player_ids = ['NN_1', 'NN_2', 'NN_3', 'NN_4']
            else:
                player_ids = ['NN_1', 'NN_2', 'NN_3']
        
        game = GameInterface(player_ids, mode)
        game_data = GameData() if collect_data else None
        
        move_count = 0
        max_moves = 200
        
        while not game.is_terminal() and move_count < max_moves:
            current = game.get_current_player()
            
            if current is None:
                break
            
            # Pobierz stan i legalne akcje
            state_dict = game.get_state(current)
            legal_indices = game.get_legal_action_indices(current)
            
            if not legal_indices:
                break
            
            # Enkoduj stan
            state_tensor = self.encoder.encode_state(state_dict, current)
            action_mask = self.encoder.get_action_mask(state_dict, current)
            
            # Wybierz akcję
            if self.model is not None:
                action, policy, value = self._select_action_with_model(
                    state_tensor, action_mask, legal_indices
                )
            else:
                action, policy = self._select_random_action(legal_indices, action_mask)
            
            # Zbierz doświadczenie
            if collect_data:
                exp = Experience(
                    state=state_tensor,
                    action_mask=action_mask,
                    action=action,
                    policy=policy,
                    value=0.0,  # Zostanie ustawione po grze
                    player_id=current,
                    phase=game.get_phase(),
                )
                game_data.add_experience(exp)
            
            # Wykonaj akcję
            game.perform_action_by_index(current, action)
            move_count += 1
        
        # Pobierz wynik
        outcome = game.get_outcome()
        
        # Finalizuj dane
        if collect_data and outcome:
            game_data.finalize(outcome)
        
        return outcome, game_data
    
    def _select_action_with_model(self,
                                   state: torch.Tensor,
                                   action_mask: torch.Tensor,
                                   legal_indices: List[int]) -> Tuple[int, torch.Tensor, torch.Tensor]:
        """Wybiera akcję używając modelu.
        
        Returns:
            (action, policy, value) - wybrana akcja, policy i wartość
        """
        state = state.to(self.device)
        action_mask = action_mask.to(self.device)
        
        with torch.no_grad():
            action, policy, value = self.model.get_action(
                state, action_mask, 
                temperature=self.temperature,
                greedy=False
            )
        
        # Upewnij się, że wybrana akcja jest legalna
        if action not in legal_indices:
            # Fallback: wybierz losową legalną
            action = random.choice(legal_indices)
            # Popraw policy (daj całą masę na wybraną akcję)
            policy = torch.zeros_like(policy)
            policy[action] = 1.0
        
        return action, policy.cpu(), value.cpu()
    
    def _select_random_action(self,
                               legal_indices: List[int],
                               action_mask: torch.Tensor) -> Tuple[int, torch.Tensor]:
        """Wybiera losową legalną akcję."""
        action = random.choice(legal_indices)
        
        # Stwórz równomierną policy dla legalnych akcji
        policy = torch.zeros(action_mask.shape[0])
        for idx in legal_indices:
            policy[idx] = 1.0 / len(legal_indices)
        
        return action, policy


def generate_self_play_data(model: Optional[CardGameNetwork] = None,
                            num_games: int = 100,
                            temperature: float = 1.0,
                            mode: str = '4p',
                            device: str = 'cpu',
                            show_progress: bool = True) -> List[Experience]:
    """
    Generuje dane treningowe przez self-play.
    
    Args:
        model: Model do użycia (None = losowy)
        num_games: Liczba gier
        temperature: Temperatura eksploracji
        mode: Tryb gry
        device: Urządzenie
        show_progress: Czy pokazywać progress bar
        
    Returns:
        Lista doświadczeń
    """
    worker = SelfPlayWorker(model, temperature=temperature, device=device)
    
    all_experiences = []
    outcomes = {'wins': 0, 'total_points': 0}
    
    iterator = range(num_games)
    if show_progress:
        iterator = tqdm(iterator, desc="Self-play")
    
    for _ in iterator:
        outcome, game_data = worker.play_game(mode=mode, collect_data=True)
        
        if game_data:
            all_experiences.extend(game_data.experiences)
        
        if outcome:
            outcomes['total_points'] += outcome.points_awarded
    
    if show_progress:
        print(f"Generated {len(all_experiences)} experiences from {num_games} games")
        print(f"Avg points per game: {outcomes['total_points'] / num_games:.2f}")
    
    return all_experiences


def save_experiences(experiences: List[Experience], 
                     filename: str = None) -> Path:
    """
    Zapisuje doświadczenia do pliku.
    
    Args:
        experiences: Lista doświadczeń
        filename: Nazwa pliku (auto-generowana jeśli None)
        
    Returns:
        Ścieżka do zapisanego pliku
    """
    if filename is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"selfplay_data_{timestamp}.pt"
    
    filepath = DATA_DIR / filename
    
    # Konwertuj do formatu do zapisu
    data = []
    for exp in experiences:
        data.append({
            'state': exp.state.numpy().tolist(),
            'action_mask': exp.action_mask.numpy().tolist(),
            'action': exp.action,
            'policy': exp.policy.numpy().tolist(),
            'value': exp.value,
            'player_id': exp.player_id,
            'phase': exp.phase,
        })
    
    # Zapisz
    torch.save(data, filepath)
    print(f"Saved {len(experiences)} experiences to {filepath}")
    
    return filepath


def load_experiences(filepath: str) -> List[Experience]:
    """
    Ładuje doświadczenia z pliku.
    
    Args:
        filepath: Ścieżka do pliku
        
    Returns:
        Lista doświadczeń
    """
    data = torch.load(filepath)
    
    experiences = []
    for item in data:
        exp = Experience(
            state=torch.tensor(item['state'], dtype=torch.float32),
            action_mask=torch.tensor(item['action_mask'], dtype=torch.bool),
            action=item['action'],
            policy=torch.tensor(item['policy'], dtype=torch.float32),
            value=item['value'],
            player_id=item['player_id'],
            phase=item['phase'],
        )
        experiences.append(exp)
    
    print(f"Loaded {len(experiences)} experiences from {filepath}")
    return experiences


class ReplayBuffer:
    """
    Bufor do przechowywania doświadczeń z self-play.
    Wspiera priorytetyzowane próbkowanie i ograniczoną pojemność.
    """
    
    def __init__(self, capacity: int = 100000):
        """
        Args:
            capacity: Maksymalna liczba doświadczeń
        """
        self.capacity = capacity
        self.buffer: List[Experience] = []
        self.position = 0
    
    def add(self, experience: Experience):
        """Dodaje doświadczenie do bufora."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        
        self.position = (self.position + 1) % self.capacity
    
    def add_batch(self, experiences: List[Experience]):
        """Dodaje wiele doświadczeń."""
        for exp in experiences:
            self.add(exp)
    
    def sample(self, batch_size: int) -> List[Experience]:
        """Próbkuje batch doświadczeń."""
        batch_size = min(batch_size, len(self.buffer))
        return random.sample(self.buffer, batch_size)
    
    def sample_by_phase(self, batch_size: int, phases: List[str] = None) -> List[Experience]:
        """
        Próbkuje z priorytetem dla określonych faz.
        
        Args:
            batch_size: Rozmiar batcha
            phases: Lista faz do priorytetyzacji (None = wszystkie)
        """
        if phases is None:
            return self.sample(batch_size)
        
        # Filtruj po fazach
        filtered = [exp for exp in self.buffer if exp.phase in phases]
        
        if not filtered:
            return self.sample(batch_size)
        
        batch_size = min(batch_size, len(filtered))
        return random.sample(filtered, batch_size)
    
    def __len__(self):
        return len(self.buffer)
    
    def clear(self):
        """Czyści bufor."""
        self.buffer.clear()
        self.position = 0
    
    def save(self, filepath: str):
        """Zapisuje bufor do pliku."""
        save_experiences(self.buffer, filepath)
    
    def load(self, filepath: str):
        """Ładuje bufor z pliku."""
        self.buffer = load_experiences(filepath)
        self.position = len(self.buffer) % self.capacity


if __name__ == "__main__":
    # Test self-play
    print("=== Test Self-Play ===\n")
    
    # Test z losowym graczem
    print("Testing random self-play...")
    experiences = generate_self_play_data(
        model=None,
        num_games=10,
        temperature=1.0,
        show_progress=True
    )
    
    print(f"\nExperiences by phase:")
    phase_counts = {}
    for exp in experiences:
        phase_counts[exp.phase] = phase_counts.get(exp.phase, 0) + 1
    for phase, count in sorted(phase_counts.items()):
        print(f"  {phase}: {count}")
    
    print(f"\nValue distribution:")
    values = [exp.value for exp in experiences]
    print(f"  Min: {min(values):.2f}")
    print(f"  Max: {max(values):.2f}")
    print(f"  Mean: {np.mean(values):.2f}")
    
    # Test zapisu/odczytu
    print("\n=== Test Save/Load ===")
    filepath = save_experiences(experiences[:100], "test_data.pt")
    loaded = load_experiences(filepath)
    print(f"Loaded {len(loaded)} experiences")
    
    # Test replay buffer
    print("\n=== Test Replay Buffer ===")
    buffer = ReplayBuffer(capacity=1000)
    buffer.add_batch(experiences)
    print(f"Buffer size: {len(buffer)}")
    
    batch = buffer.sample(32)
    print(f"Sampled batch size: {len(batch)}")
    
    bidding_batch = buffer.sample_by_phase(32, ['DEKLARACJA_1', 'LICYTACJA', 'LUFA'])
    print(f"Bidding-focused batch size: {len(bidding_batch)}")
