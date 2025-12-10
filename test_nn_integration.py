# test_nn_integration.py
"""
Test integracji bota NN z systemem botów portalu.
"""

import sys
from pathlib import Path

# Dodaj ścieżki
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_bot_creation():
    """Test tworzenia botów."""
    from boty import stworz_bota, DOSTEPNE_ALGORYTMY, BOT_ALGORITHMS
    
    print("=== Test tworzenia botów ===\n")
    print(f"Dostępne algorytmy: {len(DOSTEPNE_ALGORYTMY)}")
    print(f"Algorytmy: {DOSTEPNE_ALGORYTMY}\n")
    
    # Test tworzenia każdego typu bota
    success = 0
    failed = 0
    
    for algorytm in DOSTEPNE_ALGORYTMY:
        try:
            bot = stworz_bota(algorytm)
            if bot is not None:
                print(f"✓ {algorytm}: {type(bot).__name__}")
                success += 1
            else:
                print(f"✗ {algorytm}: zwrócono None")
                failed += 1
        except Exception as e:
            print(f"✗ {algorytm}: BŁĄD - {e}")
            failed += 1
    
    print(f"\nWynik: {success}/{len(DOSTEPNE_ALGORYTMY)} sukces")
    return failed == 0


def test_nn_bot_game():
    """Test gry z botem NN."""
    from boty import stworz_bota
    from engines.sixtysix_engine import SixtySixEngine
    
    print("\n=== Test gry z botem NN ===\n")
    
    # Stwórz bota NN
    nn_bot = stworz_bota('nn_topplayer')
    if nn_bot is None:
        print("Nie udało się stworzyć bota NN")
        return False
    
    print(f"Bot NN: {type(nn_bot).__name__}")
    
    # Stwórz grę
    players = ['NNBot', 'Random1', 'NNBot2', 'Random2']
    settings = {'tryb': '4p'}
    engine = SixtySixEngine(players, settings)
    
    # Rozegraj kilka ruchów
    moves = 0
    max_moves = 50
    
    while not engine.is_terminal() and moves < max_moves:
        # Finalizuj lewę jeśli potrzeba
        if engine.game_state.lewa_do_zamkniecia:
            engine.game_state.finalizuj_lewe()
            continue
        
        current = engine.get_current_player()
        if current is None:
            break
        
        # Bot NN dla graczy NNBot i NNBot2
        if 'NNBot' in current:
            action = nn_bot.znajdz_najlepszy_ruch(engine, current)
        else:
            # Losowy dla pozostałych
            legal = engine.get_legal_actions(current)
            import random
            action = random.choice(legal) if legal else None
        
        if action:
            try:
                engine.perform_action(current, action)
                moves += 1
                if moves <= 5:
                    print(f"  Ruch {moves}: {current} -> {action.get('typ')}")
            except Exception as e:
                print(f"  BŁĄD ruchu: {e}")
                break
        else:
            break
    
    print(f"\nRozegrano {moves} ruchów")
    print(f"Gra zakończona: {engine.is_terminal()}")
    
    if engine.is_terminal():
        outcome = engine.get_outcome()
        print(f"Wynik: {outcome}")
    
    return True


def test_nn_vs_mcts():
    """Porównanie szybkości NN vs MCTS."""
    import time
    from boty import stworz_bota
    from engines.sixtysix_engine import SixtySixEngine
    
    print("\n=== Porównanie szybkości NN vs MCTS ===\n")
    
    nn_bot = stworz_bota('nn_topplayer')
    mcts_bot = stworz_bota('topplayer')
    
    if nn_bot is None or mcts_bot is None:
        print("Nie udało się stworzyć botów")
        return False
    
    # Test szybkości - 10 decyzji
    players = ['Bot1', 'Bot2', 'Bot3', 'Bot4']
    engine = SixtySixEngine(players, {'tryb': '4p'})
    
    current = engine.get_current_player()
    
    # NN
    start = time.time()
    for _ in range(10):
        _ = nn_bot.znajdz_najlepszy_ruch(engine, current)
    nn_time = time.time() - start
    
    # MCTS (krótki limit)
    start = time.time()
    _ = mcts_bot.znajdz_najlepszy_ruch(engine, current, limit_czasu_s=0.1)
    mcts_time = time.time() - start
    
    print(f"NN Bot:   10 decyzji w {nn_time*1000:.1f}ms ({nn_time/10*1000:.2f}ms/decyzja)")
    print(f"MCTS Bot: 1 decyzja w {mcts_time*1000:.1f}ms (limit 100ms)")
    print(f"\nNN jest ~{mcts_time/(nn_time/10):.0f}x szybszy!")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("TEST INTEGRACJI BOTA NN Z PORTALEM MIEDZIOWE KARTY")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Tworzenie botów
    if not test_bot_creation():
        all_passed = False
    
    # Test 2: Gra z botem NN
    if not test_nn_bot_game():
        all_passed = False
    
    # Test 3: Porównanie szybkości
    if not test_nn_vs_mcts():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ WSZYSTKIE TESTY ZAKOŃCZONE SUKCESEM!")
    else:
        print("✗ NIEKTÓRE TESTY NIE POWIODŁY SIĘ")
    print("=" * 60)
