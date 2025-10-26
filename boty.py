import random
import math
import copy
import time
import traceback # Do logowania błędów
from enum import Enum, auto
from typing import Union, Optional, Any, Tuple

import silnik_gry

# Stałe do normalizacji
MAX_PUNKTY_ROZDANIA = 66.0 # Używane w licytacji
MAX_NORMAL_GAME_POINTS = 3.0 # Max pkt meczowe w grze Normalnej

# --- Bot Testowy (bez zmian) ---
def wybierz_akcje_dla_bota_testowego(bot: silnik_gry.Gracz, rozdanie: Any) -> tuple[str, Any]:
    """Wybiera akcję dla bota. Aktualnie w trybie testowym wymusza konkretne akcje."""

    # Logika rozgrywki (wybiera losową grywalną kartę)
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        if grywalne_karty:
            return 'karta', random.choice(grywalne_karty)
    # Logika licytacji (wymuszone akcje)
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        if not mozliwe_akcje:
            return 'brak', None

        # --- Testowe wymuszenia akcji ---
        if rozdanie.faza == silnik_gry.FazaGry.LICYTACJA:
            akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
            if akcja_pas: print(f"BOT TEST: {bot.nazwa} wymuszony 'pas'"); return 'licytacja', akcja_pas
        if rozdanie.faza == silnik_gry.FazaGry.LUFA:
            akcja_pas_lufa = next((a for a in mozliwe_akcje if a['typ'] == 'pas_lufa'), None)
            if akcja_pas_lufa: print(f"BOT TEST: {bot.nazwa} wymuszony 'pas_lufa'"); return 'licytacja', akcja_pas_lufa
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_DECYZJI_PO_PASACH:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'graj_normalnie'), None)
            if akcja_normalna: print(f"BOT TEST: {bot.nazwa} wymuszony 'graj_normalnie'"); return 'licytacja', akcja_normalna
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_PYTANIA_START:
            akcja_pytanie = next((a for a in mozliwe_akcje if a['typ'] == 'pytanie'), None)
            if akcja_pytanie: print(f"BOT TEST: {bot.nazwa} wymuszony 'pytanie'"); return 'licytacja', akcja_pytanie
        if rozdanie.faza == silnik_gry.FazaGry.DEKLARACJA_1:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'deklaracja' and a['kontrakt'] == silnik_gry.Kontrakt.NORMALNA), None)
            if akcja_normalna:
                print(f"BOT TEST: {bot.nazwa} wymuszony 'NORMALNA'")
                # Wybierz losowy atut, jeśli to możliwe
                kolory = list(silnik_gry.Kolor)
                akcja_normalna['atut'] = random.choice(kolory).name
                return 'licytacja', akcja_normalna

        # Fallback - wybierz losową akcję
        print(f"BOT TEST: {bot.nazwa} wybiera losową akcję.")
        wybrana_akcja = random.choice(mozliwe_akcje)
        # Przekonwertuj Enumy na stringi dla spójności (jeśli backend tego wymagałby)
        # Ale MCTS_Bot używa Enumów, więc zostawiamy je
        # if 'atut' in wybrana_akcja and isinstance(wybrana_akcja['atut'], silnik_gry.Kolor):
        #     wybrana_akcja['atut'] = wybrana_akcja['atut'].name
        # if 'kontrakt' in wybrana_akcja and isinstance(wybrana_akcja['kontrakt'], silnik_gry.Kontrakt):
        #     wybrana_akcja['kontrakt'] = wybrana_akcja['kontrakt'].name
        return 'licytacja', wybrana_akcja

    return 'brak', None


# --- Węzeł MCTS (z nową logiką nagród) ---
class MonteCarloTreeSearchNode:
    """
    Węzeł w drzewie przeszukiwania MCTS.
    (Wersja z różnymi nagrodami dla licytacji i rozgrywki)
    """

    def __init__(self, stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                 parent: 'MonteCarloTreeSearchNode' = None,
                 akcja: dict = None,
                 gracz_do_optymalizacji: str = None):

        self.stan_gry = stan_gry
        self.parent = parent
        self.akcja = akcja
        self.faza_wezla = stan_gry.faza
        self.kontrakt_wezla = stan_gry.kontrakt # Zapamiętaj kontrakt (jeśli już ustalony)

        # Ustalanie perspektywy (kto jest "MY")
        if gracz_do_optymalizacji:
            self._gracz_startowy_nazwa = gracz_do_optymalizacji
            if isinstance(stan_gry, silnik_gry.Rozdanie): # 4-graczy
                gracz_obj = next((g for g in stan_gry.gracze if g.nazwa == gracz_do_optymalizacji), None)
                if not gracz_obj or not gracz_obj.druzyna:
                     raise ValueError(f"Nie można znaleźć gracza {gracz_do_optymalizacji} lub jego drużyny w stanie 4p")
                self.perspektywa_optymalizacji = gracz_obj.druzyna.nazwa
            else: # 3-graczy
                self.perspektywa_optymalizacji = gracz_do_optymalizacji
        elif parent:
            self._gracz_startowy_nazwa = parent._gracz_startowy_nazwa
            self.perspektywa_optymalizacji = parent.perspektywa_optymalizacji
        else:
            raise ValueError("Korzeń drzewa musi mieć zdefiniowanego 'gracz_do_optymalizacji'")


        self._ilosc_wizyt = 0
        self._wyniki_wygranych = 0.0 # Przechowuje sumę odpowiedniej nagrody

        # Ustal, czyja jest tura W TYM WĘŹLE
        self.jest_tura_optymalizujacego = True
        if stan_gry.kolej_gracza_idx is not None:
            # Upewnij się, że indeks jest prawidłowy
            if 0 <= stan_gry.kolej_gracza_idx < len(stan_gry.gracze):
                gracz_w_turze = stan_gry.gracze[stan_gry.kolej_gracza_idx]
                if isinstance(stan_gry, silnik_gry.Rozdanie): # 4-graczy
                    if gracz_w_turze.druzyna and gracz_w_turze.druzyna.nazwa != self.perspektywa_optymalizacji:
                        self.jest_tura_optymalizujacego = False
                else: # 3-graczy
                    if gracz_w_turze.nazwa != self.perspektywa_optymalizacji:
                        self.jest_tura_optymalizujacego = False
            else:
                # Błąd indeksu w silniku gry - załóż, że to nasza tura dla bezpieczeństwa
                print(f"OSTRZEŻENIE: Nieprawidłowy kolej_gracza_idx ({stan_gry.kolej_gracza_idx}) w stanie gry.")


        self.dzieci: list['MonteCarloTreeSearchNode'] = []
        self._nieprzetestowane_akcje = self._pobierz_mozliwe_akcje()

    def _pobierz_mozliwe_akcje(self) -> list[dict]:
        """Pobiera wszystkie legalne akcje z aktualnego stanu gry."""
        if self.stan_gry.rozdanie_zakonczone or self.stan_gry.kolej_gracza_idx is None:
            return []
        # Upewnij się, że indeks jest prawidłowy
        if not (0 <= self.stan_gry.kolej_gracza_idx < len(self.stan_gry.gracze)):
             return []
        gracz_w_turze = self.stan_gry.gracze[self.stan_gry.kolej_gracza_idx]
        if not gracz_w_turze: return [] # Dodatkowe zabezpieczenie

        if self.stan_gry.faza == silnik_gry.FazaGry.ROZGRYWKA:
            akcje = []
            for karta in gracz_w_turze.reka:
                if self.stan_gry._waliduj_ruch(gracz_w_turze, karta):
                    akcje.append({'typ': 'zagraj_karte', 'karta_obj': karta})
            return akcje
        else:
            return self.stan_gry.get_mozliwe_akcje(gracz_w_turze)

    def _stworz_nastepny_stan(self, stan_wejsciowy, akcja: dict):
        """Tworzy GŁĘBOKĄ KOPIĘ stanu i stosuje na niej akcję."""
        stan_kopia = copy.deepcopy(stan_wejsciowy)
        if stan_kopia.kolej_gracza_idx is None:
             # To może się zdarzyć, jeśli stan już był terminalny
             return stan_kopia
        # Upewnij się, że indeks jest prawidłowy
        if not (0 <= stan_kopia.kolej_gracza_idx < len(stan_kopia.gracze)):
             print(f"BŁĄD KRYTYCZNY (stworz_nastepny_stan): Nieprawidłowy indeks gracza {stan_kopia.kolej_gracza_idx}")
             return stan_kopia # Zwróć kopię bez zmian w razie błędu
        gracz_w_turze_kopia = stan_kopia.gracze[stan_kopia.kolej_gracza_idx]
        if not gracz_w_turze_kopia:
             print(f"BŁĄD KRYTYCZNY (stworz_nastepny_stan): Nie znaleziono gracza o indeksie {stan_kopia.kolej_gracza_idx}")
             return stan_kopia

        typ_akcji = akcja['typ']
        try: # Dodaj obsługę błędów na wypadek problemów w silniku
            if typ_akcji == 'zagraj_karte':
                karta_obj = akcja['karta_obj']
                # Znajdź referencję karty w ręce w kopii
                karta_w_kopii = next((k for k in gracz_w_turze_kopia.reka if k.ranga == karta_obj.ranga and k.kolor == karta_obj.kolor), None)
                if karta_w_kopii:
                    stan_kopia.zagraj_karte(gracz_w_turze_kopia, karta_w_kopii)
                else:
                    # To nie powinno się zdarzyć, jeśli akcja pochodzi z _pobierz_mozliwe_akcje
                    print(f"BŁĄD KRYTYCZNY SYMULACJI: Nie znaleziono karty {karta_obj} w ręce {gracz_w_turze_kopia.nazwa} (kopia)")
            else:
                stan_kopia.wykonaj_akcje(gracz_w_turze_kopia, akcja)

            # Obsługa automatycznych zmian stanu
            if stan_kopia.lewa_do_zamkniecia:
                stan_kopia.finalizuj_lewe()
        except Exception as e:
             print(f"BŁĄD podczas tworzenia następnego stanu (akcja: {akcja}): {e}")
             traceback.print_exc()
             # W razie błędu zwróć oryginalną kopię bez zmian stanu
             return copy.deepcopy(stan_wejsciowy)

        return stan_kopia

    def czy_wezel_terminalny(self) -> bool:
        """Sprawdza, czy stan gry w węźle jest końcowy."""
        # Użyj podsumowania jako głównego wskaźnika końca (pewniejsze niż flaga)
        return bool(self.stan_gry.podsumowanie) or self.stan_gry.rozdanie_zakonczone

    def czy_pelna_ekspansja(self) -> bool:
        """Sprawdza, czy wszystkie możliwe ruchy z tego węzła zostały już rozwinięte."""
        return len(self._nieprzetestowane_akcje) == 0

    def wybierz_obiecujace_dziecko(self, stala_eksploracji: float = 1.414) -> Optional['MonteCarloTreeSearchNode']:
        """Wybiera najlepsze dziecko na podstawie formuły UCT (UCB1) z logiką Minimax."""
        if not self.dzieci: # Jeśli nie ma dzieci, nie ma co wybierać
            return None

        if self._ilosc_wizyt == 0:
            # Jeśli rodzic nie był odwiedzony, wybierz losowe dziecko
            return random.choice(self.dzieci)

        log_wizyt_rodzica = math.log(self._ilosc_wizyt)

        best_score = -float('inf')
        best_children = []

        for dziecko in self.dzieci:
            if dziecko._ilosc_wizyt == 0:
                # Dziecko nieodwiedzone ma priorytet
                score = float('inf')
            else:
                # 1. EKSPLOATACJA: Średnia nagroda dziecka (z perspektywy "MY")
                srednia_nagroda = dziecko._wyniki_wygranych / dziecko._ilosc_wizyt
                # 2. EKSPLORACJA: Bonus za rzadkie odwiedzanie
                bonus_eksploracji = stala_eksploracji * math.sqrt(
                    log_wizyt_rodzica / dziecko._ilosc_wizyt
                )
                # Logika Minimax
                if self.jest_tura_optymalizujacego:
                    score = srednia_nagroda + bonus_eksploracji
                else:
                    score = (-srednia_nagroda) + bonus_eksploracji

            if score > best_score:
                best_score = score
                best_children = [dziecko]
            elif score == best_score:
                best_children.append(dziecko)

        # Wybierz losowo spośród najlepszych dzieci (rozwiązuje remisy)
        return random.choice(best_children) if best_children else None


    def expand(self) -> Optional['MonteCarloTreeSearchNode']:
        """Tworzy i zwraca jedno nowe dziecko."""
        if not self._nieprzetestowane_akcje:
             return None # Nie ma czego ekspandować

        akcja_do_ekspansji = self._nieprzetestowane_akcje.pop(random.randrange(len(self._nieprzetestowane_akcje))) # Losowa akcja
        nowy_stan_gry = self._stworz_nastepny_stan(self.stan_gry, akcja_do_ekspansji)
        nowe_dziecko = MonteCarloTreeSearchNode(
            stan_gry=nowy_stan_gry,
            parent=self,
            akcja=akcja_do_ekspansji,
            # gracz_do_optymalizacji jest dziedziczony
        )
        self.dzieci.append(nowe_dziecko)
        return nowe_dziecko

    def symuluj_rozgrywke(self) -> Tuple[float, float, float]:
        """
        Symuluje losową rozgrywkę (rollout).
        Zwraca KROTKĘ: (wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)
        """
        stan_symulacji = copy.deepcopy(self.stan_gry)
        kontrakt_przed_symulacja = stan_symulacji.kontrakt # Zapamiętaj kontrakt
        licznik_bezpieczenstwa = 0

        while not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
            licznik_bezpieczenstwa += 1
            if licznik_bezpieczenstwa > 150: # Zwiększony limit bezpieczeństwa
                print(f"BŁĄD SYMULACJI: Przekroczono limit pętli ({licznik_bezpieczenstwa}). Faza: {stan_symulacji.faza}")
                return (0.0, 0.0, 0.0)

            # Obsługa automatycznych akcji
            if stan_symulacji.lewa_do_zamkniecia:
                try:
                    stan_symulacji.finalizuj_lewe()
                except Exception as e_fin:
                     print(f"BŁĄD podczas finalizuj_lewe w symulacji: {e_fin}")
                     return (0.0, 0.0, 0.0)
                continue # Sprawdź, czy gra się zakończyła

            # Wykonanie ruchu gracza
            if stan_symulacji.kolej_gracza_idx is not None:
                if not (0 <= stan_symulacji.kolej_gracza_idx < len(stan_symulacji.gracze)):
                    print(f"BŁĄD SYMULACJI: Nieprawidłowy indeks gracza {stan_symulacji.kolej_gracza_idx}")
                    break
                gracz_w_turze_sym = stan_symulacji.gracze[stan_symulacji.kolej_gracza_idx]
                if not gracz_w_turze_sym:
                     print(f"BŁĄD SYMULACJI: Brak obiektu gracza dla indeksu {stan_symulacji.kolej_gracza_idx}")
                     break

                # Pobierz legalne akcje
                akcje = []
                try:
                    if stan_symulacji.faza == silnik_gry.FazaGry.ROZGRYWKA:
                        for karta in gracz_w_turze_sym.reka:
                            if stan_symulacji._waliduj_ruch(gracz_w_turze_sym, karta):
                                akcje.append({'typ': 'zagraj_karte', 'karta_obj': karta})
                    else:
                        akcje = stan_symulacji.get_mozliwe_akcje(gracz_w_turze_sym)
                except Exception as e_akcje:
                     print(f"BŁĄD podczas pobierania akcji w symulacji dla {gracz_w_turze_sym.nazwa}: {e_akcje}")
                     break # Przerwij symulację w razie błędu

                # Wykonaj losową akcję
                if akcje:
                    losowa_akcja = random.choice(akcje)
                    try:
                        if losowa_akcja['typ'] == 'zagraj_karte':
                            karta_obj = losowa_akcja['karta_obj']
                            # Znajdź kartę w ręce (ponownie, na wszelki wypadek)
                            karta_w_kopii = next((k for k in gracz_w_turze_sym.reka if k.ranga == karta_obj.ranga and k.kolor == karta_obj.kolor), None)
                            if karta_w_kopii:
                                stan_symulacji.zagraj_karte(gracz_w_turze_sym, karta_w_kopii)
                            else: pass # Cichy błąd, jeśli karta zniknęła
                        else:
                            stan_symulacji.wykonaj_akcje(gracz_w_turze_sym, losowa_akcja)
                    except Exception as e_wykonaj:
                        print(f"BŁĄD podczas wykonywania akcji {losowa_akcja} w symulacji: {e_wykonaj}")
                        break # Przerwij symulację
                else:
                    # Brak akcji? Spróbujmy sprawdzić koniec gry.
                    try:
                        stan_symulacji._sprawdz_koniec_rozdania()
                    except Exception as e_sprawdz:
                         print(f"BŁĄD podczas _sprawdz_koniec_rozdania przy braku akcji: {e_sprawdz}")
                    # Jeśli nadal nie zakończone, to jest problem
                    if not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
                         print(f"INFO SYMULACJI: Brak akcji mimo braku końca gry. Faza: {stan_symulacji.faza}")
                    break # Przerwij pętlę, jeśli nie ma akcji

            else: # kolej_gracza_idx is None, a gra nie zakończona i nie ma podsumowania
                 # To nie powinno się zdarzyć po poprawkach
                 print("INFO SYMULACJI: Martwy stan (brak tury, brak finalizacji, brak końca).")
                 break

        # Upewnij się, że stan końcowy jest poprawny
        if not stan_symulacji.podsumowanie:
            try:
                stan_symulacji._sprawdz_koniec_rozdania() # Ostatnia szansa na wywołanie rozliczenia
            except Exception as e_sprawdz_koniec:
                 print(f"BŁĄD podczas końcowego _sprawdz_koniec_rozdania: {e_sprawdz_koniec}")
                 return (0.0, 0.0, 0.0)

        podsumowanie = stan_symulacji.podsumowanie
        if not podsumowanie:
            print(f"BŁĄD KRYTYCZNY SYMULACJI: Brak podsumowania po zakończeniu pętli (licznik: {licznik_bezpieczenstwa}).")
            return (0.0, 0.0, 0.0)

        # Obliczanie wyników (bez zmian)
        punkty_zdobyte = podsumowanie.get('przyznane_punkty', 0)
        wynik_skalowany_pkt = 0.0
        wynik_zero_jeden = 0.0
        wynik_skalowany_normalny = 0.0

        if MAX_PUNKTY_ROZDANIA > 0:
            wynik_skalowany_pkt = punkty_zdobyte / MAX_PUNKTY_ROZDANIA
            wynik_skalowany_pkt = max(-1.0, min(1.0, wynik_skalowany_pkt))

        wygralismy = False
        # ... (logika ustalania wygralismy bez zmian) ...
        if isinstance(stan_symulacji, silnik_gry.Rozdanie): # Gra 4-osobowa
            wygrana_druzyna = podsumowanie.get('wygrana_druzyna')
            if wygrana_druzyna == self.perspektywa_optymalizacji:
                wygralismy = True
            elif wygrana_druzyna is None and punkty_zdobyte == 0: # Remis lub błąd bez punktów
                 pass # wygralismy = False
            elif wygrana_druzyna is None: # Błąd
                print("OSTRZEŻENIE SYMULACJI: Podsumowanie 4p nie zawiera 'wygrana_druzyna'.")
                return (0.0, 0.0, 0.0)
        else: # Gra 3-osobowa
            wygrani_gracze_raw = podsumowanie.get('wygrani_gracze', [])
            wygrani_gracze = [g.nazwa if hasattr(g, 'nazwa') else g for g in wygrani_gracze_raw]
            if self.perspektywa_optymalizacji in wygrani_gracze:
                wygralismy = True

        wynik_zero_jeden = 1.0 if wygralismy else -1.0
        if not wygralismy:
             wynik_skalowany_pkt = -abs(wynik_skalowany_pkt)

        if kontrakt_przed_symulacja == silnik_gry.Kontrakt.NORMALNA:
             mnoznik_gry = podsumowanie.get('mnoznik_gry', 1) # Pobierz mnożnik (teraz jest też w 3p)
             punkty_meczu_normal = mnoznik_gry
             if MAX_NORMAL_GAME_POINTS > 0:
                 wynik_skalowany_normalny = punkty_meczu_normal / MAX_NORMAL_GAME_POINTS
                 wynik_skalowany_normalny = max(0.0, min(1.0, wynik_skalowany_normalny))
             else: wynik_skalowany_normalny = 1.0
             if not wygralismy: wynik_skalowany_normalny = -wynik_skalowany_normalny
        else:
            wynik_skalowany_normalny = wynik_zero_jeden


        return (wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)


    def propaguj_wynik_wstecz(self, wynik_zero_jeden: float, wynik_skalowany_pkt: float, wynik_skalowany_normalny: float):
        """Propaguje odpowiedni wynik w górę drzewa."""
        wynik_do_uzycia = 0.0
        if self.faza_wezla == silnik_gry.FazaGry.ROZGRYWKA:
            if self.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA: # Applies to both 4p and 3p
                wynik_do_uzycia = wynik_skalowany_normalny
            else:
                wynik_do_uzycia = wynik_zero_jeden
        else: # Faza licytacji
            wynik_do_uzycia = wynik_skalowany_pkt

        self._ilosc_wizyt += 1
        self._wyniki_wygranych += wynik_do_uzycia

        if self.parent:
            self.parent.propaguj_wynik_wstecz(wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)


# --- Główna klasa Bota MCTS ---
class MCTS_Bot:
    def __init__(self, stala_eksploracji: float = 1.414):
        self.stala_eksploracji = stala_eksploracji

    def _wykonaj_pojedyncza_iteracje(self, korzen: MonteCarloTreeSearchNode):
        """Wykonuje jeden cykl MCTS."""
        aktualny_wezel = korzen
        # Selekcja
        while not aktualny_wezel.czy_wezel_terminalny() and aktualny_wezel.czy_pelna_ekspansja():
            nastepny_wezel = aktualny_wezel.wybierz_obiecujace_dziecko(self.stala_eksploracji)
            if nastepny_wezel is None: break
            aktualny_wezel = nastepny_wezel

        # Ekspansja
        if not aktualny_wezel.czy_wezel_terminalny() and not aktualny_wezel.czy_pelna_ekspansja():
             if aktualny_wezel._nieprzetestowane_akcje:
                  nowe_dziecko = aktualny_wezel.expand()
                  if nowe_dziecko: # Upewnij się, że ekspansja się udała
                       aktualny_wezel = nowe_dziecko

        # Symulacja
        # Sprawdź, czy węzeł nie jest None (co może się zdarzyć, jeśli ekspansja zawiedzie)
        if aktualny_wezel:
            wynik_01, wynik_pkt, wynik_norm = aktualny_wezel.symuluj_rozgrywke()
            # Propagacja
            aktualny_wezel.propaguj_wynik_wstecz(wynik_01, wynik_pkt, wynik_norm)
        else:
             print("OSTRZEŻENIE: _wykonaj_pojedyncza_iteracje - aktualny_wezel jest None po selekcji/ekspansji.")


    def znajdz_najlepszy_ruch(self,
                                poczatkowy_stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                                nazwa_gracza_bota: str,
                                limit_czasu_s: float = 1.0) -> dict:
        """Główna metoda bota, znajduje najlepszy ruch."""
        stan_kopia = copy.deepcopy(poczatkowy_stan_gry)
        korzen = MonteCarloTreeSearchNode(
            stan_gry=stan_kopia,
            gracz_do_optymalizacji=nazwa_gracza_bota
        )

        # Sprawdzenie ruchów
        if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
             print(f"BOT MCTS ({nazwa_gracza_bota}): Brak ruchów do wykonania (faza: {korzen.faza_wezla}).")
             # ... (logika fallback dla braku ruchów) ...
             if korzen.faza_wezla not in [silnik_gry.FazaGry.ROZGRYWKA, silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]:
                  mozliwe = korzen._pobierz_mozliwe_akcje()
                  akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                  if akcja_pas:
                       print(f"BOT MCTS ({nazwa_gracza_bota}): Wymuszam akcję PAS.")
                       return akcja_pas.copy()
             return {}


        # Pętla MCTS
        czas_konca = time.time() + limit_czasu_s
        licznik_symulacji = 0
        while time.time() < czas_konca:
            self._wykonaj_pojedyncza_iteracje(korzen)
            licznik_symulacji += 1

        print(f"BOT MCTS ({nazwa_gracza_bota}): Wykonano {licznik_symulacji} symulacji w {limit_czasu_s:.2f}s.")

        # Logowanie ewaluacji (bez zmian)
        print(f"--- EWALUACJA BOTA MCTS ({nazwa_gracza_bota}) --- Faza: {korzen.faza_wezla.name}")
        try:
            czy_licytacja = korzen.faza_wezla != silnik_gry.FazaGry.ROZGRYWKA
            czy_normalna_rozgrywka = (korzen.faza_wezla == silnik_gry.FazaGry.ROZGRYWKA and
                                     korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA and
                                     isinstance(korzen.stan_gry, silnik_gry.Rozdanie))
            etykieta_wartosci = "Oczekiwana wartość:"
            jednostka = "pkt"
            mnoznik = MAX_PUNKTY_ROZDANIA
            if not czy_licytacja:
                if czy_normalna_rozgrywka:
                    etykieta_wartosci = "Oczekiwany wynik:"
                    mnoznik = MAX_NORMAL_GAME_POINTS
                    jednostka = "pkt mecz."
                else:
                    etykieta_wartosci = "Szansa na wygraną:"
                    mnoznik = 100.0
                    jednostka = "%"
            ogolna_wartosc = 0.0
            if korzen._ilosc_wizyt > 0:
                 wynik_do_uzycia = korzen._wyniki_wygranych / korzen._ilosc_wizyt
                 ogolna_wartosc = wynik_do_uzycia * mnoznik
            print(f"STAN OGÓLNY: {korzen._ilosc_wizyt} wizyt, {etykieta_wartosci} {ogolna_wartosc: 6.2f}{jednostka}")
            posortowane_dzieci = sorted(korzen.dzieci, key=lambda d: d._ilosc_wizyt, reverse=True)
            for dziecko in posortowane_dzieci:
                akcja = dziecko.akcja; akcja_str = "Brak akcji"
                if akcja:
                    if akcja['typ'] == 'zagraj_karte': akcja_str = str(akcja.get('karta_obj', '?'))
                    else: akcja_kopia = {k: (v.name if isinstance(v, Enum) else v) for k, v in akcja.items()}; akcja_str = str(akcja_kopia)
                if len(akcja_str) > 55: akcja_str = akcja_str[:52] + "..." # Zmniejszona szerokość

                wartosc_ruchu = 0.0
                if dziecko._ilosc_wizyt > 0:
                    wynik_do_uzycia = dziecko._wyniki_wygranych / dziecko._ilosc_wizyt
                    wartosc_ruchu = wynik_do_uzycia * mnoznik
                # ZMIANA: Mniejsza szerokość
                print(f"  RUCH: {akcja_str:<55} -> {etykieta_wartosci} {wartosc_ruchu: 6.2f}{jednostka} (Wizyty: {dziecko._ilosc_wizyt})")
            print("--------------------------------------------------")
        except Exception as e:
            print(f"Błąd podczas logowania ewaluacji: {e}")
            traceback.print_exc()

        # Wybór najlepszego ruchu (bez zmian)
        if not korzen.dzieci:
             print(f"BOT MCTS ({nazwa_gracza_bota}): Nie rozwinięto żadnych dzieci, brak ruchu.")
             # ... (logika fallback braku dzieci) ...
             if korzen._nieprzetestowane_akcje:
                 print("BOT MCTS: Zwracam pierwszą nieprzetestowaną akcję.")
                 akcja_fallback = korzen._nieprzetestowane_akcje[0].copy()
                 return akcja_fallback
             else:
                 mozliwe = korzen._pobierz_mozliwe_akcje()
                 akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                 if akcja_pas: return akcja_pas.copy()
             return {}

        najlepsze_dziecko = max(korzen.dzieci, key=lambda d: d._ilosc_wizyt)
        akcja_do_zwrotu = najlepsze_dziecko.akcja.copy()
        return akcja_do_zwrotu

    # --- NOWA METODA EWALUACJI STANU ---
    def evaluate_state(self,
                       stan_gry: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby],
                       nazwa_gracza_perspektywa: str,
                       limit_symulacji: int = 500) -> Optional[float]:
        """Uruchamia MCTS, aby ocenić stan gry."""
        try:
            stan_kopia = copy.deepcopy(stan_gry)
            # Symuluj finalizację wewnętrznie
            if stan_kopia.lewa_do_zamkniecia and stan_kopia.kolej_gracza_idx is None:
                print("Evaluate state: Wykonuję wewnętrzną finalizację lewy...")
                stan_kopia.finalizuj_lewe()

            korzen = MonteCarloTreeSearchNode(
                stan_gry=stan_kopia,
                gracz_do_optymalizacji=nazwa_gracza_perspektywa
            )

            # Sprawdź stan terminalny PO finalizacji
            if korzen.czy_wezel_terminalny():
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke()
                # Zwróć wynik 0/1 dla rozgrywki, 0 dla innych faz
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01

            # Sprawdź, czy są ruchy PO finalizacji
            if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
                print(f"Evaluate state: Brak ruchów po (potencjalnej) finalizacji. Faza: {korzen.faza_wezla}")
                # Jeśli brak ruchów, ale gra nie skończona, to może być normalne (np. koniec kart)
                # Spróbujmy zwrócić wynik symulacji z tego stanu
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke()
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01


            # Uruchom MCTS
            for _ in range(limit_symulacji):
                self._wykonaj_pojedyncza_iteracje(korzen)

            # Zwróć średni wynik z korzenia
            if korzen._ilosc_wizyt > 0:
                srednia_nagroda = korzen._wyniki_wygranych / korzen._ilosc_wizyt
                # Zwracamy wynik odpowiedni dla fazy KORZENIA (który był ROZGRYWKA)
                # Zawsze zwracaj wynik [-1, 1] dla paska
                return srednia_nagroda
            else:
                print("Evaluate state: Nie wykonano żadnych symulacji.")
                return None

        except Exception as e:
            print(f"BŁĄD podczas ewaluacji stanu: {e}")
            traceback.print_exc()
            return None