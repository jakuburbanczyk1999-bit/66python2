# boty.py
# WERSJA ZREFRAKTORYZOWANA (z adapterem/shimem dla AbstractGameEngine)

import random
import math
import copy
import time
import traceback
from enum import Enum
from typing import Union, Optional, Any, Tuple

# Import silnika gry (wciąż potrzebny dla logiki wewnętrznej)
import silnik_gry

# === NOWE IMPORTY ===
# Importujemy interfejs i silnik-adapter
from engines.abstract_game_engine import AbstractGameEngine
from engines.sixtysix_engine import SixtySixEngine
# === KONIEC NOWYCH IMPORTÓW ===

# === IMPORT BOTA NN (lazy loading) ===
_nn_bot_class = None
def _get_nn_bot_class():
    """Lazy loading klasy NeuralNetworkBot - ładuje model tylko gdy potrzebny."""
    global _nn_bot_class
    if _nn_bot_class is None:
        try:
            from nn_training.nn_bot import NeuralNetworkBot
            _nn_bot_class = NeuralNetworkBot
        except ImportError as e:
            print(f"OSTRZEŻENIE: Nie można załadować NeuralNetworkBot: {e}")
            _nn_bot_class = False  # Oznacz że próbowano i nie udało się
    return _nn_bot_class if _nn_bot_class else None
# === KONIEC IMPORTU BOTA NN ===


# ==========================================================================
# SEKCJA 1: IMPORTY I STAŁE
# ==========================================================================

# Stałe używane do normalizacji wyników w MCTS
MAX_PUNKTY_ROZDANIA = 120.0 # Maksymalna liczba punktów możliwa do zdobycia w kartach w rozdaniu
MAX_NORMAL_GAME_POINTS = 3.0 # Maksymalna liczba punktów meczowych do zdobycia w kontrakcie NORMALNA
MAX_EV_NORMALIZATION = 66.0 # Maksymalna wartość oczekiwana używana do normalizacji EV w licytacji

# ==========================================================================
# SEKCJA 1.5: MODYFIKATORY NAGRODY (dla różnych "osobowości" botów)
# ==========================================================================

from dataclasses import dataclass, field

@dataclass
class RewardModifiers:
    """
    Parametry modyfikujące funkcję nagrody w MCTS.
    Pozwalają tworzyć boty o różnych "osobowościach" - preferujące
    określone kontrakty, bardziej agresywne/ostrożne, itp.
    
    Wszystkie mnożniki domyślnie = 1.0 (neutralne).
    Bonusy domyślnie = 0.0 (brak modyfikacji).
    """
    
    # === Mnożniki kontraktów (wpływają na EV w fazie licytacji) ===
    normalna_mult: float = 1.0      # Preferuj/unikaj NORMALNA
    gorsza_mult: float = 1.0        # Preferuj/unikaj GORSZA  
    lepsza_mult: float = 1.0        # Preferuj/unikaj LEPSZA
    bez_pytania_mult: float = 1.0   # Preferuj/unikaj BEZ_PYTANIA
    
    # === Modyfikatory licytacji (bonusy/kary za akcje) ===
    lufa_bonus: float = 0.0         # Bonus za danie lufy (ujemny = kara)
    kontra_bonus: float = 0.0       # Bonus za danie kontry
    pas_bonus: float = 0.0          # Bonus za spasowanie
    
    # === Modyfikatory ryzyka ===
    win_multiplier: float = 1.0     # Mnożnik nagrody za wygraną
    loss_multiplier: float = 1.0    # Mnożnik kary za przegraną (wyższy = ostrożniejszy)
    
    def get_contract_multiplier(self, kontrakt) -> float:
        """Zwraca mnożnik dla danego kontraktu."""
        if kontrakt == silnik_gry.Kontrakt.NORMALNA:
            return self.normalna_mult
        elif kontrakt == silnik_gry.Kontrakt.GORSZA:
            return self.gorsza_mult
        elif kontrakt == silnik_gry.Kontrakt.LEPSZA:
            return self.lepsza_mult
        elif kontrakt == silnik_gry.Kontrakt.BEZ_PYTANIA:
            return self.bez_pytania_mult
        return 1.0  # Domyślnie neutralny


# === PREDEFINIOWANE OSOBOWOŚCI BOTÓW (dla gry 66) ===
BOT_PERSONALITIES = {
    # Domyślny - neutralny, optymalny gracz
    'topplayer': RewardModifiers(),
    
    # Szaleniec - kocha kontrakty solo i lufy, nie lubi normalnej
    # Solo: x1.5 za wygraną, x0.8 za przegraną
    # Lufa: x3 bonus (tylko wygrana)
    # Normalna: x0.8 za wygraną, x1.2 za przegraną
    'szaleniec': RewardModifiers(
        normalna_mult=0.8,
        gorsza_mult=1.5,
        lepsza_mult=1.5,
        bez_pytania_mult=1.5,
        lufa_bonus=0.5,  # Duży bonus za lufę
        kontra_bonus=0.3,
        win_multiplier=1.2,
        loss_multiplier=0.7,  # Mało go obchodzą przegrane
    ),
    
    # Gorsza Enjoyer - specjalizuje się w kontrakcie GORSZA
    'gorsza_enjoyer': RewardModifiers(
        gorsza_mult=1.8,
        normalna_mult=0.9,
        lepsza_mult=0.7,
        loss_multiplier=0.8,  # Mniejsza kara za przegraną
    ),
    
    # Lepsza Enjoyer - specjalizuje się w kontrakcie LEPSZA
    'lepsza_enjoyer': RewardModifiers(
        lepsza_mult=1.8,
        normalna_mult=0.9,
        gorsza_mult=0.7,
        loss_multiplier=0.8,  # Mniejsza kara za przegraną
    ),
    
    # Beginner - boi się ryzyka, unika luf i specjalnych kontraktów
    'beginner': RewardModifiers(
        normalna_mult=1.4,
        gorsza_mult=0.5,
        lepsza_mult=0.5,
        bez_pytania_mult=0.6,
        lufa_bonus=-0.4,  # Duża kara za lufę
        kontra_bonus=-0.3,  # Kara za kontrę
        loss_multiplier=1.5,  # Bardzo boi się przegranych
        pas_bonus=0.2,  # Lubi pasować
    ),
    
    # Chaotic - ogromne bonusy na specjalne kontrakty, nigdy normalna
    'chaotic': RewardModifiers(
        normalna_mult=0.1,  # Prawie nigdy nie gra normalnej
        gorsza_mult=2.5,
        lepsza_mult=2.5,
        bez_pytania_mult=2.0,
        lufa_bonus=0.6,
        kontra_bonus=0.5,
        win_multiplier=1.5,
        loss_multiplier=0.5,  # Kompletnie ignoruje przegrane
    ),
    
    # Counter - analizuje i kontruje przeciwników
    # Lubi dawać lufy i kontry, czeka na błędy przeciwników
    'counter': RewardModifiers(
        normalna_mult=1.1,      # Preferuje grę normalną (bezpieczna)
        gorsza_mult=0.9,        # Mniej skłonny do gorszej (ryzyko)
        lepsza_mult=0.9,        # Mniej skłonny do lepszej (ryzyko)
        bez_pytania_mult=0.8,   # Unika bez pytania
        lufa_bonus=0.5,         # BARDZO lubi dawać lufy!
        kontra_bonus=0.5,       # BARDZO lubi dawać kontry!
        pas_bonus=0.15,         # Lubi pasować - czeka na błędy
        win_multiplier=1.1,     # Ceni wygrane
        loss_multiplier=0.85,   # Nie boi się przegranych (agresywny)
    ),
    
    # Nie lubię pytać - preferuje grę bez pytania
    'nie_lubie_pytac': RewardModifiers(
        bez_pytania_mult=2.0,
        normalna_mult=0.7,
        pas_bonus=-0.1,  # Nie lubi pasować przy pytaniu
    ),
}


def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    """Konwertuje string reprezentujący kartę (np. "As Czerwien") na obiekt Karta."""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        # Mapowanie nazw stringowych na obiekty Enum
        mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
        mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
        # Znajdź odpowiednie Enumy
        ranga = mapowanie_rang[ranga_str]
        kolor = mapowanie_kolorow[kolor_str]
        # Stwórz i zwróć obiekt Karta
        return silnik_gry.Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        # Złap błędy parsowania lub nieznanych nazw
        print(f"BŁĄD: Nie można przekonwertować stringa '{nazwa_karty}' na kartę: {e}")
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e

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
                 gracz_do_optymalizacji: Optional[str] = None,
                 perfect_information: bool = False,  # Domyślnie FAIR (nie oszukuje)
                 reward_modifiers: Optional[RewardModifiers] = None):  # Modyfikatory nagrody
        """
        Inicjalizuje węzeł MCTS.

        Args:
            stan_gry: Obiekt Rozdanie lub RozdanieTrzyOsoby reprezentujący stan gry w tym węźle.
            parent: Węzeł nadrzędny (None dla korzenia).
            akcja: Akcja, która doprowadziła do tego stanu z węzła nadrzędnego.
            gracz_do_optymalizacji: Nazwa gracza, z perspektywy którego optymalizujemy (wymagane dla korzenia).
            perfect_information: Czy bot widzi karty przeciwników (False = fair play).
            reward_modifiers: Parametry modyfikujące funkcję nagrody (osobowość bota).
        """
        self.perfect_information = perfect_information  # Zapamiętaj tryb
        # Modyfikatory nagrody - dziedzicz z rodzica lub użyj domyślnych
        if reward_modifiers is not None:
            self.reward_modifiers = reward_modifiers
        elif parent is not None:
            self.reward_modifiers = parent.reward_modifiers
        else:
            self.reward_modifiers = RewardModifiers()  # Domyślne (neutralne)
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
        self._sum_wynik_zero_jeden = 0.0 # Przechowuje sumę nagrody 1.0 (wygrana) / -1.0 (przegrana)
        self._sum_raw_ev = 0.0 # Przechowuje sumę surowej wartości oczekiwanej (EV) bez normalizacji

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
        if not self.perfect_information and not self._czy_tura_optymalizujacego():
             # Jeśli to nie nasza tura i gramy fair, nie generujemy akcji
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
            perfect_information=self.perfect_information 
        )
        self.dzieci.append(nowe_dziecko) # Dodaj dziecko do listy dzieci rodzica
        return nowe_dziecko
    
    # W boty.py, w klasie MonteCarloTreeSearchNode

    def _determinize_state(self) -> Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby]:
        """
        Tworzy determinizację stanu gry (hipotetyczny pełny stan).
        Losowo rozdaje nieznane karty przeciwnikom, UWZGLĘDNIAJĄC historię gry
        (np. pokazane braki w kolorach - voidy).
        """
        stan_do_determinizacji = self.stan_gry # Użyj stanu z węzła jako bazy
        stan_determinizowany = copy.deepcopy(stan_do_determinizacji)

        # 1. Zbierz wszystkie znane karty (ręka bota + stół + wygrane + zagrane w historii)
        znane_karty = set()
        gracz_opt_obj = next((g for g in stan_determinizowany.gracze if g and g.nazwa == self._gracz_startowy_nazwa), None)

        if gracz_opt_obj:
            znane_karty.update(gracz_opt_obj.reka)

        znane_karty.update(karta for _, karta in stan_determinizowany.aktualna_lewa)
        for gracz in stan_determinizowany.gracze:
             if gracz: znane_karty.update(gracz.wygrane_karty)

        historia_rozdania = stan_determinizowany.szczegolowa_historia
        for log in historia_rozdania:
            if log.get('typ') == 'zagranie_karty':
                 karta_str = log.get('karta')
                 if karta_str:
                      try:
                           karta_obj = karta_ze_stringa(karta_str)
                           znane_karty.add(karta_obj)
                      except ValueError:
                           print(f"OSTRZEŻENIE determinizacji: Nie można sparsować karty '{karta_str}' z historii.")

        # 2. Ustal pulę nieznanych kart
        pelna_talia = set(silnik_gry.Talia()._stworz_pelna_talie())
        nieznane_karty = list(pelna_talia - znane_karty)
        random.shuffle(nieznane_karty)

        # 3. Ustal bazową liczbę kart (ile kart mieli gracze NA POCZĄTKU tej lewy)
        liczba_kart_startowa_lewy = 0
        if gracz_opt_obj:
            liczba_kart_startowa_lewy = len(gracz_opt_obj.reka)
            # Sprawdź, czy MY (gracz_opt_obj) już zagraliśmy w tej lewie
            if (stan_determinizowany.aktualna_lewa and
                any(g.nazwa == self._gracz_startowy_nazwa for g, k in stan_determinizowany.aktualna_lewa)):
                # Jeśli tak, to na początku lewy mieliśmy o 1 kartę więcej
                liczba_kart_startowa_lewy += 1
        
        # Awaryjny fallback - jeśli bot ma 0 kart, ale gra się toczy, coś jest nie tak,
        # ale przynajmniej nie doprowadzimy do ujemnych liczb kart.
        if liczba_kart_startowa_lewy < 0:
            liczba_kart_startowa_lewy = 0

        # === Logika ustalania voidów (braków w kolorach)  ===
        voidy_graczy = {g.nazwa: set() for g in stan_determinizowany.gracze if g and g.nazwa != self._gracz_startowy_nazwa}
        biezaca_lewa_karty = {}
        aktualny_kolor_wiodacy = None
        gracze_w_lewie = []

        for log in historia_rozdania:
            if log.get('typ') == 'zagranie_karty':
                gracz_nazwa = log.get('gracz')
                karta_str = log.get('karta')
                if not gracz_nazwa or not karta_str or gracz_nazwa == self._gracz_startowy_nazwa: continue
                try: karta_obj = karta_ze_stringa(karta_str)
                except ValueError: continue

                if not aktualny_kolor_wiodacy:
                    aktualny_kolor_wiodacy = karta_obj.kolor
                    gracze_w_lewie = [gracz_nazwa]
                    biezaca_lewa_karty = {gracz_nazwa: karta_obj}
                else:
                    gracze_w_lewie.append(gracz_nazwa)
                    biezaca_lewa_karty[gracz_nazwa] = karta_obj
                    if karta_obj.kolor != aktualny_kolor_wiodacy:
                        czy_przebil_atutem = stan_determinizowany.atut is not None and karta_obj.kolor == stan_determinizowany.atut
                        if not czy_przebil_atutem:
                             if gracz_nazwa in voidy_graczy:
                                  voidy_graczy[gracz_nazwa].add(aktualny_kolor_wiodacy)
                    if len(gracze_w_lewie) == stan_determinizowany.liczba_aktywnych_graczy:
                        aktualny_kolor_wiodacy = None; gracze_w_lewie = []; biezaca_lewa_karty = {}
            elif log.get('typ') == 'koniec_lewy':
                 aktualny_kolor_wiodacy = None; gracze_w_lewie = []; biezaca_lewa_karty = {}
        # === Koniec ustalania voidów ===

        # 4. Rozdaj nieznane karty przeciwnikom, respektując voidy i POPRAWNĄ liczbę kart
        licznik_prob = 0
        MAX_PROB_ROZDANIA = 150 # (Tak jak było)
        przeciwnicy_do_rozdania = [g for g in stan_determinizowany.gracze if g and g.nazwa != self._gracz_startowy_nazwa]

        while licznik_prob < MAX_PROB_ROZDANIA:
            random.shuffle(nieznane_karty)
            kopia_nieznanych = nieznane_karty[:]
            rozdanie_udane = True
            wszystkie_rece = {}
            
            random.shuffle(przeciwnicy_do_rozdania)
            
            for gracz in przeciwnicy_do_rozdania:
                voidy = voidy_graczy.get(gracz.nazwa, set())
                
                # --- START POPRAWIONEJ LOGIKI ---
                
                # 1. Oblicz, ile kart powinien mieć TEN KONKRETNY gracz
                oczekiwana_liczba_kart_dla_tego_gracza = liczba_kart_startowa_lewy
                
                # 2. Sprawdź, czy TEN gracz już zagrał w bieżącej lewie
                if (stan_determinizowany.aktualna_lewa and
                    any(g.nazwa == gracz.nazwa for g, k in stan_determinizowany.aktualna_lewa)):
                    # Jeśli tak, musi mieć o jedną kartę mniej
                    oczekiwana_liczba_kart_dla_tego_gracza -= 1
                
                # Zabezpieczenie przed ujemną liczbą kart
                if oczekiwana_liczba_kart_dla_tego_gracza < 0:
                    oczekiwana_liczba_kart_dla_tego_gracza = 0

                # 3. Znajdź karty, które ten gracz MOŻE wziąć (respektując voidy)
                karty_do_wziecia = [k for k in kopia_nieznanych if k.kolor not in voidy]

                # 4. Sprawdź, czy pula jest wystarczająca (użyj nowej, poprawnej zmiennej)
                if len(karty_do_wziecia) < oczekiwana_liczba_kart_dla_tego_gracza:
                    rozdanie_udane = False
                    break 

                # 5. Rozdaj karty (użyj nowej, poprawnej zmiennej)
                try:
                    # Nie rozdawaj kart, jeśli gracz nie powinien ich mieć (liczba = 0)
                    if oczekiwana_liczba_kart_dla_tego_gracza > 0:
                        reka_gracza = random.sample(karty_do_wziecia, oczekiwana_liczba_kart_dla_tego_gracza)
                    else:
                        reka_gracza = [] # Pusta ręka
                except ValueError as e:
                    print(f"BŁĄD KRYTYCZNY (random.sample) w determinizacji: {e}. Próba wzięcia {oczekiwana_liczba_kart_dla_tego_gracza} z {len(karty_do_wziecia)} kart.")
                    rozdanie_udane = False
                    break

                # 6. Zapisz rękę i usuń karty z puli
                wszystkie_rece[gracz.nazwa] = reka_gracza
                if reka_gracza: # Usuń tylko jeśli coś zostało rozdane
                    kopia_nieznanych = [k for k in kopia_nieznanych if k not in reka_gracza]
                
                # --- KONIEC POPRAWIONEJ LOGIKI ---

            if rozdanie_udane:
                # Przypisz ręce
                for gracz in stan_determinizowany.gracze:
                    if gracz and gracz.nazwa in wszystkie_rece:
                        gracz.reka = wszystkie_rece[gracz.nazwa]
                        gracz.reka.sort(key=lambda k: (silnik_gry.KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
                return stan_determinizowany # Zwróć pomyślnie zdeterminizowany stan
            else:
                licznik_prob += 1
                
        # Jeśli pętla 'while' zakończyła się po MAX_PROB_ROZDANIA
        # print(f"OSTRZEŻENIE Determinizacji: Nie udało się rozdać kart zgodnie z voidami po {MAX_PROB_ROZDANIA} próbach. Próbuję ponownie IGNORUJĄC VOIDY.")

        # --- FALLBACK: Spróbuj rozdać jeszcze raz, ale ignorując voidy ---
        # (To jest ten sam kod co powyżej, ale 'voidy' są zawsze puste)
        random.shuffle(nieznane_karty)
        kopia_nieznanych_fallback = nieznane_karty[:]
        rozdanie_udane_fallback = True
        wszystkie_rece_fallback = {}

        # Użyj tej samej (losowej) kolejności przeciwników
        for gracz in przeciwnicy_do_rozdania:
            # JEDYNA RÓŻNICA: 'voidy' są puste, 'karty_do_wziecia' to cała pula
            karty_do_wziecia = kopia_nieznanych_fallback 

            # Oblicz, ile kart powinien mieć TEN KONKRETNY gracz
            oczekiwana_liczba_kart_dla_tego_gracza = liczba_kart_startowa_lewy
            if (stan_determinizowany.aktualna_lewa and
                any(g.nazwa == gracz.nazwa for g, k in stan_determinizowany.aktualna_lewa)):
                oczekiwana_liczba_kart_dla_tego_gracza -= 1
            if oczekiwana_liczba_kart_dla_tego_gracza < 0:
                oczekiwana_liczba_kart_dla_tego_gracza = 0

            # Sprawdź (ten check powinien teraz zawsze się udać)
            if len(karty_do_wziecia) < oczekiwana_liczba_kart_dla_tego_gracza:
                rozdanie_udane_fallback = False
                break # Jeśli to zawiedzie, to mamy GŁĘBSZY błąd (np. w liczeniu kart)

            try:
                if oczekiwana_liczba_kart_dla_tego_gracza > 0:
                    reka_gracza = random.sample(karty_do_wziecia, oczekiwana_liczba_kart_dla_tego_gracza)
                else:
                    reka_gracza = [] 
            except ValueError:
                rozdanie_udane_fallback = False
                break

            wszystkie_rece_fallback[gracz.nazwa] = reka_gracza
            if reka_gracza: 
                kopia_nieznanych_fallback = [k for k in kopia_nieznanych_fallback if k not in reka_gracza]

        if rozdanie_udane_fallback:
            # Przypisz ręce (ignorując voidy)
            for gracz in stan_determinizowany.gracze:
                if gracz and gracz.nazwa in wszystkie_rece_fallback:
                    gracz.reka = wszystkie_rece_fallback[gracz.nazwa]
                    gracz.reka.sort(key=lambda k: (silnik_gry.KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
            return stan_determinizowany # Zwróć stan z zignorowanymi voidami
        else:
            # Jeśli nawet fallback zawiódł (np. błąd w liczeniu kart)
            print(f"BŁĄD KRYTYCZNY Determinizacji: Fallback (ignorowanie voidów) również zawiódł.")
            # Zwróć stan bazowy (przeciwnicy będą mieli puste ręce w symulacji)
            return copy.deepcopy(stan_do_determinizacji)

    def symuluj_rozgrywke(self) -> Tuple[float, float, float]:
        """
        Symuluje losową rozgrywkę (rollout).
        W trybie niepełnej informacji (`perfect_information=False`) najpierw determinizuje stan.
        Ogranicza liczbę luf/kontr do jednej na symulację.
        Zwraca KROTKĘ: (wynik_zero_jeden, wynik_skalowany_pkt, wynik_skalowany_normalny)
        """

        wynik_zero_jeden = 0.0
        wynik_skalowany_normalny = 0.0
        ev_raw_points = 0.0 # NOWA METRYKA: Oczekiwana Wartość (EV)
        # --- Krok determinizacji (jeśli tryb fair) ---
        if not self.perfect_information:
            try:
                stan_symulacji = self._determinize_state() # Stwórz hipotetyczny pełny stan
            except Exception as e_det:
                 print(f"BŁĄD KRYTYCZNY podczas determinizacji: {e_det}")
                 traceback.print_exc()
                 return (0.0, 0.0, 0.0) # Zwróć neutralny wynik w razie błędu
        else: # Tryb oszukujący (bez zmian)
            stan_symulacji = copy.deepcopy(self.stan_gry)
        # --- Koniec kroku determinizacji ---
        aktywni_gracze_sym = [g for g in stan_symulacji.gracze if g and (not hasattr(stan_symulacji, 'nieaktywny_gracz') or g != stan_symulacji.nieaktywny_gracz)]
        wszyscy_bez_kart = not any(g.reka for g in aktywni_gracze_sym)

        if (wszyscy_bez_kart and 
            stan_symulacji.faza == silnik_gry.FazaGry.ROZGRYWKA and 
            not stan_symulacji.rozdanie_zakonczone and 
            not stan_symulacji.podsumowanie and
            not stan_symulacji.lewa_do_zamkniecia): # Upewnij się, że stół też jest pusty

            # print("INFO SYMULACJI: Wykryto 'zombie state' po determinizacji (brak kart). Wymuszam rozliczenie.") # (Opcjonalny log)
            try:
                # Wymuś sprawdzenie końca. To powinno wywołać rozlicz_rozdanie()
                # i poprawnie utworzyć podsumowanie na podstawie 0-0 punktów.
                stan_symulacji._sprawdz_koniec_rozdania() 
                
                # Dodatkowe zabezpieczenie, gdyby _sprawdz_koniec_rozdania zawiodło
                if not stan_symulacji.podsumowanie:
                    # print("OSTRZEŻENIE SYMULACJI: _sprawdz_koniec_rozdania nie stworzyło podsumowania, próba ręczna.")
                    stan_symulacji.rozdanie_zakonczone = True
                    stan_symulacji.rozlicz_rozdanie()
            except Exception as e_zombie:
                 print(f"BŁĄD podczas wymuszonego rozliczenia 'zombie state': {e_zombie}")
                 traceback.print_exc()
                 return (0.0, 0.0, 0.0) # Zwróć neutralny wynik

        kontrakt_przed_symulacja = stan_symulacji.kontrakt
        licznik_bezpieczenstwa = 0
        lufa_kontra_w_symulacji = False

        # Pętla symulacji - trwa dopóki rozdanie się nie zakończy
        while not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
            licznik_bezpieczenstwa += 1
            if licznik_bezpieczenstwa > 150: # Limit iteracji
                print(f"BŁĄD SYMULACJI: Przekroczono limit pętli ({licznik_bezpieczenstwa}). Faza: {stan_symulacji.faza}")
                return (0.0, 0.0, 0.0) # Zwróć neutralny wynik w razie błędu

            # Obsługa automatycznej finalizacji lewy
            if stan_symulacji.lewa_do_zamkniecia:
                try: stan_symulacji.finalizuj_lewe()
                except Exception as e_fin: print(f"BŁĄD podczas finalizuj_lewe w symulacji: {e_fin}"); return (0.0, 0.0, 0.0)
                # Sprawdź koniec gry PO finalizacji lewy
                if stan_symulacji.rozdanie_zakonczone or stan_symulacji.podsumowanie: break
                continue # Kontynuuj pętlę (tura powinna być ustawiona)

            # Wykonanie ruchu gracza, jeśli jest jego tura
            if stan_symulacji.kolej_gracza_idx is not None:
                if not (0 <= stan_symulacji.kolej_gracza_idx < len(stan_symulacji.gracze)): print(f"BŁĄD SYMULACJI: Nieprawidłowy indeks gracza {stan_symulacji.kolej_gracza_idx}"); break
                gracz_w_turze_sym = stan_symulacji.gracze[stan_symulacji.kolej_gracza_idx]
                if not gracz_w_turze_sym: print(f"BŁĄD SYMULACJI: Brak obiektu gracza dla indeksu {stan_symulacji.kolej_gracza_idx}"); break

                # Pobierz legalne akcje
                akcje = []
                try:
                    if stan_symulacji.faza == silnik_gry.FazaGry.ROZGRYWKA:
                        akcje = [{'typ': 'zagraj_karte', 'karta_obj': k} for k in gracz_w_turze_sym.reka if stan_symulacji._waliduj_ruch(gracz_w_turze_sym, k)]
                    else:
                        akcje = stan_symulacji.get_mozliwe_akcje(gracz_w_turze_sym)
                except Exception as e_akcje: print(f"BŁĄD podczas pobierania akcji w symulacji dla {gracz_w_turze_sym.nazwa}: {e_akcje}"); break

                # Filtrowanie luf/kontr
                if stan_symulacji.faza != silnik_gry.FazaGry.ROZGRYWKA:
                    akcje_filtrowane = [a for a in akcje if a.get('typ') not in ['lufa', 'kontra', 'do_konca']]
                    if not akcje_filtrowane:
                         fallback_pas = None
                         if stan_symulacji.faza == silnik_gry.FazaGry.LICYTACJA: fallback_pas = {'typ': 'pas'}
                         elif stan_symulacji.faza == silnik_gry.FazaGry.LUFA: fallback_pas = {'typ': 'pas_lufa'}
                         if fallback_pas:
                              print("INFO SYMULACJI: Wymuszono PAS po odfiltrowaniu luf/kontr.")
                              akcje = [fallback_pas]
                         else: akcje = []
                    else: akcje = akcje_filtrowane

                # Wykonaj losową akcję (z przefiltrowanej listy)
                if akcje:
                    losowa_akcja = random.choice(akcje)
                    if losowa_akcja.get('typ') in ['lufa', 'kontra', 'do_konca']: lufa_kontra_w_symulacji = True
                    try:
                        if losowa_akcja['typ'] == 'zagraj_karte':
                            karta_obj = losowa_akcja['karta_obj']
                            # Znajdź referencję do karty w kopii stanu
                            karta_w_kopii = next((k for k in gracz_w_turze_sym.reka if k == karta_obj), None)
                            if karta_w_kopii: stan_symulacji.zagraj_karte(gracz_w_turze_sym, karta_w_kopii)
                            else: print(f"OSTRZEŻENIE SYMULACJI: Nie znaleziono {karta_obj} w ręce {gracz_w_turze_sym.nazwa} (kopia)") # Dodano ostrzeżenie
                        else:
                            stan_symulacji.wykonaj_akcje(gracz_w_turze_sym, losowa_akcja)
                        # Sprawdź koniec PO KAŻDEJ AKCJI
                        stan_symulacji._sprawdz_koniec_rozdania()
                        # Jeśli koniec, przerwij pętlę
                        if stan_symulacji.rozdanie_zakonczone or stan_symulacji.podsumowanie:
                            break
                    except Exception as e_wykonaj: print(f"BŁĄD podczas wykonywania akcji {losowa_akcja} w symulacji: {e_wykonaj}"); break
                else: # Brak akcji
                    # Spróbuj sprawdzić koniec przed logowaniem błędu
                    try: stan_symulacji._sprawdz_koniec_rozdania()
                    except Exception as e_sprawdz: print(f"BŁĄD podczas _sprawdz_koniec_rozdania przy braku akcji: {e_sprawdz}")
                    # Loguj tylko jeśli gra się *naprawdę* nie zakończyła
                    if not stan_symulacji.rozdanie_zakonczone and not stan_symulacji.podsumowanie:
                         print(f"--- LOG Brak Akcji START ---")
                         print(f"  INFO SYMULACJI: Brak akcji mimo braku końca gry. Faza: {stan_symulacji.faza}")
                         try:
                              gracz_w_turze_log = stan_symulacji.gracze[stan_symulacji.kolej_gracza_idx] if stan_symulacji.kolej_gracza_idx is not None else None
                              print(f"  Gracz w turze: {gracz_w_turze_log.nazwa if gracz_w_turze_log else 'Brak'}")
                              print(f"  Ręka: {[str(k) for k in gracz_w_turze_log.reka] if gracz_w_turze_log else 'Brak'}")
                              print(f"  Stół: {[(g.nazwa, str(k)) for g, k in stan_symulacji.aktualna_lewa]}")
                              print(f"  Atut: {stan_symulacji.atut}")
                              print(f"  Kontrakt: {stan_symulacji.kontrakt}")
                         except Exception as e_log: print(f"  Błąd podczas logowania stanu: {e_log}")
                         print(f"--- LOG Brak Akcji KONIEC ---")
                    break # Przerwij pętlę (bez zmian)
            else: # kolej_gracza_idx is None
                 print("INFO SYMULACJI: Martwy stan (brak tury, brak finalizacji, brak końca).")
                 break

        # --- Kod PO PĘTLI WHILE ---
        if not stan_symulacji.podsumowanie and stan_symulacji.rozdanie_zakonczone:
             try:
                  wynik_rozliczenia = stan_symulacji.rozlicz_rozdanie()
                  if not stan_symulacji.podsumowanie:
                    print("BŁĄD KRYTYCZNY SYMULACJI: rozlicz_rozdanie() zostało wywołane, ale nie stworzyło podsumowania!")
                    return (0.0, 0.0, 0.0)
             except Exception as e_rozlicz:
                  print(f"BŁĄD podczas wymuszonego rozlicz_rozdanie: {e_rozlicz}")
                  traceback.print_exc()
                  return (0.0, 0.0, 0.0)

        podsumowanie = stan_symulacji.podsumowanie
        if not podsumowanie:
             print("BŁĄD KRYTYCZNY SYMULACJI: Brak podsumowania po wszystkich próbach rozliczenia!")
             return (0.0, 0.0, 0.0)

        # --- Obliczanie wyników z perspektywy optymalizującego ---
        punkty_zdobyte = podsumowanie.get('przyznane_punkty', 0) # To SĄ surowe punkty meczowe
        wynik_skalowany_pkt = 0.0 # Ta zmienna nie jest już używana do decyzji


        # Metryka 'wynik_skalowany_pkt' nie jest już potrzebna do decyzji MCTS
        if MAX_PUNKTY_ROZDANIA > 0:
            wynik_skalowany_pkt = punkty_zdobyte / MAX_PUNKTY_ROZDANIA
            wynik_skalowany_pkt = max(-1.0, min(1.0, wynik_skalowany_pkt))

        wygralismy = False
        if isinstance(stan_symulacji, silnik_gry.Rozdanie):
            wygrana_druzyna = podsumowanie.get('wygrana_druzyna')
            if wygrana_druzyna == self.perspektywa_optymalizacji: wygralismy = True
            elif wygrana_druzyna is None and punkty_zdobyte != 0: print(f"OSTRZEŻENIE SYMULACJI 4p: Brak 'wygrana_druzyna'...")
        else:
            wygrani_gracze_raw = podsumowanie.get('wygrani_gracze', [])
            wygrani_gracze_nazwy = [g.nazwa if hasattr(g, 'nazwa') else g for g in wygrani_gracze_raw]
            if self.perspektywa_optymalizacji in wygrani_gracze_nazwy: wygralismy = True

        # Ustaw kluczowe metryki: Win/Loss (+1/-1) oraz EV (np. +6, -3)
        if wygralismy:
            wynik_zero_jeden = 1.0
            ev_raw_points = float(punkty_zdobyte)
        else:
            wynik_zero_jeden = -1.0
            ev_raw_points = float(-punkty_zdobyte)
        
        # === ZASTOSUJ MODYFIKATORY NAGRODY (osobowość bota) ===
        if self.reward_modifiers:
            mods = self.reward_modifiers
            
            # 1. Mnożnik za kontrakt (wpływa na EV)
            contract_mult = mods.get_contract_multiplier(kontrakt_przed_symulacja)
            ev_raw_points *= contract_mult
            
            # 2. Mnożnik za wygraną/przegraną (wpływa na postrzeganie ryzyka)
            if wygralismy:
                ev_raw_points *= mods.win_multiplier
                wynik_skalowany_normalny *= mods.win_multiplier
            else:
                ev_raw_points *= mods.loss_multiplier
                wynik_skalowany_normalny *= mods.loss_multiplier
            
            # 3. Bonus/kara za akcję prowadzącą do tego węzła (jeśli to faza licytacji)
            if self.akcja and self.faza_wezla != silnik_gry.FazaGry.ROZGRYWKA:
                typ_akcji = self.akcja.get('typ', '')
                if typ_akcji == 'lufa':
                    ev_raw_points += mods.lufa_bonus * MAX_EV_NORMALIZATION
                elif typ_akcji == 'kontra':
                    ev_raw_points += mods.kontra_bonus * MAX_EV_NORMALIZATION
                elif typ_akcji in ['pas', 'pas_lufa']:
                    ev_raw_points += mods.pas_bonus * MAX_EV_NORMALIZATION

        # Oblicz specjalną metrykę skalowaną dla rozgrywki NORMALNEJ
        if kontrakt_przed_symulacja == silnik_gry.Kontrakt.NORMALNA:
             mnoznik_gry = podsumowanie.get('mnoznik_gry', 1)
             punkty_meczu_normal = float(mnoznik_gry) # 1.0, 2.0, lub 3.0
             if MAX_NORMAL_GAME_POINTS > 0:
                 wynik_skalowany_normalny = punkty_meczu_normal / MAX_NORMAL_GAME_POINTS
             else: wynik_skalowany_normalny = 1.0
             if not wygralismy: wynik_skalowany_normalny = -wynik_skalowany_normalny
        else:
            # Dla kontraktów solo (Lepsza, Gorsza) skalowana metryka to po prostu win/loss
            wynik_skalowany_normalny = wynik_zero_jeden

        # Zwróć: (Win/Loss, EV (Raw Points), Scaled Pts (dla rozgrywki Normalnej))
        return (wynik_zero_jeden, ev_raw_points, wynik_skalowany_normalny)

    def propaguj_wynik_wstecz(self, wynik_zero_jeden: float, ev_raw_points: float, wynik_skalowany_normalny: float):
        """
        Propaguje (przekazuje w górę drzewa) wynik symulacji, aktualizując statystyki
        odwiedzin i wyników w węzłach nadrzędnych. 
        Normalizuje EV dla UCT, ale przechowuje surowe EV dla logów.
        """
        wynik_do_uzycia_dla_uct = 0.0
        
        # Wybierz odpowiednią "walutę" do myślenia dla UCT (zawsze znormalizowaną!)
        if self.faza_wezla == silnik_gry.FazaGry.ROZGRYWKA:
            # W ROZGRYWCE: Użyj 'wynik_skalowany_normalny' (to jest już [-1, 1] lub [-3, 3]/3.0)
            wynik_do_uzycia_dla_uct = wynik_skalowany_normalny
        else: 
            # W LICYTACJI (NOWA LOGIKA):
            # Użyj surowego EV, ale ZNORMALIZOWANEGO przez naszą stałą (48.0),
            # aby utrzymać relacje wartości (Lepsza > Gorsza), ale bez niszczenia UCT.
            if MAX_EV_NORMALIZATION > 0:
                wynik_do_uzycia_dla_uct = ev_raw_points / MAX_EV_NORMALIZATION
                # Ogranicz do [-1, 1] na wypadek ekstremalnych wartości (np. lufa x16)
                wynik_do_uzycia_dla_uct = max(-1.0, min(1.0, wynik_do_uzycia_dla_uct))
            else:
                wynik_do_uzycia_dla_uct = wynik_zero_jeden # Fallback

        # Zaktualizuj statystyki tego węzła
        self._ilosc_wizyt += 1
        
        # _wyniki_wygranych (dla UCT) przechowuje teraz ZNORMALIZOWANĄ wartość EV
        self._wyniki_wygranych += wynik_do_uzycia_dla_uct 
        
        # Przechowuj pozostałe metryki oddzielnie do logowania
        self._sum_wynik_zero_jeden += wynik_zero_jeden 
        self._sum_raw_ev += ev_raw_points # Zapisz SUROWE EV

        # Przekaż wszystkie metryki do rodzica (on sam je znormalizuje)
        if self.parent:
            self.parent.propaguj_wynik_wstecz(wynik_zero_jeden, ev_raw_points, wynik_skalowany_normalny)
            
# ==========================================================================
# SEKCJA 4: GŁÓWNA KLASA BOTA MCTS (ZREFRAKTORYZOWANA)
# ==========================================================================

class MCTS_Bot:
    """Implementuje algorytm Monte Carlo Tree Search. Metody publiczne zostały
    zrefaktoryzowane, aby przyjmować AbstractGameEngine."""

    def __init__(self, 
                 stala_eksploracji: float = 1.8, 
                 perfect_information: bool = False,  # Domyślnie FAIR (nie oszukuje)
                 reward_modifiers: Optional[RewardModifiers] = None,  # Osobowość bota
                 personality: Optional[str] = None):  # Lub nazwa predefiniowanej osobowości
        """
        Inicjalizuje bota MCTS.

        Args:
            stala_eksploracji: Stała C w formule UCT, kontrolująca balans między
                               eksploatacją a eksploracją. Domyślnie sqrt(2).
            perfect_information: Czy bot widzi karty przeciwników (False = fair play).
            reward_modifiers: Obiekt RewardModifiers z parametrami osobowości.
            personality: Nazwa predefiniowanej osobowości z BOT_PERSONALITIES.
                         Jeśli podano, nadpisuje reward_modifiers.
        """
        self.stala_eksploracji = stala_eksploracji
        self.perfect_information = perfect_information  # Zapamiętaj tryb
        
        # Ustaw modyfikatory nagrody (osobowość bota)
        if personality and personality in BOT_PERSONALITIES:
            self.reward_modifiers = BOT_PERSONALITIES[personality]
        elif reward_modifiers:
            self.reward_modifiers = reward_modifiers
        else:
            self.reward_modifiers = RewardModifiers()  # Domyślne (neutralne)

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
            if nastepny_wezel is None: break
            aktualny_wezel = nastepny_wezel

        # --- 2. Ekspansja ---
        # Jeśli węzeł nie jest końcowy i nie jest w pełni rozwinięty, stwórz nowe dziecko
        if not aktualny_wezel.czy_wezel_terminalny() and not aktualny_wezel.czy_pelna_ekspansja():
             if aktualny_wezel._nieprzetestowane_akcje:
                  nowe_dziecko = aktualny_wezel.expand()
                  if nowe_dziecko: aktualny_wezel = nowe_dziecko

        # --- 3. Symulacja ---
        # Przeprowadź losową rozgrywkę z aktualnego węzła (może być to nowy liść lub węzeł terminalny)
        if aktualny_wezel: # Sprawdź, czy węzeł istnieje
            wynik_01, ev_raw_points, wynik_norm = aktualny_wezel.symuluj_rozgrywke()
            aktualny_wezel.propaguj_wynik_wstecz(wynik_01, ev_raw_points, wynik_norm)
        else:
             # To nie powinno się zdarzyć, ale zabezpiecza przed błędami
             print("OSTRZEŻENIE MCTS: _wykonaj_pojedyncza_iteracje - aktualny_wezel jest None po selekcji/ekspansji.")

    def znajdz_najlepszy_ruch(self,
                                poczatkowy_stan_gry: AbstractGameEngine, # <-- ZMIANA
                                nazwa_gracza_bota: str,
                                limit_czasu_s: float = 3.0) -> dict:
        """
        Główna metoda bota. Uruchamia algorytm MCTS przez określony czas,
        a następnie wybiera najlepszy ruch.
        Używa "shima" do wyciągnięcia wewnętrznego stanu gry.
        """
        
        # === POCZĄTEK SHIM ADAPTERA ===
        # Sprawdzamy, czy przekazany silnik to ten, który rozumiemy
        if not isinstance(poczatkowy_stan_gry, SixtySixEngine):
            print(f"BŁĄD: MCTS_Bot (jeszcze) nie obsługuje silnika typu {type(poczatkowy_stan_gry)}")
            return {} # Zwróć pustą akcję
            
        # Wyciągamy wewnętrzny, konkretny stan gry (Rozdanie / RozdanieTrzyOsoby)
        stan_wewnetrzny = poczatkowy_stan_gry.game_state
        # === KONIEC SHIM ADAPTERA ===
        
        # Stara logika MCTS, teraz działa na 'stan_wewnetrzny'
        stan_kopia = copy.deepcopy(stan_wewnetrzny) # Kopiujemy stan wewnętrzny
        korzen = MonteCarloTreeSearchNode(
            stan_gry=stan_kopia, # Przekazujemy stan wewnętrzny
            gracz_do_optymalizacji=nazwa_gracza_bota,
            perfect_information=self.perfect_information,
            reward_modifiers=self.reward_modifiers  # Przekazujemy osobowość bota
        )
        
        mozliwe_akcje_korzenia = korzen._nieprzetestowane_akcje
        if len(mozliwe_akcje_korzenia) == 1:
            # print(f"BOT MCTS ({nazwa_gracza_bota}): Wykonuję jedyny możliwy ruch.")
            # Zwróć kopię tej jedynej akcji
            akcja_do_zwrotu = mozliwe_akcje_korzenia[0].copy()
            # Poprawka formatu
            if akcja_do_zwrotu['typ'] == 'zagraj_karte' and 'karta_obj' in akcja_do_zwrotu:
                karta_obj = akcja_do_zwrotu.pop('karta_obj')
                akcja_do_zwrotu['karta'] = {'ranga': karta_obj.ranga.name, 'kolor': karta_obj.kolor.name}
            return akcja_do_zwrotu

        # Sprawdź, czy w ogóle są możliwe ruchy z korzenia
        if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
             print(f"BOT MCTS ({nazwa_gracza_bota}): Brak ruchów do wykonania (faza: {korzen.faza_wezla}).")
             if korzen.faza_wezla not in [silnik_gry.FazaGry.ROZGRYWKA, silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]:
                  mozliwe = korzen._pobierz_mozliwe_akcje()
                  akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                  if akcja_pas:
                       print(f"BOT MCTS ({nazwa_gracza_bota}): Wymuszam akcję PAS (brak ruchów w korzeniu).")
                       return akcja_pas.copy() # Zwróć kopię
             return {} # Zwróć pusty słownik, jeśli nie ma co zrobić

        # --- Główna pętla MCTS ---
        czas_konca = time.time() + limit_czasu_s
        licznik_symulacji = 0
        MIN_SYMULACJI_DO_WCZESNEGO_WYJSCIA = 500 # Minimalna liczba symulacji przed sprawdzeniem
        PRÓG_PEWNEJ_WYGRANEJ = 0.98  
        PRÓG_PEWNEJ_PRZEGRANEJ = -0.98
        while time.time() < czas_konca:
            self._wykonaj_pojedyncza_iteracje(korzen)
            licznik_symulacji += 1

            # ---  Sprawdzenie wczesnego wyjścia ---
            if licznik_symulacji >= MIN_SYMULACJI_DO_WCZESNEGO_WYJSCIA and licznik_symulacji % 100 == 0:
                if not korzen.dzieci: continue

                czy_licytacja_wybor = korzen.faza_wezla != silnik_gry.FazaGry.ROZGRYWKA
                def get_node_value(dziecko: MonteCarloTreeSearchNode) -> float:
                    if dziecko._ilosc_wizyt == 0: return -float('inf')
                    if czy_licytacja_wybor:
                        return dziecko._sum_raw_ev / dziecko._ilosc_wizyt
                    else:
                        return dziecko._wyniki_wygranych / dziecko._ilosc_wizyt
                
                naj_dziecko_wg_wartosci = max(korzen.dzieci, key=get_node_value)
                naj_dziecko_wg_wizyt = max(korzen.dzieci, key=lambda d: d._ilosc_wizyt)
                
                if naj_dziecko_wg_wizyt._ilosc_wizyt > MIN_SYMULACJI_DO_WCZESNEGO_WYJSCIA / max(1, len(korzen.dzieci)):
                    srednia_szansa_wygranej_minmax = 0.0
                    if naj_dziecko_wg_wartosci._ilosc_wizyt > 0:
                        srednia_szansa_wygranej_minmax = naj_dziecko_wg_wartosci._sum_wynik_zero_jeden / naj_dziecko_wg_wartosci._ilosc_wizyt

                    if srednia_szansa_wygranej_minmax >= PRÓG_PEWNEJ_WYGRANEJ:
                        break
                    elif srednia_szansa_wygranej_minmax <= PRÓG_PEWNEJ_PRZEGRANEJ:
                        break
        
        # --- Logowanie (bez zmian) ---
        try:
            czy_licytacja = korzen.faza_wezla != silnik_gry.FazaGry.ROZGRYWKA
            czy_normalna_rozgrywka = (korzen.faza_wezla == silnik_gry.FazaGry.ROZGRYWKA and
                                     korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA)
            etykieta_wartosci = ""
            jednostka = ""
            mnoznik = 1.0
            if czy_licytacja:
                etykieta_wartosci = "Oczekiwana wartość (EV):"
                jednostka = " pkt mecz."
                mnoznik = 1.0
            elif czy_normalna_rozgrywka:
                etykieta_wartosci = "Oczekiwany wynik:"
                jednostka = " pkt mecz."
                mnoznik = MAX_NORMAL_GAME_POINTS
            else:
                etykieta_wartosci = "Szansa na wygraną:"
                jednostka = "%"
                mnoznik = 100.0
            
            # ... (reszta logowania) ...

        except Exception as e:
            print(f"Błąd podczas logowania ewaluacji MCTS: {e}")
            traceback.print_exc()

        # --- Wybór najlepszego ruchu ---
        if not korzen.dzieci:
             print(f"BOT MCTS ({nazwa_gracza_bota}): Nie rozwinięto żadnych dzieci (czas?).")
             if korzen._nieprzetestowane_akcje:
                 print("BOT MCTS: Zwracam pierwszą nieprzetestowaną akcję jako fallback.")
                 akcja_fallback = korzen._nieprzetestowane_akcje[0].copy()
                 # Poprawka formatu
                 if akcja_fallback['typ'] == 'zagraj_karte' and 'karta_obj' in akcja_fallback:
                     karta_obj = akcja_fallback.pop('karta_obj')
                     akcja_fallback['karta'] = {'ranga': karta_obj.ranga.name, 'kolor': karta_obj.kolor.name}
                 return akcja_fallback
             else:
                 mozliwe = korzen._pobierz_mozliwe_akcje()
                 akcja_pas = next((a for a in mozliwe if 'pas' in a.get('typ','')), None)
                 if akcja_pas: return akcja_pas.copy()
             return {}

        czy_licytacja_wybor = korzen.faza_wezla != silnik_gry.FazaGry.ROZGRYWKA

        def get_node_value(dziecko: MonteCarloTreeSearchNode) -> float:
            if dziecko._ilosc_wizyt == 0:
                return -float('inf')
            if czy_licytacja_wybor:
                return dziecko._sum_raw_ev / dziecko._ilosc_wizyt
            else:
                return dziecko._wyniki_wygranych / dziecko._ilosc_wizyt

        najlepsze_dziecko = max(korzen.dzieci, key=get_node_value)
        
        akcja_do_zwrotu = najlepsze_dziecko.akcja.copy()
        
        # === WAŻNA POPRAWKA FORMATU ===
        # Zwracamy akcję w formacie JSON (słownik), a nie z obiektem 'karta_obj'
        if akcja_do_zwrotu['typ'] == 'zagraj_karte' and 'karta_obj' in akcja_do_zwrotu:
            karta_obj = akcja_do_zwrotu.pop('karta_obj') # Usuń stary klucz
            # Dodaj nowy klucz ze zserializowaną kartą
            akcja_do_zwrotu['karta'] = {'ranga': karta_obj.ranga.name, 'kolor': karta_obj.kolor.name}
        
        return akcja_do_zwrotu

    def evaluate_state(self,
                       stan_gry: AbstractGameEngine, # <-- ZMIANA
                       nazwa_gracza_perspektywa: str,
                       limit_symulacji: int = 500) -> Optional[float]:
        """
        Używa MCTS do oszacowania wartości danego stanu gry.
        Używa "shima" do wyciągnięcia wewnętrznego stanu gry.
        """
        
        # === POCZĄTEK SHIM ADAPTERA ===
        if not isinstance(stan_gry, SixtySixEngine):
            print(f"BŁĄD: MCTS_Bot (evaluate) nie obsługuje silnika typu {type(stan_gry)}")
            return None
        stan_wewnetrzny = stan_gry.game_state
        # === KONIEC SHIM ADAPTERA ===

        try:
            stan_kopia = copy.deepcopy(stan_wewnetrzny) # Użyj stanu wewnętrznego
            if stan_kopia.lewa_do_zamkniecia and stan_kopia.kolej_gracza_idx is None:
                stan_kopia.finalizuj_lewe()

            korzen = MonteCarloTreeSearchNode(
                stan_gry=stan_kopia, # Użyj stanu wewnętrznego
                gracz_do_optymalizacji=nazwa_gracza_perspektywa,
                perfect_information=self.perfect_information,
                reward_modifiers=self.reward_modifiers
            )

            if korzen.czy_wezel_terminalny():
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke()
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01

            if not korzen._nieprzetestowane_akcje and not korzen.dzieci:
                print(f"Evaluate state: Brak ruchów po (potencjalnej) finalizacji. Faza: {korzen.faza_wezla}")
                wynik_01, _, wynik_norm = korzen.symuluj_rozgrywke()
                return wynik_norm if korzen.kontrakt_wezla == silnik_gry.Kontrakt.NORMALNA else wynik_01

            for _ in range(limit_symulacji):
                self._wykonaj_pojedyncza_iteracje(korzen)

            if korzen._ilosc_wizyt > 0:
                srednia_nagroda = korzen._wyniki_wygranych / korzen._ilosc_wizyt
                return srednia_nagroda
            else:
                print("Evaluate state: Nie wykonano żadnych symulacji.")
                return None

        except Exception as e:
            print(f"BŁĄD podczas ewaluacji stanu: {e}")
            traceback.print_exc()
            return None # Zwróć None w razie błędu

# ==========================================================================
# SEKCJA 5: ZAAWANSOWANY BOT HEURYSTYCZNY (ZREFRAKTORYZOWANY)
# ==========================================================================

class AdvancedHeuristicBot:
    """
    Bot podejmujący decyzje na podstawie prostych heurystyk i analizy ręki.
    """

    def __init__(self):
        # Definicja "siły" rang (przydatne do sortowania i wybierania kart)
        self.sila_rang = {
            silnik_gry.Ranga.DZIEWIATKA: 0,
            silnik_gry.Ranga.WALET: 1,
            silnik_gry.Ranga.DAMA: 2,
            silnik_gry.Ranga.KROL: 3,
            silnik_gry.Ranga.DZIESIATKA: 4,
            silnik_gry.Ranga.AS: 5,
        }

    def _oblicz_sile_reki(self, reka: list[silnik_gry.Karta]) -> tuple[dict[silnik_gry.Kolor, int], int]:
        """
        Oblicza siłę ręki gracza.
        Zwraca: (słownik {Kolor: siła_koloru}, całkowita_siła)
        Prosta heurystyka: As=6, 10=5, Król=4, Dama=3, Walet=2, 9=1
        """
        sila_kolorow = {kolor: 0 for kolor in silnik_gry.Kolor}
        calkowita_sila = 0
        wartosci_sily = {
            silnik_gry.Ranga.AS: 6, silnik_gry.Ranga.DZIESIATKA: 5, silnik_gry.Ranga.KROL: 4,
            silnik_gry.Ranga.DAMA: 3, silnik_gry.Ranga.WALET: 2, silnik_gry.Ranga.DZIEWIATKA: 1,
        }
        for karta in reka:
            sila = wartosci_sily.get(karta.ranga, 0)
            sila_kolorow[karta.kolor] += sila
            calkowita_sila += sila
        return sila_kolorow, calkowita_sila

    def _wybierz_karte_rozgrywka(self, gracz: silnik_gry.Gracz, rozdanie: Union[silnik_gry.Rozdanie, silnik_gry.RozdanieTrzyOsoby]) -> Optional[silnik_gry.Karta]:
        """ Wybiera kartę do zagrania w fazie ROZGRYWKA. """
        grywalne_karty = [k for k in gracz.reka if rozdanie._waliduj_ruch(gracz, k)]
        if not grywalne_karty:
            return None # Nie ma co zagrać

        # --- Specjalne strategie dla gier solo (tylko jako grający) ---
        if gracz == rozdanie.grajacy:
            if rozdanie.kontrakt == silnik_gry.Kontrakt.LEPSZA:
                # Zagraj najsilniejszą grywalną kartę (wg naszej definicji siły)
                return max(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])
            elif rozdanie.kontrakt == silnik_gry.Kontrakt.GORSZA:
                # Zagraj najsłabszą grywalną kartę
                return min(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])

        # --- Domyślna strategia (Normalna, Bez Pytania, obrona w solo) ---
        # Heurystyka:
        # 1. Jeśli to nie pierwszy ruch w lewie, spróbuj wziąć lewę najwyższą możliwą kartą.
        # 2. Jeśli to pierwszy ruch, zagraj najsilniejszą kartę (prostota).
        # 3. Jeśli nie da się wziąć lewy, zagraj najsłabszą kartę.
        elif rozdanie.kontrakt == silnik_gry.Kontrakt.GORSZA:
            # Obrońca w GORSZEJ również gra najsłabszą legalną kartę.
            return min(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])
        elif rozdanie.kontrakt == silnik_gry.Kontrakt.LEPSZA:
            return min(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])

        if rozdanie.aktualna_lewa: # Jeśli to nie pierwszy ruch
            naj_karta_na_stole = None
            naj_sila = -1
            kolor_wiodacy = rozdanie.aktualna_lewa[0][1].kolor
            karty_atutowe_stole = [(g, k) for g, k in rozdanie.aktualna_lewa if k.kolor == rozdanie.atut]

            if karty_atutowe_stole: # Wygrywa atut
                naj_karta_na_stole = max(karty_atutowe_stole, key=lambda p: self.sila_rang[p[1].ranga])[1]
                naj_sila = self.sila_rang[naj_karta_na_stole.ranga]
            else: # Wygrywa kolor wiodący
                karty_wiodace_stole = [(g, k) for g, k in rozdanie.aktualna_lewa if k.kolor == kolor_wiodacy]
                if karty_wiodace_stole:
                     naj_karta_na_stole = max(karty_wiodace_stole, key=lambda p: self.sila_rang[p[1].ranga])[1]
                     naj_sila = self.sila_rang[naj_karta_na_stole.ranga]

            # Znajdź karty, którymi można wziąć lewę
            karty_wygrywajace = []
            for k in grywalne_karty:
                sila_karty = self.sila_rang[k.ranga]
                if naj_karta_na_stole:
                    if k.kolor == rozdanie.atut and naj_karta_na_stole.kolor != rozdanie.atut:
                        karty_wygrywajace.append(k) # Przebicie atutem
                    elif k.kolor == naj_karta_na_stole.kolor and sila_karty > naj_sila:
                        karty_wygrywajace.append(k) # Nadbicie w kolorze lub atucie
                # Jeśli naj_karta_na_stole jest None (błąd?), traktujemy każdą jako wygrywającą
                else: karty_wygrywajace.append(k)


            if karty_wygrywajace:
                # Zagraj najsilniejszą z wygrywających
                return max(karty_wygrywajace, key=lambda k: self.sila_rang[k.ranga])
            else:
                # Nie da się wziąć - zagraj najsłabszą grywalną
                return min(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])
        else: # Pierwszy ruch w lewie
            # Zagraj najsilniejszą grywalną kartę (prosta heurystyka)
            return max(grywalne_karty, key=lambda k: self.sila_rang[k.ranga])


    def znajdz_najlepszy_ruch(self,
                                poczatkowy_stan_gry: AbstractGameEngine, # <-- ZMIANA
                                nazwa_gracza_bota: str) -> dict:
        """ Główna metoda bota heurystycznego (z adapterem/shimem). """

        # === POCZĄTEK SHIM ADAPTERA ===
        if not isinstance(poczatkowy_stan_gry, SixtySixEngine):
            print(f"BŁĄD: AdvancedHeuristicBot nie obsługuje silnika typu {type(poczatkowy_stan_gry)}")
            return {}
        stan_wewnetrzny = poczatkowy_stan_gry.game_state # Pobierz Rozdanie/RozdanieTrzyOsoby
        # === KONIEC SHIM ADAPTERA ===

        gracz_obj = next((g for g in stan_wewnetrzny.gracze if g and g.nazwa == nazwa_gracza_bota), None)
        if not gracz_obj:
            print(f"BŁĄD BOTA HEURYSTYCZNEGO: Nie znaleziono obiektu gracza {nazwa_gracza_bota}")
            return {} # Zwróć pustą akcję w razie błędu

        faza = stan_wewnetrzny.faza

        # --- Logika Rozgrywki ---
        if faza == silnik_gry.FazaGry.ROZGRYWKA:
            wybrana_karta = self._wybierz_karte_rozgrywka(gracz_obj, stan_wewnetrzny)
            if wybrana_karta:
                # Zwróć akcję w formacie JSON
                return {
                    'typ': 'zagraj_karte', 
                    'karta': {'ranga': wybrana_karta.ranga.name, 'kolor': wybrana_karta.kolor.name}
                }
            else:
                print(f"OSTRZEŻENIE BOTA HEURYSTYCZNEGO: {nazwa_gracza_bota} nie ma kart do zagrania.")
                return {} # Zwróć pustą akcję, jeśli nie ma co zagrać

        # --- Logika Faz Licytacyjnych ---
        mozliwe_akcje = stan_wewnetrzny.get_mozliwe_akcje(gracz_obj)
        if not mozliwe_akcje:
            print(f"OSTRZEŻENIE BOTA HEURYSTYCZNEGO: {nazwa_gracza_bota} nie ma możliwych akcji w fazie {faza}.")
            return {}

        # 1. Faza DEKLARACJA_1
        if faza == silnik_gry.FazaGry.DEKLARACJA_1:
            sila_kolorow, calkowita_sila = self._oblicz_sile_reki(gracz_obj.reka)
            # print(f"BOT HEURYSTYCZNY ({nazwa_gracza_bota}): Siła ręki={calkowita_sila}, Kolory={sila_kolorow}") # Log siły

            prog_bez_pytania = 18
            prog_normalna = 10
            prog_gorsza = 5

            akcje_normalna = [a for a in mozliwe_akcje if a['kontrakt'] == silnik_gry.Kontrakt.NORMALNA]
            akcja_bez_pytania = next((a for a in mozliwe_akcje if a['kontrakt'] == silnik_gry.Kontrakt.BEZ_PYTANIA), None)
            akcja_gorsza = next((a for a in mozliwe_akcje if a['kontrakt'] == silnik_gry.Kontrakt.GORSZA), None)

            if calkowita_sila <= prog_gorsza and akcja_gorsza:
                return akcja_gorsza.copy()
            elif calkowita_sila >= prog_bez_pytania and akcja_bez_pytania:
                naj_kolor = max(sila_kolorow, key=sila_kolorow.get)
                akcja_bp_final = next((a for a in mozliwe_akcje if a['kontrakt'] == silnik_gry.Kontrakt.BEZ_PYTANIA and a['atut'] == naj_kolor), None)
                if akcja_bp_final:
                     return akcja_bp_final.copy()
            elif calkowita_sila >= prog_normalna and akcje_normalna:
                naj_kolor = max(sila_kolorow, key=sila_kolorow.get)
                akcja_norm_final = next((a for a in akcje_normalna if a['atut'] == naj_kolor), None)
                if akcja_norm_final:
                     return akcja_norm_final.copy()

            if akcje_normalna:
                naj_kolor = max(sila_kolorow, key=sila_kolorow.get)
                akcja_norm_fallback = next((a for a in akcje_normalna if a['atut'] == naj_kolor), akcje_normalna[0])
                return akcja_norm_fallback.copy()
            else:
                 return random.choice(mozliwe_akcje).copy()

        # 2. Faza LUFA
        elif faza == silnik_gry.FazaGry.LUFA:
            akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas_lufa'), None)
            if akcja_pas:
                return akcja_pas.copy()
            else:
                 return random.choice(mozliwe_akcje).copy()

        # 3. Faza FAZA_PYTANIA_START
        elif faza == silnik_gry.FazaGry.FAZA_PYTANIA_START:
            akcja_pytanie = next((a for a in mozliwe_akcje if a['typ'] == 'pytanie'), None)
            if akcja_pytanie:
                return akcja_pytanie.copy()
            else:
                 return random.choice(mozliwe_akcje).copy()

        # 4. Faza LICYTACJA
        elif faza == silnik_gry.FazaGry.LICYTACJA:
            akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
            if akcja_pas:
                return akcja_pas.copy()
            else:
                 return random.choice(mozliwe_akcje).copy()

        # 5. Faza FAZA_DECYZJI_PO_PASACH
        elif faza == silnik_gry.FazaGry.FAZA_DECYZJI_PO_PASACH:
            akcja_graj = next((a for a in mozliwe_akcje if a['typ'] == 'graj_normalnie'), None)
            if akcja_graj:
                return akcja_graj.copy()
            else:
                 return random.choice(mozliwe_akcje).copy()

        # --- Fallback dla innych, nieprzewidzianych faz ---
        else:
            return random.choice(mozliwe_akcje).copy()
        
# ==========================================================================
# SEKCJA 6: RANDOMBOT (ZREFRAKTORYZOWANY)
# ==========================================================================
class RandomBot:
    """
    Bot, który zawsze wybiera losową legalną akcję.
    Ten bot jest w pełni generyczny i używa tylko AbstractGameEngine.
    """
    def __init__(self):
        """Inicjalizuje bota."""
        pass # Ten bot nie potrzebuje stanu

    def znajdz_najlepszy_ruch(self,
                                poczatkowy_stan_gry: AbstractGameEngine, # <-- Przyjmuje nowy interfejs
                                nazwa_gracza_bota: str,
                                limit_czasu_s: float = 0.0) -> dict: # Ignoruje limit czasu
        """Wybiera losową legalną akcję używając generycznego interfejsu."""

        # --- NOWA, GENERYCZNA LOGIKA ---
        # Ten bot nie musi wiedzieć, czym jest "Rozdanie".
        # Pyta silnik o legalne akcje i wybiera losową.
        
        try:
            # Użyj generycznej metody z interfejsu
            mozliwe_akcje = poczatkowy_stan_gry.get_legal_actions(nazwa_gracza_bota)
            
            if mozliwe_akcje:
                # Wybierz losową akcję
                wybrana_akcja = random.choice(mozliwe_akcje)
                # Zwróć ją (nie musi być kopia, bo silnik zwraca nowe obiekty)
                return wybrana_akcja
            else:
                # Brak akcji (np. nie nasza tura, lub koniec rozdania)
                return {}
        except Exception as e:
            print(f"BŁĄD BOTA LOSOWEGO (generyczny): {e}")
            traceback.print_exc()
            return {}


# ==========================================================================
# SEKCJA 7: REJESTR ALGORYTMÓW BOTÓW
# ==========================================================================

# Słownik mapujący nazwy algorytmów na funkcje tworzące boty
# Każdy algorytm to funkcja zwracająca instancję bota
#
# UWAGA: MCTS boty są WYŁĄCZONE (zbyt wolne, zasobożerne)
# Stare nazwy przekierowują na NN boty lub heuristic jako fallback

def _create_nn_or_fallback(temperature=0.5, greedy=False, personality=None):
    """Tworzy NN bota lub fallback do heuristic/random."""
    nn_class = _get_nn_bot_class()
    if nn_class:
        return nn_class(temperature=temperature, greedy=greedy, personality=personality)
    else:
        # Fallback do heuristic (lepszy niż random)
        return AdvancedHeuristicBot()

BOT_ALGORITHMS = {
    # === STARE NAZWY (przekierowane na NN) ===
    # Te nazwy są zachowane dla kompatybilności z istniejącymi kontami botów
    'topplayer': lambda: _create_nn_or_fallback(temperature=0.3, greedy=True),
    'szaleniec': lambda: _create_nn_or_fallback(temperature=1.0, personality='aggressive'),
    'gorsza_enjoyer': lambda: _create_nn_or_fallback(temperature=0.5, personality='gorsza_enjoyer'),
    'lepsza_enjoyer': lambda: _create_nn_or_fallback(temperature=0.5, personality='lepsza_enjoyer'),
    'beginner': lambda: _create_nn_or_fallback(temperature=0.3, personality='cautious'),
    'chaotic': lambda: _create_nn_or_fallback(temperature=1.5, personality='chaotic'),
    'counter': lambda: _create_nn_or_fallback(temperature=0.8, personality='aggressive'),
    'nie_lubie_pytac': lambda: _create_nn_or_fallback(temperature=0.5),
    
    # === BOTY SIECI NEURONOWEJ (szybkie, skalowalne) ===
    'nn_topplayer': lambda: _create_nn_or_fallback(temperature=0.3, greedy=True),
    'nn_aggressive': lambda: _create_nn_or_fallback(temperature=1.0, personality='aggressive'),
    'nn_cautious': lambda: _create_nn_or_fallback(temperature=0.3, personality='cautious'),
    'nn_chaotic': lambda: _create_nn_or_fallback(temperature=1.5, personality='chaotic'),
    'nn_calculated': lambda: _create_nn_or_fallback(temperature=0.2, greedy=True, personality='calculated'),
    
    # === INNE TYPY BOTÓW ===
    'heuristic': lambda: AdvancedHeuristicBot(),
    'random': lambda: RandomBot(),
}

# Dostępne nazwy algorytmów (dla walidacji)
DOSTEPNE_ALGORYTMY = list(BOT_ALGORITHMS.keys())


# ==========================================================================
# SEKCJA 8: KONFIGURACJA KONT BOTÓW
# ==========================================================================

# Lista botów do stworzenia w bazie danych
# Format: (NazwaUżytkownika, Algorytm)
# Każdy typ osobowości ma 2 konta

BOTY_DO_STWORZENIA = [
    # === TOPPLAYER (neutralny, optymalny) ===
    ("Szefuncio", "topplayer"),
    ("ProPlayer66", "topplayer"),
    
    # === SZALENIEC (kocha solo i lufy) ===
    ("CRAZZYHAMBURGER", "szaleniec"),
    ("LufaKing", "szaleniec"),
    
    # === GORSZA ENJOYER ===
    ("agreSya", "gorsza_enjoyer"),
    ("AlemamSrake", "gorsza_enjoyer"),
    
    # === LEPSZA ENJOYER ===
    ("Kingme", "lepsza_enjoyer"),
    ("LepszyGracz", "lepsza_enjoyer"),
    
    # === BEGINNER (boi się ryzyka) ===
    ("Brzeszczot", "beginner"),
    ("Krzysiu_zwany_Ibisz", "beginner"),
    
    # === CHAOTIC (nieprzewidywalny) ===
    ("Khaos", "chaotic"),
    ("Krolwicz", "chaotic"),
    
    # === COUNTER (kontruje przeciwników) ===
    ("Kontradmirał", "counter"),
    ("LufaMaster", "counter"),
    
    # === NIE LUBIĘ PYTAĆ ===
    ("Ktopytal", "nie_lubie_pytac"),
    ("NiePytamZ3", "nie_lubie_pytac"),
    
    # === HEURYSTYCZNY (prostszy, przewidywalny) ===
    ("Esssa", "heuristic"),
    ("67676767", "heuristic"),
    
    # === BOTY SIECI NEURONOWEJ (szybkie, skalowalne) ===
    ("NeuralMaster", "nn_topplayer"),
    ("DeepPlayer66", "nn_topplayer"),
    ("AIAgressor", "nn_aggressive"),
    ("NNKiller", "nn_aggressive"),
    ("SafeBot", "nn_cautious"),
    ("Ostrozny_AI", "nn_cautious"),
    ("RandomNeural", "nn_chaotic"),
    ("ChaoticAI", "nn_chaotic"),
    ("Kalkulator", "nn_calculated"),
    ("PrecyzyjnyBot", "nn_calculated"),
]


def stworz_bota(algorytm: str) -> Union[MCTS_Bot, AdvancedHeuristicBot, RandomBot, Any, None]:
    """
    Tworzy instancję bota na podstawie nazwy algorytmu.
    
    Args:
        algorytm: Nazwa algorytmu z BOT_ALGORITHMS
    
    Returns:
        Instancja bota lub None jeśli algorytm nie istnieje
        
    Note:
        Boty 'nn_*' zwracają NeuralNetworkBot (szybki, ~100x szybszy od MCTS)
        Jeśli model NN nie jest dostępny, automatycznie fallback do RandomBot
    """
    if algorytm in BOT_ALGORITHMS:
        return BOT_ALGORITHMS[algorytm]()
    else:
        print(f"OSTRZEŻENIE: Nieznany algorytm bota '{algorytm}'. Dostępne: {DOSTEPNE_ALGORYTMY}")
        return None