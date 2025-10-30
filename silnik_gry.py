# silnik_gry.py

import random
import copy
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Union, Optional

# ==========================================================================
# SEKCJA 1: PODSTAWOWE DEFINICJE (ENUMY, KARTY, TALIA)
# ==========================================================================

class Kolor(Enum):
    """Reprezentuje kolory kart."""
    CZERWIEN = auto() # ♥
    DZWONEK = auto()  # ♦
    ZOLADZ = auto()   # ♣
    WINO = auto()     # ♠

class Ranga(Enum):
    """Reprezentuje rangi kart."""
    DZIEWIATKA = auto() # 9
    WALET = auto()      # J
    DAMA = auto()       # Q
    KROL = auto()       # K
    DZIESIATKA = auto() # 10
    AS = auto()         # A

# Słownik mapujący rangi kart na ich wartości punktowe.
WARTOSCI_KART = {
    Ranga.AS: 11, Ranga.DZIESIATKA: 10, Ranga.KROL: 4,
    Ranga.DAMA: 3, Ranga.WALET: 2, Ranga.DZIEWIATKA: 0,
}

# Słownik do sortowania kart według ustalonej kolejności kolorów.
KOLEJNOSC_KOLOROW_SORT = {
    Kolor.CZERWIEN: 1,
    Kolor.ZOLADZ: 2,
    Kolor.DZWONEK: 3,
    Kolor.WINO: 4,
}

@dataclass(frozen=True)
class Karta:
    """Reprezentuje pojedynczą kartę do gry. Jest niezmienna (frozen=True)."""
    ranga: Ranga
    kolor: Kolor

    @property
    def wartosc(self) -> int:
        """Zwraca wartość punktową karty."""
        return WARTOSCI_KART[self.ranga]

    def __str__(self) -> str:
        """Zwraca czytelną reprezentację karty (np. "As Czerwien")."""
        return f"{self.ranga.name.capitalize()} {self.kolor.name.capitalize()}"

    def __eq__(self, other):
        """Porównuje dwie karty."""
        if not isinstance(other, Karta):
            return NotImplemented
        return self.ranga == other.ranga and self.kolor == other.kolor

    def __hash__(self):
        """Generuje hash dla karty (potrzebne, bo klasa jest frozen)."""
        return hash((self.ranga, self.kolor))

class Talia:
    """Reprezentuje talię 24 kart używaną w grze."""
    def __init__(self):
        """Inicjalizuje talię, tworzy karty i je tasuje."""
        self.karty = self._stworz_pelna_talie()
        self.tasuj()

    def _stworz_pelna_talie(self) -> list['Karta']:
        """Tworzy standardową talię 24 kart."""
        return [Karta(ranga, kolor) for kolor in Kolor for ranga in Ranga]

    def tasuj(self):
        """Tasuje karty w talii."""
        random.shuffle(self.karty)

    def rozdaj_karte(self) -> Optional['Karta']:
        """Pobiera i zwraca jedną kartę z góry talii (lub None, jeśli pusta)."""
        if self.karty:
            return self.karty.pop()
        return None

    def __len__(self) -> int:
        """Zwraca liczbę kart pozostałych w talii."""
        return len(self.karty)

class Kontrakt(Enum):
    """Definiuje możliwe typy kontraktów w grze."""
    NORMALNA = auto()
    BEZ_PYTANIA = auto()
    GORSZA = auto()
    LEPSZA = auto()

class FazaGry(Enum):
    """Definiuje, w jakim stanie znajduje się aktualnie rozdanie."""
    PRZED_ROZDANIEM = auto()         # Stan początkowy
    DEKLARACJA_1 = auto()           # Pierwsza deklaracja po rozdaniu 3/4 kart
    LICYTACJA = auto()              # Faza po pytaniu/zmianie kontraktu
    LUFA = auto()                   # Faza lufy/kontry (wstępna lub finalna)
    ROZGRYWKA = auto()              # Faza zagrywania kart
    PODSUMOWANIE_ROZDANIA = auto()  # Stan po zakończeniu rozdania, przed przejściem do następnego
    ZAKONCZONE = auto()             # Rozdanie zakończone i rozliczone (stan przejściowy?)
    FAZA_PYTANIA_START = auto()     # Gracz zadeklarował NORMALNĄ, może zapytać lub grać Bez Pytania
    FAZA_DECYZJI_PO_PASACH = auto() # Przeciwnicy spasowali, grający decyduje (Gorsza/Lepsza/Graj)

# Podstawowe stawki punktowe dla poszczególnych kontraktów.
STAWKI_KONTRAKTOW = {
    Kontrakt.NORMALNA: 1,
    Kontrakt.BEZ_PYTANIA: 6,
    Kontrakt.GORSZA: 6,
    Kontrakt.LEPSZA: 12,
}

# ==========================================================================
# SEKCJA 2: GRACZE I DRUŻYNY
# ==========================================================================

@dataclass
class Gracz:
    """Reprezentuje pojedynczego gracza w grze."""
    nazwa: str
    reka: list[Karta] = field(default_factory=list)      # Karty trzymane przez gracza
    druzyna: Optional['Druzyna'] = None                # Drużyna gracza (tylko w grze 4-osobowej)
    wygrane_karty: list[Karta] = field(default_factory=list) # Karty zebrane w wygranych lewach
    punkty_meczu: int = 0                               # Punkty w całym meczu (używane też w 3p)

    def __str__(self) -> str:
        """Zwraca nazwę gracza."""
        return self.nazwa

@dataclass
class Druzyna:
    """Reprezentuje drużynę złożoną z dwóch graczy (dla gry 4-osobowej)."""
    nazwa: str
    gracze: list[Gracz] = field(default_factory=list) # Lista graczy w drużynie
    punkty_meczu: int = 0                            # Punkty zdobyte przez drużynę w całym meczu
    przeciwnicy: Optional['Druzyna'] = None          # Referencja do drużyny przeciwnej

    def dodaj_gracza(self, gracz: Gracz):
        """Dodaje gracza do drużyny i ustawia mu referencję do tej drużyny."""
        if len(self.gracze) < 2:
            self.gracze.append(gracz)
            gracz.druzyna = self

# ==========================================================================
# SEKCJA 3: KLASA ROZDANIE (LOGIKA GRY 4-OSOBOWEJ)
# ==========================================================================

class Rozdanie:
    """Zarządza logiką pojedynczego rozdania w grze 4-osobowej (2 vs 2)."""
    def __init__(self, gracze: list[Gracz], druzyny: list[Druzyna], rozdajacy_idx: int):
        # --- Podstawowe informacje ---
        self.gracze = gracze                     # Lista 4 obiektów Gracz
        self.druzyny = druzyny                   # Lista 2 obiektów Druzyna
        self.rozdajacy_idx = rozdajacy_idx       # Indeks gracza rozdającego karty
        self.talia = Talia()                     # Talia kart dla tego rozdania

        # --- Stan kontraktu ---
        self.kontrakt: Optional[Kontrakt] = None # Aktualnie obowiązujący kontrakt
        self.grajacy: Optional[Gracz] = None     # Gracz, który wygrał licytację / zadeklarował kontrakt
        self.atut: Optional[Kolor] = None        # Kolor atutowy (jeśli dotyczy)

        # --- Stan punktacji ---
        self.mnoznik_lufy: int = 1               # Mnożnik punktów z luf/kontr (1, 2, 4, 8...)
        self.punkty_w_rozdaniu = {d.nazwa: 0 for d in druzyny} # Punkty zdobyte w kartach w tym rozdaniu
        self.bonus_z_trzech_kart: bool = False   # Czy zadeklarowano grę solo z 3 kart (x2 pkt)

        # --- Stan rozgrywki ---
        self.kolej_gracza_idx: Optional[int] = None # Indeks gracza, którego jest tura
        self.aktualna_lewa: list[tuple[Gracz, Karta]] = [] # Karty zagrane w bieżącej lewie
        self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None # Kto wziął ostatnią lewę (+10 pkt dla drużyny)
        self.zadeklarowane_meldunki: list[tuple[Gracz, Kolor]] = [] # Przechowuje zadeklarowane pary K+Q

        # --- Stan fazy gry ---
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM # Aktualna faza rozdania
        self.kolejka_licytacji: list[int] = [] # Kolejność graczy w fazie LICYTACJA

        # --- Stan licytacji / lufy ---
        self.historia_licytacji: list[tuple[Gracz, dict]] = [] # Uproszczona historia licytacji
        self.pasujacy_gracze: list[Gracz] = []                # Gracze, którzy spasowali w danej fazie (licytacji/lufy)
        self.oferty_przebicia: list[tuple[Gracz, dict]] = []  # Oferty przebicia (Gorsza/Lepsza) w fazie LICYTACJA
        self.ostatni_podbijajacy: Optional[Gracz] = None      # Gracz, który ostatni dał lufę/kontrę
        self.lufa_challenger: Optional[Gracz] = None          # Przeciwnik, który dał ostatnią lufę (rozpoczyna 'pojedynek')

        # --- Stan gry solo (Gorsza/Lepsza) ---
        self.nieaktywny_gracz: Optional[Gracz] = None # Partner grającego, który nie bierze udziału
        self.liczba_aktywnych_graczy = 4             # Liczba graczy biorących udział w lewie (3 dla solo)

        # --- Stan zakończenia rozdania ---
        self.rozdanie_zakonczone: bool = False          # Czy rozdanie się zakończyło
        self.zwyciezca_rozdania: Optional[Druzyna] = None # Drużyna, która wygrała rozdanie (jeśli ustalony przedwcześnie)
        self.powod_zakonczenia: str = ""                # Opis powodu zakończenia rozdania
        self.podsumowanie: dict = {}                    # Słownik z wynikiem rozdania (generowany na końcu)

        # --- Stan przejściowy lewy ---
        self.lewa_do_zamkniecia = False # Flaga wskazująca na konieczność finalizacji lewy
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None # Zwycięzca lewy przed finalizacją

        # --- Historia szczegółowa ---
        self.szczegolowa_historia: list[dict] = [] # Pełna historia zdarzeń w rozdaniu dla logów

    def _get_player_index(self, player_or_name: Union[Gracz, str, None]) -> Optional[int]:
        """Bezpiecznie znajduje indeks gracza wg obiektu lub nazwy."""
        if player_or_name is None: return None
        target_name = player_or_name.nazwa if isinstance(player_or_name, Gracz) else player_or_name
        try:
            # Użyj generatora, aby znaleźć pierwszego pasującego gracza
            return next(i for i, p in enumerate(self.gracze) if p and p.nazwa == target_name)
        except StopIteration:
            # Tego błędu nie powinno być w normalnej grze
            print(f"BŁĄD KRYTYCZNY (Rozdanie): Nie znaleziono gracza '{target_name}'!")
            return None

    def _sprawdz_koniec_rozdania(self):
        """Sprawdza warunki końca rozdania i jeśli spełnione, wywołuje rozliczenie."""
        # Jeśli już zakończone i rozliczone, nic nie rób
        if self.rozdanie_zakonczone and self.podsumowanie:
            return
        # Jeśli zakończone, ale nierozliczone (np. przez meldunek), rozlicz
        if self.rozdanie_zakonczone and not self.podsumowanie:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            self.rozlicz_rozdanie()
            return

        # Sprawdź, czy skończyły się karty
        aktywni_gracze = [gracz for gracz in self.gracze if gracz != self.nieaktywny_gracz]
        if not any(gracz.reka for gracz in aktywni_gracze):
            self.rozdanie_zakonczone = True
            if not self.powod_zakonczenia: self.powod_zakonczenia = "Rozegrano wszystkie lewy."
            # Specjalny warunek wygranej Gorszej (brak wziętych lew przez grającego)
            if self.kontrakt == Kontrakt.GORSZA and self.grajacy and not any(k for g in self.grajacy.druzyna.gracze for k in g.wygrane_karty):
                 if not self.zwyciezca_rozdania:
                     self.zwyciezca_rozdania = self.grajacy.druzyna
                     self.powod_zakonczenia = f"spełnienie Gorszej"

        # Jeśli rozdanie się zakończyło (z jakiegokolwiek powodu), przejdź do podsumowania i rozlicz
        if self.rozdanie_zakonczone:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            if not self.podsumowanie: self.rozlicz_rozdanie()

    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        """Ustawia wybrany kontrakt, grającego, atut i obsługuje gry solo."""
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        self.ostatni_podbijajacy = self.grajacy # Grający jest pierwszym podbijającym
        self.nieaktywny_gracz = None
        self.liczba_aktywnych_graczy = 4
        # W grach solo (Lepsza/Gorsza) nie ma atutu, a partner grającego staje się nieaktywny
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]:
            self.atut = None
            self.liczba_aktywnych_graczy = 3
            # Znajdź partnera grającego
            partner = next((p for p in self.grajacy.druzyna.gracze if p != self.grajacy), None)
            if partner: self.nieaktywny_gracz = partner

    def _dodaj_log(self, typ: str, **kwargs):
        """Dodaje wpis do szczegółowej historii rozdania, konwertując Enumy na stringi."""
        # Stwórz kopię argumentów, aby nie modyfikować oryginałów
        log_kwargs = kwargs.copy()
        # Przekonwertuj wartości Enum na ich nazwy (stringi)
        for k, v in log_kwargs.items():
            if isinstance(v, Enum):
                log_kwargs[k] = v.name
            elif isinstance(v, dict): # Obsługa zagnieżdżonych słowników (np. akcja)
                nested_dict_copy = copy.deepcopy(v)
                for k2, v2 in nested_dict_copy.items():
                    if isinstance(v2, Enum): nested_dict_copy[k2] = v2.name
                log_kwargs[k] = nested_dict_copy
            elif isinstance(v, list): # Obsługa list (np. wygrani gracze)
                list_copy = [item.name if isinstance(item, Enum) else item for item in v]
                log_kwargs[k] = list_copy
        # Stwórz wpis logu i dodaj do historii
        log = {'typ': typ, **log_kwargs}
        self.szczegolowa_historia.append(log)

    def _zakoncz_faze_lufy(self):
        """Kończy fazę lufy, dobiera karty (jeśli trzeba) i ustawia następną fazę."""
        self.pasujacy_gracze.clear()
        self.lufa_challenger = None

        # Dobierz pozostałe 3 karty, jeśli to była lufa wstępna (po rozdaniu 3 kart)
        if self.gracze and self.gracze[0] and len(self.gracze[0].reka) < 6:
            self.rozdaj_karty(3)

        grajacy_idx = self._get_player_index(self.grajacy)
        if grajacy_idx is None:
             print("BŁĄD KRYTYCZNY: Nie znaleziono grającego w _zakoncz_faze_lufy!")
             return # Zakończ, aby uniknąć dalszych błędów

        # Ustal następną fazę
        if self.kontrakt == Kontrakt.NORMALNA and self.mnoznik_lufy == 1:
            # Jeśli Normalna i nie było lufy, przejdź do pytania
            self.faza = FazaGry.FAZA_PYTANIA_START
            self.kolej_gracza_idx = grajacy_idx
        else:
            # W przeciwnym razie (kontrakt specjalny lub była lufa) przejdź do rozgrywki
            self.faza = FazaGry.ROZGRYWKA
            self.kolej_gracza_idx = grajacy_idx

        # Pomiń turę nieaktywnego gracza w grach solo
        if self.nieaktywny_gracz and self.kolej_gracza_idx is not None and self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
            self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)

    def rozpocznij_nowe_rozdanie(self):
        """Przygotowuje rozdanie: rozdaje pierwsze 3 karty, ustawia fazę i pierwszego gracza."""
        if not (0 <= self.rozdajacy_idx < len(self.gracze)): self.rozdajacy_idx = 0 # Zabezpieczenie
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa, numer_rozdania=len(self.szczegolowa_historia) + 1)
        self.rozdaj_karty(3)
        self.faza = FazaGry.DEKLARACJA_1
        # Turę rozpoczyna gracz po lewej od rozdającego
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % len(self.gracze)

    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        """Zwraca listę możliwych akcji dla gracza w danej fazie."""
        gracz_idx = self._get_player_index(gracz)
        # Akcje są możliwe tylko dla gracza, którego jest tura
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return []

        # --- Faza DEKLARACJA_1 ---
        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            # Deklaracje z atutem (Normalna, Bez Pytania)
            for kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                for kolor in Kolor:
                    akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': kolor})
            # Deklaracje bez atutu (Gorsza, Lepsza)
            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje

        # --- Faza FAZA_PYTANIA_START ---
        if self.faza == FazaGry.FAZA_PYTANIA_START:
            # Gracz zadeklarował NORMALNĄ, może zapytać lub grać BEZ_PYTANIA
            return [{'typ': 'pytanie'}, {'typ': 'nie_pytam'}]

        # --- Faza FAZA_DECYZJI_PO_PASACH ---
        if self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            # Przeciwnicy spasowali, grający decyduje co dalej
            return [
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'graj_normalnie'}, # Zagraj pierwotnie zadeklarowaną NORMALNĄ
            ]

        # --- Faza LICYTACJA ---
        if self.faza == FazaGry.LICYTACJA:
            akcje = [{'typ': 'pas'}]
            # Sprawdź, czy można jeszcze przebić na Gorsza/Lepsza
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)
            if not has_lepsza: # Jeśli nikt nie przebił na Lepszą
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                if not has_gorsza: # Jeśli nikt nie przebił na Gorszą
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            # Przeciwnik grającego może dać lufę
            if self.grajacy and gracz.druzyna != self.grajacy.druzyna:
                # Dodaj kontekst (kontrakt, atut) do akcji lufa
                akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
            return akcje

        # --- Faza LUFA ---
        if self.faza == FazaGry.LUFA:
            if gracz in self.pasujacy_gracze: return [] # Spasował już w tej fazie lufy
            # W 'pojedynku' lufy, tylko grający i challenger mogą podbijać
            if self.lufa_challenger and gracz not in [self.grajacy, self.lufa_challenger]: return []
            # Wymagane sprawdzenia obiektów
            if not self.grajacy or not self.grajacy.druzyna or not self.grajacy.druzyna.przeciwnicy: return []

            # Sprawdź, czy 'do_konca' jest możliwe
            punkty_do_konca = [66 - d.punkty_meczu for d in self.druzyny] # Ile brakuje każdej drużynie do 66
            max_punkty_do_konca = max([0] + punkty_do_konca) # Maksymalna brakująca liczba punktów
            potencjalna_wartosc = self.oblicz_aktualna_stawke(mnoznik_dodatkowy=2) # Wartość po następnym podbiciu

            akcje = []
            if potencjalna_wartosc >= max_punkty_do_konca and max_punkty_do_konca > 0:
                # Jeśli potencjalna stawka jest wystarczająca do wygrania meczu
                akcje.append({'typ': 'do_konca'})
            else:
                # Określ typ podbicia (kontra dla drużyny grającej, lufa dla przeciwników)
                typ_podbicia = 'kontra' if gracz.druzyna == self.grajacy.druzyna else 'lufa'
                # Dodaj kontekst (kontrakt, atut) do akcji
                akcja_podbicia = {'typ': typ_podbicia, 'kontrakt': self.kontrakt, 'atut': self.atut}
                akcje.append(akcja_podbicia)
            # Zawsze można spasować
            akcje.append({'typ': 'pas_lufa'})
            return akcje

        # Domyślnie brak akcji (np. w fazie ROZGRYWKA - obsługiwane przez _waliduj_ruch)
        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        """Przetwarza akcję licytacyjną gracza, aktualizując stan gry."""
        gracz_idx = self._get_player_index(gracz)
        # Ignoruj akcje od gracza, którego nie jest tura
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
             # print(f"OSTRZEŻENIE: Akcja gracza {gracz.nazwa} poza turą.")
             return

        # Dodaj log i zapisz w uproszczonej historii
        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)
        self.historia_licytacji.append((gracz, akcja.copy()))

        # --- Obsługa Akcji w Fazie DEKLARACJA_1 ---
        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                # Sprawdź bonus za grę solo z 3 kart
                kontrakt_specjalny = akcja['kontrakt'] in [Kontrakt.BEZ_PYTANIA, Kontrakt.LEPSZA, Kontrakt.GORSZA]
                if len(gracz.reka) == 3 and kontrakt_specjalny:
                    self.bonus_z_trzech_kart = True
                    self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 3 kart (x2)")
                # Ustaw kontrakt
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                # Przejdź do fazy lufy wstępnej
                self.faza = FazaGry.LUFA
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                # Ustaw turę na gracza po lewej od nowego grającego (pomijając nieaktywnego)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx

        # --- Obsługa Akcji w Fazie LUFA ---
        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                # Podbij stawkę i zakończ lufę
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz
                self._zakoncz_faze_lufy()
                return # Zakończ przetwarzanie akcji

            # Sprawdź, czy drużyna grającego istnieje (zabezpieczenie)
            if not self.grajacy or not self.grajacy.druzyna: return
            druzyna_grajacego = self.grajacy.druzyna

            # Obsługa 'pojedynku' lufy (grający vs challenger)
            if self.lufa_challenger:
                # Jeśli to nie grający ani challenger, ignoruj
                if gracz not in [self.grajacy, self.lufa_challenger]: return
                # Podbicie (lufa/kontra)
                if akcja['typ'] in ['lufa', 'kontra']:
                    self.mnoznik_lufy *= 2
                    self.ostatni_podbijajacy = gracz
                    # Tura przechodzi na drugą stronę pojedynku
                    next_player = self.lufa_challenger if gracz == self.grajacy else self.grajacy
                    idx = self._get_player_index(next_player)
                    if idx is not None: self.kolej_gracza_idx = idx
                elif akcja['typ'] == 'pas_lufa':
                    # Pas kończy pojedynek i całą fazę lufy
                    self._zakoncz_faze_lufy()
            # Obsługa pierwszej lufy od przeciwnika
            else:
                # Tylko przeciwnicy mogą dać pierwszą lufę
                if gracz.druzyna == druzyna_grajacego: return
                if akcja['typ'] == 'lufa':
                    self.mnoznik_lufy *= 2
                    self.ostatni_podbijajacy = gracz
                    self.lufa_challenger = gracz # Ten gracz rozpoczyna pojedynek
                    # Tura wraca do grającego
                    idx = self._get_player_index(self.grajacy)
                    if idx is not None: self.kolej_gracza_idx = idx
                elif akcja['typ'] == 'pas_lufa':
                    self.pasujacy_gracze.append(gracz)
                    # Sprawdź, czy wszyscy przeciwnicy spasowali
                    aktywni_przeciwnicy = []
                    if druzyna_grajacego.przeciwnicy:
                         aktywni_przeciwnicy = [p for p in druzyna_grajacego.przeciwnicy.gracze if p != self.nieaktywny_gracz]
                    if all(p in self.pasujacy_gracze for p in aktywni_przeciwnicy):
                        # Jeśli tak, zakończ fazę lufy
                        self._zakoncz_faze_lufy()
                    else:
                        # Jeśli nie, przekaż turę partnerowi pasującego (jeśli aktywny)
                        partner_idx = (gracz_idx + 2) % len(self.gracze)
                        if self.gracze[partner_idx] != self.nieaktywny_gracz:
                            self.kolej_gracza_idx = partner_idx
                        else: # Jeśli partner nieaktywny, zakończ lufę (nie ma komu grać)
                            self._zakoncz_faze_lufy()

        # --- Obsługa Akcji w Fazie FAZA_PYTANIA_START ---
        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                # Zmień kontrakt na BEZ_PYTANIA i przejdź do lufy finalnej
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                # Turę rozpoczyna przeciwnik po lewej
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     # Pomiń nieaktywnego gracza
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx
            elif akcja['typ'] == 'pytanie':
                # Przejdź do fazy LICYTACJA
                self.faza = FazaGry.LICYTACJA
                # Ustaw kolejkę licytacji (przeciwnicy, potem partner)
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     opp1_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     opp2_idx = (grajacy_idx_nowy + 3) % len(self.gracze)
                     partner_idx = (grajacy_idx_nowy + 2) % len(self.gracze)
                     # Utwórz kolejkę, pomijając nieaktywnego gracza
                     self.kolejka_licytacji = [i for i in [opp1_idx, opp2_idx, partner_idx] if not (self.nieaktywny_gracz and self.gracze[i] == self.nieaktywny_gracz)]
                     # Ustaw turę na pierwszego gracza w kolejce
                     if self.kolejka_licytacji:
                          self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
                     else:
                          print("BŁĄD: Pusta kolejka licytacji po pytaniu!")
                          self._zakoncz_faze_lufy() # Awaryjne zakończenie

        # --- Obsługa Akcji w Fazie FAZA_DECYZJI_PO_PASACH ---
        elif self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            if akcja['typ'] == 'zmiana_kontraktu':
                # Zmień kontrakt na Gorsza/Lepsza i przejdź do lufy finalnej
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], None)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                # Turę rozpoczyna przeciwnik po lewej
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     # Pomiń nieaktywnego gracza
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx
            elif akcja['typ'] == 'graj_normalnie':
                # Graj pierwotnie zadeklarowaną NORMALNĄ, przejdź do rozgrywki
                self.faza = FazaGry.ROZGRYWKA
                # Turę rozpoczyna grający
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx

        # --- Obsługa Akcji w Fazie LICYTACJA ---
        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                # Podbij stawkę, ustaw pretendenta i przejdź do fazy LUFA
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz
                self.lufa_challenger = gracz
                self.faza = FazaGry.LUFA
                # Tura wraca do grającego
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
                self.kolejka_licytacji.clear() # Wyczyść pozostałą kolejkę
                return # Zakończ przetwarzanie

            # Zapisz pas lub przebicie
            if akcja['typ'] == 'pas': self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie': self.oferty_przebicia.append((gracz, akcja))

            # Przekaż turę następnemu w kolejce
            if self.kolejka_licytacji:
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            # Jeśli kolejka pusta, ostatni gracz podjął decyzję (nie rób nic, czekaj na _rozstrzygnij_licytacje_2)

            # Sprawdź, czy wszyscy aktywni gracze (poza grającym) podjęli decyzję
            liczba_decyzji = len(self.pasujacy_gracze) + len(self.oferty_przebicia)
            aktywni_poza_grajacym = self.liczba_aktywnych_graczy - 1
            if liczba_decyzji >= aktywni_poza_grajacym:
                self.kolejka_licytacji.clear() # Upewnij się, że kolejka jest pusta
                self._rozstrzygnij_licytacje_2() # Rozstrzygnij licytację

    def rozdaj_karty(self, ilosc: int):
        """Rozdaje określoną liczbę kart każdemu graczowi po kolei."""
        if not (0 <= self.rozdajacy_idx < len(self.gracze)): self.rozdajacy_idx = 0 # Zabezpieczenie
        start_idx = (self.rozdajacy_idx + 1) % len(self.gracze)
        for _ in range(ilosc):
            for i in range(len(self.gracze)):
                idx = (start_idx + i) % len(self.gracze)
                gracz = self.gracze[idx]
                karta = self.talia.rozdaj_karte()
                # Dodaj kartę do ręki gracza (jeśli istnieje)
                if karta and gracz: gracz.reka.append(karta)
        # Posortuj ręce wszystkich graczy
        for gracz in self.gracze:
            if gracz: gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))

    def rozlicz_rozdanie(self) -> tuple[Optional[Druzyna], int, int, int]:
        """Oblicza wynik zakończonego rozdania i aktualizuje punkty meczu."""
        mnoznik_gry = 1          # Mnożnik za punkty przeciwnika (1, 2, lub 3 dla NORMALNEJ)
        druzyna_wygrana = None   # Drużyna, która wygrała rozdanie
        punkty_meczu = 0         # Punkty do dodania do wyniku meczu

        # --- Ustal zwycięzcę rozdania ---
        if self.zwyciezca_rozdania: # Jeśli zwycięzca ustalony przedwcześnie (np. meldunkiem, Gorsza/Lepsza)
            druzyna_wygrana = self.zwyciezca_rozdania
        elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy:
            # W NORMALNEJ ostatnia lewa decyduje (jeśli nikt nie osiągnął 66 pkt)
            druzyna_wygrana = self.zwyciezca_ostatniej_lewy.druzyna
        elif self.kontrakt == Kontrakt.GORSZA and self.grajacy and not any(k for g in self.grajacy.druzyna.gracze for k in g.wygrane_karty):
            # Warunek wygranej Gorszej (grający nie wziął żadnej lewy)
            druzyna_wygrana = self.grajacy.druzyna
        elif self.grajacy: # W pozostałych przypadkach porównaj punkty w kartach
             punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.druzyna.nazwa, 0)
             przeciwnicy = self.grajacy.druzyna.przeciwnicy
             punkty_przeciwnikow = self.punkty_w_rozdaniu.get(przeciwnicy.nazwa, 0) if przeciwnicy else 0
             # Jeśli grający ma >= 66 pkt
             if punkty_grajacego >= 66: druzyna_wygrana = self.grajacy.druzyna
             # Jeśli przeciwnicy mają >= 66 pkt
             elif punkty_przeciwnikow >= 66 and przeciwnicy: druzyna_wygrana = przeciwnicy
             # Jeśli skończyły się karty i nikt nie ma 66 pkt
             elif not any(g.reka for g in self.gracze if g != self.nieaktywny_gracz):
                  # Wygrywa ten, kto ma więcej punktów w kartach
                  if punkty_grajacego > punkty_przeciwnikow: druzyna_wygrana = self.grajacy.druzyna
                  elif przeciwnicy: druzyna_wygrana = przeciwnicy

        # --- Oblicz punkty meczu ---
        if druzyna_wygrana:
            druzyna_przegrana = druzyna_wygrana.przeciwnicy
            # Awaryjne znalezienie przegranego, jeśli referencja .przeciwnicy zawiedzie
            if not druzyna_przegrana:
                druzyna_przegrana = next((d for d in self.druzyny if d != druzyna_wygrana), None)

            # Pobierz punkty w kartach przegranej drużyny
            punkty_przegranego = self.punkty_w_rozdaniu.get(druzyna_przegrana.nazwa, 0) if druzyna_przegrana else 0
            # Pobierz bazową stawkę kontraktu
            punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)

            # Oblicz mnożnik gry dla NORMALNEJ (zależy od punktów przegranego)
            if self.kontrakt == Kontrakt.NORMALNA:
                mnoznik_gry = 1
                if punkty_przegranego < 33: # Jeśli przegrany ma mniej niż 33 pkt
                    mnoznik_gry = 2
                    # Sprawdź, czy przegrany wziął jakąkolwiek lewę
                    przegrany_wzial_lewe = False
                    if druzyna_przegrana:
                        przegrany_wzial_lewe = any(gracz.wygrane_karty for gracz in druzyna_przegrana.gracze)
                    if not przegrany_wzial_lewe: # Jeśli przegrany nie wziął żadnej lewy
                        mnoznik_gry = 3
                punkty_meczu *= mnoznik_gry # Zastosuj mnożnik gry

            # Zastosuj mnożnik z luf/kontr
            punkty_meczu *= self.mnoznik_lufy
            # Zastosuj bonus za grę z 3 kart
            if self.bonus_z_trzech_kart: punkty_meczu *= 2

            # Dodaj punkty do wyniku meczu zwycięskiej drużyny
            druzyna_wygrana.punkty_meczu += punkty_meczu

            # Przygotuj podsumowanie rozdania
            self.podsumowanie = {
                "wygrana_druzyna": druzyna_wygrana.nazwa,
                "przyznane_punkty": punkty_meczu,
                "kontrakt": self.kontrakt.name if self.kontrakt else "Brak",
                "atut": self.atut.name if self.atut else "Brak",
                "mnoznik_gry": mnoznik_gry,
                "mnoznik_lufy": self.mnoznik_lufy,
                "wynik_w_kartach": self.punkty_w_rozdaniu,
                "powod": self.powod_zakonczenia or "Koniec rozdania",
                "bonus_z_trzech_kart": self.bonus_z_trzech_kart
            }
            self._dodaj_log('koniec_rozdania', **self.podsumowanie) # Dodaj podsumowanie do logów
            return druzyna_wygrana, punkty_meczu, mnoznik_gry, self.mnoznik_lufy
        else:
            # Awaryjne podsumowanie w razie błędu ustalenia zwycięzcy
            print("BŁĄD KRYTYCZNY: Nie można ustalić zwycięzcy w rozlicz_rozdanie!")
            self.podsumowanie = {
                 "wygrana_druzyna": "Brak", "przyznane_punkty": 0, "powod": "Błąd rozliczenia",
                 "kontrakt": self.kontrakt.name if self.kontrakt else "Brak",
                 "atut": self.atut.name if self.atut else "Brak",
                 "mnoznik_gry": 1, "mnoznik_lufy": 1,
                 "wynik_w_kartach": self.punkty_w_rozdaniu, "bonus_z_trzech_kart": False
            }
            # Zwróć wartości domyślne
            return None, 0, 1, 1

    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        """Sprawdza, czy zagranie danej karty przez gracza jest legalne."""
        gracz_idx = self._get_player_index(gracz)
        # 1. Sprawdź, czy to tura gracza i czy ma tę kartę
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return False
        if karta not in gracz.reka: return False
        # 2. Pierwszy ruch w lewie jest zawsze legalny
        if not self.aktualna_lewa: return True

        # 3. Logika dokładania do koloru / przebijania
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor # Kolor pierwszej zagranej karty
        reka_gracza = gracz.reka
        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]

        if karty_do_koloru: # Gracz MA karty do koloru wiodącego
            if karta.kolor != kolor_wiodacy: return False # Musi dołożyć do koloru

            # Sprawdź, czy ktoś już przebił atutem (jeśli kolor wiodący nie jest atutem)
            zostalo_przebite_atutem = False
            if kolor_wiodacy != self.atut and self.atut and any(k.kolor == self.atut for _, k in self.aktualna_lewa):
                zostalo_przebite_atutem = True

            if zostalo_przebite_atutem:
                # Jeśli przebito atutem, gracz musi tylko dołożyć do koloru (nie musi przebijać w kolorze)
                return True
            else:
                # Jeśli nie przebito atutem, sprawdź, czy musi przebić w kolorze
                # Znajdź najwyższą kartę w kolorze wiodącym zagraną do tej pory
                najwyzsza_karta_wiodaca_para = max([p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy], key=lambda p: p[1].ranga.value, default=None)
                if not najwyzsza_karta_wiodaca_para: return True # Jest pierwszą kartą do koloru

                najwyzsza_karta_wiodaca = najwyzsza_karta_wiodaca_para[1]
                # Znajdź karty w ręce gracza, które są wyższe niż najwyższa na stole
                wyzsze_karty_w_rece = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_karta_wiodaca.ranga.value]

                # Jeśli ma wyższe karty, musi zagrać jedną z nich
                if wyzsze_karty_w_rece:
                    return karta in wyzsze_karty_w_rece
                else: # Jeśli nie ma wyższych kart, może zagrać dowolną do koloru
                    return True
        else: # Gracz NIE MA kart do koloru wiodącego
            atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut]
            if self.atut and atuty_w_rece: # Ma atuty
                if karta.kolor != self.atut: return False # Musi dać atut

                # Sprawdź, czy musi przebić wyższym atutem
                atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
                if not atuty_na_stole: return True # Jest pierwszym przebiciem atutem

                najwyzszy_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
                # Znajdź atuty w ręce wyższe niż najwyższy na stole
                wyzsze_atuty_w_rece = [k for k in atuty_w_rece if k.ranga.value > najwyzszy_atut_na_stole.ranga.value]

                # Jeśli ma wyższe atuty, musi zagrać jeden z nich
                if wyzsze_atuty_w_rece:
                    return karta in wyzsze_atuty_w_rece
                else: # Jeśli nie ma wyższych atutów, może zagrać dowolny atut
                    return True
            else: # Nie ma koloru ani atutów
                return True # Może zagrać dowolną kartę

    def _zakoncz_lewe(self):
        """Ustalą zwycięzcę lewy i ustawia flagę do finalizacji (bez przypisywania punktów)."""
        if not self.aktualna_lewa: return

        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]

        zwyciezca_pary = None
        if karty_atutowe: # Jeśli zagrano atuty, wygrywa najwyższy atut
             zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value)
        else: # W przeciwnym razie wygrywa najwyższa karta w kolorze wiodącym
             karty_wiodace = [p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy]
             if karty_wiodace: zwyciezca_pary = max(karty_wiodace, key=lambda p: p[1].ranga.value)

        # Awaryjnie - jeśli coś poszło nie tak, pierwszy gracz wygrywa (nie powinno się zdarzyć)
        if not zwyciezca_pary: zwyciezca_pary = self.aktualna_lewa[0]

        zwyciezca_lewy = zwyciezca_pary[0]

        # Ustaw flagę do finalizacji, zapisz tymczasowego zwycięzcę i zablokuj ruchy
        self.lewa_do_zamkniecia = True
        self.zwyciezca_lewy_tymczasowy = zwyciezca_lewy
        self.kolej_gracza_idx = None # Nikt nie ma tury, dopóki lewa nie jest sfinalizowana

        # --- Sprawdź natychmiastowy koniec rozdania PO zakończeniu lewy ---
        if not self.rozdanie_zakonczone and self.grajacy and self.grajacy.druzyna:
            druzyna_zwyciezcy = zwyciezca_lewy.druzyna
            druzyna_grajacego = self.grajacy.druzyna
            # Oblicz punkty zwycięzcy PO tej lewie (aktualne + punkty z tej lewy)
            punkty_zwyciezcy_teraz = self.punkty_w_rozdaniu.get(druzyna_zwyciezcy.nazwa, 0) + sum(k.wartosc for _, k in self.aktualna_lewa)

            # Warunki końca dla NORMALNA / BEZ_PYTANIA
            if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                if punkty_zwyciezcy_teraz >= 66: # Jeśli ktoś osiągnął 66 pkt
                    self.rozdanie_zakonczone = True
                    self.zwyciezca_rozdania = druzyna_zwyciezcy
                    self.powod_zakonczenia = f"osiągnięcie >= 66 punktów"

            # Sprawdzenia dla gier solo
            przeciwnicy = druzyna_grajacego.przeciwnicy
            if przeciwnicy:
                 # W BEZ_PYTANIA przegrywasz, gdy przeciwnik weźmie lewę
                 if self.kontrakt == Kontrakt.BEZ_PYTANIA and zwyciezca_lewy != self.grajacy:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy
                     self.powod_zakonczenia = f"przejęcie lewy (Bez Pyt.)"
                 # W LEPSZEJ przegrywasz, gdy przeciwnik weźmie lewę
                 elif self.kontrakt == Kontrakt.LEPSZA and druzyna_zwyciezcy != druzyna_grajacego:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy
                     self.powod_zakonczenia = f"przejęcie lewy (Lepsza)"
                 # W GORSZEJ przegrywasz, gdy TY weźmiesz lewę
                 elif self.kontrakt == Kontrakt.GORSZA and zwyciezca_lewy == self.grajacy:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy
                     self.powod_zakonczenia = f"wzięcie lewy (Gorsza)"

    def finalizuj_lewe(self):
        """Finalizuje lewę: czyści stół, przypisuje karty/punkty, ustawia kolejnego gracza."""
        if not self.zwyciezca_lewy_tymczasowy: return # Zabezpieczenie

        zwyciezca_lewy = self.zwyciezca_lewy_tymczasowy
        punkty_w_lewie = sum(k.wartosc for _, k in self.aktualna_lewa) # Oblicz punkty przed czyszczeniem

        # Dodaj log o zakończeniu lewy
        self._dodaj_log('koniec_lewy', zwyciezca=zwyciezca_lewy.nazwa, punkty=punkty_w_lewie, karty=[str(k[1]) for k in self.aktualna_lewa], numer_lewy=6 - len(zwyciezca_lewy.reka) if zwyciezca_lewy.reka else '?')

        # Przypisz punkty do drużyny
        if zwyciezca_lewy.druzyna:
            self.punkty_w_rozdaniu[zwyciezca_lewy.druzyna.nazwa] += punkty_w_lewie

        # Przypisz wygrane karty graczowi
        zwyciezca_lewy.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])

        # Sprawdź, czy to była ostatnia lewa
        liczba_kart_w_grze = len(self.gracze) * 6
        kart_w_lewie = len(self.aktualna_lewa)
        kart_wygranych = sum(len(g.wygrane_karty) for g in self.gracze if g)

        if kart_wygranych + kart_w_lewie == liczba_kart_w_grze:
            self.zwyciezca_ostatniej_lewy = zwyciezca_lewy
            # W NORMALNEJ, dodaj  pkt za ostatnią lewę
            if self.kontrakt == Kontrakt.NORMALNA and zwyciezca_lewy.druzyna:
                 self._dodaj_log('bonus_ostatnia_lewa', gracz=zwyciezca_lewy.nazwa)

        # Resetowanie stanu lewy
        self.aktualna_lewa.clear()
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy = None

        # Ustaw następnego gracza (zwycięzcę lewy), jeśli rozdanie się nie skończyło
        if not self.rozdanie_zakonczone:
             idx = self._get_player_index(zwyciezca_lewy)
             if idx is not None:
                  self.kolej_gracza_idx = idx
                  # Pomiń nieaktywnego gracza w grach solo
                  while self.nieaktywny_gracz and self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                       self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
             else: # Awaryjny fallback
                  print("BŁĄD: Nie znaleziono indeksu zwycięzcy lewy w finalizuj_lewe!")
                  self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % len(self.gracze)

        # Sprawdź koniec rozdania PO finalizacji lewy
        self._sprawdz_koniec_rozdania()

    def zagraj_karte(self, gracz: Gracz, karta: Karta) -> dict:
        """Obsługuje zagranie karty przez gracza, w tym meldunki."""
        # Sprawdź legalność ruchu
        if not self._waliduj_ruch(gracz, karta): return {}

        # Dodaj log zagrania karty
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta))

        punkty_z_meldunku = 0
        # Sprawdź możliwość meldunku (tylko pierwszy ruch w lewie, tylko Normalna/Bez Pytania)
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            # Meldunek możliwy tylko z Królem lub Damą
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                # Znajdź rangę partnera do pary
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                # Sprawdź, czy gracz ma partnera w ręce
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    # Sprawdź, czy ten meldunek nie był już zadeklarowany
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        # Oblicz punkty za meldunek (40 za atutowy, 20 za zwykły)
                        punkty_z_meldunku = 40 if karta.kolor == self.atut else 20
                        # Dodaj punkty i zapisz meldunek
                        if gracz.druzyna:
                             self.punkty_w_rozdaniu[gracz.druzyna.nazwa] += punkty_z_meldunku
                             self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                             self._dodaj_log('meldunek', gracz=gracz.nazwa, punkty=punkty_z_meldunku, kolor=karta.kolor.name)
                             # Sprawdź, czy meldunek kończy rozdanie (osiągnięcie 66 pkt)
                             if self.punkty_w_rozdaniu.get(gracz.druzyna.nazwa, 0) >= 66 and not self.rozdanie_zakonczone:
                                 self.rozdanie_zakonczone = True
                                 self.zwyciezca_rozdania = gracz.druzyna
                                 self.powod_zakonczenia = f"osiągnięcie >= 66 pkt po meldunku"
                                 self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
                                 self.kolej_gracza_idx = None # Zablokuj ruchy
                                 self.rozlicz_rozdanie() # Rozlicz natychmiast
                                 # Zwróć informację o zakończeniu przez meldunek
                                 return {'meldunek_pkt': punkty_z_meldunku, 'rozdanie_skonczone_meldunkiem': True}

        # Usuń kartę z ręki gracza
        if karta in gracz.reka: gracz.reka.remove(karta)
        else:
             # To nie powinno się zdarzyć, jeśli walidacja działa
             print(f"OSTRZEŻENIE: Karta {karta} nie w ręce {gracz.nazwa} podczas zagrywania.")
             return {'meldunek_pkt': punkty_z_meldunku} # Zwróć tylko punkty z meldunku

        # Dodaj kartę do aktualnej lewy
        self.aktualna_lewa.append((gracz, karta))

        wynik = {'meldunek_pkt': punkty_z_meldunku} # Wynik akcji (na razie tylko info o meldunku)

        # Sprawdź, czy lewa się zakończyła
        if len(self.aktualna_lewa) == self.liczba_aktywnych_graczy:
            self._zakoncz_lewe() # Rozpocznij proces zamykania lewy
        else: # Lewa trwa dalej
            # Przekaż turę następnemu graczowi
            if self.kolej_gracza_idx is not None:
                 next_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
                 # Pomiń nieaktywnego gracza
                 while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                      next_idx = (next_idx + 1) % len(self.gracze)
                 self.kolej_gracza_idx = next_idx

        return wynik

    def _rozstrzygnij_licytacje_2(self):
        """Wyłania zwycięzcę po fazie LICYTACJA (po zebraniu decyzji od wszystkich)."""
        # Znajdź najwyższe oferty przebicia (Lepsza > Gorsza)
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza: # Jeśli ktoś przebił na Lepszą
            nowy_grajacy, nowa_akcja = oferty_lepsza[0] # Pierwszy, kto dał Lepszą, wygrywa
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza: # Jeśli nikt nie dał Lepszej, ale ktoś dał Gorszą
                nowy_grajacy, nowa_akcja = oferty_gorsza[0] # Pierwszy, kto dał Gorszą, wygrywa

        if nowy_grajacy and nowa_akcja: # Ktoś przebił (i wygrał licytację)
            # Ustaw nowy kontrakt i grającego
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            # Przejdź do fazy lufy finalnej
            self.pasujacy_gracze.clear(); self.lufa_challenger = None
            self.faza = FazaGry.LUFA
            # Turę rozpoczyna przeciwnik po lewej od nowego grającego
            grajacy_idx_nowy = self._get_player_index(self.grajacy)
            if grajacy_idx_nowy is not None:
                 next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                 # Pomiń nieaktywnego gracza
                 while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                      next_idx = (next_idx + 1) % len(self.gracze)
                 self.kolej_gracza_idx = next_idx
        else: # Nikt nie przebił (wszyscy spasowali)
            # Przejdź do fazy decyzji dla pierwotnego grającego
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            # Tura wraca do pierwotnego grającego
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
            # Wyczyść stan licytacji
            self.pasujacy_gracze.clear(); self.oferty_przebicia.clear()

    def oblicz_aktualna_stawke(self, mnoznik_dodatkowy: int = 1) -> int:
        """Oblicza potencjalną wartość punktową rozdania (ile jest warte w danym momencie)."""
        if not self.kontrakt: return 0
        # Pobierz bazową stawkę kontraktu
        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
        # Oblicz mnożnik gry (zakładając najgorszy scenariusz dla NORMALNEJ)
        mnoznik_gry = 1
        if self.kontrakt == Kontrakt.NORMALNA: mnoznik_gry = 3
        # Zastosuj mnożniki
        punkty_meczu *= mnoznik_gry
        punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart: punkty_meczu *= 2
        punkty_meczu *= mnoznik_dodatkowy # Dodatkowy mnożnik (np. dla sprawdzenia 'do końca')
        return punkty_meczu


# ==========================================================================
# SEKCJA 4: KLASA ROZDANIE TRZY OSOBY (LOGIKA GRY FFA)
# ==========================================================================

class RozdanieTrzyOsoby:
    """Zarządza logiką pojedynczego rozdania w grze 3-osobowej (każdy na każdego)."""
    def __init__(self, gracze: list[Gracz], rozdajacy_idx: int):
        if len(gracze) != 3: raise ValueError("Ta klasa obsługuje dokładnie 3 graczy.")
        # --- Podstawowe informacje ---
        self.gracze = gracze                     # Lista 3 obiektów Gracz
        for gracz in self.gracze: # Inicjalizacja graczy (ważne przy powrocie do lobby)
            if not hasattr(gracz, 'punkty_meczu'): gracz.punkty_meczu = 0
            gracz.reka.clear(); gracz.wygrane_karty.clear()
        self.rozdajacy_idx = rozdajacy_idx       # Indeks gracza rozdającego

        # --- Stan kontraktu ---
        self.grajacy: Optional[Gracz] = None     # Gracz grający solo przeciwko pozostałym dwóm
        self.obroncy: list[Gracz] = []           # Lista dwóch graczy grających przeciwko grającemu
        self.kontrakt: Optional[Kontrakt] = None # Aktualny kontrakt
        self.atut: Optional[Kolor] = None        # Kolor atutowy

        # --- Stan punktacji ---
        self.mnoznik_lufy: int = 1               # Mnożnik z luf/kontr
        self.bonus_z_trzech_kart: bool = False   # W 3p: bonus za grę solo z 4 kart (x2 pkt)
        self.punkty_w_rozdaniu = {g.nazwa: 0 for g in gracze} # Punkty w kartach dla każdego gracza

        # --- Stan rozgrywki ---
        self.kolej_gracza_idx: Optional[int] = None # Indeks gracza w turze
        self.aktualna_lewa: list[tuple[Gracz, Karta]] = [] # Karty w bieżącej lewie
        self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None # Kto wziął ostatnią lewę (+10 pkt dla NORMALNEJ)
        self.zadeklarowane_meldunki: list[tuple[Gracz, Kolor]] = [] # Zadeklarowane pary K+Q

        # --- Stan fazy gry ---
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM # Aktualna faza
        self.kolejka_licytacji: list[int] = []     # Kolejność w fazie LICYTACJA

        # --- Stan licytacji / lufy ---
        self.lufa_challenger: Optional[Gracz] = None # Obrońca, który dał ostatnią lufę
        self.ostatni_podbijajacy: Optional[Gracz] = None # Gracz, który ostatni podbił stawkę
        self.lufa_wstepna: bool = False             # Czy jesteśmy w lufie wstępnej (po 4 kartach)
        self.pasujacy_gracze: list[Gracz] = []     # Gracze, którzy spasowali
        self.oferty_przebicia: list[tuple[Gracz, dict]] = [] # Oferty Gorsza/Lepsza

        # --- Stan zakończenia rozdania ---
        self.podsumowanie: dict = {}              # Wynik rozdania
        self.rozdanie_zakonczone: bool = False    # Czy rozdanie zakończone
        self.zwyciezca_rozdania_info: dict = {}   # Informacje o zwycięzcy (przed pełnym rozliczeniem)

        # --- Stan przejściowy lewy ---
        self.lewa_do_zamkniecia = False         # Czy lewa czeka na finalizację
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None # Zwycięzca lewy przed finalizacją

        # --- Inne ---
        self.szczegolowa_historia: list[dict] = [] # Pełna historia zdarzeń
        self.talia = Talia()                     # Talia kart
        self.liczba_aktywnych_graczy = 3         # Wszyscy grają

    def _get_player_index(self, player_or_name: Union[Gracz, str, None]) -> Optional[int]:
        """Bezpiecznie znajduje indeks gracza wg obiektu lub nazwy."""
        if player_or_name is None: return None
        target_name = player_or_name.nazwa if isinstance(player_or_name, Gracz) else player_or_name
        try:
            return next(i for i, p in enumerate(self.gracze) if p and p.nazwa == target_name)
        except StopIteration:
            print(f"BŁĄD KRYTYCZNY (3p): Nie znaleziono gracza '{target_name}'!")
            return None

    # Metoda _dodaj_log jest identyczna jak w klasie Rozdanie
    _dodaj_log = Rozdanie._dodaj_log

    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        """Ustawia kontrakt, grającego i obrońców w grze 3-osobowej."""
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        # Obrońcami są wszyscy gracze poza grającym
        self.obroncy = [g for g in self.gracze if g != self.grajacy]
        self.ostatni_podbijajacy = self.grajacy
        # W grach solo nie ma atutu
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]: self.atut = None

    def rozpocznij_nowe_rozdanie(self):
        """Przygotowuje rozdanie 3-osobowe: rozdaje 4 karty, ustawia fazę."""
        if not (0 <= self.rozdajacy_idx < 3): self.rozdajacy_idx = 0 # Zabezpieczenie
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa, numer_rozdania=len(self.szczegolowa_historia) + 1)
        self.rozdaj_karty(4) # W 3p rozdaje się 4+4
        self.faza = FazaGry.DEKLARACJA_1
        # Turę rozpoczyna gracz po lewej od rozdającego
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % 3

    def rozdaj_karty(self, ilosc: int):
        """Rozdaje karty w grze 3-osobowej."""
        if not (0 <= self.rozdajacy_idx < 3): self.rozdajacy_idx = 0 # Zabezpieczenie
        start_idx = (self.rozdajacy_idx + 1) % 3
        for _ in range(ilosc):
            for i in range(3):
                idx = (start_idx + i) % 3
                karta = self.talia.rozdaj_karte()
                # Dodaj kartę (jeśli gracz i karta istnieją)
                if karta and self.gracze[idx]: self.gracze[idx].reka.append(karta)
        # Posortuj ręce
        for gracz in self.gracze:
            if gracz: gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))

    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        """Zwraca możliwe akcje dla gracza w grze 3-osobowej."""
        gracz_idx = self._get_player_index(gracz)
        # Akcje tylko dla gracza w turze
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return []

        # --- Logika dla poszczególnych faz ---
        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            # Deklaracje z atutem (Normalna, Bez Pytania)
            for kolor in Kolor:
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.NORMALNA, 'atut': kolor})
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.BEZ_PYTANIA, 'atut': kolor})
            # Deklaracje bez atutu (Gorsza, Lepsza)
            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje

        # --- Faza LUFA (może być wstępna lub finalna) ---
        if self.faza == FazaGry.LUFA:
            # Sprawdź, czy to lufa wstępna (przy 4 kartach)
            czy_wstepna = self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4
            if czy_wstepna:
                if self.lufa_wstepna and gracz == self.grajacy: # Odpowiedź grającego na lufę wstępną
                    return [{'typ': 'kontra'}, {'typ': 'pas_lufa'}]
                elif gracz in self.obroncy and gracz not in self.pasujacy_gracze: # Obrońca może dać lufę wstępną
                    return [{'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut}, {'typ': 'pas_lufa'}]
                else: return [] # Inne przypadki (np. drugi pasujący obrońca w lufie wstępnej)

            # --- Logika dla lufy finalnej (po 8 kartach lub po przebiciu) ---
            if gracz in self.pasujacy_gracze: return [] # Spasował już
            # W 'pojedynku' tylko grający i challenger mogą podbijać
            if self.lufa_challenger and gracz not in [self.grajacy, self.lufa_challenger]: return []
            if not self.grajacy: return [] # Wymagane sprawdzenie

            # Sprawdź możliwość 'do_konca'
            punkty_do_konca = [66 - g.punkty_meczu for g in self.gracze if g]
            max_punkty_do_konca = max([0] + punkty_do_konca)
            potencjalna_wartosc = self.oblicz_aktualna_stawke(mnoznik_dodatkowy=2)

            akcje = []
            if potencjalna_wartosc >= max_punkty_do_konca and max_punkty_do_konca > 0:
                akcje.append({'typ': 'do_konca'})
            else:
                # Określ typ podbicia (kontra dla grającego, lufa dla obrońcy)
                typ_podbicia = 'kontra' if gracz == self.grajacy else 'lufa'
                # Dodaj kontekst (kontrakt, atut)
                akcja_podbicia = {'typ': typ_podbicia, 'kontrakt': self.kontrakt, 'atut': self.atut}
                akcje.append(akcja_podbicia)
            # Zawsze można spasować
            akcje.append({'typ': 'pas_lufa'})
            return akcje

        # --- Pozostałe fazy licytacyjne (jak w 4p) ---
        if self.faza == FazaGry.FAZA_PYTANIA_START:
            return [{'typ': 'pytanie'}, {'typ': 'nie_pytam'}]

        if self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            return [
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'graj_normalnie'},
            ]

        if self.faza == FazaGry.LICYTACJA:
            akcje = [{'typ': 'pas'}]
            # Sprawdź możliwość przebicia
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)
            if not has_lepsza:
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                if not has_gorsza:
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            # Każdy obrońca może dać lufę
            if gracz != self.grajacy:
                 akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
            return akcje

        # Domyślnie brak akcji
        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        """Przetwarza akcję licytacyjną gracza w grze 3-osobowej."""
        gracz_idx = self._get_player_index(gracz)
        # Ignoruj akcje poza turą
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
             # print(f"OSTRZEŻENIE (3p): Akcja gracza {gracz.nazwa} poza turą.")
             return

        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)

        # --- Obsługa Akcji w Fazie DEKLARACJA_1 ---
        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                # Bonus za grę solo z 4 kart
                if akcja['kontrakt'] in [Kontrakt.LEPSZA, Kontrakt.GORSZA, Kontrakt.BEZ_PYTANIA]:
                    self.bonus_z_trzech_kart = True # Używamy tej samej flagi co w 4p
                    self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 4 kart (x2)")
                # Przejdź do lufy wstępnej
                self.faza = FazaGry.LUFA
                # Turę rozpoczyna pierwszy obrońca
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None: self.kolej_gracza_idx = (grajacy_idx_nowy + 1) % 3

        # --- Obsługa Akcji w Fazie LUFA ---
        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                # Podbij stawkę i zakończ lufę
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz
                self._zakoncz_lufe()
                return

            if akcja['typ'] in ['lufa', 'kontra']:
                # Jeśli to pierwsza lufa w lufie finalnej przez obrońcę, ustaw go jako pretendenta
                czy_wstepna = self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4
                if not czy_wstepna and akcja['typ'] == 'lufa' and not self.lufa_challenger and gracz != self.grajacy:
                    self.lufa_challenger = gracz

                # Zaznacz, że była lufa wstępna
                if czy_wstepna and akcja['typ'] == 'lufa':
                    self.lufa_wstepna = True

                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz

                # Tura przechodzi na drugą stronę pojedynku
                next_player = None
                if gracz == self.grajacy: # Grający dał kontrę
                    next_player = self.lufa_challenger # Odpowiada pretendent (jeśli jest)
                    if not next_player: # Jeśli nie ma pretendenta (np. drugi obrońca myśli), tura na następnego obrońcę
                        next_player = next((o for o in self.obroncy if o not in self.pasujacy_gracze), None)
                elif gracz == self.lufa_challenger: # Pretendent dał lufę/kontrę (jeśli zmienił się grający)
                    next_player = self.grajacy # Odpowiada grający
                else: # Drugi obrońca dał lufę (lub pierwszy, jeśli nie było pretendenta)
                    self.lufa_challenger = gracz # Zostaje nowym pretendentem
                    next_player = self.grajacy # Odpowiada grający

                # Ustaw turę
                idx = self._get_player_index(next_player) if next_player else None
                if idx is not None: self.kolej_gracza_idx = idx
                else: # Błąd - nie znaleziono następnego gracza
                     print("BŁĄD (3p LUFA): Nie znaleziono następnego gracza do podbicia!")
                     self._zakoncz_lufe() # Awaryjne zakończenie

            elif akcja['typ'] == 'pas_lufa':
                self.pasujacy_gracze.append(gracz)
                koniec_lufy = False

                # Sprawdź warunki zakończenia lufy
                if gracz == self.grajacy: koniec_lufy = True # Grający pasuje -> koniec
                elif gracz == self.lufa_challenger: koniec_lufy = True # Pretendent pasuje -> koniec
                # Sprawdź, czy obaj obrońcy spasowali
                elif len([p for p in self.pasujacy_gracze if p in self.obroncy]) >= 2:
                    koniec_lufy = True

                if koniec_lufy:
                    self._zakoncz_lufe()
                else: # Lufa trwa dalej
                    # Jeśli pierwszy obrońca spasował (przed wyłonieniem pretendenta), tura na drugiego
                    if not self.lufa_challenger and len(self.pasujacy_gracze) == 1 and gracz in self.obroncy:
                         drugi_obronca = next((o for o in self.obroncy if o != gracz), None)
                         if drugi_obronca:
                              idx = self._get_player_index(drugi_obronca)
                              if idx is not None: self.kolej_gracza_idx = idx
                              else: self._zakoncz_lufe() # Błąd
                         else: self._zakoncz_lufe() # Błąd
                    # Jeśli tura nie została zmieniona (np. drugi obrońca myśli), znajdź następnego aktywnego
                    elif self._get_player_index(gracz) == self.kolej_gracza_idx:
                         next_idx = (gracz_idx + 1) % 3
                         start_check_idx = next_idx # Zapamiętaj punkt startowy pętli
                         while self.gracze[next_idx] in self.pasujacy_gracze:
                               next_idx = (next_idx + 1) % 3
                               if next_idx == start_check_idx: # Wróciliśmy do punktu wyjścia - wszyscy spasowali
                                     koniec_lufy = True; break
                         if koniec_lufy: self._zakoncz_lufe()
                         else: self.kolej_gracza_idx = next_idx

        # --- Obsługa Akcji w Pozostałych Fazach Licytacyjnych (logika podobna do 4p) ---
        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.lufa_wstepna = False
                self.faza = FazaGry.LUFA # Przejdź do lufy finalnej
                # Turę rozpoczyna pierwszy obrońca
                idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
                if idx is not None: self.kolej_gracza_idx = idx
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
                # Ustaw kolejkę licytacji (obaj obrońcy)
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     opp1_idx = (grajacy_idx_nowy + 1) % 3
                     opp2_idx = (grajacy_idx_nowy + 2) % 3
                     self.kolejka_licytacji = [opp1_idx, opp2_idx]
                     if self.kolejka_licytacji: self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)

        elif self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            if akcja['typ'] == 'zmiana_kontraktu':
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], None)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.lufa_wstepna = False
                self.faza = FazaGry.LUFA # Przejdź do lufy finalnej
                # Turę rozpoczyna pierwszy obrońca
                idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
                if idx is not None: self.kolej_gracza_idx = idx
            elif akcja['typ'] == 'graj_normalnie':
                self.faza = FazaGry.ROZGRYWKA
                # Turę rozpoczyna grający
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx

        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                # Podbij stawkę, ustaw pretendenta i przejdź do fazy LUFA
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz
                self.lufa_challenger = gracz # Pierwsza lufa w tej fazie ustawia pretendenta
                self.faza = FazaGry.LUFA
                # Tura wraca do grającego
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
                self.kolejka_licytacji.clear() # Wyczyść pozostałą kolejkę
                return # Zakończ przetwarzanie

            # Zapisz pas lub przebicie
            if akcja['typ'] == 'pas': self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie': self.oferty_przebicia.append((gracz, akcja))

            # Przekaż turę następnemu w kolejce
            if self.kolejka_licytacji:
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            # Jeśli kolejka pusta, ostatni obrońca podjął decyzję

            # Sprawdź, czy obaj obrońcy podjęli decyzję
            if len(self.pasujacy_gracze) + len(self.oferty_przebicia) >= 2:
                self.kolejka_licytacji.clear() # Upewnij się, że pusta
                self._rozstrzygnij_licytacje() # Rozstrzygnij licytację

    def _zakoncz_lufe(self):
        """Kończy fazę lufy w grze 3-osobowej, dobiera karty i ustawia następną fazę."""
        # Sprawdź, czy to była lufa wstępna
        czy_wstepna = self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4
        if czy_wstepna:
            self.rozdaj_karty(4) # Dobierz pozostałe 4 karty
            self.pasujacy_gracze.clear() # Wyczyść pasy z lufy wstępnej
            # Ustal następną fazę po dobraniu kart
            if self.kontrakt == Kontrakt.NORMALNA and not self.lufa_wstepna:
                # Jeśli Normalna i nie było lufy wstępnej, przejdź do pytania
                self.faza = FazaGry.FAZA_PYTANIA_START
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
            else:
                # W przeciwnym razie (kontrakt specjalny lub była lufa wstępna) przejdź do rozgrywki
                self.faza = FazaGry.ROZGRYWKA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
        else: # Lufa finalna
            self._dodaj_log('koniec_licytacji', grajacy=self.grajacy.nazwa if self.grajacy else '?', kontrakt=self.kontrakt.name if self.kontrakt else '?')
            self.faza = FazaGry.ROZGRYWKA
            # Turę rozpoczyna grający
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
        # Zawsze resetuj flagę lufy wstępnej po zakończeniu fazy lufy
        self.lufa_wstepna = False

    def _rozstrzygnij_licytacje(self):
        """Wyłania zwycięzcę po fazie LICYTACJA w grze 3-osobowej."""
        # Znajdź najwyższe oferty przebicia
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza: # Lepsza ma priorytet
            nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza: # Jeśli nie ma Lepszej, weź Gorszą
                nowy_grajacy, nowa_akcja = oferty_gorsza[0]

        if nowy_grajacy and nowa_akcja: # Ktoś przebił i wygrał licytację
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            self.faza = FazaGry.LUFA # Przejdź do lufy finalnej
            self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.lufa_wstepna = False
            # Turę rozpoczyna pierwszy z nowych obrońców
            idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
            if idx is not None: self.kolej_gracza_idx = idx
        else: # Obaj obrońcy spasowali
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            # Tura wraca do pierwotnego grającego
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
            # Wyczyść stan licytacji
            self.pasujacy_gracze.clear(); self.oferty_przebicia.clear()


    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        """Sprawdza legalność ruchu w grze 3-osobowej (logika jak w 4p)."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return False
        if karta not in gracz.reka: return False
        if not self.aktualna_lewa: return True
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        reka_gracza = gracz.reka
        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]
        if karty_do_koloru:
            if karta.kolor != kolor_wiodacy: return False
            zostalo_przebite = False
            if kolor_wiodacy != self.atut and self.atut and any(k.kolor == self.atut for _, k in self.aktualna_lewa): zostalo_przebite = True
            if zostalo_przebite: return True
            naj_karta_wiodaca_p = max([p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy], key=lambda p: p[1].ranga.value, default=None)
            if not naj_karta_wiodaca_p: return True
            naj_karta_wiodaca = naj_karta_wiodaca_p[1]
            wyzsze_karty = [k for k in karty_do_koloru if k.ranga.value > naj_karta_wiodaca.ranga.value]
            return karta in wyzsze_karty if wyzsze_karty else True
        atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut]
        if self.atut and atuty_w_rece:
            if karta.kolor != self.atut: return False
            atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
            if not atuty_na_stole: return True
            naj_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
            wyzsze_atuty = [k for k in atuty_w_rece if k.ranga.value > naj_atut_na_stole.ranga.value]
            return karta in wyzsze_atuty if wyzsze_atuty else True
        return True # Brak koloru i atutów

    def zagraj_karte(self, gracz: Gracz, karta: Karta):
        """Obsługuje zagranie karty w grze 3-osobowej."""
        if not self._waliduj_ruch(gracz, karta): return {'meldunek_pkt': 0}
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta))
        punkty_z_meldunku = 0
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty_z_meldunku = 40 if karta.kolor == self.atut else 20
                        self.punkty_w_rozdaniu[gracz.nazwa] += punkty_z_meldunku
                        self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                        self._dodaj_log('meldunek', gracz=gracz.nazwa, punkty=punkty_z_meldunku)
                        if self.punkty_w_rozdaniu.get(gracz.nazwa, 0) >= 66 and not self.rozdanie_zakonczone:
                            self.rozdanie_zakonczone = True
                            powod_meldunek = f"osiągnięcie >= 66 pkt po meldunku"
                            if gracz == self.grajacy: self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': powod_meldunek}
                            else: self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': powod_meldunek + " obrońcy"}
                            self.faza = FazaGry.PODSUMOWANIE_ROZDANIA; self.kolej_gracza_idx = None
                            self.rozlicz_rozdanie()
                            return {'meldunek_pkt': punkty_z_meldunku, 'rozdanie_skonczone_meldunkiem': True}

        if karta in gracz.reka: gracz.reka.remove(karta)
        else: print(f"OSTRZEŻENIE (3p): Karta {karta} nie w ręce {gracz.nazwa}."); return {'meldunek_pkt': punkty_z_meldunku}
        self.aktualna_lewa.append((gracz, karta))
        wynik = {'meldunek_pkt': punkty_z_meldunku}
        if len(self.aktualna_lewa) == self.liczba_aktywnych_graczy: self._zakoncz_lewe()
        else:
            if self.kolej_gracza_idx is not None: self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
        return wynik

    def _zakoncz_lewe(self):
        """Rozpoczyna zamykanie lewy w grze 3-osobowej."""
        if not self.aktualna_lewa: return
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]
        zwyciezca_pary = None
        if karty_atutowe: zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value)
        else:
             karty_wiodace = [p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy]
             if karty_wiodace: zwyciezca_pary = max(karty_wiodace, key=lambda p: p[1].ranga.value)
        if not zwyciezca_pary: zwyciezca_pary = self.aktualna_lewa[0]
        zwyciezca = zwyciezca_pary[0]
        self.lewa_do_zamkniecia = True; self.zwyciezca_lewy_tymczasowy = zwyciezca; self.kolej_gracza_idx = None
        # Sprawdź natychmiastowy koniec rozdania
        if not self.rozdanie_zakonczone and self.grajacy:
            przegrana_grajacego = False; powod = ""
            if self.kontrakt == Kontrakt.LEPSZA and zwyciezca in self.obroncy: przegrana_grajacego = True; powod = f"przejęcie lewy (Lepsza)"
            elif self.kontrakt == Kontrakt.GORSZA and zwyciezca == self.grajacy: przegrana_grajacego = True; powod = f"wzięcie lewy (Gorsza)"
            elif self.kontrakt == Kontrakt.BEZ_PYTANIA and zwyciezca in self.obroncy: przegrana_grajacego = True; powod = f"przejęcie lewy (Bez Pyt.)"
            if przegrana_grajacego:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': powod}
                self.faza = FazaGry.PODSUMOWANIE_ROZDANIA # Zmień fazę od razu
                if not self.podsumowanie: # Upewnij się, że robisz to tylko raz
                    self.rozlicz_rozdanie()


    def finalizuj_lewe(self):
        """Finalizuje lewę w grze 3-osobowej."""
        if not self.zwyciezca_lewy_tymczasowy: return
        zwyciezca = self.zwyciezca_lewy_tymczasowy
        punkty_w_lewie = sum(k.wartosc for _, k in self.aktualna_lewa)
        self._dodaj_log('koniec_lewy', zwyciezca=zwyciezca.nazwa, punkty=punkty_w_lewie, karty=[str(k[1]) for k in self.aktualna_lewa])
        self.punkty_w_rozdaniu[zwyciezca.nazwa] += punkty_w_lewie
        zwyciezca.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])
        # Sprawdź ostatnią lewę (24 karty)
        kart_w_lewie = len(self.aktualna_lewa)
        kart_wygranych = sum(len(g.wygrane_karty) for g in self.gracze if g)
        
        if kart_wygranych + kart_w_lewie == 24: # 3 graczy * 8 kart
            self.zwyciezca_ostatniej_lewy = zwyciezca
        self.aktualna_lewa.clear(); self.lewa_do_zamkniecia = False; self.zwyciezca_lewy_tymczasowy = None
        # Ustaw następnego gracza
        if not self.rozdanie_zakonczone:
             idx = self._get_player_index(zwyciezca)
             if idx is not None: self.kolej_gracza_idx = idx
             else: print("BŁĄD (3p)..."); self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % 3
        # Zawsze sprawdzaj koniec po finalizacji
        self._sprawdz_koniec_rozdania()

    def _sprawdz_koniec_rozdania(self):
        """Sprawdza warunki końca rozdania w grze 3-osobowej."""
        if self.rozdanie_zakonczone and self.podsumowanie: return
        if self.rozdanie_zakonczone and not self.podsumowanie:
             if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
             print("OSTRZEŻENIE: _sprawdz_koniec (3p) - rozdanie zakończone, próba rozliczenia.")
             self.rozlicz_rozdanie(); return

        # Sprawdź warunki punktowe (>= 66)
        if self.grajacy and not self.rozdanie_zakonczone:
            for obronca in self.obroncy:
                if self.punkty_w_rozdaniu.get(obronca.nazwa, 0) >= 66:
                     if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                          self.rozdanie_zakonczone = True
                          self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': f"osiągnięcie >= 66 pkt przez obronę"}; break
            if not self.rozdanie_zakonczone and self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0) >= 66:
                 if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                      self.rozdanie_zakonczone = True
                      self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': f"osiągnięcie >= 66 pkt"}

        # Sprawdź koniec kart
        if not self.rozdanie_zakonczone and not any(gracz.reka for gracz in self.gracze if gracz):
            self.rozdanie_zakonczone = True
            if not self.zwyciezca_rozdania_info and self.grajacy:
                punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0)
                punkty_obrony_sum = sum(self.punkty_w_rozdaniu.get(o.nazwa, 0) for o in self.obroncy)
                if self.kontrakt == Kontrakt.GORSZA: self.zwyciezca_rozdania_info = {'powod': "nie wzięcie żadnej lewy"}
                elif self.kontrakt == Kontrakt.LEPSZA: self.zwyciezca_rozdania_info = {'powod': "wzięcie wszystkich lew"}
                elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy:
                    if self.zwyciezca_ostatniej_lewy == self.grajacy: self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "wzięcie ostatniej lewy"}
                    else: self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': "wzięcie ostatniej lewy przez obronę"}
                elif punkty_grajacego > punkty_obrony_sum: self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "więcej punktów na koniec"}
                else: self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': "mniej lub tyle samo punktów na koniec"}
            elif not self.grajacy: self.zwyciezca_rozdania_info = {'powod': "Błąd - brak grającego"}

        # Jeśli zakończone, ustaw fazę i rozlicz
        if self.rozdanie_zakonczone:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            if not self.podsumowanie: self.rozlicz_rozdanie()

    def rozlicz_rozdanie(self):
        """Oblicza wynik rozdania 3-osobowego i aktualizuje punkty meczu."""
        wygrani = []
        punkty_meczu = 0
        mnoznik_gry = 1
        powod = self.zwyciezca_rozdania_info.get('powod', 'Koniec kart') if self.zwyciezca_rozdania_info else 'Koniec kart'

        # 1. Ustal zwycięzców
        if self.zwyciezca_rozdania_info and 'wygrani' in self.zwyciezca_rozdania_info:
            wygrani = self.zwyciezca_rozdania_info.get('wygrani', [])
        elif self.grajacy: # Fallback
             punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0)
             punkty_obrony_sum = sum(self.punkty_w_rozdaniu.get(o.nazwa, 0) for o in self.obroncy)
             if self.kontrakt == Kontrakt.GORSZA: wygrani = [self.grajacy] if not any(self.grajacy.wygrane_karty) else self.obroncy
             elif self.kontrakt == Kontrakt.LEPSZA: wygrani = [self.grajacy] if not any(o.wygrane_karty for o in self.obroncy) else self.obroncy
             elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy: wygrani = [self.grajacy] if self.zwyciezca_ostatniej_lewy == self.grajacy else self.obroncy
             elif punkty_grajacego > punkty_obrony_sum: wygrani = [self.grajacy]
             else: wygrani = self.obroncy
             if not wygrani: print("BŁĄD KRYTYCZNY (fallback, 3p): Nie ustalono zwycięzcy!")
        else: print("BŁĄD KRYTYCZNY (rozlicz, 3p): Brak grającego!")

        # 2. Oblicz punkty
        if wygrani:
            punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0) if self.kontrakt else 0
            if self.kontrakt == Kontrakt.NORMALNA:
                mnoznik_gry = 1
                if self.grajacy in wygrani:
                    punkty_obrony = sum(self.punkty_w_rozdaniu.get(o.nazwa, 0) for o in self.obroncy)
                    if punkty_obrony < 33: mnoznik_gry = 2
                    if punkty_obrony == 0: mnoznik_gry = 3
                else: # Obrona wygrała
                    punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0) if self.grajacy else 0
                    if punkty_grajacego < 33: mnoznik_gry = 2
                    if punkty_grajacego == 0: mnoznik_gry = 3
            punkty_meczu *= mnoznik_gry; punkty_meczu *= self.mnoznik_lufy
            if self.bonus_z_trzech_kart: punkty_meczu *= 2
            # Zastosuj punkty
            punkty_do_dodania = punkty_meczu // len(wygrani) if len(wygrani) > 0 else 0
            for zwyciezca in wygrani:
                if zwyciezca: zwyciezca.punkty_meczu += punkty_do_dodania

        # 3. Stwórz podsumowanie
        self.podsumowanie = {
            "wygrani_gracze": [g.nazwa for g in wygrani if g],
            "przyznane_punkty": punkty_meczu, # Całkowita pula punktów
            "kontrakt": self.kontrakt.name if self.kontrakt else "Brak",
            "atut": self.atut.name if self.atut else "Brak",
            "mnoznik_gry": mnoznik_gry, "mnoznik_lufy": self.mnoznik_lufy,
            "wynik_w_kartach": self.punkty_w_rozdaniu, "powod": powod,
            "bonus_z_trzech_kart": self.bonus_z_trzech_kart
        }
        if not wygrani: # Jeśli wystąpił błąd
            self.podsumowanie["wygrani_gracze"] = ["Brak"]; self.podsumowanie["przyznane_punkty"] = 0; self.podsumowanie["powod"] = "Błąd rozliczenia"
            print("BŁĄD KRYTYCZNY: Podsumowanie (3p) - nie ustalono zwycięzcy!")

        self._dodaj_log('koniec_rozdania', **self.podsumowanie)

    def oblicz_aktualna_stawke(self, mnoznik_dodatkowy: int = 1) -> int:
        """Oblicza potencjalną wartość punktową rozdania (3 os.)."""
        if not self.kontrakt: return 0
        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
        mnoznik_gry = 1
        if self.kontrakt == Kontrakt.NORMALNA: mnoznik_gry = 3 # Załóż max
        punkty_meczu *= mnoznik_gry; punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart: punkty_meczu *= 2
        punkty_meczu *= mnoznik_dodatkowy
        return punkty_meczu