#!/usr/bin/env python3
"""
Test wyboru musiku w trybie 2p dla gry Tysiąc
"""

from silnik_tysiac import RozdanieTysiac, Gracz, FazaGry

def test_wybor_musiku_2p():
    """Test wyboru musiku w grze 2 osobowej"""
    print("\n=== TEST WYBORU MUSIKU W GRZE 2 OSOBOWEJ ===\n")
    
    # Stwórz graczy
    gracze = [
        Gracz("Gracz1"),
        Gracz("Gracz2")
    ]
    
    # Stwórz rozdanie
    rozdanie = RozdanieTysiac(gracze, rozdajacy_idx=0, tryb='2p')
    rozdanie.rozpocznij_nowe_rozdanie()
    
    print(f"✓ Rozdanie utworzone")
    print(f"  Faza: {rozdanie.faza.name}")
    print(f"  Gracz 1 ma {len(gracze[0].reka)} kart")
    print(f"  Gracz 2 ma {len(gracze[1].reka)} kart")
    print(f"  Musik 1: {len(rozdanie.musik_1)} karty")
    print(f"  Musik 2: {len(rozdanie.musik_2)} karty")
    print(f"  musik_odkryty: {rozdanie.musik_odkryty}")
    print(f"  musik_wybrany: {rozdanie.musik_wybrany}")
    
    # Symuluj licytację - pierwszy gracz licytuje, drugi pasuje
    print(f"\n--- LICYTACJA ---")
    current_player_name = rozdanie.get_current_player()
    current_player = next(g for g in gracze if g.nazwa == current_player_name)
    
    print(f"  {current_player_name} licytuje 100")
    rozdanie.wykonaj_akcje(current_player, {'typ': 'licytuj', 'wartosc': 100})
    
    next_player_name = rozdanie.get_current_player()
    next_player = next(g for g in gracze if g.nazwa == next_player_name)
    print(f"  {next_player_name} pasuje")
    rozdanie.wykonaj_akcje(next_player, {'typ': 'pas'})
    
    print(f"\n✓ Licytacja zakończona")
    print(f"  Faza: {rozdanie.faza.name}")
    print(f"  Grający: {rozdanie.grajacy.nazwa if rozdanie.grajacy else 'Brak'}")
    print(f"  Kontrakt: {rozdanie.kontrakt_wartosc}")
    print(f"  musik_odkryty (przed wyborem): {rozdanie.musik_odkryty}")
    print(f"  musik_wybrany (przed wyborem): {rozdanie.musik_wybrany}")
    
    # Wybierz musik
    if rozdanie.faza == FazaGry.WYMIANA_MUSZKU and not rozdanie.musik_odkryty:
        print(f"\n--- WYBÓR MUSIKU ---")
        gracz_grajacy = rozdanie.grajacy
        kart_przed = len(gracz_grajacy.reka)
        
        print(f"  {gracz_grajacy.nazwa} ma {kart_przed} kart przed wyborem musiku")
        print(f"  Wybiera musik 1...")
        
        rozdanie.wykonaj_akcje(gracz_grajacy, {'typ': 'wybierz_musik', 'musik': 1})
        
        kart_po = len(gracz_grajacy.reka)
        print(f"\n✓ Musik wybrany!")
        print(f"  {gracz_grajacy.nazwa} ma teraz {kart_po} kart (było {kart_przed})")
        print(f"  musik_odkryty: {rozdanie.musik_odkryty}")
        print(f"  musik_wybrany: {rozdanie.musik_wybrany}")
        print(f"  Faza: {rozdanie.faza.name}")
        
        # Sprawdź czy karty zostały dodane
        if kart_po == kart_przed + 2:
            print(f"  ✅ Karty z musiku zostały poprawnie dodane do ręki!")
        else:
            print(f"  ❌ BŁĄD: Karty nie zostały dodane poprawnie")
            return False
        
        # Sprawdź flagi
        if rozdanie.musik_odkryty and rozdanie.musik_wybrany == 1:
            print(f"  ✅ Flagi poprawnie ustawione!")
        else:
            print(f"  ❌ BŁĄD: Flagi nie zostały poprawnie ustawione")
            return False
    else:
        print(f"\n❌ BŁĄD: Nie jesteśmy w fazie wyboru musiku")
        print(f"  Faza: {rozdanie.faza.name}")
        print(f"  musik_odkryty: {rozdanie.musik_odkryty}")
        return False
    
    print(f"\n=== ✅ TEST ZAKOŃCZONY POMYŚLNIE ===")
    return True

if __name__ == "__main__":
    try:
        success = test_wybor_musiku_2p()
        if not success:
            print("\n❌ TEST NIEUDANY")
            exit(1)
    except Exception as e:
        print(f"\n❌ BŁĄD W TEŚCIE: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
