# nn_training/train_with_expert.py
"""
Trening sieci neuronowej z ekspertem heurystycznym jako nauczycielem.
Skupiony na fazie DEKLARACJA - najważniejszej w grze.
"""

import torch
import random
import numpy as np
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from tqdm import tqdm
from datetime import datetime

# Ścieżki
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import (
    NETWORK_CONFIG, TRAINING_CONFIG, CHECKPOINTS_DIR, DATA_DIR,
    ACTION_INDEX_TO_DICT, DICT_TO_ACTION_INDEX
)
from state_encoder import StateEncoder, ENCODER
from network import CardGameNetwork
from game_interface import GameInterface
from expert_heuristics import ExpertBot, EXPERT, analyze_hand
from self_play import Experience, ReplayBuffer
from trainer import Trainer, ExperienceDataset

from torch.utils.data import DataLoader


@dataclass  
class DeclarationExperience:
    """Doświadczenie z fazy deklaracji."""
    state: torch.Tensor
    action_mask: torch.Tensor
    expert_action: int  # Akcja wybrana przez eksperta
    hand_strength: float  # Siła ręki (dla debugowania)


def generate_declaration_data(num_samples: int = 10000,
                               show_progress: bool = True) -> List[Experience]:
    """
    Generuje dane treningowe TYLKO dla fazy DEKLARACJA_1.
    Używa eksperta jako nauczyciela.
    
    Args:
        num_samples: Liczba próbek do wygenerowania
        show_progress: Czy pokazywać progress bar
        
    Returns:
        Lista Experience z fazą DEKLARACJA_1
    """
    experiences = []
    expert = EXPERT
    encoder = ENCODER
    
    iterator = range(num_samples)
    if show_progress:
        iterator = tqdm(iterator, desc="Generating declaration data")
    
    for _ in iterator:
        # Stwórz nową grę
        players = ['P1', 'P2', 'P3', 'P4']
        game = GameInterface(players, '4p')
        
        # Pobierz gracza który deklaruje
        current = game.get_current_player()
        if current is None:
            continue
        
        # Pobierz stan
        state_dict = game.get_state(current)
        
        # Sprawdź czy to faza deklaracji
        if state_dict.get('faza') != 'DEKLARACJA_1':
            continue
        
        # Enkoduj stan
        state_tensor = encoder.encode_state(state_dict, current)
        action_mask = encoder.get_action_mask(state_dict, current)
        
        # Pobierz akcję eksperta
        expert_action = expert.get_action(state_dict, current)
        
        # Konwertuj na indeks
        action_idx = _action_to_index(expert_action)
        if action_idx is None:
            continue
        
        # Stwórz policy (one-hot dla eksperta)
        policy = torch.zeros(NETWORK_CONFIG.TOTAL_ACTIONS)
        policy[action_idx] = 1.0
        
        # Dodaj doświadczenie
        exp = Experience(
            state=state_tensor,
            action_mask=action_mask,
            action=action_idx,
            policy=policy,
            value=0.0,  # Nie używamy value dla supervised learning
            player_id=current,
            phase='DEKLARACJA_1',
        )
        experiences.append(exp)
    
    if show_progress:
        print(f"Generated {len(experiences)} declaration experiences")
        
        # Statystyki akcji
        action_counts = {}
        for exp in experiences:
            action = ACTION_INDEX_TO_DICT.get(exp.action, {})
            key = f"{action.get('kontrakt', '?')}_{action.get('atut', '?')}"
            action_counts[key] = action_counts.get(key, 0) + 1
        
        print("Action distribution:")
        for key, count in sorted(action_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {key}: {count} ({count/len(experiences)*100:.1f}%)")
    
    return experiences


def generate_mixed_data_with_expert(num_games: int = 500,
                                     declaration_weight: float = 0.5,
                                     show_progress: bool = True) -> List[Experience]:
    """
    Generuje mieszane dane z ekspertem.
    
    Rozgrywa pełne gry z ekspertem i zbiera dane ze wszystkich faz,
    ale priorytetyzuje DEKLARACJA przez nadpróbkowanie.
    
    Args:
        num_games: Liczba gier
        declaration_weight: Docelowy procent danych z DEKLARACJA
        show_progress: Czy pokazywać progress
        
    Returns:
        Lista Experience
    """
    all_experiences = []
    declaration_experiences = []
    other_experiences = []
    
    expert = EXPERT
    encoder = ENCODER
    
    iterator = range(num_games)
    if show_progress:
        iterator = tqdm(iterator, desc="Expert self-play")
    
    for _ in iterator:
        players = ['P1', 'P2', 'P3', 'P4']
        game = GameInterface(players, '4p')
        
        game_experiences = []
        move_count = 0
        max_moves = 200
        
        while not game.is_terminal() and move_count < max_moves:
            current = game.get_current_player()
            if current is None:
                break
            
            state_dict = game.get_state(current)
            phase = state_dict.get('faza', '')
            
            # Enkoduj
            state_tensor = encoder.encode_state(state_dict, current)
            action_mask = encoder.get_action_mask(state_dict, current)
            
            # Akcja eksperta
            expert_action = expert.get_action(state_dict, current)
            action_idx = _action_to_index(expert_action)
            
            if action_idx is not None:
                policy = torch.zeros(NETWORK_CONFIG.TOTAL_ACTIONS)
                policy[action_idx] = 1.0
                
                exp = Experience(
                    state=state_tensor,
                    action_mask=action_mask,
                    action=action_idx,
                    policy=policy,
                    value=0.0,
                    player_id=current,
                    phase=phase,
                )
                game_experiences.append(exp)
            
            # Wykonaj akcję
            if expert_action:
                game.perform_action(current, expert_action)
            else:
                break
            
            move_count += 1
        
        # Rozdziel doświadczenia
        for exp in game_experiences:
            if exp.phase == 'DEKLARACJA_1':
                declaration_experiences.append(exp)
            else:
                other_experiences.append(exp)
    
    # Zbilansuj dane
    # Chcemy declaration_weight % danych z DEKLARACJA
    n_decl = len(declaration_experiences)
    n_other = len(other_experiences)
    
    if n_decl > 0 and n_other > 0:
        # Ile danych z innych faz potrzebujemy?
        target_other = int(n_decl * (1 - declaration_weight) / declaration_weight)
        
        if target_other < n_other:
            # Próbkuj inne fazy
            other_experiences = random.sample(other_experiences, target_other)
        else:
            # Nadpróbkuj deklaracje
            target_decl = int(n_other * declaration_weight / (1 - declaration_weight))
            if target_decl > n_decl:
                # Powiel deklaracje
                multiplier = target_decl // n_decl + 1
                declaration_experiences = declaration_experiences * multiplier
                declaration_experiences = declaration_experiences[:target_decl]
    
    all_experiences = declaration_experiences + other_experiences
    random.shuffle(all_experiences)
    
    if show_progress:
        print(f"\nTotal experiences: {len(all_experiences)}")
        print(f"  Declaration: {len(declaration_experiences)} ({len(declaration_experiences)/len(all_experiences)*100:.1f}%)")
        print(f"  Other: {len(other_experiences)} ({len(other_experiences)/len(all_experiences)*100:.1f}%)")
    
    return all_experiences


def _action_to_index(action: Dict[str, Any]) -> Optional[int]:
    """Konwertuje akcję na indeks."""
    if not action:
        return None
    
    typ = action.get('typ', '')
    
    if typ == 'deklaracja':
        kontrakt = action.get('kontrakt', '')
        if hasattr(kontrakt, 'name'):
            kontrakt = kontrakt.name
        
        atut = action.get('atut')
        if atut:
            if hasattr(atut, 'name'):
                atut = atut.name
            elif isinstance(atut, str):
                atut = atut.upper()
        
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


def train_declaration_model(num_samples: int = 20000,
                            epochs: int = 50,
                            batch_size: int = 128,
                            learning_rate: float = 0.001,
                            device: str = None) -> CardGameNetwork:
    """
    Trenuje model skupiony na deklaracji.
    
    Args:
        num_samples: Liczba próbek
        epochs: Liczba epok
        batch_size: Rozmiar batcha
        learning_rate: Learning rate
        device: Urządzenie
        
    Returns:
        Wytrenowany model
    """
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"=== Training Declaration Model ===")
    print(f"Device: {device}")
    print(f"Samples: {num_samples}")
    print(f"Epochs: {epochs}")
    print()
    
    # Generuj dane
    print("Step 1: Generating declaration data from expert...")
    experiences = generate_declaration_data(num_samples, show_progress=True)
    
    if len(experiences) < 100:
        print("ERROR: Not enough experiences!")
        return None
    
    # Stwórz model
    print("\nStep 2: Creating model...")
    model = CardGameNetwork()
    model.to(device)
    print(f"Parameters: {model.count_parameters():,}")
    
    # Trener
    trainer = Trainer(model, learning_rate=learning_rate, device=device)
    
    # Trening
    print("\nStep 3: Training...")
    history = trainer.train(
        experiences,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        early_stopping_patience=15,
        save_best=True
    )
    
    # Zapisz
    model.save(name="declaration_model")
    
    print(f"\n=== Training Complete ===")
    print(f"Final loss: {history[-1].total_loss:.4f}")
    print(f"Final accuracy: {history[-1].policy_accuracy:.1f}%")
    
    return model


def train_full_model_with_expert(num_games: int = 1000,
                                  declaration_weight: float = 0.5,
                                  epochs: int = 30,
                                  device: str = None) -> CardGameNetwork:
    """
    Trenuje pełny model z ekspertem, priorytetyzując deklarację.
    """
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"=== Training Full Model with Expert ===")
    print(f"Device: {device}")
    print(f"Games: {num_games}")
    print(f"Declaration weight: {declaration_weight*100:.0f}%")
    print()
    
    # Generuj dane
    print("Step 1: Generating data from expert play...")
    experiences = generate_mixed_data_with_expert(
        num_games=num_games,
        declaration_weight=declaration_weight,
        show_progress=True
    )
    
    # Stwórz model
    print("\nStep 2: Creating model...")
    model = CardGameNetwork()
    model.to(device)
    
    # Trening
    trainer = Trainer(model, device=device)
    
    print("\nStep 3: Training...")
    history = trainer.train(
        experiences,
        epochs=epochs,
        validation_split=0.1,
        save_best=True
    )
    
    model.save(name="expert_trained_model")
    
    print(f"\n=== Training Complete ===")
    print(f"Final accuracy: {history[-1].policy_accuracy:.1f}%")
    
    return model


def evaluate_vs_random(model: CardGameNetwork,
                       num_games: int = 100,
                       device: str = 'cpu',
                       use_hybrid: bool = True) -> float:
    """
    Ewaluacja przeciwko losowemu botowi.
    
    Args:
        model: Model NN
        num_games: Liczba gier
        device: Urządzenie
        use_hybrid: Jeśli True, używa NN dla deklaracji i eksperta dla reszty
    """
    from nn_bot import NeuralNetworkBot
    
    model.to(device)
    model.eval()
    
    nn_bot = NeuralNetworkBot(model=model, temperature=0.1, greedy=True, device=device)
    expert = EXPERT
    
    wins = 0
    
    mode_str = "hybrid (NN+expert)" if use_hybrid else "pure NN"
    print(f"Evaluating {mode_str} vs random ({num_games} games)...")
    
    for i in tqdm(range(num_games), desc="Evaluation"):
        players = ['NN', 'R1', 'NN2', 'R2']  # NN vs Random teams
        game = GameInterface(players, '4p')
        
        move_count = 0
        while not game.is_terminal() and move_count < 200:
            current = game.get_current_player()
            if current is None:
                break
            
            state_dict = game.get_state(current)
            phase = state_dict.get('faza', '')
            
            if current in ['NN', 'NN2']:
                if use_hybrid:
                    # Hybrid: NN dla deklaracji, ekspert dla reszty
                    if phase == 'DEKLARACJA_1':
                        action = nn_bot.znajdz_najlepszy_ruch(game.engine, current)
                    else:
                        action = expert.get_action(state_dict, current)
                else:
                    # Pure NN
                    action = nn_bot.znajdz_najlepszy_ruch(game.engine, current)
                
                if action:
                    game.perform_action(current, action)
                else:
                    break
            else:
                # Losowy
                legal = game.get_legal_action_indices(current)
                if legal:
                    action_idx = random.choice(legal)
                    game.perform_action_by_index(current, action_idx)
                else:
                    break
            
            move_count += 1
        
        outcome = game.get_outcome()
        if outcome and outcome.is_win.get('NN', False):
            wins += 1
    
    win_rate = wins / num_games * 100
    print(f"Win rate vs random: {win_rate:.1f}%")
    
    return win_rate


def evaluate_vs_expert(model: CardGameNetwork,
                       num_games: int = 100,
                       device: str = 'cpu') -> float:
    """Ewaluacja przeciwko ekspertowi heurystycznemu."""
    from nn_bot import NeuralNetworkBot
    
    model.to(device)
    model.eval()
    
    nn_bot = NeuralNetworkBot(model=model, temperature=0.1, greedy=True, device=device)
    expert = EXPERT
    
    wins = 0
    
    print(f"Evaluating vs expert ({num_games} games)...")
    
    for i in tqdm(range(num_games), desc="Evaluation"):
        players = ['NN', 'EX1', 'NN2', 'EX2']
        game = GameInterface(players, '4p')
        
        move_count = 0
        while not game.is_terminal() and move_count < 200:
            current = game.get_current_player()
            if current is None:
                break
            
            state_dict = game.get_state(current)
            
            if current in ['NN', 'NN2']:
                action = nn_bot.znajdz_najlepszy_ruch(game.engine, current)
            else:
                action = expert.get_action(state_dict, current)
            
            if action:
                game.perform_action(current, action)
            else:
                break
            
            move_count += 1
        
        outcome = game.get_outcome()
        if outcome and outcome.is_win.get('NN', False):
            wins += 1
    
    win_rate = wins / num_games * 100
    print(f"Win rate vs expert: {win_rate:.1f}%")
    
    return win_rate


def evaluate_expert_vs_random(num_games: int = 200) -> float:
    """
    Ewaluacja samego eksperta vs losowy.
    Pozwala sprawdzić jak dobry jest ekspert.
    """
    expert = EXPERT
    wins = 0
    
    print(f"Evaluating EXPERT vs random ({num_games} games)...")
    
    for i in tqdm(range(num_games), desc="Expert eval"):
        players = ['EX', 'R1', 'EX2', 'R2']
        game = GameInterface(players, '4p')
        
        move_count = 0
        while not game.is_terminal() and move_count < 200:
            current = game.get_current_player()
            if current is None:
                break
            
            state_dict = game.get_state(current)
            
            if current in ['EX', 'EX2']:
                action = expert.get_action(state_dict, current)
                if action:
                    game.perform_action(current, action)
                else:
                    break
            else:
                # Losowy
                legal = game.get_legal_action_indices(current)
                if legal:
                    action_idx = random.choice(legal)
                    game.perform_action_by_index(current, action_idx)
                else:
                    break
            
            move_count += 1
        
        outcome = game.get_outcome()
        if outcome and outcome.is_win.get('EX', False):
            wins += 1
    
    win_rate = wins / num_games * 100
    print(f"Expert win rate vs random: {win_rate:.1f}%")
    
    return win_rate


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='declaration',
                        choices=['declaration', 'full', 'evaluate', 'test_expert'])
    parser.add_argument('--samples', type=int, default=20000)
    parser.add_argument('--games', type=int, default=1000)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--device', type=str, default=None)
    
    args = parser.parse_args()
    
    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    
    if args.mode == 'declaration':
        # Tylko deklaracja
        model = train_declaration_model(
            num_samples=args.samples,
            epochs=args.epochs,
            device=device
        )
        
        if model:
            print("\n=== Evaluation ===")
            evaluate_vs_random(model, num_games=200, device=device)
    
    elif args.mode == 'full':
        # Pełny model
        model = train_full_model_with_expert(
            num_games=args.games,
            epochs=args.epochs,
            device=device
        )
        
        if model:
            print("\n=== Evaluation ===")
            evaluate_vs_random(model, num_games=200, device=device)
            evaluate_vs_expert(model, num_games=200, device=device)
    
    elif args.mode == 'evaluate':
        # Tylko ewaluacja
        model_path = CHECKPOINTS_DIR / "best_model.pt"
        if model_path.exists():
            model = CardGameNetwork.load(str(model_path))
            print("\n--- Pure NN ---")
            evaluate_vs_random(model, num_games=200, device=device, use_hybrid=False)
            print("\n--- Hybrid (NN decl + expert rest) ---")
            evaluate_vs_random(model, num_games=200, device=device, use_hybrid=True)
            print("\n--- vs Expert ---")
            evaluate_vs_expert(model, num_games=200, device=device)
        else:
            print(f"Model not found: {model_path}")
    
    elif args.mode == 'test_expert':
        # Test samego eksperta
        evaluate_expert_vs_random(num_games=500)
