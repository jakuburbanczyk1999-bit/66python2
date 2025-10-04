# ZAKTUALIZOWANY PLIK: uruchom_test.py
import sys
import random
from typing import Union
from silnik_gry import Gracz, Druzyna, Rozdanie, Karta, FazaGry

def znajdz_legalny_ruch(rozdanie: Rozdanie, gracz: Gracz) -> Union[Karta, None]:
    """Prosta AI: znajduje pierwszą legalną kartę do zagrania z ręki gracza."""
    for karta in gracz.reka:
        if rozdanie._waliduj_ruch(gracz, karta):
            return karta
    return None

def formatuj_akcje(akcje: list[dict]) -> str:
    """Pomocnicza funkcja do ładnego wyświetlania możliwych akcji."""
    opisy = []
    for akcja in akcje:
        if akcja.get('kontrakt'):
            atut_str = f" ({akcja['atut'].name})" if akcja.get('atut') else ""
            typ_akcji = akcja['typ'].replace('_', ' ').capitalize()
            if typ_akcji == 'Deklaracja': typ_akcji = akcja['kontrakt'].name
            if typ_akcji == 'Przebicie': typ_akcji = f"Przebij na {akcja['kontrakt'].name}"
            if typ_akcji == 'Zmiana kontraktu': typ_akcji = f"Zmień na {akcja['kontrakt'].name}"
            opisy.append(f"{typ_akcji}{atut_str}")
        else:
            opisy.append(akcja['typ'].replace('_', ' ').capitalize())
    return ", ".join(opisy)

def uruchom_symulacje_rozdania(numer_rozdania: int, druzyny: list[Druzyna]):
    print(f"--- ROZDANIE #{numer_rozdania} ---")

    gracze = [
        Gracz(nazwa="Jakub"), Gracz(nazwa="Przeciwnik1"),
        Gracz(nazwa="Nasz"), Gracz(nazwa="Przeciwnik2")
    ]
    for gracz in gracze: gracz.reka.clear(); gracz.wygrane_karty.clear()
    druzyny[0].gracze.clear(); druzyny[1].gracze.clear()
    druzyny[0].dodaj_gracza(gracze[0]); druzyny[0].dodaj_gracza(gracze[2])
    druzyny[1].dodaj_gracza(gracze[1]); druzyny[1].dodaj_gracza(gracze[3])
    
    rozdajacy_idx = (numer_rozdania - 1) % 4
    rozdanie = Rozdanie(gracze=gracze, druzyny=druzyny, rozdajacy_idx=rozdajacy_idx)
    print(f"Rozdającym jest: {gracze[rozdajacy_idx].nazwa}")
    
    rozdanie.rozpocznij_nowe_rozdanie()
    print("\n--- ETAP: Rozdanie 3 kart ---")
    for gracz in gracze:
        print(f"  Ręka gracza '{gracz.nazwa}': {', '.join(map(str, gracz.reka))}")

    if rozdanie.faza == FazaGry.DEKLARACJA_1:
        print("\n--- ETAP: Deklaracja 1 ---")
        gracz_deklarujacy = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(gracz_deklarujacy)
        wybrana_akcja = random.choice(mozliwe_akcje)
        print(f"  Deklaruje: {gracz_deklarujacy.nazwa}")
        print(f"  Możliwe akcje: {formatuj_akcje(mozliwe_akcje)}")
        atut_str = wybrana_akcja.get('atut').name if wybrana_akcja.get('atut') else "Brak"
        print(f"  Decyzja: {wybrana_akcja['kontrakt'].name}, Atut: {atut_str}")
        rozdanie.wykonaj_akcje(gracz_deklarujacy, wybrana_akcja)

    if rozdanie.faza == FazaGry.LUFA:
        print("\n--- ETAP: Faza Lufy ---")
        while rozdanie.faza == FazaGry.LUFA:
            gracz = rozdanie.gracze[rozdanie.kolej_gracza_idx]
            print(f"  Decyzję podejmuje: {gracz.nazwa}")
            akcje_lufa = rozdanie.get_mozliwe_akcje(gracz)
            # AI: 50% szansy na podbicie, reszta to pas
            akcja = random.choice(akcje_lufa) if random.random() > 0.5 and len(akcje_lufa) > 1 else {'typ': 'pas_lufa'}
            print(f"  Decyzja: {akcja['typ'].replace('_lufa', '').capitalize()}")
            rozdanie.wykonaj_akcje(gracz, akcja)
            if 'lufa' in akcja['typ'] or 'kontra' in akcja['typ']:
                print(f"  Stawka podbita do x{rozdanie.mnoznik_lufy}")

    if rozdanie.faza == FazaGry.FAZA_PYTANIA:
        print("\n--- ETAP: Faza Pytania ---")
        gracz = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        print(f"  Ponownie decyduje: {gracz.nazwa}")
        akcje = rozdanie.get_mozliwe_akcje(gracz)
        wybrana_akcja = random.choice(akcje)
        decyzja_str = f"Zmień na {wybrana_akcja['kontrakt'].name}" if 'kontrakt' in wybrana_akcja else "Pytam"
        print(f"  Możliwe akcje: {formatuj_akcje(akcje)}")
        print(f"  Decyzja: {decyzja_str}")
        rozdanie.wykonaj_akcje(gracz, wybrana_akcja)

    if rozdanie.faza == FazaGry.LICYTACJA:
        print("\n--- ETAP: LicytacjA 2 (Przebicie) ---")
        for _ in range(3):
            if rozdanie.faza != FazaGry.LICYTACJA: break
            gracz = rozdanie.gracze[rozdanie.kolej_gracza_idx]
            akcje = rozdanie.get_mozliwe_akcje(gracz)
            if not akcje: continue
            wybrana_akcja = random.choice(akcje)
            decyzja = "Pas" if wybrana_akcja['typ'] == 'pas' else f"Przebijam na {wybrana_akcja['kontrakt'].name}"
            print(f"  Licytuje: {gracz.nazwa}\n  Możliwe akcje: {formatuj_akcje(akcje)}\n  Decyzja: {decyzja}")
            rozdanie.wykonaj_akcje(gracz, wybrana_akcja)
      
    if rozdanie.faza == FazaGry.ROZGRYWKA:
        print("\n" + "="*25 + "\n--- ETAP: Rozgrywka ---")
        if rozdanie.nieaktywny_gracz:
            print(f"INFO: Gra 1 vs 2. Gracz '{rozdanie.nieaktywny_gracz.nazwa}' nie bierze udziału w rozgrywce.")
        
        for numer_lewy in range(1, 7):
            if rozdanie.rozdanie_zakonczone: break
            print(f"\n-- Lewa #{numer_lewy} --")
            
            for i in range(rozdanie.liczba_aktywnych_graczy):
                gracz = rozdanie.gracze[rozdanie.kolej_gracza_idx]
                if i == 0: print(f"  Rozpoczyna: {gracz.nazwa}")

                karta = znajdz_legalny_ruch(rozdanie, gracz)
                if not karta:
                    print(f"BŁĄD: Gracz {gracz.nazwa} nie ma legalnego ruchu!")
                    return

                wynik = rozdanie.zagraj_karte(gracz, karta)
                meldunek = f" (MELDUNEK! +{wynik['meldunek_pkt']} pkt)" if wynik.get('meldunek_pkt', 0) > 0 else ""
                print(f"  [{gracz.nazwa}] zagrywa: {karta}{meldunek}")
                
                if rozdanie.rozdanie_zakonczone and not rozdanie.aktualna_lewa: break
            
            if rozdanie.rozdanie_zakonczone: break

    if rozdanie.rozdanie_zakonczone and rozdanie.powod_zakonczenia:
         print(f"\n!!! Rozdanie zakończone przed czasem: {rozdanie.powod_zakonczenia} !!!")

    druzyna_wygrana, punkty_dodane, mnoznik = rozdanie.rozlicz_rozdanie()

    print("\n" + "="*25)
    print("--- WYNIK KOŃCOWY ROZDANIA ---")
    print(f"  Grany kontrakt: {rozdanie.kontrakt.name}")
    
    if rozdanie.rozdanie_zakonczone and druzyna_wygrana != rozdanie.grajacy.druzyna:
        print(f"  Punkty z kart (z bonusem): Kontrakt niespełniony przez drużynę '{rozdanie.grajacy.druzyna.nazwa}'")
    else:
        punkty_a = rozdanie.punkty_w_rozdaniu[druzyny[0].nazwa]
        punkty_b = rozdanie.punkty_w_rozdaniu[druzyny[1].nazwa]
        print(f"  Punkty z kart (z bonusem): {druzyny[0].nazwa} {punkty_a} - {punkty_b} {druzyny[1].nazwa}")
    
    print(f"  Rozdanie wygrywa: {druzyna_wygrana.nazwa}")
    print(f"  Przyznane punkty meczowe: {punkty_dodane} (mnożnik: x{mnoznik})")
    print(f"  OGÓLNY WYNIK MECZU: {druzyny[0].nazwa} {druzyny[0].punkty_meczu} - {druzyny[1].nazwa} {druzyny[1].punkty_meczu}")
    print("="*25 + "\n")

if __name__ == "__main__":
    # >>> POCZĄTEK ZMIANY: Zwiększenie liczby partii <<<
    LICZBA_PARTII = 15
    # >>> KONIEC ZMIANY <<<
    NAZWA_PLIKU_LOGU = "log_finalny_poprawiony.txt"
    
    oryginalny_stdout = sys.stdout 
    with open(NAZWA_PLIKU_LOGU, 'w', encoding='utf-8') as f:
        sys.stdout = f
        
        for i in range(1, LICZBA_PARTII + 1):
            print("\n" + "#"*40 + f"\n### ROZPOCZYNAMY PARTIĘ #{i} ###\n" + "#"*40 + "\n")
            
            druzyna_a = Druzyna(nazwa="My")
            druzyna_b = Druzyna(nazwa="Oni")
            druzyna_a.przeciwnicy = druzyna_b
            druzyna_b.przeciwnicy = druzyna_a
            
            numer_rozdania_w_partii = 1
            while druzyna_a.punkty_meczu < 66 and druzyna_b.punkty_meczu < 66:
                uruchom_symulacje_rozdania(numer_rozdania_w_partii, [druzyna_a, druzyna_b])
                numer_rozdania_w_partii += 1

            print("\n" + "#"*30 + "\n!!! KONIEC GRY !!!")
            zwyciezca = druzyna_a if druzyna_a.punkty_meczu >= 66 else druzyna_b
            print(f"Partię wygrywa drużyna: {zwyciezca.nazwa}")
            print(f"OSTATECZNY WYNIK: {druzyna_a.nazwa} {druzyna_a.punkty_meczu} - {druzyna_b.nazwa} {druzyna_b.punkty_meczu}")
            print("#"*30)

    sys.stdout = oryginalny_stdout
    print(f"✅ Symulacja zakończona. Pełny, poprawiony log z {LICZBA_PARTII} partii zapisano do pliku: {NAZWA_PLIKU_LOGU}")