# boty.py

import random
import math
import copy
import time
import traceback
from enum import Enum
from typing import Union, Optional, Any, Tuple

# Import silnika gry
import silnik_gry

# ==========================================================================
# SEKCJA 1: IMPORTY I STAŁE
# ==========================================================================

# Stałe używane do normalizacji wyników w MCTS
MAX_PUNKTY_ROZDANIA = 66.0 # Maksymalna liczba punktów możliwa do zdobycia w kartach w rozdaniu
MAX_NORMAL_GAME_POINTS = 3.0 # Maksymalna liczba punktów meczowych do zdobycia w kontrakcie NORMALNA

# ==========================================================================
# SEKCJA 2: BOT TESTOWY (PROSTY)
# ==========================================================================

def wybierz_akcje_dla_bota_testowego(bot: silnik_gry.Gracz, rozdanie: Any) -> tuple[str, Any]:
    """
    Wybiera akcję dla prostego bota testowego.
    W fazie rozgrywki wybiera losową legalną kartę.
    W fazach licytacyjnych próbuje wykonać predefiniowane akcje (np. pas),
    a jeśli to niemożliwe, wybiera losową legalną akcję licytacyjną.
    Zwraca krotkę: (typ_akcji_dla_serwera, dane_akcji_dla_silnika).
    """

    # --- Logika Rozgrywki ---
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        # Znajdź wszystkie karty, które można legalnie zagrać
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        if grywalne_karty:
            # Wybierz i zwróć losową z nich
            return 'karta', random.choice(grywalne_karty)

    # --- Logika Licytacji ---
    else:
        # Pobierz wszystkie możliwe akcje licytacyjne dla bota
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        if not mozliwe_akcje:
            # Jeśli nie ma akcji, zwróć 'brak'
            return 'brak', None

        # --- Predefiniowane akcje testowe (można je usunąć/zmienić) ---
        # W fazie LICYTACJA, jeśli można, spasuj
        if rozdanie.faza == silnik_gry.FazaGry.LICYTACJA:
            akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
            if akcja_pas: return 'licytacja', akcja_pas
        # W fazie LUFA, jeśli można, spasuj
        if rozdanie.faza == silnik_gry.FazaGry.LUFA:
            akcja_pas_lufa = next((a for a in mozliwe_akcje if a['typ'] == 'pas_lufa'), None)
            if akcja_pas_lufa: return 'licytacja', akcja_pas_lufa
        # Po pasach przeciwników, jeśli można, graj normalnie
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_DECYZJI_PO_PASACH:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'graj_normalnie'), None)
            if akcja_normalna: return 'licytacja', akcja_normalna
        # Po deklaracji NORMALNEJ, jeśli można, zapytaj
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_PYTANIA_START:
            akcja_pytanie = next((a for a in mozliwe_akcje if a['typ'] == 'pytanie'), None)
            if akcja_pytanie: return 'licytacja', akcja_pytanie
        # Przy pierwszej deklaracji, jeśli można, zadeklaruj NORMALNĄ z losowym atutem
        if rozdanie.faza == silnik_gry.FazaGry.DEKLARACJA_1:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'deklaracja' and a['kontrakt'] == silnik_gry.Kontrakt.NORMALNA), None)
            if akcja_normalna:
                kolory = list(silnik_gry.Kolor)
                # Skopiuj słownik akcji, aby nie modyfikować oryginału z silnika
                akcja_do_wykonania = akcja_normalna.copy()
                akcja_do_wykonania['atut'] = random.choice(kolory) # Ustaw losowy atut
                return 'licytacja', akcja_do_wykonania

        # --- Fallback: Losowa akcja ---
        # Jeśli żadna z predefiniowanych akcji nie pasowała, wybierz losową
        wybrana_akcja = random.choice(mozliwe_akcje)
        return 'licytacja', wybrana_akcja

    # Jeśli nie znaleziono żadnej akcji (nie powinno się zdarzyć)
    return 'brak', None

# ==========================================================================
# SEKCJA 3: WĘZEŁ DRZEWA MONTE CARLO (MCTS)
# ==========================================================================

class MonteCarloTreeSearchNode:
    """
    Reprezentuje węzeł w drzewie przeszukiwania Monte Carlo Tree Search (MCTS).
    Przechowuje stan gry, statystyki odwiedzin/wyników oraz możliwe akcje.
    """

    def __init__(self, stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                 parent: Optional['MonteCarloTreeSearchNode'] = None,
                 akcja: Optional[dict] = None,
                 gracz_do_optymalizacji: Optional[str] = None):
        """
        Inicjalizuje węzeł MCTS.

        Args:
            stan_gry: Obiekt Rozdanie lub RozdanieTrzyOsoby reprezentujący stan gry w tym węźle.
            parent: Węzeł nadrzędny (None dla korzenia).
            akcja: Akcja, która doprowadziła do tego stanu z węzła nadrzędnego.
            gracz_do_optymalizacji: Nazwa gracza, z perspektywy którego optymalizujemy (wymagane dla korzenia).
        """
        self.stan_gry = stan_gry              # Stan gry w tym węźle
        self.parent = parent                  # Węzeł nadrzędny
        self.akcja = akcja                    # Akcja prowadząca do tego węzła
        self.faza_wezla = stan_gry.faza       # Faza gry w tym węźle (dla strategii nagród)
        self.kontrakt_wezla = stan_gry.kontrakt # Kontrakt w tym węźle (jeśli ustalony)

        # --- Ustalanie perspektywy optymalizacji (kto jest "MY") ---
        if gracz_do_optymalizacji: # Jeśli podano jawnie (dla korzenia)
            self._gracz_startowy_nazwa = gracz_do_optymalizacji
            if isinstance(stan_gry, silnik_gry.Rozdanie): # Gra 4-osobowa
                gracz_obj = next((g for g in stan_gry.gracze if g and g.nazwa == gracz_do_optymalizacji), None)
                if not gracz_obj or not gracz_obj.druzyna:
                     raise ValueError(f"MCTS Node Init: Nie można znaleźć gracza {gracz_do_optymalizacji} lub jego drużyny.")
                # Perspektywą jest nazwa drużyny
                self.perspektywa_optymalizacji = gracz_obj.druzyna.nazwa
            else: # Gra 3-osobowa
                # Perspektywą jest nazwa gracza
                self.perspektywa_optymalizacji = gracz_do_optymalizacji
        elif parent: # Jeśli nie podano, dziedzicz z rodzica
            self._gracz_startowy_nazwa = parent._gracz_startowy_nazwa
            self.perspektywa_optymalizacji = parent.perspektywa_optymalizacji
        else: # Błąd - korzeń musi mieć zdefiniowaną perspektywę
            raise ValueError("Korzeń drzewa MCTS musi mieć zdefiniowanego 'gracz_do_optymalizacji'")

        # --- Statystyki MCTS ---
        self._ilosc_wizyt = 0       # Liczba odwiedzin tego węzła
        self._wyniki_wygranych = 0.0 # Suma nagród (znormalizowanych) uzyskanych z symulacji przechodzących przez ten węzeł

        # --- Informacje o turze ---
        # Określa, czy w tym węźle ruch należy do gracza/drużyny optymalizowanej
        self.jest_tura_optymalizujacego = self._czy_tura_optymalizujacego()

        # --- Zarządzanie dziećmi ---
        self.dzieci: list['MonteCarloTreeSearchNode'] = [] # Lista węzłów-dzieci
        # Lista akcji możliwych do wykonania z tego węzła, które nie zostały jeszcze rozwinięte
        self._nieprzetestowane_akcje = self._pobierz_mozliwe_akcje()

    def _czy_tura_optymalizujacego(self) -> bool:
        """Sprawdza, czyja tura jest w stanie gry tego węzła."""
        if self.stan_gry.kolej_gracza_idx is None:
            return False # Jeśli gra zakończona, tura nie jest niczyja
        # Sprawdź poprawność indeksu
        if not (0 <= self.stan_gry.kolej_gracza_idx < len(self.stan_gry.gracze)):
            print(f"OSTRZEŻENIE MCTS: Nieprawidłowy kolej_gracza_idx ({self.stan_gry.kolej_gracza_idx}) w _czy_tura_optymalizujacego.")
            return True # Awaryjnie załóż, że to nasza tura

        gracz_w_turze = self.stan_gry.gracze[self.stan_gry.kolej_gracza_idx]
        if not gracz_w_turze: return False # Błąd - brak gracza

        if isinstance(self.stan_gry, silnik_gry.Rozdanie): # Gra 4-osobowa
            # Sprawdź, czy drużyna gracza w turze zgadza się z perspektywą
            return gracz_w_turze.druzyna is not None and gracz_w_turze.druzyna.nazwa == self.perspektywa_optymalizacji
        else: # Gra 3-osobowa
            # Sprawdź, czy nazwa gracza w turze zgadza się z perspektywą
            return gracz_w_turze.nazwa == self.perspektywa_optymalizacji

    def _pobierz_mozliwe_akcje(self) -> list[dict]:
        """Pobiera wszystkie legalne akcje z aktualnego stanu gry."""
        # Jeśli rozdanie zakończone lub nikt nie ma tury, brak akcji
        if self.stan_gry.rozdanie_zakonczone or self.stan_gry.kolej_gracza_idx is None:
            return []
        # Sprawdź poprawność indeksu
        if not (0 <= self.stan_gry.kolej_gracza_idx < len(self.stan_gry.gracze)):
             print(f"BŁĄD MCTS: Nieprawidłowy indeks gracza {self.stan_gry.kolej_gracza_idx} w _pobierz_mozliwe_akcje.")
             return []

        gracz_w_turze = self.stan_gry.gracze[self.stan_gry.kolej_gracza_idx]
        if not gracz_w_turze:
             print(f"BŁĄD MCTS: Brak obiektu gracza dla indeksu {self.stan_gry.kolej_gracza_idx}.")
             return []

        # W fazie rozgrywki generuj akcje zagrania karty
        if self.stan_gry.faza == silnik_gry.FazaGry.ROZGRYWKA:
            akcje = []
            for karta in gracz_w_turze.reka:
                # Użyj walidatora z silnika gry
                if self.stan_gry._waliduj_ruch(gracz_w_turze, karta):
                    # Przechowuj obiekt karty dla łatwiejszego wykonania
                    akcje.append({'typ': 'zagraj_karte', 'karta_obj': karta})
            return akcje
        # W innych fazach użyj metody z silnika gry
        else:
            return self.stan_gry.get_mozliwe_akcje(gracz_w_turze)

    def _stworz_nastepny_stan(self, stan_wejsciowy, akcja: dict):
        """
        Tworzy GŁĘBOKĄ KOPIĘ stanu gry i stosuje na niej podaną akcję.
        Obsługuje również automatyczne zmiany stanu (np. finalizację lewy).
        """
        stan_kopia = copy.deepcopy(stan_wejsciowy)

        # Sprawdź, czy stan nie jest już terminalny lub czy jest tura
        if stan_kopia.kolej_gracza_idx is None:
             return stan_kopia # Zwróć kopię bez zmian
        # Sprawdź poprawność indeksu
        if not (0 <= stan_kopia.kolej_gracza_idx < len(stan_kopia.gracze)):
             print(f"BŁĄD KRYTYCZNY (stworz_nastepny_stan): Nieprawidłowy indeks gracza {stan_kopia.kolej_gracza_idx}")
             return stan_kopia

        gracz_w_turze_kopia = stan_kopia.gracze[stan_kopia.kolej_gracza_idx]
        if not gracz_w_turze_kopia:
             print(f"BŁĄD KRYTYCZNY (stworz_nastepny_stan): Nie znaleziono gracza o indeksie {stan_kopia.kolej_gracza_idx}")
             return stan_kopia

        typ_akcji = akcja['typ']
        try:
            # Wykonaj akcję w silniku gry
            if typ_akcji == 'zagraj_karte':
                karta_obj = akcja['karta_obj']
                # Znajdź referencję do tej samej karty w ręce gracza w kopii stanu
                # (ważne, bo deepcopy tworzy nowe obiekty kart)
                karta_w_kopii = next((k for k in gracz_w_turze_kopia.reka if k == karta_obj), None)
                if karta_w_kopii:
                    stan_kopia.zagraj_karte(gracz_w_turze_kopia, karta_w_kopii)
                else:
                    # To nie powinno się zdarzyć, jeśli akcja pochodzi z _pobierz_mozliwe_akcje
                    print(f"BŁĄD KRYTYCZNY SYMULACJI: Nie znaleziono karty {karta_obj} w ręce {gracz_w_turze_kopia.nazwa} (kopia)")
            else: # Akcja licytacyjna
                stan_kopia.wykonaj_akcje(gracz_w_turze_kopia, akcja)

            # Obsługa automatycznej finalizacji lewy
            if stan_kopia.lewa_do_zamkniecia:
                stan_kopia.finalizuj_lewe()
        except Exception as e:
             # Złap potencjalne błędy z silnika gry podczas symulacji
             print(f"BŁĄD podczas tworzenia następnego stanu (akcja: {akcja}): {e}")
             traceback.print_exc()
             # W razie błędu zwróć kopię stanu *przed* próbą wykonania akcji
             return copy.deepcopy(stan_wejsciowy)

        return stan_kopia

    def czy_wezel_terminalny(self) -> bool:
        """Sprawdza, czy stan gry w węźle jest końcowy (rozdanie zakończone)."""
        # Użycie `podsumowanie` jest pewniejsze niż flaga `rozdanie_zakonczone`
        return bool(self.stan_gry.podsumowanie)

    def czy_pelna_ekspansja(self) -> bool:
        """Sprawdza, czy wszystkie możliwe akcje z tego węzła zostały już rozwinięte w dzieci."""
        return len(self._nieprzetestowane_akcje) == 0

    def wybierz_obiecujace_dziecko(self, stala_eksploracji: float = 1.414) -> Optional['MonteCarloTreeSearchNode']:
        """
        Wybiera najlepsze dziecko na podstawie formuły UCT (Upper Confidence Bound 1 applied to Trees).
        Używa logiki Minimax: maksymalizuje wynik, gdy jest tura optymalizującego,
        minimalizuje (maksymalizuje wynik przeciwnika), gdy jest tura przeciwnika.
        """
        if not self.dzieci: return None # Brak dzieci do wyboru

        # Jeśli rodzic nie był odwiedzony (nie powinno się zdarzyć w standardowym MCTS), wybierz losowo
        if self._ilosc_wizyt == 0:
            return random.choice(self.dzieci)

        log_wizyt_rodzica = math.log(self._ilosc_wizyt) # Część formuły UCT, obliczana raz

        best_score = -float('inf') # Inicjalizacja najlepszego wyniku
        best_children = []         # Lista dzieci z najlepszym wynikiem (do obsługi remisów)

        for dziecko in self.dzieci:
            if dziecko._ilosc_wizyt == 0:
                # Nieodwiedzone dzieci mają priorytet (nieskończony wynik UCT)
                score = float('inf')
            else:
                # --- Formuła UCT ---
                # 1. Termin Eksploatacji: Średnia nagroda uzyskana z dziecka
                srednia_nagroda = dziecko._wyniki_wygranych / dziecko._ilosc_wizyt
                # 2. Termin Eksploracji: Bonus za rzadkie odwiedzanie
                bonus_eksploracji = stala_eksploracji * math.sqrt(
                    log_wizyt_rodzica / dziecko._ilosc_wizyt
                )

                # --- Logika Minimax ---
                if self.jest_tura_optymalizujacego: # Jeśli to nasza tura, maksymalizujemy UCT
                    score = srednia_nagroda + bonus_eksploracji
                else: # Jeśli to tura przeciwnika, chcemy wybrać ruch, który minimalizuje *naszą* nagrodę
                      # co jest równoważne maksymalizacji UCT liczonego dla *negacji* naszej nagrody.
                    score = (-srednia_nagroda) + bonus_eksploracji

            # Aktualizuj najlepszy wynik i listę najlepszych dzieci
            if score > best_score:
                best_score = score
                best_children = [dziecko]
            elif score == best_score:
                best_children.append(dziecko)

        # Wybierz losowo spośród dzieci z najwyższym wynikiem UCT
        return random.choice(best_children) if best_children else None

    def expand(self) -> Optional['MonteCarloTreeSearchNode']:
        """
        Rozwija jedno losowe, jeszcze nieprzetestowane działanie, tworząc nowy węzeł-dziecko.
        Zwraca nowo utworzone dziecko lub None, jeśli nie ma już akcji do rozwinięcia.
        """
        if not self._nieprzetestowane_akcje:
             return None # Wszystkie akcje już rozwinięte

        # Wybierz losową akcję z listy nieprzetestowanych
        akcja_do_ekspansji = self._nieprzetestowane_akcje.pop(random.randrange(len(self._nieprzetestowane_akcje)))
        # Stwórz nowy stan gry po wykonaniu tej akcji
        nowy_stan_gry = self._stworz_nastepny_stan(self.stan_gry, akcja_do_ekspansji)
        # Stwórz nowy węzeł-dziecko
        nowe_dziecko = MonteCarloTreeSearchNode(
            stan_gry=nowy_stan_gry,
            parent=self,
            akcja=akcja_do_ekspansji,
            # Perspektywa optymalizacji jest dziedziczona automatycznie z rodzica
        )
        self.dzieci.append(nowe_dziecko) # Dodaj dziecko do listy dzieci rodzica
        return nowe_dziecko

    def symuluj_rozgrywke(self) -> Tuple[float, float, float]:
        """
        Symuluje losową rozgrywkę (rollout) od aktualnego stanu węzła aż do końca rozdania.
        Zwraca krotkę trzech znormalizowanych wyników z perspektywy gracza optymalizującego:
        - wynik_zero_jeden: 1.0 za wygraną, -1.0 za przegraną.
        - wynik_skalowany_pkt: Punkty rozdania przeskalowane do [-1, 1].
        - wynik_skalowany_normalny: Punkty meczowe dla NORMALNEJ przeskalowane do [-1, 1],
                                     lub wynik_zero_jeden dla innych kontraktów.
        """
        # Stwórz głęboką kopię stanu, aby nie modyfikować stanu węzła
        stan_symulacji = copy.deepcopy(self.stan_gry)
        kontrakt_przed_symulacja = stan_symulacji.kontrakt # Zapamiętaj kontrakt na początku symulacji
        licznik_bezpieczenstwa = 0 # Zabezpieczenie przed nieskończoną pętlą

        # Pętla symulacji - trwa dopóki rozdanie się nie zakończy
        while not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
            licznik_bezpieczenstwa += 1
            if licznik_bezpieczenstwa > 150: # Limit iteracji
                print(f"BŁĄD SYMULACJI: Przekroczono limit pętli ({licznik_bezpieczenstwa}). Faza: {stan_symulacji.faza}")
                return (0.0, 0.0, 0.0) # Zwróć neutralny wynik w razie błędu

            # Obsługa automatycznej finalizacji lewy
            if stan_symulacji.lewa_do_zamkniecia:
                try:
                    stan_symulacji.finalizuj_lewe()
                except Exception as e_fin:
                     print(f"BŁĄD podczas finalizuj_lewe w symulacji: {e_fin}")
                     return (0.0, 0.0, 0.0)
                continue # Kontynuuj pętlę, aby sprawdzić, czy gra się zakończyła

            # Wykonanie ruchu gracza, jeśli jest jego tura
            if stan_symulacji.kolej_gracza_idx is not None:
                # Sprawdź poprawność indeksu
                if not (0 <= stan_symulacji.kolej_gracza_idx < len(stan_symulacji.gracze)):
                    print(f"BŁĄD SYMULACJI: Nieprawidłowy indeks gracza {stan_symulacji.kolej_gracza_idx}")
                    break
                gracz_w_turze_sym = stan_symulacji.gracze[stan_symulacji.kolej_gracza_idx]
                if not gracz_w_turze_sym:
                     print(f"BŁĄD SYMULACJI: Brak obiektu gracza dla indeksu {stan_symulacji.kolej_gracza_idx}")
                     break

                # Pobierz legalne akcje (jak w _pobierz_mozliwe_akcje)
                akcje = []
                try:
                    if stan_symulacji.faza == silnik_gry.FazaGry.ROZGRYWKA:
                        akcje = [{'typ': 'zagraj_karte', 'karta_obj': k} for k in gracz_w_turze_sym.reka if stan_symulacji._waliduj_ruch(gracz_w_turze_sym, k)]
                    else:
                        akcje = stan_symulacji.get_mozliwe_akcje(gracz_w_turze_sym)
                except Exception as e_akcje:
                     print(f"BŁĄD podczas pobierania akcji w symulacji dla {gracz_w_turze_sym.nazwa}: {e_akcje}")
                     break

                # Wykonaj losową akcję, jeśli są dostępne
                if akcje:
                    losowa_akcja = random.choice(akcje)
                    try:
                        # Wykonaj akcję w silniku gry (jak w _stworz_nastepny_stan)
                        if losowa_akcja['typ'] == 'zagraj_karte':
                            karta_obj = losowa_akcja['karta_obj']
                            karta_w_kopii = next((k for k in gracz_w_turze_sym.reka if k == karta_obj), None)
                            if karta_w_kopii: stan_symulacji.zagraj_karte(gracz_w_turze_sym, karta_w_kopii)
                        else:
                            stan_symulacji.wykonaj_akcje(gracz_w_turze_sym, losowa_akcja)
                    except Exception as e_wykonaj:
                        print(f"BŁĄD podczas wykonywania akcji {losowa_akcja} w symulacji: {e_wykonaj}")
                        break
                else: # Brak akcji
                    # Spróbuj sprawdzić koniec gry - może to normalny koniec (np. brak kart)
                    try: stan_symulacji._sprawdz_koniec_rozdania()
                    except Exception as e_sprawdz: print(f"BŁĄD podczas _sprawdz_koniec_rozdania przy braku akcji: {e_sprawdz}")
                    # Jeśli nadal nie zakończone, to coś jest nie tak
                    if not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
                         print(f"INFO SYMULACJI: Brak akcji mimo braku końca gry. Faza: {stan_symulacji.faza}")
                    break # Przerwij pętlę, jeśli nie ma akcji

            else: # kolej_gracza_idx is None, a gra nie zakończona
                 print("INFO SYMULACJI: Martwy stan (brak tury, brak finalizacji, brak końca).")
                 break

        # --- Po zakończeniu pętli symulacji ---
        # Upewnij się, że stan końcowy jest poprawnie rozliczony
        if not stan_symulacji.podsumowanie:
            try:
                stan_symulacji._sprawdz_koniec_rozdania() # Wywołaj rozliczenie, jeśli jeszcze nie nastąpiło
            except Exception as e_sprawdz_koniec:
                 print(f"BŁĄD podczas końcowego _sprawdz_koniec_rozdania: {e_sprawdz_koniec}")
                 return (0.0, 0.0, 0.0)

        podsumowanie = stan_symulacji.podsumowanie
        if not podsumowanie: # Jeśli nadal brak podsumowania, to krytyczny błąd
            print(f"BŁĄD KRYTYCZNY SYMULACJI: Brak podsumowania po zakończeniu pętli (licznik: {licznik_bezpieczenstwa}).")
            return (0.0, 0.0, 0.0)

        # --- Obliczanie wyników z perspektywy optymalizującego ---
        punkty_zdobyte = podsumowanie.get('przyznane_punkty', 0) # Całkowita pula punktów w rozdaniu
        wynik_skalowany_pkt = 0.0 # Punkty rozdania [-1, 1]
        wynik_zero_jeden = 0.0    # Wygrana/przegrana [-1, 1]
        wynik_skalowany_normalny = 0.0 # Punkty meczowe Normalnej [-1, 1] lub 0/1

        # Skalowanie punktów rozdania
        if MAX_PUNKTY_ROZDANIA > 0:
            wynik_skalowany_pkt = punkty_zdobyte / MAX_PUNKTY_ROZDANIA
            # Ogranicz do zakresu [-1, 1]
            wynik_skalowany_pkt = max(-1.0, min(1.0, wynik_skalowany_pkt))

        # Ustal, czy optymalizujący wygrał
        wygralismy = False
        if isinstance(stan_symulacji, silnik_gry.Rozdanie): # Gra 4-osobowa
            wygrana_druzyna = podsumowanie.get('wygrana_druzyna')
            if wygrana_druzyna == self.perspektywa_optymalizacji:
                wygralismy = True
            elif wygrana_druzyna is None: # Remis lub błąd
                 # Jeśli nie ma punktów, traktuj jako remis (0), inaczej jako błąd (0)
                 # wygralismy pozostaje False
                 if punkty_zdobyte != 0:
                      print(f"OSTRZEŻENIE SYMULACJI 4p: Brak 'wygrana_druzyna' w podsumowaniu z punktami={punkty_zdobyte}.")
        else: # Gra 3-osobowa
            # Sprawdź, czy nazwa optymalizującego gracza jest na liście zwycięzców
            wygrani_gracze_raw = podsumowanie.get('wygrani_gracze', [])
            # Upewnij się, że porównujemy nazwy (stringi)
            wygrani_gracze_nazwy = [g.nazwa if hasattr(g, 'nazwa') else g for g in wygrani_gracze_raw]
            if self.perspektywa_optymalizacji in wygrani_gracze_nazwy:
                wygralismy = True

        # Ustaw wynik zero-jeden
        wynik_zero_jeden = 1.0 if wygralismy else -1.0
        # Jeśli przegraliśmy, punkty rozdania też są ujemne
        if not wygralismy:
             wynik_skalowany_pkt = -abs(wynik_skalowany_pkt)

        # Oblicz wynik skalowany dla Normalnej (punkty meczowe)
        if kontrakt_przed_symulacja == silnik_gry.Kontrakt.NORMALNA:
             mnoznik_gry = podsumowanie.get('mnoznik_gry', 1) # Mnożnik gry (1, 2 lub 3)
             punkty_meczu_normal = mnoznik_gry # Punkty meczowe zdobyte w tym rozdaniu
             if MAX_NORMAL_GAME_POINTS > 0:
                 wynik_skalowany_normalny = punkty_meczu_normal / MAX_NORMAL_GAME_POINTS
                 # Ogranicz do zakresu [0, 1]
                 wynik_skalowany_normalny = max(0.0, min(1.0, wynik_skalowany_normalny))
             else: # Jeśli MAX_NORMAL_GAME_POINTS == 0, użyj 0/1
                 wynik_skalowany_normalny = 1.0
             # Jeśli przegraliśmy, wynik jest ujemny
             if not wygralismy: wynik_skalowany_normalny = -wynik_skalowany_normalny
        else: # Dla innych kontraktów użyj wyniku zero-jeden
            wynik_skalowany_normalny = wynik_zero_jeden

        return (wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)

    def propaguj_wynik_wstecz(self, wynik_zero_jeden: float, wynik_skalowany_pkt: float, wynik_skalowany_normalny: float):
        """
        Propaguje (przekazuje w górę drzewa) wynik symulacji, aktualizując statystyki
        odwiedzin i wyników w węzłach nadrzędnych. Wybiera odpowiedni wynik
        (znormalizowany) w zależności od fazy gry węzła.
        """
        wynik_do_uzycia = 0.0
        # Wybierz odpowiednią nagrodę w zależności od fazy gry *tego węzła*
        if self.faza_wezla == silnik_gry.FazaGry.ROZGRYWKA:
            # W rozgrywce użyj wyniku dla Normalnej lub 0/1
            if self.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA:
                wynik_do_uzycia = wynik_skalowany_normalny
            else:
                wynik_do_uzycia = wynik_zero_jeden
        else: # W fazach licytacyjnych użyj skalowanych punktów rozdania
            wynik_do_uzycia = wynik_skalowany_pkt

        # Zaktualizuj statystyki tego węzła
        self._ilosc_wizyt += 1
        self._wyniki_wygranych += wynik_do_uzycia

        # Przekaż wynik do rodzica (jeśli istnieje)
        if self.parent:
            self.parent.propaguj_wynik_wstecz(wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)

# ==========================================================================
# SEKCJA 4: GŁÓWNA KLASA BOTA MCTS
# ==========================================================================

class MCTS_Bot:
    """Implementuje algorytm Monte Carlo Tree Search do wybierania ruchów w grze."""

    def __init__(self, stala_eksploracji: float = 1.414):
        """
        Inicjalizuje bota MCTS.

        Args:
            stala_eksploracji: Stała C w formule UCT, kontrolująca balans między
                               eksploatacją a eksploracją. Domyślnie sqrt(2).
        """
        self.stala_eksploracji = stala_eksploracji

    def _wykonaj_pojedyncza_iteracje(self, korzen: MonteCarloTreeSearchNode):
        """
        Wykonuje jeden pełny cykl algorytmu MCTS:
        1. Selekcja: Przechodzi w dół drzewa, wybierając najlepsze dzieci wg UCT.
        2. Ekspansja: Jeśli dotrze do węzła nie w pełni rozwiniętego, tworzy nowe dziecko.
        3. Symulacja: Z nowego dziecka (lub z węzła terminalnego) przeprowadza losową rozgrywkę.
        4. Propagacja: Przekazuje wynik symulacji w górę drzewa do korzenia.
        """
        aktualny_wezel = korzen

        # --- 1. Selekcja ---
        # Dopóki węzeł nie jest końcowy i jest w pełni rozwinięty, wybieraj najlepsze dziecko
        while not aktualny_wezel.czy_wezel_terminalny() and aktualny_wezel.czy_pelna_ekspansja():
            nastepny_wezel = aktualny_wezel.wybierz_obiecujace_dziecko(self.stala_eksploracji)
            if nastepny_wezel is None: break # Powinno się zdarzyć tylko w węźle terminalnym
            aktualny_wezel = nastepny_wezel

        # --- 2. Ekspansja ---
        # Jeśli węzeł nie jest końcowy i nie jest w pełni rozwinięty, stwórz nowe dziecko
        if not aktualny_wezel.czy_wezel_terminalny() and not aktualny_wezel.czy_pelna_ekspansja():
             if aktualny_wezel._nieprzetestowane_akcje: # Dodatkowe sprawdzenie
                  nowe_dziecko = aktualny_wezel.expand()
                  if nowe_dziecko: # Upewnij się, że ekspansja się udała
                       aktualny_wezel = nowe_dziecko # Symulacja rozpocznie się od nowego dziecka

        # --- 3. Symulacja ---
        # Przeprowadź losową rozgrywkę z aktualnego węzła (może być to nowy liść lub węzeł terminalny)
        if aktualny_wezel: # Sprawdź, czy węzeł istnieje
            wynik_01, wynik_pkt, wynik_norm = aktualny_wezel.symuluj_rozgrywke()
            # --- 4. Propagacja ---
            aktualny_wezel.propaguj_wynik_wstecz(wynik_01, wynik_pkt, wynik_norm)
        else:
             # To nie powinno się zdarzyć, ale zabezpiecza przed błędami
             print("OSTRZEŻENIE MCTS: _wykonaj_pojedyncza_iteracje - aktualny_wezel jest None po selekcji/ekspansji.")

    def znajdz_najlepszy_ruch(self,
                                poczatkowy_stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                                nazwa_gracza_bota: str,
                                limit_czasu_s: float = 1.0) -> dict:
        """
        Główna metoda bota. Uruchamia algorytm MCTS przez określony czas,
        a następnie wybiera najlepszy ruch na podstawie liczby odwiedzin dzieci korzenia.

        Args:
            poczatkowy_stan_gry: Aktualny stan gry (obiekt Rozdanie lub RozdanieTrzyOsoby).
            nazwa_gracza_bota: Nazwa gracza, dla którego bot ma wybrać ruch.
            limit_czasu_s: Maksymalny czas (w sekundach) na przeszukiwanie drzewa.

        Returns:
            Słownik reprezentujący najlepszą znalezioną akcję lub pusty słownik, jeśli brak ruchów.
        """
        # Stwórz głęboką kopię stanu gry, aby MCTS nie modyfikował oryginalnego stanu
        stan_kopia = copy.deepcopy(poczatkowy_stan_gry)
        # Stwórz korzeń drzewa MCTS
        korzen = MonteCarloTreeSearchNode(
            stan_gry=stan_kopia,
            gracz_do_optymalizacji=nazwa_gracza_bota
        )

        # Sprawdź, czy w ogóle są możliwe ruchy z korzenia
        if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
             print(f"BOT MCTS ({nazwa_gracza_bota}): Brak ruchów do wykonania (faza: {korzen.faza_wezla}).")
             # Awaryjny fallback dla braku ruchów (np. spróbuj spasować)
             if korzen.faza_wezla not in [silnik_gry.FazaGry.ROZGRYWKA, silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]:
                  mozliwe = korzen._pobierz_mozliwe_akcje() # Spróbuj pobrać jeszcze raz
                  akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                  if akcja_pas:
                       print(f"BOT MCTS ({nazwa_gracza_bota}): Wymuszam akcję PAS (brak ruchów w korzeniu).")
                       return akcja_pas.copy() # Zwróć kopię
             return {} # Zwróć pusty słownik, jeśli nie ma co zrobić

        # --- Główna pętla MCTS ---
        czas_konca = time.time() + limit_czasu_s
        licznik_symulacji = 0
        while time.time() < czas_konca:
            self._wykonaj_pojedyncza_iteracje(korzen)
            licznik_symulacji += 1

        print(f"BOT MCTS ({nazwa_gracza_bota}): Wykonano {licznik_symulacji} symulacji w ~{limit_czasu_s:.2f}s.")

        # --- Wybór najlepszego ruchu ---
        # Po zakończeniu pętli wybierz dziecko korzenia z największą liczbą odwiedzin
        if not korzen.dzieci:
             # Jeśli nie rozwinięto żadnych dzieci (np. bardzo krótki czas),
             # spróbuj zwrócić pierwszą dostępną akcję lub pas
             print(f"BOT MCTS ({nazwa_gracza_bota}): Nie rozwinięto żadnych dzieci (czas?).")
             if korzen._nieprzetestowane_akcje:
                 print("BOT MCTS: Zwracam pierwszą nieprzetestowaną akcję jako fallback.")
                 akcja_fallback = korzen._nieprzetestowane_akcje[0].copy()
                 return akcja_fallback
             else: # Jeśli nie ma też nieprzetestowanych, spróbuj spasować
                 mozliwe = korzen._pobierz_mozliwe_akcje()
                 akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                 if akcja_pas: return akcja_pas.copy()
             return {} # Ostateczny fallback

        # Wybierz dziecko z największą liczbą wizyt
        najlepsze_dziecko = max(korzen.dzieci, key=lambda d: d._ilosc_wizyt)

        # Zwróć kopię akcji prowadzącej do najlepszego dziecka
        akcja_do_zwrotu = najlepsze_dziecko.akcja.copy()
        return akcja_do_zwrotu

    def evaluate_state(self,
                       stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                       nazwa_gracza_perspektywa: str,
                       limit_symulacji: int = 500) -> Optional[float]:
        """
        Używa MCTS do oszacowania wartości danego stanu gry z perspektywy podanego gracza.
        Przeprowadza określoną liczbę symulacji i zwraca średnią znormalizowaną nagrodę
        uzyskaną w korzeniu drzewa (w zakresie [-1, 1]).

        Args:
            stan_gry: Stan gry do oceny.
            nazwa_gracza_perspektywa: Gracz, z którego perspektywy oceniamy.
            limit_symulacji: Liczba iteracji MCTS do wykonania.

        Returns:
            Średnia znormalizowana nagroda (ocena stanu) w zakresie [-1, 1] lub None w razie błędu.
        """
        try:
            stan_kopia = copy.deepcopy(stan_gry)
            # Jeśli lewa czeka na finalizację, zasymuluj ją wewnętrznie przed oceną
            if stan_kopia.lewa_do_zamkniecia and stan_kopia.kolej_gracza_idx is None:
                # print("Evaluate state: Wykonuję wewnętrzną finalizację lewy...") # Usunięto log
                stan_kopia.finalizuj_lewe()

            # Stwórz korzeń drzewa
            korzen = MonteCarloTreeSearchNode(
                stan_gry=stan_kopia,
                gracz_do_optymalizacji=nazwa_gracza_perspektywa
            )

            # Jeśli stan jest terminalny (koniec gry) PO finalizacji, zwróć wynik końcowy
            if korzen.czy_wezel_terminalny():
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke() # Symulacja zwróci wynik
                # Użyj wyniku dla Normalnej lub 0/1, w zależności od kontraktu
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01

            # Sprawdź, czy są ruchy PO finalizacji
            if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
                print(f"Evaluate state: Brak ruchów po (potencjalnej) finalizacji. Faza: {korzen.faza_wezla}")
                # Jeśli brak ruchów, ale gra nie skończona, to normalny koniec (brak kart)
                # Zwróć wynik symulacji z tego stanu
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke()
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01

            # Uruchom MCTS przez zadaną liczbę symulacji
            for _ in range(limit_symulacji):
                self._wykonaj_pojedyncza_iteracje(korzen)

            # Zwróć średnią znormalizowaną nagrodę uzyskaną w korzeniu
            if korzen._ilosc_wizyt > 0:
                srednia_nagroda = korzen._wyniki_wygranych / korzen._ilosc_wizyt
                # Zwracamy bezpośrednio średnią nagrodę [-1, 1], która jest już dostosowana do fazy gry
                return srednia_nagroda
            else:
                # To nie powinno się zdarzyć przy limicie > 0
                print("Evaluate state: Nie wykonano żadnych symulacji.")
                return None

        except Exception as e:
            print(f"BŁĄD podczas ewaluacji stanu: {e}")
            traceback.print_exc()
            return None # Zwróć None w razie błędu