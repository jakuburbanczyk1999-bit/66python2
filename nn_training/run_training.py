# nn_training/run_training.py
"""
Główny skrypt do treningu sieci neuronowej dla gry 66.

Użycie:
    python run_training.py --mode selfplay --games 1000 --epochs 50
    python run_training.py --mode evaluate --model best_model.pt
    python run_training.py --mode full --iterations 10
"""

import argparse
import torch
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# WAŻNE: Najpierw dodaj nn_training do ścieżki (przed głównym katalogiem)
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent

# Usuń PROJECT_ROOT jeśli jest na początku (żeby nn_training/config.py miał priorytet)
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))

# Dodaj NN_DIR na początek
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))

# Dodaj PROJECT_ROOT na koniec (dla engines itp.)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import TRAINING_CONFIG, CHECKPOINTS_DIR, NETWORK_CONFIG
from network import CardGameNetwork
from self_play import generate_self_play_data, ReplayBuffer, save_experiences
from trainer import Trainer, train_from_scratch
from game_interface import GameInterface, play_random_game
from state_encoder import ENCODER


def evaluate_model(model: CardGameNetwork,
                   num_games: int = 100,
                   opponent: str = 'random',
                   device: str = 'cpu') -> dict:
    """
    Ewaluuje model przeciwko określonemu przeciwnikowi.
    
    Args:
        model: Model do ewaluacji
        num_games: Liczba gier
        opponent: Typ przeciwnika ('random', 'heuristic', 'self')
        device: Urządzenie
        
    Returns:
        Słownik z metrykami
    """
    from nn_bot import NeuralNetworkBot
    
    model.to(device)
    model.eval()
    
    # Stwórz bota NN
    nn_bot = NeuralNetworkBot(model=model, temperature=0.3, greedy=True)
    
    wins = 0
    total_points = 0
    
    print(f"Evaluating against {opponent} ({num_games} games)...")
    
    for i in range(num_games):
        # Stwórz grę
        players = ['NN_Player', 'Opp_1', 'NN_Partner', 'Opp_2']
        game = GameInterface(players, '4p')
        
        move_count = 0
        max_moves = 200
        
        while not game.is_terminal() and move_count < max_moves:
            current = game.get_current_player()
            if current is None:
                break
            
            # Wybierz akcję
            if current in ['NN_Player', 'NN_Partner']:
                # Użyj bota NN
                action = nn_bot.znajdz_najlepszy_ruch(game.engine, current)
                if action:
                    game.perform_action(current, action)
            else:
                # Przeciwnik (losowy)
                legal = game.get_legal_action_indices(current)
                if legal:
                    import random
                    action_idx = random.choice(legal)
                    game.perform_action_by_index(current, action_idx)
            
            move_count += 1
        
        # Sprawdź wynik
        outcome = game.get_outcome()
        if outcome:
            if outcome.is_win.get('NN_Player', False):
                wins += 1
            total_points += outcome.points_awarded
        
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{num_games}, Win rate: {wins/(i+1)*100:.1f}%")
    
    win_rate = wins / num_games * 100
    avg_points = total_points / num_games
    
    print(f"\n=== Evaluation Results ===")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg points: {avg_points:.2f}")
    
    return {
        'win_rate': win_rate,
        'avg_points': avg_points,
        'games_played': num_games,
    }


def run_selfplay_iteration(model: Optional[CardGameNetwork],
                           num_games: int,
                           temperature: float,
                           device: str) -> list:
    """Generuje dane przez self-play."""
    print(f"\n=== Self-Play ({num_games} games, temp={temperature}) ===")
    
    experiences = generate_self_play_data(
        model=model,
        num_games=num_games,
        temperature=temperature,
        device=device,
        show_progress=True
    )
    
    # Statystyki
    phases = {}
    for exp in experiences:
        phases[exp.phase] = phases.get(exp.phase, 0) + 1
    
    print(f"\nExperiences by phase:")
    for phase, count in sorted(phases.items()):
        print(f"  {phase}: {count} ({count/len(experiences)*100:.1f}%)")
    
    return experiences


def run_training_iteration(model: CardGameNetwork,
                           experiences: list,
                           epochs: int,
                           device: str) -> Trainer:
    """Trenuje model na zebranych danych."""
    print(f"\n=== Training ({len(experiences)} samples, {epochs} epochs) ===")
    
    trainer = Trainer(model, device=device)
    
    trainer.train(
        experiences,
        epochs=epochs,
        save_best=True
    )
    
    return trainer


def run_full_training(iterations: int = 10,
                      games_per_iteration: int = 500,
                      epochs_per_iteration: int = 20,
                      device: str = None):
    """
    Pełny cykl treningowy AlphaZero-style.
    
    Pętla:
    1. Self-play z aktualnym modelem
    2. Trening na zebranych danych
    3. Ewaluacja
    4. Powtórz
    """
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"=== Full Training Pipeline ===")
    print(f"Device: {device}")
    print(f"Iterations: {iterations}")
    print(f"Games per iteration: {games_per_iteration}")
    print(f"Epochs per iteration: {epochs_per_iteration}")
    print()
    
    # Inicjalizacja
    model = CardGameNetwork()
    replay_buffer = ReplayBuffer(capacity=100000)
    
    best_win_rate = 0.0
    temperature = TRAINING_CONFIG.TEMPERATURE
    
    for iteration in range(1, iterations + 1):
        print(f"\n{'='*60}")
        print(f"ITERATION {iteration}/{iterations}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # 1. Self-play
        experiences = run_selfplay_iteration(
            model=model if iteration > 1 else None,  # Random na początku
            num_games=games_per_iteration,
            temperature=temperature,
            device=device
        )
        
        # Dodaj do bufora
        replay_buffer.add_batch(experiences)
        print(f"Replay buffer size: {len(replay_buffer)}")
        
        # 2. Trening
        # Użyj danych z bufora (może zawierać stare doświadczenia)
        training_data = replay_buffer.sample(min(len(replay_buffer), games_per_iteration * 50))
        
        trainer = run_training_iteration(
            model=model,
            experiences=training_data,
            epochs=epochs_per_iteration,
            device=device
        )
        
        # 3. Ewaluacja
        eval_results = evaluate_model(model, num_games=50, device=device)
        
        # 4. Zapisz jeśli lepszy
        if eval_results['win_rate'] > best_win_rate:
            best_win_rate = eval_results['win_rate']
            model.save(name=f"best_model_iter{iteration}")
            print(f"New best model! Win rate: {best_win_rate:.1f}%")
        
        # Zmniejsz temperaturę
        temperature = max(
            TRAINING_CONFIG.MIN_TEMPERATURE,
            temperature * TRAINING_CONFIG.TEMPERATURE_DECAY
        )
        
        elapsed = time.time() - start_time
        print(f"\nIteration time: {elapsed/60:.1f} minutes")
        print(f"Current temperature: {temperature:.3f}")
    
    # Zapisz finalny model
    model.save(name="final_model")
    print(f"\n=== Training Complete ===")
    print(f"Best win rate: {best_win_rate:.1f}%")
    
    return model


def main():
    parser = argparse.ArgumentParser(description='Train Neural Network for 66 card game')
    
    parser.add_argument('--mode', type=str, default='full',
                        choices=['selfplay', 'train', 'evaluate', 'full', 'quick'],
                        help='Training mode')
    
    parser.add_argument('--games', type=int, default=500,
                        help='Number of games for self-play')
    
    parser.add_argument('--epochs', type=int, default=30,
                        help='Training epochs')
    
    parser.add_argument('--iterations', type=int, default=10,
                        help='Full training iterations')
    
    parser.add_argument('--model', type=str, default=None,
                        help='Path to model checkpoint')
    
    parser.add_argument('--device', type=str, default=None,
                        help='Device (cuda/cpu)')
    
    parser.add_argument('--temperature', type=float, default=1.0,
                        help='Self-play temperature')
    
    args = parser.parse_args()
    
    # Ustaw urządzenie
    if args.device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"Using device: {device}")
    print()
    
    if args.mode == 'selfplay':
        # Tylko generowanie danych
        model = None
        if args.model:
            model = CardGameNetwork.load(args.model)
        
        experiences = run_selfplay_iteration(
            model=model,
            num_games=args.games,
            temperature=args.temperature,
            device=device
        )
        
        # Zapisz dane
        save_experiences(experiences)
    
    elif args.mode == 'train':
        # Tylko trening (wymaga danych)
        from self_play import load_experiences
        
        # Znajdź najnowsze dane
        data_files = list(Path('data').glob('*.pt'))
        if not data_files:
            print("Brak danych do treningu! Uruchom najpierw self-play.")
            return
        
        latest_file = max(data_files, key=lambda p: p.stat().st_mtime)
        print(f"Loading data from: {latest_file}")
        
        experiences = load_experiences(str(latest_file))
        
        # Stwórz/załaduj model
        if args.model:
            model = CardGameNetwork.load(args.model)
        else:
            model = CardGameNetwork()
        
        run_training_iteration(model, experiences, args.epochs, device)
    
    elif args.mode == 'evaluate':
        # Tylko ewaluacja
        if not args.model:
            model_path = CHECKPOINTS_DIR / "best_model.pt"
        else:
            model_path = args.model
        
        model = CardGameNetwork.load(str(model_path))
        evaluate_model(model, num_games=args.games, device=device)
    
    elif args.mode == 'full':
        # Pełny cykl
        run_full_training(
            iterations=args.iterations,
            games_per_iteration=args.games,
            epochs_per_iteration=args.epochs,
            device=device
        )
    
    elif args.mode == 'quick':
        # Szybki test (mało gier, mało epok)
        print("=== Quick Test Mode ===")
        run_full_training(
            iterations=2,
            games_per_iteration=50,
            epochs_per_iteration=5,
            device=device
        )


if __name__ == "__main__":
    main()
