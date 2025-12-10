# nn_training/network.py
"""
Architektura sieci neuronowej dla gry 66.
Policy-Value Network inspirowana AlphaZero.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
from pathlib import Path
import sys

# Dodaj ścieżki do importów - NN_DIR musi być PRZED PROJECT_ROOT
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Fix imports - działa zarówno jako moduł jak i bezpośrednio
try:
    from .config import NETWORK_CONFIG, CHECKPOINTS_DIR
except ImportError:
    from config import NETWORK_CONFIG, CHECKPOINTS_DIR


class ResidualBlock(nn.Module):
    """Blok rezydualny dla głębszych sieci."""
    
    def __init__(self, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(hidden_dim)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.layer_norm(x + residual)
        return F.relu(x)


class CardGameNetwork(nn.Module):
    """
    Sieć neuronowa do gry w 66.
    
    Architektura:
    - Input encoder: przetwarza stan gry
    - Shared trunk: wspólne warstwy dla policy i value
    - Policy head: prawdopodobieństwa akcji
    - Value head: ocena pozycji
    
    Input: state tensor (TOTAL_STATE_DIM)
    Output: 
        - policy: (TOTAL_ACTIONS,) - logits akcji
        - value: (1,) - ocena pozycji w [-1, 1]
    """
    
    def __init__(self, 
                 state_dim: Optional[int] = None,
                 action_dim: Optional[int] = None,
                 hidden_dim: Optional[int] = None,
                 num_hidden_layers: Optional[int] = None,
                 dropout: Optional[float] = None):
        super().__init__()
        
        # Użyj wartości z konfiguracji jeśli nie podano
        self.state_dim = state_dim or NETWORK_CONFIG.TOTAL_STATE_DIM
        self.action_dim = action_dim or NETWORK_CONFIG.TOTAL_ACTIONS
        self.hidden_dim = hidden_dim or NETWORK_CONFIG.HIDDEN_DIM
        self.num_hidden_layers = num_hidden_layers or NETWORK_CONFIG.NUM_HIDDEN_LAYERS
        self.dropout_rate = dropout or NETWORK_CONFIG.DROPOUT
        
        # Input encoder
        self.input_encoder = nn.Sequential(
            nn.Linear(self.state_dim, self.hidden_dim),
            nn.LayerNorm(self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(self.dropout_rate),
        )
        
        # Shared trunk (residual blocks)
        self.trunk = nn.ModuleList([
            ResidualBlock(self.hidden_dim, self.dropout_rate)
            for _ in range(self.num_hidden_layers)
        ])
        
        # Policy head
        self.policy_head = nn.Sequential(
            nn.Linear(self.hidden_dim, self.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(self.dropout_rate),
            nn.Linear(self.hidden_dim // 2, self.action_dim),
        )
        
        # Value head
        self.value_head = nn.Sequential(
            nn.Linear(self.hidden_dim, self.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(self.dropout_rate),
            nn.Linear(self.hidden_dim // 2, 1),
            nn.Tanh(),  # Output w [-1, 1]
        )
        
        # Inicjalizacja wag
        self._init_weights()
    
    def _init_weights(self):
        """Inicjalizacja wag sieci."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, nonlinearity='relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, 
                state: torch.Tensor,
                action_mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            state: Tensor stanu (batch_size, state_dim)
            action_mask: Maska legalnych akcji (batch_size, action_dim), True = legalna
            
        Returns:
            policy: Prawdopodobieństwa akcji (batch_size, action_dim)
            value: Ocena pozycji (batch_size, 1)
        """
        # Encode input
        x = self.input_encoder(state)
        
        # Trunk
        for block in self.trunk:
            x = block(x)
        
        # Policy head (logits)
        policy_logits = self.policy_head(x)
        
        # Zastosuj maskę (nielegalne akcje = -inf)
        if action_mask is not None:
            # Zamień False na bardzo małą wartość
            policy_logits = policy_logits.masked_fill(~action_mask, float('-inf'))
        
        # Softmax na logitach
        policy = F.softmax(policy_logits, dim=-1)
        
        # Value head
        value = self.value_head(x)
        
        return policy, value
    
    def get_action(self,
                   state: torch.Tensor,
                   action_mask: torch.Tensor,
                   temperature: float = 1.0,
                   greedy: bool = False) -> Tuple[int, torch.Tensor, torch.Tensor]:
        """
        Wybiera akcję na podstawie policy.
        
        Args:
            state: Tensor stanu (state_dim,) lub (1, state_dim)
            action_mask: Maska legalnych akcji
            temperature: Temperatura dla softmax (wyższa = więcej eksploracji)
            greedy: Jeśli True, wybierz najlepszą akcję
            
        Returns:
            action: Indeks wybranej akcji
            policy: Prawdopodobieństwa wszystkich akcji
            value: Ocena pozycji
        """
        # Dodaj wymiar batch jeśli potrzeba
        if state.dim() == 1:
            state = state.unsqueeze(0)
        if action_mask.dim() == 1:
            action_mask = action_mask.unsqueeze(0)
        
        # Forward pass
        with torch.no_grad():
            policy, value = self.forward(state, action_mask)
        
        # Wybór akcji
        if greedy:
            action = policy.argmax(dim=-1).item()
        else:
            # Zastosuj temperaturę
            if temperature != 1.0:
                # Przelicz logity z temperaturą
                policy_logits = torch.log(policy + 1e-10) / temperature
                policy_logits = policy_logits.masked_fill(~action_mask, float('-inf'))
                policy_temp = F.softmax(policy_logits, dim=-1)
            else:
                policy_temp = policy
            
            # Sampluj akcję
            action = torch.multinomial(policy_temp.squeeze(0), 1).item()
        
        return action, policy.squeeze(0), value.squeeze()
    
    def save(self, path: Optional[str] = None, name: str = "model"):
        """Zapisuje model do pliku."""
        if path is None:
            path = CHECKPOINTS_DIR / f"{name}.pt"
        else:
            path = Path(path)
        
        torch.save({
            'state_dict': self.state_dict(),
            'config': {
                'state_dim': self.state_dim,
                'action_dim': self.action_dim,
                'hidden_dim': self.hidden_dim,
                'num_hidden_layers': self.num_hidden_layers,
                'dropout': self.dropout_rate,
            }
        }, path)
        
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'CardGameNetwork':
        """Ładuje model z pliku. Obsługuje oba formaty: model.save() i Trainer.save_checkpoint()."""
        path = Path(path)
        
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        
        # Sprawdź format - model.save() używa 'config' i 'state_dict'
        # Trainer.save_checkpoint() używa 'model_state_dict' bez 'config'
        if 'config' in checkpoint:
            # Format z model.save()
            config = checkpoint['config']
            model = cls(
                state_dim=config['state_dim'],
                action_dim=config['action_dim'],
                hidden_dim=config['hidden_dim'],
                num_hidden_layers=config['num_hidden_layers'],
                dropout=config['dropout'],
            )
            model.load_state_dict(checkpoint['state_dict'])
        elif 'model_state_dict' in checkpoint:
            # Format z Trainer.save_checkpoint() - użyj domyślnej konfiguracji
            model = cls()  # domyślne parametry z NETWORK_CONFIG
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            raise ValueError(f"Unknown checkpoint format. Keys: {checkpoint.keys()}")
        
        print(f"Model loaded from {path}")
        return model
    
    def count_parameters(self) -> int:
        """Liczy parametry modelu."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class LightweightNetwork(nn.Module):
    """
    Lekka wersja sieci dla szybszego inference.
    Mniej warstw, prostsza architektura.
    """
    
    def __init__(self,
                 state_dim: Optional[int] = None,
                 action_dim: Optional[int] = None,
                 hidden_dim: int = 128):
        super().__init__()
        
        self.state_dim = state_dim or NETWORK_CONFIG.TOTAL_STATE_DIM
        self.action_dim = action_dim or NETWORK_CONFIG.TOTAL_ACTIONS
        self.hidden_dim = hidden_dim
        
        # Shared layers
        self.shared = nn.Sequential(
            nn.Linear(self.state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        
        # Heads
        self.policy_head = nn.Linear(hidden_dim, self.action_dim)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, 1),
            nn.Tanh(),
        )
    
    def forward(self,
                state: torch.Tensor,
                action_mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.shared(state)
        
        policy_logits = self.policy_head(x)
        if action_mask is not None:
            policy_logits = policy_logits.masked_fill(~action_mask, float('-inf'))
        policy = F.softmax(policy_logits, dim=-1)
        
        value = self.value_head(x)
        
        return policy, value
    
    def save(self, path: str):
        torch.save({
            'state_dict': self.state_dict(),
            'config': {
                'state_dim': self.state_dim,
                'action_dim': self.action_dim,
                'hidden_dim': self.hidden_dim,
            }
        }, path)
    
    @classmethod
    def load(cls, path: str) -> 'LightweightNetwork':
        checkpoint = torch.load(path, map_location='cpu')
        config = checkpoint['config']
        model = cls(**config)
        model.load_state_dict(checkpoint['state_dict'])
        return model


if __name__ == "__main__":
    # Test sieci
    print("=== Testing CardGameNetwork ===")
    
    model = CardGameNetwork()
    print(f"State dim: {model.state_dim}")
    print(f"Action dim: {model.action_dim}")
    print(f"Hidden dim: {model.hidden_dim}")
    print(f"Parameters: {model.count_parameters():,}")
    
    # Test forward pass
    batch_size = 4
    state = torch.randn(batch_size, model.state_dim)
    action_mask = torch.randint(0, 2, (batch_size, model.action_dim)).bool()
    # Upewnij się, że każdy sample ma przynajmniej jedną legalną akcję
    action_mask[:, 0] = True
    
    policy, value = model(state, action_mask)
    print(f"\nForward pass:")
    print(f"  Policy shape: {policy.shape}")
    print(f"  Value shape: {value.shape}")
    print(f"  Policy sum (should be ~1): {policy.sum(dim=-1)}")
    
    # Test get_action
    single_state = torch.randn(model.state_dim)
    single_mask = torch.randint(0, 2, (model.action_dim,)).bool()
    single_mask[0] = True
    
    action, policy, value = model.get_action(single_state, single_mask, temperature=1.0)
    print(f"\nGet action:")
    print(f"  Selected action: {action}")
    print(f"  Value: {value.item():.4f}")
    
    # Test save/load
    print("\n=== Testing save/load ===")
    model.save(name="test_model")
    
    loaded_model = CardGameNetwork.load(CHECKPOINTS_DIR / "test_model.pt")
    print(f"Loaded model parameters: {loaded_model.count_parameters():,}")
    
    # Test lightweight
    print("\n=== Testing LightweightNetwork ===")
    light_model = LightweightNetwork()
    light_params = sum(p.numel() for p in light_model.parameters())
    print(f"Lightweight parameters: {light_params:,}")
    
    policy, value = light_model(state, action_mask)
    print(f"Lightweight forward pass OK")
