# ZAKTUALIZOWANY PLIK: test_boty.py
import time
import pytest
import copy
from silnik_gry import Gracz, Druzyna, Rozdanie, Karta, Ranga, Kolor, FazaGry, RozdanieTrzyOsoby, Kontrakt
from boty import MonteCarloTreeSearchNode, MCTS_Bot

# --- Funkcje pomocnicze do tworzenia kart ---
def K(ranga_str, kolor_str):
    """Tworzy obiekt Karta z krótkich stringów, np. K('As', 'Wino')"""
    ranga_map = {
        '9': Ranga.DZIEWIATKA, 'W': Ranga.WALET, 'D': Ranga.DAMA,
        'K': Ranga.KROL, '10': Ranga.DZIESIATKA, 'A': Ranga.AS
    }
    kolor_map = {
        'C': Kolor.CZERWIEN, 'Dzw': Kolor.DZWONEK,
        'Z': Kolor.ZOLADZ, 'W': Kolor.WINO
    }
    return Karta(ranga=ranga_map[ranga_str], kolor=kolor_map[kolor_str])

# --- Funkcje pomocnicze do tworzenia stanu gry ---

def stworz_testowe_rozdanie_4p():
    """
    Tworzy gotowe do gry rozdanie 4-osobowe.
    Rozdaje 3 KARTY i ustawia fazę na DEKLARACJA_1.
    """
    gracz_a = Gracz(nazwa="Gracz_A")
    gracz_b = Gracz(nazwa="Gracz_B")
    gracz_c = Gracz(nazwa="Gracz_C")
    gracz_d = Gracz(nazwa="Gracz_D")
    
    druzyna_1 = Druzyna(nazwa="My")
    druzyna_2 = Druzyna(nazwa="Oni")
    
    druzyna_1.dodaj_gracza(gracz_a)
    druzyna_1.dodaj_gracza(gracz_c)
    druzyna_2.dodaj_gracza(gracz_b)
    druzyna_2.dodaj_gracza(gracz_d)
    druzyna_1.przeciwnicy = druzyna_2
    druzyna_2.przeciwnicy = druzyna_1
    
    gracze = [gracz_a, gracz_b, gracz_c, gracz_d]
    druzyny = [druzyna_1, druzyna_2]
    
    rozdanie = Rozdanie(gracze, druzyny, rozdajacy_idx=3) # D rozdaje
    
    # Ustawiamy DOKŁADNIE 24 karty, aby silnik poprawnie je rozdał
    rozdanie.talia.karty = [
        K('A','W'), K('10','W'), K('K','W'), K('D','W'), K('W','W'), K('9','W'), # Dostanie Gracz D (do ręki)
        K('A','Z'), K('10','Z'), K('K','Z'), K('D','Z'), K('W','Z'), K('9','Z'), # Dostanie Gracz C (do ręki)
        K('A','Dzw'), K('10','Dzw'), K('K','Dzw'), K('D','Dzw'), K('W','Dzw'), K('9','Dzw'), # Dostanie Gracz B (do ręki)
        K('A','C'), K('10','C'), K('K','C'), K('D','C'), K('W','C'), K('9','C'), # Dostanie Gracz A (do ręki)
    ]
    
    # Silnik gry sam zarządza rozdawaniem (najpierw 3, potem 3)
    # My tylko inicjujemy rozdanie:
    rozdanie.rozpocznij_nowe_rozdanie() # To rozdaje 3 karty i ustawia FAZA_DEKLARACJA_1
    
    # Zwracamy stan gotowy do licytacji
    return rozdanie
# --- Testy ---

def test_pobierz_akcje_rozgrywka_musi_dolaczyc_do_koloru():
    """Testuje filtrowanie akcji w fazie rozgrywki."""
    # 1. Setup
    rozdanie = stworz_testowe_rozdanie_4p() # Używamy nowej funkcji pomocniczej
    
    # 2. Mocking stanu
    rozdanie.faza = FazaGry.ROZGRYWKA
    rozdanie.atut = Kolor.CZERWIEN
    
    # Ręka gracza A (z funkcji pomocniczej): [A, 10, K, D, W, 9 Czerwien]
    # Ustawiamy stół: Gracz D (indeks 3) zaczął Wino
    rozdanie.aktualna_lewa = [(rozdanie.gracze[3], K('A', 'W'))] 
    rozdanie.kolej_gracza_idx = 0 # Tura gracza A
    
    # Dajemy graczowi A rękę z różnymi kartami, w tym Wino
    rozdanie.gracze[0].reka = [
        K('K', 'C'),  # Atut
        K('D', 'Z'),  # Inny kolor
        K('10', 'W'), # Do koloru (legalna)
        K('9', 'W')   # Do koloru (legalna)
    ]
    
    # 3. Logika
    wezel = MonteCarloTreeSearchNode(
        stan_gry=rozdanie, 
        gracz_do_optymalizacji="Gracz_A" # Nazwa drużyny zostanie wyliczona na "My"
    )
    
    mozliwe_akcje = wezel._pobierz_mozliwe_akcje()
    
    # 4. Asercje
    assert len(mozliwe_akcje) == 2
    karty_w_akcjach = [a['karta_obj'] for a in mozliwe_akcje]
    assert K('10', 'W') in karty_w_akcjach
    assert K('9', 'W') in karty_w_akcjach
    assert K('K', 'C') not in karty_w_akcjach


def test_expand_tworzy_nowe_dziecko_i_zmienia_stan():
    """Testuje, czy expand() poprawnie tworzy kopię stanu."""
    # 1. Setup
    rozdanie = stworz_testowe_rozdanie_4p()
    gracz_a = rozdanie.gracze[0]
    
    # 2. Mocking
    rozdanie.faza = FazaGry.ROZGRYWKA
    rozdanie.atut = Kolor.CZERWIEN
    rozdanie.kolej_gracza_idx = 0 # Tura gracza A
    gracz_a.reka = [K('A', 'W'), K('K', 'Z')]
    
    # 3. Logika
    wezel_rodzic = MonteCarloTreeSearchNode(
        stan_gry=rozdanie, 
        gracz_do_optymalizacji=gracz_a.nazwa
    )
    
    # Zapisz stan oryginalny do porównania
    oryginalna_reka_gracza_a = copy.copy(wezel_rodzic.stan_gry.gracze[0].reka)
    
    assert len(wezel_rodzic._nieprzetestowane_akcje) == 2
    assert len(wezel_rodzic.dzieci) == 0
    
    nowe_dziecko = wezel_rodzic.expand()
    
    # 3. Asercje
    assert nowe_dziecko is not None
    assert nowe_dziecko.parent == wezel_rodzic
    assert len(wezel_rodzic._nieprzetestowane_akcje) == 1
    assert len(wezel_rodzic.dzieci) == 1
    
    akcja_dziecka = nowe_dziecko.akcja
    stan_dziecka = nowe_dziecko.stan_gry
    assert stan_dziecka is not wezel_rodzic.stan_gry 
    
    # Sprawdź, czy karta jest na stole, a tura przeszła
    assert len(stan_dziecka.aktualna_lewa) == 1
    gracz_na_stole = stan_dziecka.aktualna_lewa[0][0]
    karta_na_stole = stan_dziecka.aktualna_lewa[0][1]
    
    assert gracz_na_stole.nazwa == gracz_a.nazwa # Porównaj nazwy, nie obiekty
    assert karta_na_stole == akcja_dziecka['karta_obj']
    assert stan_dziecka.kolej_gracza_idx == 1 # Tura przeszła na gracza B
    
    # Kluczowy test: sprawdź, czy stan rodzica nie został zmieniony
    assert len(wezel_rodzic.stan_gry.aktualna_lewa) == 0
    assert wezel_rodzic.stan_gry.kolej_gracza_idx == 0
    assert wezel_rodzic.stan_gry.gracze[0].reka == oryginalna_reka_gracza_a


# --- NOWY TEST ---
def test_symuluj_rozgrywke_konczy_gre_i_nie_zmienia_oryginalu():
    """
    Testuje, czy symulacja (rollout) dochodzi do końca
    i czy nie modyfikuje stanu węzła, z którego została wywołana.
    Test ten POPRAWNIE przechodzi przez fazy licytacji.
    """
    # 1. Setup: Stwórz rozdanie gotowe do licytacji (3 karty, faza DEKLARACJA_1)
    rozdanie = stworz_testowe_rozdanie_4p()
    gracze = rozdanie.gracze # Skrót dla łatwiejszego dostępu

    # 2. Symuluj POPRAWNĄ sekwencję licytacji, aby dojść do rozgrywki
    
    # KROK A: DEKLARACJA_1 (Tura: Gracz A, idx 0)
    assert rozdanie.faza == FazaGry.DEKLARACJA_1
    rozdanie.wykonaj_akcje(gracze[0], {
        'typ': 'deklaracja', 
        'kontrakt': Kontrakt.NORMALNA, 
        'atut': Kolor.CZERWIEN
    })
    
    # KROK B: LUFA (Tura: Gracz B, idx 1)
    assert rozdanie.faza == FazaGry.LUFA
    rozdanie.wykonaj_akcje(gracze[1], {'typ': 'pas_lufa'})
    
    # KROK C: LUFA (Tura: Gracz D, idx 3)
    assert rozdanie.faza == FazaGry.LUFA
    rozdanie.wykonaj_akcje(gracze[3], {'typ': 'pas_lufa'})
    # (Silnik automatycznie wywołuje _zakoncz_faze_lufy, rozdaje 3 karty)
    
    # KROK D: FAZA_PYTANIA_START (Tura: Gracz A, idx 0)
    assert rozdanie.faza == FazaGry.FAZA_PYTANIA_START
    rozdanie.wykonaj_akcje(gracze[0], {'typ': 'pytanie'})

    # KROK E: LICYTACJA (Tura: Gracz B, idx 1)
    assert rozdanie.faza == FazaGry.LICYTACJA
    rozdanie.wykonaj_akcje(gracze[1], {'typ': 'pas'})
    
    # KROK F: LICYTACJA (Tura: Gracz D, idx 3)
    assert rozdanie.faza == FazaGry.LICYTACJA
    rozdanie.wykonaj_akcje(gracze[3], {'typ': 'pas'})
    
    # KROK G: LICYTACJA (Tura: Gracz C, idx 2)
    assert rozdanie.faza == FazaGry.LICYTACJA
    rozdanie.wykonaj_akcje(gracze[2], {'typ': 'pas'})
    # (Silnik automatycznie wywołuje _rozstrzygnij_licytacje_2 -> wszyscy spasowali)

    # KROK H: FAZA_DECYZJI_PO_PASACH (Tura: Gracz A, idx 0)
    assert rozdanie.faza == FazaGry.FAZA_DECYZJI_PO_PASACH
    rozdanie.wykonaj_akcje(gracze[0], {'typ': 'graj_normalnie'})

    # KROK I: ROZGRYWKA (Tura: Gracz A, idx 0)
    # STAN GRY JEST TERAZ POPRAWNY i gotowy do rozgrywki
    assert rozdanie.faza == FazaGry.ROZGRYWKA
    assert len(rozdanie.gracze[0].reka) == 6 # Sprawdź, czy karty zostały dobrane
    assert rozdanie.kolej_gracza_idx == 0 # Tura gracza A
    
    # 3. Logika testu
    wezel_rodzic = MonteCarloTreeSearchNode(
        stan_gry=rozdanie, 
        gracz_do_optymalizacji="Gracz_A" # Optymalizujemy dla drużyny "My"
    )
    
    # Zapisz stan PRZED symulacją (już po licytacji)
    oryginalny_stan_przed_symulacja_json = str(rozdanie.__dict__)
    
    wynik = wezel_rodzic.symuluj_rozgrywke()
    
    # 4. Asercje
    
    # Wynik musi być 1.0 (wygrana "My") lub -1.0 (przegrana "My")
    assert wynik in [1.0, -1.0], f"Otrzymano nieoczekiwany wynik: {wynik}"
    
    # Kluczowy test: Sprawdź, czy stan oryginalny się nie zmienił
    stan_po_symulacji_json = str(wezel_rodzic.stan_gry.__dict__)
    assert stan_po_symulacji_json == oryginalny_stan_przed_symulacja_json, "Stan węzła został zmodyfikowany przez symulację!"
    
    # Dodatkowe sprawdzenie
    assert wezel_rodzic.stan_gry.rozdanie_zakonczone == False
    assert len(wezel_rodzic.stan_gry.gracze[0].reka) == 6 # Ręka nienaruszona

def test_propaguj_wynik_wstecz_aktualizuje_statystyki():
    """
    Testuje, czy propagacja poprawnie aktualizuje węzły w górę drzewa.
    """
    # 1. Setup: Stwórz łańcuch węzłów: Dziadek -> Rodzic -> Dziecko
    rozdanie = stworz_testowe_rozdanie_4p()
    
    dziadek = MonteCarloTreeSearchNode(rozdanie, gracz_do_optymalizacji="Gracz_A")
    rodzic = MonteCarloTreeSearchNode(rozdanie, parent=dziadek, akcja={'typ': 'test1'})
    dziecko = MonteCarloTreeSearchNode(rozdanie, parent=rodzic, akcja={'typ': 'test2'})
    
    # Sprawdzenia początkowe
    assert dziadek._ilosc_wizyt == 0
    assert dziadek._wyniki_wygranych == 0.0
    assert rodzic._ilosc_wizyt == 0
    assert rodzic._wyniki_wygranych == 0.0
    
    # 2. Logika
    # Symulujemy wygraną (1.0) i przegraną (-1.0) z poziomu 'dziecko'
    dziecko.propaguj_wynik_wstecz(1.0)
    dziecko.propaguj_wynik_wstecz(-1.0)
    
    # 3. Asercje
    
    # Węzeł 'dziecko'
    assert dziecko._ilosc_wizyt == 2
    assert dziecko._wyniki_wygranych == 0.0 # (1.0 + -1.0)
    
    # Węzeł 'rodzic'
    assert rodzic._ilosc_wizyt == 2
    assert rodzic._wyniki_wygranych == 0.0
    
    # Węzeł 'dziadek'
    assert dziadek._ilosc_wizyt == 2
    assert dziadek._wyniki_wygranych == 0.0
    
    # Symulujemy kolejną wygraną
    dziecko.propaguj_wynik_wstecz(1.0)

    # Sprawdź ponownie
    assert dziecko._ilosc_wizyt == 3
    assert dziecko._wyniki_wygranych == 1.0 # (0.0 + 1.0)
    assert rodzic._ilosc_wizyt == 3
    assert rodzic._wyniki_wygranych == 1.0
    assert dziadek._ilosc_wizyt == 3
    assert dziadek._wyniki_wygranych == 1.0

def test_wybierz_obiecujace_dziecko_uct():
    """
    Testuje, czy formuła UCT (selekcja) poprawnie wybiera:
    1. Niezbadane dziecko (jeśli istnieje).
    2. Dziecko z najlepszym balansem eksploracji/eksploatacji.
    """
    # 1. Setup
    rozdanie = stworz_testowe_rozdanie_4p()
    # Ustawiamy grę, aby były jakieś akcje
    rozdanie.faza = FazaGry.ROZGRYWKA
    rozdanie.gracze[0].reka = [K('A', 'W'), K('K', 'Z')]
    rozdanie.kolej_gracza_idx = 0
    
    rodzic = MonteCarloTreeSearchNode(rozdanie, gracz_do_optymalizacji="Gracz_A")
    
    # 2. Expand: Tworzymy dwoje dzieci
    dziecko_A_Wino = rodzic.expand() # Akcja: As Wino
    dziecko_K_Zoladz = rodzic.expand() # Akcja: Król Żołądź
    
    assert len(rodzic.dzieci) == 2
    assert rodzic.czy_pelna_ekspansja() == True
    
    # 3. Logika i Asercje
    
    # Scenariusz 1: Obiegi dzieci nie były odwiedzone (wizyty = 0)
    # Metoda powinna zwrócić jedno z nich (pierwsze, które zwróci UCT = inf)
    # Musimy ręcznie ustawić wizytę rodzica na > 0
    rodzic._ilosc_wizyt = 2 
    assert dziecko_A_Wino._ilosc_wizyt == 0
    assert dziecko_K_Zoladz._ilosc_wizyt == 0
    
    wybrane_dziecko = rodzic.wybierz_obiecujace_dziecko()
    assert wybrane_dziecko in [dziecko_A_Wino, dziecko_K_Zoladz]
    
    # Scenariusz 2: Dziecko A było słabe, Dziecko B nieodwiedzone
    # Musimy ręcznie zasymulować statystyki
    dziecko_A_Wino._ilosc_wizyt = 100
    dziecko_A_Wino._wyniki_wygranych = -100.0 # 100% przegranych
    
    dziecko_K_Zoladz._ilosc_wizyt = 0 # Nieodwiedzone
    
    rodzic._ilosc_wizyt = 100
    
    # UCT dla A = (-100/100) + bonus_eksploracji (niski)
    # UCT dla B = inf
    wybrane_dziecko = rodzic.wybierz_obiecujace_dziecko()
    assert wybrane_dziecko == dziecko_K_Zoladz # Musi wybrać nieodwiedzone
    
    # Scenariusz 3: Dziecko A jest "OK", Dziecko B jest "super"
    dziecko_A_Wino._ilosc_wizyt = 50
    dziecko_A_Wino._wyniki_wygranych = 25.0 # Średnia 0.5
    
    dziecko_K_Zoladz._ilosc_wizyt = 50
    dziecko_K_Zoladz._wyniki_wygranych = 45.0 # Średnia 0.9 (lepsza eksploatacja)
    
    rodzic._ilosc_wizyt = 100
    
    # Obie mają tyle samo wizyt, więc bonus eksploracji jest ten sam.
    # Wygrać musi dziecko z lepszą średnią wygranych (eksploatacja).
    wybrane_dziecko = rodzic.wybierz_obiecujace_dziecko()
    assert wybrane_dziecko == dziecko_K_Zoladz

def test_bot_mcts_znajdz_najlepszy_ruch():
    """
    Test integracyjny: Sprawdza, czy MCTS_Bot poprawnie uruchamia pętlę
    i zwraca legalną akcję.
    """
    # 1. Setup: Stwórz w pełni grywalny stan
    rozdanie = stworz_testowe_rozdanie_4p()
    gracze = rozdanie.gracze
    
    # Przejdź przez licytację do fazy rozgrywki (jak w poprzednim teście)
    rozdanie.wykonaj_akcje(gracze[0], {'typ': 'deklaracja', 'kontrakt': Kontrakt.NORMALNA, 'atut': Kolor.CZERWIEN})
    rozdanie.wykonaj_akcje(gracze[1], {'typ': 'pas_lufa'})
    rozdanie.wykonaj_akcje(gracze[3], {'typ': 'pas_lufa'})
    rozdanie.wykonaj_akcje(gracze[0], {'typ': 'pytanie'})
    rozdanie.wykonaj_akcje(gracze[1], {'typ': 'pas'})
    rozdanie.wykonaj_akcje(gracze[3], {'typ': 'pas'})
    rozdanie.wykonaj_akcje(gracze[2], {'typ': 'pas'})
    rozdanie.wykonaj_akcje(gracze[0], {'typ': 'graj_normalnie'})
    
    # Stan jest teraz w fazie ROZGRYWKA, tura Gracza A
    assert rozdanie.faza == FazaGry.ROZGRYWKA
    assert rozdanie.kolej_gracza_idx == 0
    
    # 2. Logika
    bot = MCTS_Bot()
    
    # Dajemy botowi bardzo mało czasu (0.1s), żeby test był szybki
    start_testu = time.time()
    najlepsza_akcja = bot.znajdz_najlepszy_ruch(
        poczatkowy_stan_gry=rozdanie,
        nazwa_gracza_bota="Gracz_A",
        limit_czasu_s=0.1
    )
    czas_testu = time.time() - start_testu
    
    # 3. Asercje
    assert czas_testu >= 0.1 # Sprawdź, czy bot "myślał" przez określony czas
    
    # Sprawdź, czy zwrócona akcja jest legalna
    assert najlepsza_akcja is not None
    assert najlepsza_akcja['typ'] == 'zagraj_karte'
    
    # Sprawdź, czy zwrócona karta jest jedną z kart, które Gracz A ma na ręce
    # (W naszym teście Gracz A ma 6 kart Czerwonych)
    karta_z_akcji = najlepsza_akcja['karta_obj']
    reka_gracza_a = rozdanie.gracze[0].reka
    
    assert karta_z_akcji in reka_gracza_a
    assert karta_z_akcji.kolor == Kolor.CZERWIEN
    assert len(reka_gracza_a) == 6