# nn_training/test_all.py
"""
Test wszystkich komponentów systemu NN.
Uruchom przed treningiem aby upewnić się że wszystko działa.
"""

import sys
from pathlib import Path

# Upewnij się, że ścieżki są poprawne - NN_DIR musi być PRZED PROJECT_ROOT
NN_DIR = Path(__file__).parent
PROJECT_ROOT = NN_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if str(NN_DIR) not in sys.path:
    sys.path.insert(0, str(NN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

def test_imports():
    """Test importów."""
    print("1. Testing imports...")
    
    try:
        from nn_training.config import NETWORK_CONFIG, TRAINING_CONFIG, ACTION_INDEX_TO_DICT
        print(f"   ✓ config.py - {NETWORK_CONFIG.TOTAL_STATE_DIM} state dims, {NETWORK_CONFIG.TOTAL_ACTIONS} actions")
        
        from nn_training.state_encoder import StateEncoder, ENCODER
        print(f"   ✓ state_encoder.py")
        
        from nn_training.network import CardGameNetwork
        print(f"   ✓ network.py")
        
        from nn_training.game_interface import GameInterface
        print(f"   ✓ game_interface.py")
        
        from nn_training.self_play import SelfPlayWorker, generate_self_play_data
        print(f"   ✓ self_play.py")
        
        from nn_training.trainer import Trainer
        print(f"   ✓ trainer.py")
        
        from nn_training.nn_bot import NeuralNetworkBot
        print(f"   ✓ nn_bot.py")
        
        return True
    except Exception as e:
        print(f"   ✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_engine():
    """Test silnika gry."""
    print("\n2. Testing game engine...")
    
    try:
        from engines.sixtysix_engine import SixtySixEngine
        
        players = ['P1', 'P2', 'P3', 'P4']
        settings = {
            'tryb': '4p',
            'rozdajacy_idx': 0,
            'nazwy_druzyn': {'My': 'Team1', 'Oni': 'Team2'}
        }
        
        engine = SixtySixEngine(players, settings)
        
        # Test podstawowych metod
        current = engine.get_current_player()
        state = engine.get_state_for_player(current)
        legal = engine.get_legal_actions(current)
        
        print(f"   ✓ Engine created, current player: {current}")
        print(f"   ✓ Phase: {state['faza']}")
        print(f"   ✓ Legal actions: {len(legal)}")
        
        return True
    except Exception as e:
        print(f"   ✗ Game engine error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_encoder():
    """Test enkodera stanu."""
    print("\n3. Testing state encoder...")
    
    try:
        import torch
        from nn_training.state_encoder import StateEncoder, ENCODER
        from nn_training.config import NETWORK_CONFIG
        from engines.sixtysix_engine import SixtySixEngine
        
        # Stwórz grę
        players = ['P1', 'P2', 'P3', 'P4']
        settings = {'tryb': '4p', 'rozdajacy_idx': 0, 'nazwy_druzyn': {'My': 'T1', 'Oni': 'T2'}}
        engine = SixtySixEngine(players, settings)
        
        current = engine.get_current_player()
        state_dict = engine.get_state_for_player(current)
        
        # Enkoduj stan
        state_tensor = ENCODER.encode_state(state_dict, current)
        action_mask = ENCODER.get_action_mask(state_dict, current)
        
        print(f"   ✓ State tensor shape: {state_tensor.shape}")
        print(f"   ✓ Expected: ({NETWORK_CONFIG.TOTAL_STATE_DIM},)")
        print(f"   ✓ Action mask shape: {action_mask.shape}")
        print(f"   ✓ Legal actions: {action_mask.sum().item()}")
        
        assert state_tensor.shape[0] == NETWORK_CONFIG.TOTAL_STATE_DIM, "Wrong state dimension!"
        assert action_mask.shape[0] == NETWORK_CONFIG.TOTAL_ACTIONS, "Wrong action dimension!"
        
        return True
    except Exception as e:
        print(f"   ✗ State encoder error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_network():
    """Test sieci neuronowej."""
    print("\n4. Testing neural network...")
    
    try:
        import torch
        from nn_training.network import CardGameNetwork
        from nn_training.config import NETWORK_CONFIG
        
        model = CardGameNetwork()
        
        print(f"   ✓ Model created")
        print(f"   ✓ Parameters: {model.count_parameters():,}")
        
        # Test forward pass
        batch_size = 4
        state = torch.randn(batch_size, NETWORK_CONFIG.TOTAL_STATE_DIM)
        mask = torch.ones(batch_size, NETWORK_CONFIG.TOTAL_ACTIONS, dtype=torch.bool)
        
        policy, value = model(state, mask)
        
        print(f"   ✓ Forward pass OK")
        print(f"   ✓ Policy shape: {policy.shape}")
        print(f"   ✓ Value shape: {value.shape}")
        
        # Test get_action
        single_state = torch.randn(NETWORK_CONFIG.TOTAL_STATE_DIM)
        single_mask = torch.ones(NETWORK_CONFIG.TOTAL_ACTIONS, dtype=torch.bool)
        
        action, pol, val = model.get_action(single_state, single_mask, temperature=1.0)
        
        print(f"   ✓ Get action OK, selected: {action}")
        
        # Test save/load
        from nn_training.config import CHECKPOINTS_DIR
        model.save(name="test_network")
        loaded = CardGameNetwork.load(CHECKPOINTS_DIR / "test_network.pt")
        
        print(f"   ✓ Save/load OK")
        
        return True
    except Exception as e:
        print(f"   ✗ Network error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_interface():
    """Test interfejsu gry."""
    print("\n5. Testing game interface...")
    
    try:
        from nn_training.game_interface import GameInterface, play_random_game
        
        # Test prostej gry
        game = GameInterface(['A', 'B', 'C', 'D'], '4p')
        
        current = game.get_current_player()
        legal = game.get_legal_action_indices(current)
        
        print(f"   ✓ Game created")
        print(f"   ✓ Current player: {current}")
        print(f"   ✓ Legal actions: {len(legal)}")
        
        # Test losowej gry
        outcome = play_random_game(verbose=False)
        
        if outcome:
            print(f"   ✓ Random game completed")
            print(f"   ✓ Winner: {outcome.winner_team}, Points: {outcome.points_awarded}")
        else:
            print(f"   ⚠ Random game had no outcome")
        
        return True
    except Exception as e:
        print(f"   ✗ Game interface error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_self_play():
    """Test self-play."""
    print("\n6. Testing self-play...")
    
    try:
        from nn_training.self_play import generate_self_play_data, ReplayBuffer
        
        # Generuj małą ilość danych
        experiences = generate_self_play_data(
            model=None,
            num_games=5,
            temperature=1.0,
            show_progress=False
        )
        
        print(f"   ✓ Generated {len(experiences)} experiences from 5 games")
        
        # Test replay buffer
        buffer = ReplayBuffer(capacity=1000)
        buffer.add_batch(experiences)
        
        batch = buffer.sample(min(10, len(buffer)))
        print(f"   ✓ Replay buffer OK, sampled {len(batch)} experiences")
        
        return True
    except Exception as e:
        print(f"   ✗ Self-play error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trainer():
    """Test trenera."""
    print("\n7. Testing trainer...")
    
    try:
        import torch
        from nn_training.trainer import Trainer
        from nn_training.network import CardGameNetwork
        from nn_training.self_play import generate_self_play_data
        
        # Stwórz model i trener
        model = CardGameNetwork()
        trainer = Trainer(model, device='cpu')
        
        print(f"   ✓ Trainer created on {trainer.device}")
        
        # Generuj dane
        experiences = generate_self_play_data(
            model=None,
            num_games=3,
            show_progress=False
        )
        
        if len(experiences) < 10:
            print(f"   ⚠ Not enough experiences ({len(experiences)}), skipping training test")
            return True
        
        # Krótki trening
        history = trainer.train(
            experiences,
            epochs=2,
            validation_split=0.2,
            save_best=False
        )
        
        print(f"   ✓ Training OK, final loss: {history[-1].total_loss:.4f}")
        
        return True
    except Exception as e:
        print(f"   ✗ Trainer error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nn_bot():
    """Test bota NN."""
    print("\n8. Testing NN bot...")
    
    try:
        from nn_training.nn_bot import NeuralNetworkBot
        from nn_training.network import CardGameNetwork
        from nn_training.config import CHECKPOINTS_DIR
        from engines.sixtysix_engine import SixtySixEngine
        
        # Stwórz model
        model = CardGameNetwork()
        model.save(name="test_bot_model")
        
        # Stwórz bota
        bot = NeuralNetworkBot(model=model, temperature=0.5)
        
        print(f"   ✓ Bot created on {bot.device}")
        
        # Test z grą
        players = ['Bot', 'P2', 'P3', 'P4']
        settings = {'tryb': '4p', 'rozdajacy_idx': 0, 'nazwy_druzyn': {'My': 'T1', 'Oni': 'T2'}}
        engine = SixtySixEngine(players, settings)
        
        # Poczekaj na turę bota
        current = engine.get_current_player()
        if current == 'Bot':
            action = bot.znajdz_najlepszy_ruch(engine, 'Bot')
            print(f"   ✓ Bot action: {action}")
        else:
            print(f"   ⚠ Not Bot's turn (current: {current})")
        
        return True
    except Exception as e:
        print(f"   ✗ NN bot error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Uruchom wszystkie testy."""
    print("="*60)
    print("NN TRAINING SYSTEM - COMPREHENSIVE TEST")
    print("="*60)
    
    results = {}
    
    results['imports'] = test_imports()
    results['game_engine'] = test_game_engine()
    results['state_encoder'] = test_state_encoder()
    results['network'] = test_network()
    results['game_interface'] = test_game_interface()
    results['self_play'] = test_self_play()
    results['trainer'] = test_trainer()
    results['nn_bot'] = test_nn_bot()
    
    # Podsumowanie
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! System ready for training.")
        print("\nNext steps:")
        print("  1. Run quick test:  python run_training.py --mode quick")
        print("  2. Full training:   python run_training.py --mode full --iterations 10")
    else:
        print("\n✗ Some tests failed. Please fix errors before training.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
