#!/usr/bin/env python3
"""
Test wyróżnienia kart z musiku w trybie 2p dla gry Tysiąc
"""

from silnik_tysiac import RozdanieTysiac, Gracz, FazaGry
from engines.tysiac_engine import TysiacEngine

def test_wyroznienie_kart_z_musiku():
    """Test wyróżnienia kart z musiku w grze 2 osobowej"""
    print("\n=== TEST WYRÓŻNIENIA KART Z MUSIKU ===\n")
    
    # Stwórz graczy
    player_ids = ["Gracz1", "Gracz2"]
    settings = {'tryb': '2p', 'rozdajacy_idx': 0}
    
    # Stwórz engine
    engine = TysiacEngine(player_ids, settings)
    
    print(f"✓ Engine utworzony")
    print(f"  Faza: {engine.game_state.faza.name}")
    
    # Symuluj licytację
    print(f"\n--- LICYTACJA ---")
    current_player = engine.get_current_player()
    print(f"  {current_player} licytuje 100")
    engine.perform_action(current_player, {'typ': 'licytuj', 'wartosc': 100})
    
    current_player = engine.get_current_player()
    print(f"  {current_player} pasuje")
    engine.perform_action(current_player, {'typ': 'pas'})
    
    print(f"\n✓ Licytacja zakończona")
    
    # Wybierz musik
    if engine.game_state.faza == FazaGry.WYMIANA_MUSZKU:
        print(f"\n--- WYBÓR MUSIKU ---")
        grajacy = engine.game_state.grajacy.nazwa
        
        # Pobierz stan PRZED wyborem musiku
        state_before = engine.get_state_for_player(grajacy)
        print(f"  Grający: {grajacy}")
        print(f"  Kart w ręce (przed): {len(state_before['rece_graczy'][grajacy])}")
        print(f"  karty_z_musiku (przed): {state_before.get('karty_z_musiku', [])}")
        
        # Wybierz musik 1
        print(f"\n  Wybiera musik 1...")
        engine.perform_action(grajacy, {'typ': 'wybierz_musik', 'musik': 1})
        
        # Pobierz stan PO wyborze musiku
        state_after = engine.get_state_for_player(grajacy)
        print(f"\n✓ Musik wybrany!")
        print(f"  Kart w ręce (po): {len(state_after['rece_graczy'][grajacy])}")
        print(f"  karty_z_musiku (po): {state_after.get('karty_z_musiku', [])}")
        
        # Sprawdź czy karty z musiku są oznaczone
        karty_z_musiku = state_after.get('karty_z_musiku', [])
        if len(karty_z_musiku) == 2:
            print(f"  ✅ Karty z musiku są poprawnie oznaczone:")
            for karta in karty_z_musiku:
                print(f"     - {karta}")
        else:
            print(f"  ❌ BŁĄD: Nieprawidłowa liczba kart z musiku: {len(karty_z_musiku)}")
            return False
        
        # Sprawdź czy karty są w ręce
        reka = state_after['rece_graczy'][grajacy]
        wszystkie_w_rece = all(karta in reka for karta in karty_z_musiku)
        if wszystkie_w_rece:
            print(f"  ✅ Wszystkie karty z musiku są w ręce gracza!")
        else:
            print(f"  ❌ BŁĄD: Nie wszystkie karty z musiku są w ręce")
            return False
    else:
        print(f"\n❌ BŁĄD: Nie jesteśmy w fazie wyboru musiku")
        return False
    
    print(f"\n=== ✅ TEST ZAKOŃCZONY POMYŚLNIE ===")
    return True

if __name__ == "__main__":
    try:
        # Dodaj ścieżkę do engines
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        success = test_wyroznienie_kart_z_musiku()
        if not success:
            print("\n❌ TEST NIEUDANY")
            exit(1)
    except Exception as e:
        print(f"\n❌ BŁĄD W TEŚCIE: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
