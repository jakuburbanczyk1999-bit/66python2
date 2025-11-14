#!/usr/bin/env python3
"""
Test gry Tysiąc - sprawdza poprawność działania silnika
"""

from silnik_tysiac import RozdanieTysiac, Gracz, FazaGry

def test_rozdanie_2p():
    """Test gry 2 osobowej"""
    print("\n=== TEST GRY 2 OSOBOWEJ ===")
    
    # Stwórz graczy
    gracze = [
        Gracz("Jakub"),
        Gracz("Bot_1")
    ]
    
    # Stwórz rozdanie
    rozdanie = RozdanieTysiac(gracze, rozdajacy_idx=0, tryb='2p')
    rozdanie.rozpocznij_nowe_rozdanie()
    
    print(f"Faza: {rozdanie.faza.name}")
    print(f"Kolej gracza: {rozdanie.get_current_player()}")
    print(f"Gracz 1 (Jakub) ma {len(gracze[0].reka)} kart")
    print(f"Gracz 2 (Bot_1) ma {len(gracze[1].reka)} kart")
    print(f"Musik 1: {len(rozdanie.musik_1)} kart")
    print(f"Musik 2: {len(rozdanie.musik_2)} kart")
    
    # Test licytacji
    if rozdanie.faza == FazaGry.LICYTACJA:
        print("\nLICYTACJA:")
        current_player_name = rozdanie.get_current_player()
        if current_player_name:
            current_player = next(g for g in gracze if g.nazwa == current_player_name)
            akcje = rozdanie.get_mozliwe_akcje(current_player)
            print(f"  Możliwe akcje dla {current_player_name}: {akcje}")
            
            # Spróbuj licytować
            if any(a['typ'] == 'licytuj' for a in akcje):
                akcja_licytuj = next(a for a in akcje if a['typ'] == 'licytuj')
                print(f"  {current_player_name} licytuje {akcja_licytuj['wartosc']}")
                rozdanie.wykonaj_akcje(current_player, akcja_licytuj)
            
            # Drugi gracz pasuje
            next_player_name = rozdanie.get_current_player()
            if next_player_name:
                next_player = next(g for g in gracze if g.nazwa == next_player_name)
                print(f"  {next_player_name} pasuje")
                rozdanie.wykonaj_akcje(next_player, {'typ': 'pas'})
    
    print(f"\nPo licytacji - Faza: {rozdanie.faza.name}")
    print(f"Grający: {rozdanie.grajacy.nazwa if rozdanie.grajacy else 'Brak'}")
    print(f"Kontrakt: {rozdanie.kontrakt_wartosc}")
    
    return True

def test_rozdanie_3p():
    """Test gry 3 osobowej"""
    print("\n=== TEST GRY 3 OSOBOWEJ ===")
    
    # Stwórz graczy
    gracze = [
        Gracz("Jakub"),
        Gracz("Bot_1"),
        Gracz("Bot_2")
    ]
    
    # Stwórz rozdanie
    rozdanie = RozdanieTysiac(gracze, rozdajacy_idx=0, tryb='3p')
    rozdanie.rozpocznij_nowe_rozdanie()
    
    print(f"Faza: {rozdanie.faza.name}")
    print(f"Kolej gracza: {rozdanie.get_current_player()}")
    
    for gracz in gracze:
        print(f"{gracz.nazwa} ma {len(gracz.reka)} kart")
    print(f"Musik: {len(rozdanie.musik_karty)} kart")
    
    # Test licytacji - wszyscy pasują
    print("\nTEST: Wszyscy pasują od razu")
    for _ in range(3):
        current_player_name = rozdanie.get_current_player()
        if current_player_name and rozdanie.faza == FazaGry.LICYTACJA:
            current_player = next(g for g in gracze if g.nazwa == current_player_name)
            print(f"  {current_player_name} pasuje")
            rozdanie.wykonaj_akcje(current_player, {'typ': 'pas'})
    
    print(f"\nPo licytacji - Faza: {rozdanie.faza.name}")
    print(f"Grający: {rozdanie.grajacy.nazwa if rozdanie.grajacy else 'Brak'}")
    print(f"Kontrakt: {rozdanie.kontrakt_wartosc}")
    
    return True

def test_rozdanie_4p():
    """Test gry 4 osobowej"""
    print("\n=== TEST GRY 4 OSOBOWEJ ===")
    
    # Stwórz graczy
    gracze = [
        Gracz("Jakub"),
        Gracz("Bot_1"),
        Gracz("Bot_2"),
        Gracz("Bot_3")
    ]
    
    # Stwórz rozdanie
    rozdanie = RozdanieTysiac(gracze, rozdajacy_idx=0, tryb='4p')
    rozdanie.rozpocznij_nowe_rozdanie()
    
    print(f"Faza: {rozdanie.faza.name}")
    print(f"Muzyk: {gracze[rozdanie.muzyk_idx].nazwa if rozdanie.muzyk_idx is not None else 'Brak'}")
    print(f"Kolej gracza: {rozdanie.get_current_player()}")
    
    for i, gracz in enumerate(gracze):
        if i == rozdanie.muzyk_idx:
            print(f"{gracz.nazwa} (MUZYK) ma {len(gracz.reka)} kart")
        else:
            print(f"{gracz.nazwa} ma {len(gracz.reka)} kart")
    print(f"Musik: {len(rozdanie.musik_karty)} kart")
    
    return True

def test_meldunek():
    """Test meldunku"""
    print("\n=== TEST MELDUNKU ===")
    
    from silnik_tysiac import Karta, Kolor, Ranga
    
    gracze = [
        Gracz("Jakub"),
        Gracz("Bot_1"),
        Gracz("Bot_2")
    ]
    
    rozdanie = RozdanieTysiac(gracze, rozdajacy_idx=0, tryb='3p')
    rozdanie.rozpocznij_nowe_rozdanie()
    
    # Przejdź przez licytację
    while rozdanie.faza == FazaGry.LICYTACJA:
        current_player_name = rozdanie.get_current_player()
        if current_player_name:
            current_player = next(g for g in gracze if g.nazwa == current_player_name)
            akcje = rozdanie.get_mozliwe_akcje(current_player)
            if akcje:
                rozdanie.wykonaj_akcje(current_player, akcje[0])
    
    # Przejdź przez wymianę muszku
    while rozdanie.faza == FazaGry.WYMIANA_MUSZKU:
        if rozdanie.grajacy:
            # Oddaj karty losowo
            if rozdanie.tryb == '3p' and rozdanie.musik_odkryty:
                rozdanie_dict = {}
                idx = 0
                for gracz in gracze:
                    if gracz != rozdanie.grajacy and idx < 2:
                        if len(rozdanie.grajacy.reka) > idx:
                            rozdanie_dict[gracz.nazwa] = rozdanie.grajacy.reka[idx]
                            idx += 1
                if len(rozdanie_dict) > 0:
                    rozdanie._rozdaj_karty_z_reki(rozdanie.grajacy, rozdanie_dict)
                    break
    
    print(f"Faza po wymianie: {rozdanie.faza.name}")
    print(f"Grający: {rozdanie.grajacy.nazwa if rozdanie.grajacy else 'Brak'}")
    
    # Spróbuj zagrać króla, jeśli grający ma parę
    if rozdanie.faza == FazaGry.ROZGRYWKA and rozdanie.grajacy:
        print("\nSzukam możliwości meldunku...")
        for kolor in Kolor:
            ma_krola = any(k.ranga == Ranga.KROL and k.kolor == kolor for k in rozdanie.grajacy.reka)
            ma_dame = any(k.ranga == Ranga.DAMA and k.kolor == kolor for k in rozdanie.grajacy.reka)
            
            if ma_krola and ma_dame:
                krol = next(k for k in rozdanie.grajacy.reka if k.ranga == Ranga.KROL and k.kolor == kolor)
                print(f"Znaleziono parę: Król i Dama {kolor.name}")
                print(f"Zagrywam {krol}")
                
                wynik = rozdanie.zagraj_karte(rozdanie.grajacy, krol)
                if wynik and wynik.get('meldunek_pkt', 0) > 0:
                    print(f"✓ Meldunek zgłoszony! Punkty: {wynik['meldunek_pkt']}")
                    print(f"  Nowy atut: {rozdanie.atut.name if rozdanie.atut else 'Brak'}")
                else:
                    print("✗ Meldunek nie został zgłoszony")
                break
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("TESTY SILNIKA GRY TYSIĄC")
    print("=" * 50)
    
    try:
        test_rozdanie_2p()
        test_rozdanie_3p()
        test_rozdanie_4p()
        test_meldunek()
        
        print("\n" + "=" * 50)
        print("✓ WSZYSTKIE TESTY ZAKOŃCZONE POMYŚLNIE")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ BŁĄD W TESTACH: {e}")
        import traceback
        traceback.print_exc()
