# nn_training/train_with_mcts.py
"""
Trening sieci neuronowej z MCTS jako nauczycielem (Imitation Learning).
MCTS jest wolny ale dobry - generujemy dane offline, potem trenujemy szybką sieć.
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
import time

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
from self_play import Experience, ReplayBuffer
from trainer import Trainer

# Import MCTS z głównego projektu
from boty import MCTS_Bot, stworz_bota
from engines.sixtysix_engine import SixtySixEngine


def action_to_index(action: Dict[str, Any]) -> Optional[int]:
    """Konwertuje akcję słownikową na indeks."""
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


def generate_mcts_data(num_games: int = 100,
                       mcts_time_limit: float = 1.0,
                       mcts_personality: str = 'topplayer',
                       mode: str = '4p',
                       show_progress: bool = True) -> List[Experience]:
    """
    Generuje dane treningowe używając MCTS jako eksperta.
    
    Args:
        num_games: Liczba gier do rozegrania
        mcts_time_limit: Limit czasu MCTS na ruch (sekundy)
        mcts_personality: Osobowość MCTS bota
        mode: Tryb gry ('4p' lub '3p')
        show_progress: Czy pokazywać progress bar
        
    Returns:
        Lista Experience z decyzjami MCTS
    """
    experiences = []
    encoder = ENCODER
    
    # Stwórz MCTS bota
    mcts_bot = MCTS_Bot(personality=mcts_personality)
    
    iterator = range(num_games)
    if show_progress:
        iterator = tqdm(iterator, desc=f"MCTS games (limit={mcts_time_limit}s)")
    
    total_moves = 0
    total_mcts_time = 0.0
    
    for game_idx in iterator:
        # Stwórz grę używając SixtySixEngine (wymagany przez MCTS)
        if mode == '4p':
            players = ['P1', 'P2', 'P3', 'P4']
        else:
            players = ['P1', 'P2', 'P3']
        
        engine = SixtySixEngine(players, {'tryb': mode})
        
        game_experiences = []
        move_count = 0
        max_moves = 200
        
        while not engine.is_terminal() and move_count < max_moves:
            current = engine.get_current_player()
            if current is None:
                break
            
            # Pobierz stan dla encodera
            state_dict = engine.get_state_for_player(current)
            phase = state_dict.get('faza', '')
            
            # Enkoduj stan
            state_tensor = encoder.encode_state(state_dict, current)
            action_mask = encoder.get_action_mask(state_dict, current)
            
            # Pobierz akcję od MCTS
            start_time = time.time()
            mcts_action = mcts_bot.znajdz_najlepszy_ruch(
                engine, 
                current, 
                limit_czasu_s=mcts_time_limit
            )
            mcts_time = time.time() - start_time
            total_mcts_time += mcts_time
            
            if not mcts_action:
                break
            
            # Konwertuj akcję na indeks
            action_idx = action_to_index(mcts_action)
            
            if action_idx is not None:
                # Stwórz policy (one-hot dla MCTS)
                policy = torch.zeros(NETWORK_CONFIG.TOTAL_ACTIONS)
                policy[action_idx] = 1.0
                
                exp = Experience(
                    state=state_tensor,
                    action_mask=action_mask,
                    action=action_idx,
                    policy=policy,
                    value=0.0,  # Zostanie ustawione po grze
                    player_id=current,
                    phase=phase,
                )
                game_experiences.append(exp)
            
            # Wykonaj akcję
            try:
                engine.perform_action(current, mcts_action)
            except Exception as e:
                print(f"Error applying action: {e}")
                break
            
            move_count += 1
            total_moves += 1
        
        # Pobierz wynik gry i ustaw wartości
        if engine.is_terminal():
            outcome = engine.get_game_outcome()
            if outcome:
                for exp in game_experiences:
                    # Nagroda z perspektywy gracza
                    exp.value = outcome.get('rewards', {}).get(exp.player_id, 0.0)
        
        experiences.extend(game_experiences)
    
    if show_progress:
        print(f"\nGenerated {len(experiences)} experiences from {num_games} games")
        print(f"Total MCTS time: {total_mcts_time:.1f}s")
        print(f"Avg time per move: {total_mcts_time/max(1,total_moves)*1000:.1f}ms")
        
        # Statystyki faz
        phase_counts = {}
        for exp in experiences:
            phase_counts[exp.phase] = phase_counts.get(exp.phase, 0) + 1
        print("\nExperiences by phase:")
        for phase, count in sorted(phase_counts.items()):
            print(f"  {phase}: {count} ({count/len(experiences)*100:.1f}%)")
    
    return experiences


def train_from_mcts(num_games: int = 500,
                    mcts_time_limit: float = 1.0,
                    epochs: int = 50,
                    batch_size: int = 128,
                    learning_rate: float = 0.001,
                    device: str = None) -> CardGameNetwork:
    """
    Trenuje model na danych z MCTS.
    
    Args:
        num_games: Liczba gier do wygenerowania
        mcts_time_limit: Limit czasu MCTS na ruch
        epochs: Liczba epok treningu
        batch_size: Rozmiar batcha
        learning_rate: Learning rate
        device: Urządzenie
        
    Returns:
        Wytrenowany model
    """
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"=== Training from MCTS Data ===")
    print(f"Device: {device}")
    print(f"Games: {num_games}")
    print(f"MCTS time limit: {mcts_time_limit}s per move")
    print(f"Epochs: {epochs}")
    print()
    
    # Estymacja czasu
    avg_moves_per_game = 15  # średnio
    estimated_time = num_games * avg_moves_per_game * mcts_time_limit / 60
    print(f"Estimated data generation time: ~{estimated_time:.0f} minutes")
    print()
    
    # Generuj dane
    print("Step 1: Generating data from MCTS...")
    start_time = time.time()
    experiences = generate_mcts_data(
        num_games=num_games,
        mcts_time_limit=mcts_time_limit,
        show_progress=True
    )
    gen_time = time.time() - start_time
    print(f"Data generation took {gen_time/60:.1f} minutes")
    
    if len(experiences) < 100:
        print("ERROR: Not enough experiences!")
        return None
    
    # Zapisz dane (na wypadek przerwania treningu)
    data_file = DATA_DIR / f"mcts_data_{num_games}games.pt"
    torch.save([{
        'state': exp.state.numpy().tolist(),
        'action_mask': exp.action_mask.numpy().tolist(),
        'action': exp.action,
        'policy': exp.policy.numpy().tolist(),
        'value': exp.value,
        'player_id': exp.player_id,
        'phase': exp.phase,
    } for exp in experiences], data_file)
    print(f"Data saved to {data_file}")
    
    # Stwórz model
    print("\nStep 2: Creating model...")
    model = CardGameNetwork()
    model.to(device)
    print(f"Parameters: {model.count_parameters():,}")
    
    # Trening
    trainer = Trainer(model, learning_rate=learning_rate, device=device)
    
    print("\nStep 3: Training...")
    history = trainer.train(
        experiences,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        early_stopping_patience=15,
        save_best=True
    )
    
    # Zapisz finalny model
    model.save(name="mcts_trained_model")
    
    print(f"\n=== Training Complete ===")
    print(f"Final loss: {history[-1].total_loss:.4f}")
    print(f"Final accuracy: {history[-1].policy_accuracy:.1f}%")
    
    return model


def evaluate_model_vs_random(model: CardGameNetwork,
                             num_games: int = 200,
                             device: str = 'cpu') -> float:
    """Ewaluacja modelu przeciwko losowemu botowi."""
    from nn_bot import NeuralNetworkBot
    
    model.to(device)
    model.eval()
    
    nn_bot = NeuralNetworkBot(model=model, temperature=0.1, greedy=True, device=device)
    
    wins = 0
    completed_games = 0
    total_points = 0
    
    print(f"Evaluating NN vs random ({num_games} games)...")
    
    for i in tqdm(range(num_games), desc="Evaluation"):
        players = ['NN', 'R1', 'NN2', 'R2']
        engine = SixtySixEngine(players, {'tryb': '4p'})
        
        move_count = 0
        while not engine.is_terminal() and move_count < 200:
            # Sprawdź czy trzeba sfinalizować lewę
            if engine.game_state.lewa_do_zamkniecia:
                engine.game_state.finalizuj_lewe()
                continue
            
            current = engine.get_current_player()
            if current is None:
                break
            
            # Pobierz legalne akcje
            legal = engine.get_legal_actions(current)
            if not legal:
                break
            
            if current in ['NN', 'NN2']:
                action = nn_bot.znajdz_najlepszy_ruch(engine, current)
            else:
                # Losowy
                action = random.choice(legal)
            
            if action:
                try:
                    engine.perform_action(current, action)
                except:
                    break
            else:
                break
            
            move_count += 1
        
        if engine.is_terminal():
            completed_games += 1
            outcome = engine.get_outcome()
            # Sprawdź kto wygrał - NN jest w drużynie z NN2
            nn_points = outcome.get('NN', 0) + outcome.get('NN2', 0)
            random_points = outcome.get('R1', 0) + outcome.get('R2', 0)
            if nn_points > random_points:
                wins += 1
            total_points += nn_points
    
    win_rate = wins / max(1, completed_games) * 100
    avg_points = total_points / max(1, completed_games)
    print(f"Completed games: {completed_games}/{num_games}")
    print(f"Win rate vs random: {win_rate:.1f}%")
    print(f"Avg points: {avg_points:.2f}")
    
    return win_rate


def evaluate_mcts_vs_random(num_games: int = 100,
                            mcts_time_limit: float = 1.0) -> float:
    """Test samego MCTS vs random - pokazuje górną granicę."""
    mcts_bot = MCTS_Bot(personality='topplayer')
    
    wins = 0
    completed_games = 0
    
    print(f"Evaluating MCTS vs random ({num_games} games, {mcts_time_limit}s/move)...")
    
    for i in tqdm(range(num_games), desc="MCTS eval"):
        players = ['MCTS', 'R1', 'MCTS2', 'R2']
        engine = SixtySixEngine(players, {'tryb': '4p'})
        
        # DEBUG: Sprawdź stan początkowy
        if i == 0:
            print(f"\nDEBUG Game 0:")
            print(f"  is_terminal: {engine.is_terminal()}")
            current = engine.get_current_player()
            print(f"  current_player: {current}")
            print(f"  faza: {engine.game_state.faza}")
            if current:
                legal = engine.get_legal_actions(current)
                print(f"  legal_actions count: {len(legal)}")
                if legal:
                    print(f"  first legal action: {legal[0]}")
        
        move_count = 0
        while not engine.is_terminal() and move_count < 200:
            # Sprawdź czy trzeba sfinalizować lewę
            if engine.game_state.lewa_do_zamkniecia:
                engine.game_state.finalizuj_lewe()
                continue
            
            current = engine.get_current_player()
            if current is None:
                # Gra utknęła - sprawdź czy można wymusić koniec
                if i == 0:
                    print(f"  Move {move_count}: current is None")
                    print(f"    faza: {engine.game_state.faza}")
                    print(f"    kolej_gracza_idx: {engine.game_state.kolej_gracza_idx}")
                    print(f"    rozdanie_zakonczone: {engine.game_state.rozdanie_zakonczone}")
                    print(f"    podsumowanie: {bool(engine.game_state.podsumowanie)}")
                break
            
            # Pobierz legalne akcje
            legal = engine.get_legal_actions(current)
            
            if not legal:
                if i == 0:
                    print(f"  Move {move_count}: No legal actions for {current}")
                    print(f"    faza: {engine.game_state.faza}")
                break
            
            if current in ['MCTS', 'MCTS2']:
                action = mcts_bot.znajdz_najlepszy_ruch(engine, current, mcts_time_limit)
                if i == 0 and move_count < 10:
                    print(f"  Move {move_count}: MCTS ({current}) -> {action.get('typ') if action else None}")
            else:
                action = random.choice(legal)
                if i == 0 and move_count < 10:
                    print(f"  Move {move_count}: Random ({current}) -> {action.get('typ') if action else None}")
            
            if action:
                try:
                    engine.perform_action(current, action)
                except Exception as e:
                    if i == 0:
                        print(f"  Error applying action: {e}")
                    break
            else:
                if i == 0:
                    print(f"  Move {move_count}: No action returned by bot")
                break
            
            move_count += 1
        
        if i == 0:
            print(f"  Total moves: {move_count}")
            print(f"  is_terminal after: {engine.is_terminal()}")
        
        if engine.is_terminal():
            completed_games += 1
            outcome = engine.get_outcome()
            if i == 0:
                print(f"  Outcome: {outcome}")
            # Sprawdź kto wygrał - MCTS jest w drużynie z MCTS2
            mcts_points = outcome.get('MCTS', 0) + outcome.get('MCTS2', 0)
            random_points = outcome.get('R1', 0) + outcome.get('R2', 0)
            if mcts_points > random_points:
                wins += 1
    
    win_rate = wins / max(1, completed_games) * 100
    print(f"\nCompleted games: {completed_games}/{num_games}")
    print(f"MCTS win rate vs random: {win_rate:.1f}%")
    
    return win_rate


def evaluate_model_vs_heuristic(model: CardGameNetwork,
                                num_games: int = 200,
                                device: str = 'cpu') -> float:
    """Ewaluacja modelu przeciwko heurystycznemu botowi."""
    from nn_bot import NeuralNetworkBot
    from expert_heuristics import ExpertBot
    
    model.to(device)
    model.eval()
    
    nn_bot = NeuralNetworkBot(model=model, temperature=0.1, greedy=True, device=device)
    heuristic_bot = ExpertBot()
    
    wins = 0
    completed_games = 0
    total_nn_points = 0
    total_heur_points = 0
    
    print(f"Evaluating NN vs Heuristic ({num_games} games)...")
    
    for i in tqdm(range(num_games), desc="NN vs Heuristic"):
        players = ['NN', 'H1', 'NN2', 'H2']
        engine = SixtySixEngine(players, {'tryb': '4p'})
        
        move_count = 0
        while not engine.is_terminal() and move_count < 200:
            # Sprawdź czy trzeba sfinalizować lewę
            if engine.game_state.lewa_do_zamkniecia:
                engine.game_state.finalizuj_lewe()
                continue
            
            current = engine.get_current_player()
            if current is None:
                break
            
            # Pobierz legalne akcje
            legal = engine.get_legal_actions(current)
            if not legal:
                break
            
            if current in ['NN', 'NN2']:
                action = nn_bot.znajdz_najlepszy_ruch(engine, current)
            else:
                # Heurystyczny bot
                state = engine.get_state_for_player(current)
                action = heuristic_bot.get_action(state, current)
            
            if action:
                try:
                    engine.perform_action(current, action)
                except:
                    break
            else:
                break
            
            move_count += 1
        
        if engine.is_terminal():
            completed_games += 1
            outcome = engine.get_outcome()
            # Sprawdź kto wygrał - NN jest w drużynie z NN2
            nn_points = outcome.get('NN', 0) + outcome.get('NN2', 0)
            heur_points = outcome.get('H1', 0) + outcome.get('H2', 0)
            if nn_points > heur_points:
                wins += 1
            total_nn_points += nn_points
            total_heur_points += heur_points
    
    win_rate = wins / max(1, completed_games) * 100
    avg_nn = total_nn_points / max(1, completed_games)
    avg_heur = total_heur_points / max(1, completed_games)
    print(f"Completed games: {completed_games}/{num_games}")
    print(f"NN win rate vs Heuristic: {win_rate:.1f}%")
    print(f"Avg points - NN: {avg_nn:.1f}, Heuristic: {avg_heur:.1f}")
    
    return win_rate


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train NN from MCTS data")
    parser.add_argument('--mode', type=str, default='train',
                        choices=['train', 'evaluate', 'test_mcts', 'quick', 'vs_heuristic'])
    parser.add_argument('--games', type=int, default=500,
                        help='Number of games for training data')
    parser.add_argument('--mcts_time', type=float, default=1.0,
                        help='MCTS time limit per move (seconds)')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Training epochs')
    parser.add_argument('--device', type=str, default=None)
    
    args = parser.parse_args()
    
    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    if args.mode == 'quick':
        # Szybki test - mało gier, krótki MCTS
        print("\n=== Quick Test Mode ===\n")
        model = train_from_mcts(
            num_games=50,
            mcts_time_limit=0.5,
            epochs=20,
            device=device
        )
        if model:
            print("\n=== Evaluation ===")
            evaluate_model_vs_random(model, num_games=100, device=device)
    
    elif args.mode == 'train':
        # Pełny trening
        model = train_from_mcts(
            num_games=args.games,
            mcts_time_limit=args.mcts_time,
            epochs=args.epochs,
            device=device
        )
        if model:
            print("\n=== Evaluation ===")
            evaluate_model_vs_random(model, num_games=200, device=device)
    
    elif args.mode == 'evaluate':
        # Ewaluacja istniejącego modelu
        model_path = CHECKPOINTS_DIR / "best_model.pt"
        if model_path.exists():
            model = CardGameNetwork.load(str(model_path))
            evaluate_model_vs_random(model, num_games=200, device=device)
        else:
            print(f"Model not found: {model_path}")
    
    elif args.mode == 'test_mcts':
        # Test samego MCTS
        evaluate_mcts_vs_random(num_games=50, mcts_time_limit=args.mcts_time)
    
    elif args.mode == 'vs_heuristic':
        # NN vs heurystyczny bot
        model_path = CHECKPOINTS_DIR / "best_model.pt"
        if model_path.exists():
            model = CardGameNetwork.load(str(model_path))
            evaluate_model_vs_heuristic(model, num_games=200, device=device)
        else:
            print(f"Model not found: {model_path}")
