# nn_training/trainer.py
"""
Trening sieci neuronowej dla gry 66.
Supervised learning z danych self-play oraz opcjonalnie PPO.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
from tqdm import tqdm
import json
from datetime import datetime

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
    from .config import TRAINING_CONFIG, CHECKPOINTS_DIR, LOGS_DIR, NETWORK_CONFIG
    from .network import CardGameNetwork
    from .self_play import Experience, ReplayBuffer, generate_self_play_data
except ImportError:
    from config import TRAINING_CONFIG, CHECKPOINTS_DIR, LOGS_DIR, NETWORK_CONFIG
    from network import CardGameNetwork
    from self_play import Experience, ReplayBuffer, generate_self_play_data


@dataclass
class TrainingMetrics:
    """Metryki z treningu."""
    epoch: int
    policy_loss: float
    value_loss: float
    total_loss: float
    entropy: float
    policy_accuracy: float  # % poprawnych predykcji akcji
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'epoch': self.epoch,
            'policy_loss': self.policy_loss,
            'value_loss': self.value_loss,
            'total_loss': self.total_loss,
            'entropy': self.entropy,
            'policy_accuracy': self.policy_accuracy,
        }


class ExperienceDataset(Dataset):
    """Dataset dla doświadczeń z self-play."""
    
    def __init__(self, experiences: List[Experience]):
        self.experiences = experiences
    
    def __len__(self):
        return len(self.experiences)
    
    def __getitem__(self, idx) -> Dict[str, torch.Tensor]:
        exp = self.experiences[idx]
        return {
            'state': exp.state,
            'action_mask': exp.action_mask,
            'action': torch.tensor(exp.action, dtype=torch.long),
            'target_policy': exp.policy,
            'target_value': torch.tensor(exp.value, dtype=torch.float32),
        }


class Trainer:
    """
    Trener sieci neuronowej.
    
    Obsługuje:
    - Supervised learning z danych self-play
    - Opcjonalnie PPO dla fine-tuningu
    - Logowanie metryk
    - Checkpointing
    """
    
    def __init__(self,
                 model: CardGameNetwork,
                 learning_rate: float = None,
                 weight_decay: float = None,
                 device: str = None):
        """
        Args:
            model: Sieć do trenowania
            learning_rate: Learning rate
            weight_decay: L2 regularization
            device: Urządzenie ('cuda' lub 'cpu')
        """
        self.model = model
        self.lr = learning_rate or TRAINING_CONFIG.LEARNING_RATE
        self.weight_decay = weight_decay or TRAINING_CONFIG.WEIGHT_DECAY
        
        # Automatyczny wybór urządzenia
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        
        self.model.to(self.device)
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay
        )
        
        # Scheduler (opcjonalnie)
        self.scheduler = optim.lr_scheduler.StepLR(
            self.optimizer, step_size=30, gamma=0.5
        )
        
        # Historia treningu
        self.training_history: List[TrainingMetrics] = []
        self.best_loss = float('inf')
    
    def train_epoch(self,
                    dataloader: DataLoader,
                    policy_weight: float = 1.0,
                    value_weight: float = 1.0,
                    entropy_bonus: float = 0.01) -> TrainingMetrics:
        """
        Trenuje przez jedną epokę.
        
        Args:
            dataloader: DataLoader z danymi
            policy_weight: Waga policy loss
            value_weight: Waga value loss
            entropy_bonus: Bonus za entropię (eksploracja)
            
        Returns:
            Metryki z epoki
        """
        self.model.train()
        
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_correct = 0
        total_samples = 0
        
        for batch in dataloader:
            # Przenieś na urządzenie
            states = batch['state'].to(self.device)
            action_masks = batch['action_mask'].to(self.device)
            actions = batch['action'].to(self.device)
            target_policies = batch['target_policy'].to(self.device)
            target_values = batch['target_value'].to(self.device)
            
            # Forward pass
            pred_policies, pred_values = self.model(states, action_masks)
            
            # Policy loss (Cross-entropy z target policy)
            # Używamy KL divergence zamiast cross-entropy dla soft targets
            policy_loss = F.kl_div(
                torch.log(pred_policies + 1e-10),
                target_policies,
                reduction='batchmean'
            )
            
            # Value loss (MSE)
            value_loss = F.mse_loss(pred_values.squeeze(), target_values)
            
            # Entropy bonus (zachęta do eksploracji)
            entropy = -(pred_policies * torch.log(pred_policies + 1e-10)).sum(dim=-1).mean()
            
            # Total loss
            loss = policy_weight * policy_loss + value_weight * value_loss - entropy_bonus * entropy
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            # Statystyki
            batch_size = states.shape[0]
            total_policy_loss += policy_loss.item() * batch_size
            total_value_loss += value_loss.item() * batch_size
            total_entropy += entropy.item() * batch_size
            
            # Accuracy: czy najwyższa predykcja == wybrana akcja
            pred_actions = pred_policies.argmax(dim=-1)
            correct = (pred_actions == actions).sum().item()
            total_correct += correct
            total_samples += batch_size
        
        # Średnie metryki
        metrics = TrainingMetrics(
            epoch=len(self.training_history) + 1,
            policy_loss=total_policy_loss / total_samples,
            value_loss=total_value_loss / total_samples,
            total_loss=(total_policy_loss + total_value_loss) / total_samples,
            entropy=total_entropy / total_samples,
            policy_accuracy=total_correct / total_samples * 100,
        )
        
        self.training_history.append(metrics)
        return metrics
    
    def train(self,
              experiences: List[Experience],
              epochs: int = None,
              batch_size: int = None,
              validation_split: float = 0.1,
              early_stopping_patience: int = 10,
              save_best: bool = True) -> List[TrainingMetrics]:
        """
        Pełny trening na danych.
        
        Args:
            experiences: Lista doświadczeń do treningu
            epochs: Liczba epok
            batch_size: Rozmiar batcha
            validation_split: Procent danych na walidację
            early_stopping_patience: Ile epok bez poprawy przed zatrzymaniem
            save_best: Czy zapisywać najlepszy model
            
        Returns:
            Lista metryk z każdej epoki
        """
        epochs = epochs or TRAINING_CONFIG.EPOCHS_PER_ITERATION
        batch_size = batch_size or TRAINING_CONFIG.BATCH_SIZE
        
        # Podział na train/val
        n_val = int(len(experiences) * validation_split)
        indices = list(range(len(experiences)))
        np.random.shuffle(indices)
        
        val_indices = indices[:n_val]
        train_indices = indices[n_val:]
        
        train_exps = [experiences[i] for i in train_indices]
        val_exps = [experiences[i] for i in val_indices] if n_val > 0 else []
        
        print(f"Training on {len(train_exps)} samples, validating on {len(val_exps)} samples")
        
        # Dataloaders
        train_dataset = ExperienceDataset(train_exps)
        train_loader = DataLoader(
            train_dataset, 
            batch_size=batch_size, 
            shuffle=True,
            num_workers=0,  # Windows compatibility
            pin_memory=self.device == 'cuda'
        )
        
        val_loader = None
        if val_exps:
            val_dataset = ExperienceDataset(val_exps)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(1, epochs + 1):
            # Train
            train_metrics = self.train_epoch(train_loader)
            
            # Validate
            val_loss = None
            if val_loader:
                val_loss = self.validate(val_loader)
            
            # Logging
            log_msg = f"Epoch {epoch}/{epochs} | "
            log_msg += f"Train Loss: {train_metrics.total_loss:.4f} | "
            log_msg += f"Policy Acc: {train_metrics.policy_accuracy:.1f}%"
            
            if val_loss is not None:
                log_msg += f" | Val Loss: {val_loss:.4f}"
            
            print(log_msg)
            
            # Early stopping
            current_loss = val_loss if val_loss is not None else train_metrics.total_loss
            
            if current_loss < best_val_loss:
                best_val_loss = current_loss
                patience_counter = 0
                
                if save_best:
                    self.save_checkpoint('best_model.pt')
            else:
                patience_counter += 1
                
                if patience_counter >= early_stopping_patience:
                    print(f"Early stopping at epoch {epoch}")
                    break
            
            # Step scheduler
            self.scheduler.step()
        
        return self.training_history
    
    def validate(self, dataloader: DataLoader) -> float:
        """Walidacja modelu."""
        self.model.eval()
        
        total_loss = 0.0
        total_samples = 0
        
        with torch.no_grad():
            for batch in dataloader:
                states = batch['state'].to(self.device)
                action_masks = batch['action_mask'].to(self.device)
                target_policies = batch['target_policy'].to(self.device)
                target_values = batch['target_value'].to(self.device)
                
                pred_policies, pred_values = self.model(states, action_masks)
                
                policy_loss = F.kl_div(
                    torch.log(pred_policies + 1e-10),
                    target_policies,
                    reduction='batchmean'
                )
                value_loss = F.mse_loss(pred_values.squeeze(), target_values)
                
                loss = policy_loss + value_loss
                
                batch_size = states.shape[0]
                total_loss += loss.item() * batch_size
                total_samples += batch_size
        
        return total_loss / total_samples
    
    def save_checkpoint(self, filename: str = None):
        """Zapisuje checkpoint."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkpoint_{timestamp}.pt"
        
        filepath = CHECKPOINTS_DIR / filename
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'training_history': [m.to_dict() for m in self.training_history],
            'best_loss': self.best_loss,
        }, filepath)
        
        print(f"Checkpoint saved: {filepath}")
    
    def load_checkpoint(self, filepath: str):
        """Ładuje checkpoint."""
        checkpoint = torch.load(filepath, map_location=self.device, weights_only=False)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        self.best_loss = checkpoint.get('best_loss', float('inf'))
        
        # Odtwórz historię
        history_dicts = checkpoint.get('training_history', [])
        self.training_history = [
            TrainingMetrics(**d) for d in history_dicts
        ]
        
        print(f"Checkpoint loaded: {filepath}")
    
    def save_training_log(self, filename: str = None):
        """Zapisuje log treningu do JSON."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_log_{timestamp}.json"
        
        filepath = LOGS_DIR / filename
        
        log_data = {
            'config': {
                'learning_rate': self.lr,
                'weight_decay': self.weight_decay,
                'device': self.device,
            },
            'history': [m.to_dict() for m in self.training_history],
        }
        
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"Training log saved: {filepath}")


def train_from_scratch(num_games: int = 500,
                       epochs: int = 50,
                       device: str = None) -> Tuple[CardGameNetwork, List[TrainingMetrics]]:
    """
    Trenuje nowy model od zera.
    
    Kroki:
    1. Generuj dane przez random self-play
    2. Trenuj sieć na tych danych
    3. Powtórz z lepszą siecią (opcjonalnie)
    
    Args:
        num_games: Liczba gier do wygenerowania
        epochs: Liczba epok treningu
        device: Urządzenie
        
    Returns:
        (wytrenowany model, historia treningu)
    """
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"=== Training from scratch on {device} ===\n")
    
    # 1. Generuj dane
    print("Step 1: Generating self-play data...")
    experiences = generate_self_play_data(
        model=None,  # Random play na początek
        num_games=num_games,
        temperature=1.0,
        show_progress=True
    )
    
    # 2. Stwórz i trenuj model
    print("\nStep 2: Training model...")
    model = CardGameNetwork()
    trainer = Trainer(model, device=device)
    
    history = trainer.train(
        experiences,
        epochs=epochs,
        save_best=True
    )
    
    # 3. Zapisz finalny model
    model.save(name="initial_model")
    trainer.save_training_log()
    
    print("\n=== Training complete ===")
    print(f"Final policy accuracy: {history[-1].policy_accuracy:.1f}%")
    
    return model, history


if __name__ == "__main__":
    # Test trenera
    print("=== Test Trainer ===\n")
    
    # Generuj małą ilość danych
    print("Generating test data...")
    experiences = generate_self_play_data(
        model=None,
        num_games=20,
        show_progress=True
    )
    
    # Stwórz model i trenera
    model = CardGameNetwork()
    trainer = Trainer(model)
    
    print(f"\nModel parameters: {model.count_parameters():,}")
    print(f"Device: {trainer.device}")
    
    # Krótki trening
    print("\nTraining for 5 epochs...")
    history = trainer.train(
        experiences,
        epochs=5,
        validation_split=0.2,
        save_best=True
    )
    
    # Podsumowanie
    print(f"\n=== Training Summary ===")
    print(f"Final loss: {history[-1].total_loss:.4f}")
    print(f"Final accuracy: {history[-1].policy_accuracy:.1f}%")
    
    # Test save/load
    print("\n=== Test Save/Load ===")
    trainer.save_checkpoint("test_checkpoint.pt")
    
    new_model = CardGameNetwork()
    new_trainer = Trainer(new_model)
    new_trainer.load_checkpoint(CHECKPOINTS_DIR / "test_checkpoint.pt")
    
    print("Checkpoint loaded successfully!")
