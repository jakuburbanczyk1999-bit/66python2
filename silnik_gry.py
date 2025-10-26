# silnik_gry.py (Kompletna wersja z poprawkami ValueError i AttributeError)
import random
import copy # Dodano import copy
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Union, Optional

# ==========================================================================
# === 1. PODSTAWOWE DEFINICJE (KARTY, TALIA, ENUMY) ===
# ==========================================================================

class Kolor(Enum):
    CZERWIEN = auto()
    DZWONEK = auto()
    ZOLADZ = auto()
    WINO = auto()

class Ranga(Enum):
    DZIEWIATKA = auto()
    WALET = auto()
    DAMA = auto()
    KROL = auto()
    DZIESIATKA = auto()
    AS = auto()

WARTOSCI_KART = {
    Ranga.AS: 11, Ranga.DZIESIATKA: 10, Ranga.KROL: 4,
    Ranga.DAMA: 3, Ranga.WALET: 2, Ranga.DZIEWIATKA: 0,
}

KOLEJNOSC_KOLOROW_SORT = {
    Kolor.CZERWIEN: 1, # Kier
    Kolor.ZOLADZ: 2,   # Trefl
    Kolor.DZWONEK: 3,  # Karo
    Kolor.WINO: 4,     # Pik
}

@dataclass(frozen=True)
class Karta:
    """Reprezentuje pojedynczą kartę do gry."""
    ranga: Ranga
    kolor: Kolor

    @property
    def wartosc(self) -> int:
        return WARTOSCI_KART[self.ranga]

    def __str__(self) -> str:
        return f"{self.ranga.name.capitalize()} {self.kolor.name.capitalize()}"

    def __eq__(self, other):
        if not isinstance(other, Karta):
            return NotImplemented
        return self.ranga == other.ranga and self.kolor == other.kolor

    def __hash__(self):
        return hash((self.ranga, self.kolor))

class Talia:
    """Reprezentuje talię 24 kart."""
    def __init__(self):
        self.karty = self._stworz_pelna_talie()
        self.tasuj()

    def _stworz_pelna_talie(self) -> list['Karta']:
        return [Karta(ranga, kolor) for kolor in Kolor for ranga in Ranga]

    def tasuj(self):
        random.shuffle(self.karty)

    def rozdaj_karte(self) -> Optional['Karta']:
        if self.karty:
            return self.karty.pop()
        return None

    def __len__(self) -> int:
        return len(self.karty)

class Kontrakt(Enum):
    """Definiuje możliwe typy kontraktów w grze."""
    NORMALNA = auto()
    BEZ_PYTANIA = auto()
    GORSZA = auto()
    LEPSZA = auto()

class FazaGry(Enum):
    """Definiuje, w jakim stanie znajduje się aktualnie rozdanie."""
    PRZED_ROZDANIEM = auto()
    DEKLARACJA_1 = auto()
    LICYTACJA = auto()
    LUFA = auto()
    ROZGRYWKA = auto()
    PODSUMOWANIE_ROZDANIA = auto()
    ZAKONCZONE = auto()
    FAZA_PYTANIA_START = auto()
    FAZA_DECYZJI_PO_PASACH = auto()

STAWKI_KONTRAKTOW = {
    Kontrakt.NORMALNA: 1,
    Kontrakt.BEZ_PYTANIA: 6,
    Kontrakt.GORSZA: 6,
    Kontrakt.LEPSZA: 12,
}

# ==========================================================================
# === 2. GRACZE I DRUŻYNY ===
# ==========================================================================

@dataclass
class Gracz:
    """Reprezentuje pojedynczego gracza."""
    nazwa: str
    reka: list[Karta] = field(default_factory=list)
    druzyna: Optional['Druzyna'] = None
    wygrane_karty: list[Karta] = field(default_factory=list)
    punkty_meczu: int = 0 # Dla 3p i przechowywania wyniku

    def __str__(self) -> str:
        return self.nazwa

@dataclass
class Druzyna:
    """Reprezentuje drużynę złożoną z dwóch graczy (dla gry 4-osobowej)."""
    nazwa: str
    gracze: list[Gracz] = field(default_factory=list)
    punkty_meczu: int = 0
    przeciwnicy: Optional['Druzyna'] = None

    def dodaj_gracza(self, gracz: Gracz):
        """Dodaje gracza do drużyny i ustawia mu referencję do tej drużyny."""
        if len(self.gracze) < 2:
            self.gracze.append(gracz)
            gracz.druzyna = self

# ==========================================================================
# === 3. KLASA ROZDANIE (GRA 4-OSOBOWA) ===
# ==========================================================================

class Rozdanie:
    """Zarządza logiką pojedynczego rozdania w grze 4-osobowej (2 vs 2)."""
    def __init__(self, gracze: list[Gracz], druzyny: list[Druzyna], rozdajacy_idx: int):
        self.gracze = gracze
        self.druzyny = druzyny
        self.rozdajacy_idx = rozdajacy_idx
        self.talia = Talia()
        self.kontrakt: Optional[Kontrakt] = None
        self.grajacy: Optional[Gracz] = None
        self.atut: Optional[Kolor] = None
        self.mnoznik_lufy: int = 1
        self.punkty_w_rozdaniu = {d.nazwa: 0 for d in druzyny}
        self.kolej_gracza_idx: Optional[int] = None
        self.aktualna_lewa: list[tuple[Gracz, Karta]] = []
        self.zadeklarowane_meldunki: list[tuple[Gracz, Kolor]] = []
        self.rozdanie_zakonczone: bool = False
        self.zwyciezca_rozdania: Optional[Druzyna] = None
        self.powod_zakonczenia: str = ""
        self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM
        self.historia_licytacji: list[tuple[Gracz, dict]] = []
        self.szczegolowa_historia: list[dict] = []
        self.pasujacy_gracze: list[Gracz] = []
        self.oferty_przebicia: list[tuple[Gracz, dict]] = []
        self.nieaktywny_gracz: Optional[Gracz] = None # Dla gier solo (Lepsza/Gorsza)
        self.liczba_aktywnych_graczy = 4
        self.ostatni_podbijajacy: Optional[Gracz] = None
        self.lufa_challenger: Optional[Gracz] = None # Gracz, który dał ostatnią lufę
        self.podsumowanie: dict = {} # Wynik rozdania
        self.lewa_do_zamkniecia = False # Flaga wskazująca na konieczność finalizacji lewy
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None # Zwycięzca lewy przed finalizacją
        self.bonus_z_trzech_kart: bool = False # Czy zadeklarowano grę solo z 3 kart
        self.kolejka_licytacji: list[int] = [] # Kolejność graczy w fazie LICYTACJA

    def _get_player_index(self, player_or_name: Union[Gracz, str, None]) -> Optional[int]:
        """Bezpiecznie znajduje indeks gracza wg obiektu lub nazwy."""
        if player_or_name is None: return None
        target_name = player_or_name.nazwa if isinstance(player_or_name, Gracz) else player_or_name
        try:
            return next(i for i, p in enumerate(self.gracze) if p and p.nazwa == target_name)
        except StopIteration:
            print(f"BŁĄD KRYTYCZNY (Rozdanie): Nie znaleziono gracza '{target_name}'!")
            return None

    def _sprawdz_koniec_rozdania(self):
        """Sprawdza warunki końca rozdania i wywołuje rozliczenie."""
        if self.rozdanie_zakonczone:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            if not self.podsumowanie: self.rozlicz_rozdanie()
            return

        aktywni_gracze = [gracz for gracz in self.gracze if gracz != self.nieaktywny_gracz]
        if not any(gracz.reka for gracz in aktywni_gracze):
            self.rozdanie_zakonczone = True
            if not self.powod_zakonczenia: self.powod_zakonczenia = "Rozegrano wszystkie lewy."
            if self.kontrakt == Kontrakt.GORSZA and self.grajacy and not any(k for g in self.grajacy.druzyna.gracze for k in g.wygrane_karty):
                 if not self.zwyciezca_rozdania: self.zwyciezca_rozdania = self.grajacy.druzyna; self.powod_zakonczenia = f"spełnienie Gorszej"

        if self.rozdanie_zakonczone:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA: self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            if not self.podsumowanie: self.rozlicz_rozdanie()

    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        """Ustawia wybrany kontrakt i związane z nim parametry."""
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        self.ostatni_podbijajacy = self.grajacy
        self.nieaktywny_gracz = None
        self.liczba_aktywnych_graczy = 4
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]:
            self.atut = None
            self.liczba_aktywnych_graczy = 3
            partner = next((p for p in self.grajacy.druzyna.gracze if p != self.grajacy), None)
            if partner: self.nieaktywny_gracz = partner

    def _dodaj_log(self, typ: str, **kwargs):
        """Dodaje wpis do historii, konwertując Enumy na stringi (pracuje na kopiach)."""
        log_kwargs = kwargs.copy()
        for k, v in log_kwargs.items():
            if isinstance(v, Enum): log_kwargs[k] = v.name
            elif isinstance(v, dict):
                nested_dict_copy = copy.deepcopy(v)
                for k2, v2 in nested_dict_copy.items():
                    if isinstance(v2, Enum): nested_dict_copy[k2] = v2.name
                log_kwargs[k] = nested_dict_copy
            elif isinstance(v, list):
                list_copy = [item.name if isinstance(item, Enum) else item for item in v]
                log_kwargs[k] = list_copy
        log = {'typ': typ, **log_kwargs}
        self.szczegolowa_historia.append(log)

    def _zakoncz_faze_lufy(self):
        """Kończy fazę lufy, dobiera karty (jeśli trzeba) i ustawia następną fazę."""
        self.pasujacy_gracze.clear()
        self.lufa_challenger = None

        if self.gracze and self.gracze[0] and len(self.gracze[0].reka) < 6:
            self.rozdaj_karty(3)

        grajacy_idx = self._get_player_index(self.grajacy)
        if grajacy_idx is None:
             print("BŁĄD KRYTYCZNY: Nie znaleziono grającego w _zakoncz_faze_lufy!"); return

        if self.kontrakt == Kontrakt.NORMALNA and self.mnoznik_lufy == 1:
            self.faza = FazaGry.FAZA_PYTANIA_START
            self.kolej_gracza_idx = grajacy_idx
        else:
            self.faza = FazaGry.ROZGRYWKA
            self.kolej_gracza_idx = grajacy_idx
        if self.nieaktywny_gracz and self.kolej_gracza_idx is not None and self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
            self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)

    def rozpocznij_nowe_rozdanie(self):
        """Przygotowuje rozdanie: rozdaje 3 karty, ustawia fazę i pierwszego gracza."""
        if not (0 <= self.rozdajacy_idx < len(self.gracze)): self.rozdajacy_idx = 0
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa)
        self.rozdaj_karty(3)
        self.faza = FazaGry.DEKLARACJA_1
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % len(self.gracze)

    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        """Zwraca listę możliwych akcji dla gracza w danej fazie."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return []

        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            for kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                for kolor in Kolor:
                    akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': kolor})
            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje

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
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)
            if not has_lepsza:
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                if not has_gorsza:
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            if self.grajacy and gracz.druzyna != self.grajacy.druzyna:
                akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
            return akcje

        if self.faza == FazaGry.LUFA:
            if gracz in self.pasujacy_gracze: return []
            if self.lufa_challenger and gracz not in [self.grajacy, self.lufa_challenger]: return []
            if not self.grajacy or not self.grajacy.druzyna or not self.grajacy.druzyna.przeciwnicy: return []

            punkty_do_konca = [66 - d.punkty_meczu for d in self.druzyny]
            max_punkty_do_konca = max([0] + punkty_do_konca)

            potencjalna_wartosc = self.oblicz_aktualna_stawke(mnoznik_dodatkowy=2)

            akcje = []
            if potencjalna_wartosc >= max_punkty_do_konca and max_punkty_do_konca > 0:
                akcje.append({'typ': 'do_konca'})
            else:
                akcja_podbicia = {'typ': 'kontra'} if gracz.druzyna == self.grajacy.druzyna else {'typ': 'lufa'}
                akcje.append(akcja_podbicia)
            akcje.append({'typ': 'pas_lufa'})
            return akcje

        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        """Przetwarza akcję gracza, aktualizując stan gry."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
             print(f"OSTRZEŻENIE: Akcja gracza {gracz.nazwa} poza turą."); return

        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)
        self.historia_licytacji.append((gracz, akcja.copy()))

        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                kontrakt_specjalny = akcja['kontrakt'] in [Kontrakt.BEZ_PYTANIA, Kontrakt.LEPSZA, Kontrakt.GORSZA]
                if len(gracz.reka) == 3 and kontrakt_specjalny: self.bonus_z_trzech_kart = True; self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 3 kart (x2)")
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                self.faza = FazaGry.LUFA
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx

        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                self._zakoncz_faze_lufy(); return
            if not self.grajacy or not self.grajacy.druzyna: return
            druzyna_grajacego = self.grajacy.druzyna
            if self.lufa_challenger:
                if gracz not in [self.grajacy, self.lufa_challenger]: return
                if akcja['typ'] in ['lufa', 'kontra']:
                    self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                    next_player = self.lufa_challenger if gracz == self.grajacy else self.grajacy
                    idx = self._get_player_index(next_player)
                    if idx is not None: self.kolej_gracza_idx = idx
                elif akcja['typ'] == 'pas_lufa': self._zakoncz_faze_lufy()
            else:
                if gracz.druzyna == druzyna_grajacego: return
                if akcja['typ'] == 'lufa':
                    self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz; self.lufa_challenger = gracz
                    idx = self._get_player_index(self.grajacy)
                    if idx is not None: self.kolej_gracza_idx = idx
                elif akcja['typ'] == 'pas_lufa':
                    self.pasujacy_gracze.append(gracz)
                    aktywni_przeciwnicy = []
                    if druzyna_grajacego.przeciwnicy:
                         aktywni_przeciwnicy = [p for p in druzyna_grajacego.przeciwnicy.gracze if p != self.nieaktywny_gracz]
                    if all(p in self.pasujacy_gracze for p in aktywni_przeciwnicy):
                        self._zakoncz_faze_lufy()
                    else:
                        partner_idx = (gracz_idx + 2) % len(self.gracze)
                        if self.gracze[partner_idx] != self.nieaktywny_gracz:
                            self.kolej_gracza_idx = partner_idx
                        else: self._zakoncz_faze_lufy()

        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     opp1_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     opp2_idx = (grajacy_idx_nowy + 3) % len(self.gracze)
                     partner_idx = (grajacy_idx_nowy + 2) % len(self.gracze)
                     self.kolejka_licytacji = [i for i in [opp1_idx, opp2_idx, partner_idx] if not (self.nieaktywny_gracz and self.gracze[i] == self.nieaktywny_gracz)]
                     if self.kolejka_licytacji:
                          self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
                     else: print("BŁĄD..."); self._zakoncz_faze_lufy()

        elif self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            if akcja['typ'] == 'zmiana_kontraktu':
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], None)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None:
                     next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                     while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                          next_idx = (next_idx + 1) % len(self.gracze)
                     self.kolej_gracza_idx = next_idx
            elif akcja['typ'] == 'graj_normalnie':
                self.faza = FazaGry.ROZGRYWKA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx

        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz; self.lufa_challenger = gracz
                self.faza = FazaGry.LUFA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
                self.kolejka_licytacji.clear(); return

            if akcja['typ'] == 'pas': self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie': self.oferty_przebicia.append((gracz, akcja))

            if self.kolejka_licytacji:
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            else: pass # Ostatni gracz zadecydował

            liczba_decyzji = len(self.pasujacy_gracze) + len(self.oferty_przebicia)
            # Sprawdź, czy wszyscy aktywni gracze (poza grającym) podjęli decyzję
            aktywni_poza_grajacym = self.liczba_aktywnych_graczy - 1
            if liczba_decyzji >= aktywni_poza_grajacym:
                self.kolejka_licytacji.clear()
                self._rozstrzygnij_licytacje_2()

    def rozdaj_karty(self, ilosc: int):
        """Rozdaje określoną liczbę kart graczom."""
        if not (0 <= self.rozdajacy_idx < len(self.gracze)): self.rozdajacy_idx = 0
        start_idx = (self.rozdajacy_idx + 1) % len(self.gracze)
        for _ in range(ilosc):
            for i in range(len(self.gracze)):
                idx = (start_idx + i) % len(self.gracze)
                gracz = self.gracze[idx]
                karta = self.talia.rozdaj_karte()
                if karta and gracz: gracz.reka.append(karta)
        for gracz in self.gracze:
            if gracz: gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))

    def rozlicz_rozdanie(self) -> tuple[Optional[Druzyna], int, int, int]:
        """Oblicza wynik rozdania i aktualizuje punkty meczu."""
        mnoznik_gry = 1
        druzyna_wygrana = None
        punkty_meczu = 0

        if self.zwyciezca_rozdania: druzyna_wygrana = self.zwyciezca_rozdania
        elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy: druzyna_wygrana = self.zwyciezca_ostatniej_lewy.druzyna
        elif self.kontrakt == Kontrakt.GORSZA and self.grajacy and not any(k for g in self.grajacy.druzyna.gracze for k in g.wygrane_karty): druzyna_wygrana = self.grajacy.druzyna
        elif self.grajacy:
             punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.druzyna.nazwa, 0)
             przeciwnicy = self.grajacy.druzyna.przeciwnicy
             punkty_przeciwnikow = self.punkty_w_rozdaniu.get(przeciwnicy.nazwa, 0) if przeciwnicy else 0
             if punkty_grajacego >= 66: druzyna_wygrana = self.grajacy.druzyna
             elif punkty_przeciwnikow >= 66 and przeciwnicy: druzyna_wygrana = przeciwnicy
             elif not any(g.reka for g in self.gracze if g != self.nieaktywny_gracz):
                  if punkty_grajacego > punkty_przeciwnikow: druzyna_wygrana = self.grajacy.druzyna
                  elif przeciwnicy: druzyna_wygrana = przeciwnicy

        if druzyna_wygrana:
            druzyna_przegrana = druzyna_wygrana.przeciwnicy
            if not druzyna_przegrana: druzyna_przegrana = next((d for d in self.druzyny if d != druzyna_wygrana), None)
            punkty_przegranego = self.punkty_w_rozdaniu.get(druzyna_przegrana.nazwa, 0) if druzyna_przegrana else 0
            punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
            if self.kontrakt == Kontrakt.NORMALNA:
                mnoznik_gry = 1
                if punkty_przegranego < 33:
                    mnoznik_gry = 2
                    przegrany_wzial_lewe = False
                    if druzyna_przegrana: przegrany_wzial_lewe = any(gracz.wygrane_karty for gracz in druzyna_przegrana.gracze)
                    if not przegrany_wzial_lewe: mnoznik_gry = 3
                punkty_meczu *= mnoznik_gry
            punkty_meczu *= self.mnoznik_lufy
            if self.bonus_z_trzech_kart: punkty_meczu *= 2
            druzyna_wygrana.punkty_meczu += punkty_meczu
            self.podsumowanie = {
                "wygrana_druzyna": druzyna_wygrana.nazwa, "przyznane_punkty": punkty_meczu,
                "kontrakt": self.kontrakt.name if self.kontrakt else "Brak",
                "atut": self.atut.name if self.atut else "Brak",
                "mnoznik_gry": mnoznik_gry, "mnoznik_lufy": self.mnoznik_lufy,
                "wynik_w_kartach": self.punkty_w_rozdaniu,
                "powod": self.powod_zakonczenia or "Koniec rozdania",
                "bonus_z_trzech_kart": self.bonus_z_trzech_kart
            }
            self._dodaj_log('koniec_rozdania', **self.podsumowanie)
            return druzyna_wygrana, punkty_meczu, mnoznik_gry, self.mnoznik_lufy
        else:
            print("BŁĄD KRYTYCZNY: Nie można ustalić zwycięzcy w rozlicz_rozdanie!")
            self.podsumowanie = {
                 "wygrana_druzyna": "Brak", "przyznane_punkty": 0, "powod": "Błąd rozliczenia",
                 "kontrakt": self.kontrakt.name if self.kontrakt else "Brak",
                 "atut": self.atut.name if self.atut else "Brak",
                 "mnoznik_gry": 1, "mnoznik_lufy": 1,
                 "wynik_w_kartach": self.punkty_w_rozdaniu, "bonus_z_trzech_kart": False
            }
            return None, 0, 1, 1

    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        """Sprawdza, czy zagranie danej karty przez gracza jest legalne."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return False
        if karta not in gracz.reka: return False
        if not self.aktualna_lewa: return True # Pierwszy ruch w lewie

        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        reka_gracza = gracz.reka
        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]

        if karty_do_koloru: # Ma karty do koloru
            if karta.kolor != kolor_wiodacy: return False # Musi dołożyć
            zostalo_przebite = False
            if kolor_wiodacy != self.atut and self.atut and any(k.kolor == self.atut for _, k in self.aktualna_lewa):
                zostalo_przebite = True
            if zostalo_przebite: return True # Nie musi przebijać w kolorze, jeśli przebito atutem
            # Znajdź najwyższą kartę wiodącą na stole
            najwyzsza_karta_wiodaca_para = max([p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy], key=lambda p: p[1].ranga.value, default=None)
            if not najwyzsza_karta_wiodaca_para: return True # Pierwsza karta do koloru
            najwyzsza_karta_wiodaca = najwyzsza_karta_wiodaca_para[1]
            wyzsze_karty_w_rece = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_karta_wiodaca.ranga.value]
            return karta in wyzsze_karty_w_rece if wyzsze_karty_w_rece else True # Musi przebić, jeśli może
        else: # Nie ma kart do koloru
            atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut]
            if self.atut and atuty_w_rece: # Ma atuty
                if karta.kolor != self.atut: return False # Musi dać atut
                atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
                if not atuty_na_stole: return True # Pierwsze przebicie atutem
                najwyzszy_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
                wyzsze_atuty_w_rece = [k for k in atuty_w_rece if k.ranga.value > najwyzszy_atut_na_stole.ranga.value]
                return karta in wyzsze_atuty_w_rece if wyzsze_atuty_w_rece else True # Musi przebić atutem, jeśli może
            else: # Nie ma koloru ani atutów
                return True # Może zagrać dowolną kartę

    def _zakoncz_lewe(self):
        """Rozpoczyna proces zamykania lewy."""
        if not self.aktualna_lewa: return
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]
        # Znajdź najwyższą kartę atutową lub wiodącą
        zwyciezca_pary = None
        if karty_atutowe:
             zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value)
        else:
             karty_wiodace = [p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy]
             if karty_wiodace: zwyciezca_pary = max(karty_wiodace, key=lambda p: p[1].ranga.value)
        if not zwyciezca_pary: zwyciezca_pary = self.aktualna_lewa[0] # Fallback
        zwyciezca_lewy = zwyciezca_pary[0]
        # Punkty i log zostaną dodane w finalizuj_lewe
        self.lewa_do_zamkniecia = True; self.zwyciezca_lewy_tymczasowy = zwyciezca_lewy; self.kolej_gracza_idx = None
        # Sprawdź natychmiastowy koniec rozdania
        if not self.rozdanie_zakonczone and self.grajacy and self.grajacy.druzyna:
            druzyna_zwyciezcy = zwyciezca_lewy.druzyna
            druzyna_grajacego = self.grajacy.druzyna
            punkty_zwyciezcy_teraz = self.punkty_w_rozdaniu.get(druzyna_zwyciezcy.nazwa, 0) + sum(k.wartosc for _, k in self.aktualna_lewa) # Dodaj punkty z bieżącej lewy

            if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                if punkty_zwyciezcy_teraz >= 66:
                    self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = druzyna_zwyciezcy
                    self.powod_zakonczenia = f"osiągnięcie >= 66 punktów"
            # Sprawdzenia dla gier solo
            przeciwnicy = druzyna_grajacego.przeciwnicy
            if przeciwnicy:
                 if self.kontrakt == Kontrakt.BEZ_PYTANIA and zwyciezca_lewy != self.grajacy:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy; self.powod_zakonczenia = f"przejęcie lewy (Bez Pyt.)"
                 elif self.kontrakt == Kontrakt.LEPSZA and druzyna_zwyciezcy != druzyna_grajacego:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy; self.powod_zakonczenia = f"przejęcie lewy (Lepsza)"
                 elif self.kontrakt == Kontrakt.GORSZA and zwyciezca_lewy == self.grajacy:
                     self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = przeciwnicy; self.powod_zakonczenia = f"wzięcie lewy (Gorsza)"


    def finalizuj_lewe(self):
        """Finalizuje lewę: czyści stół, przypisuje karty i ustawia kolejnego gracza."""
        if not self.zwyciezca_lewy_tymczasowy: return
        zwyciezca_lewy = self.zwyciezca_lewy_tymczasowy
        punkty_w_lewie = sum(k.wartosc for _, k in self.aktualna_lewa) # Oblicz punkty przed czyszczeniem
        # Dodaj log z punktami
        self._dodaj_log('koniec_lewy', zwyciezca=zwyciezca_lewy.nazwa, punkty=punkty_w_lewie, karty=[str(k[1]) for k in self.aktualna_lewa])
        # Przypisz punkty
        if zwyciezca_lewy.druzyna:
            self.punkty_w_rozdaniu[zwyciezca_lewy.druzyna.nazwa] += punkty_w_lewie
        # Przypisz karty
        zwyciezca_lewy.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])
        # Sprawdzenie ostatniej lewy
        liczba_kart_w_grze = len(self.gracze) * 6
        if sum(len(g.wygrane_karty) for g in self.gracze if g) == liczba_kart_w_grze:
            self.zwyciezca_ostatniej_lewy = zwyciezca_lewy
        # Resetowanie stanu
        self.aktualna_lewa.clear(); self.lewa_do_zamkniecia = False; self.zwyciezca_lewy_tymczasowy = None
        # Ustaw następnego gracza
        if not self.rozdanie_zakonczone:
             idx = self._get_player_index(zwyciezca_lewy)
             if idx is not None:
                  self.kolej_gracza_idx = idx
                  while self.nieaktywny_gracz and self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                       self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
             else: print("BŁĄD..."); self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % len(self.gracze)
        # Sprawdź koniec rozdania PO finalizacji
        self._sprawdz_koniec_rozdania()


    def zagraj_karte(self, gracz: Gracz, karta: Karta) -> dict:
        """Obsługuje zagranie karty przez gracza."""
        if not self._waliduj_ruch(gracz, karta): return {}
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta))
        punkty_z_meldunku = 0
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty_z_meldunku = 40 if karta.kolor == self.atut else 20
                        if gracz.druzyna:
                             self.punkty_w_rozdaniu[gracz.druzyna.nazwa] += punkty_z_meldunku
                             self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                             self._dodaj_log('meldunek', gracz=gracz.nazwa, punkty=punkty_z_meldunku)
                             if self.punkty_w_rozdaniu.get(gracz.druzyna.nazwa, 0) >= 66 and not self.rozdanie_zakonczone:
                                 self.rozdanie_zakonczone = True; self.zwyciezca_rozdania = gracz.druzyna
                                 self.powod_zakonczenia = f"osiągnięcie >= 66 pkt po meldunku"
                                 self.faza = FazaGry.PODSUMOWANIE_ROZDANIA; self.kolej_gracza_idx = None
                                 self.rozlicz_rozdanie()
                                 return {'meldunek_pkt': punkty_z_meldunku, 'rozdanie_skonczone_meldunkiem': True}

        if karta in gracz.reka: gracz.reka.remove(karta)
        else: print(f"OSTRZEŻENIE: Karta {karta} nie w ręce {gracz.nazwa}."); return {'meldunek_pkt': punkty_z_meldunku}
        self.aktualna_lewa.append((gracz, karta))
        wynik = {'meldunek_pkt': punkty_z_meldunku}
        if len(self.aktualna_lewa) == self.liczba_aktywnych_graczy: self._zakoncz_lewe()
        else:
            if self.kolej_gracza_idx is not None:
                 next_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
                 while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                      next_idx = (next_idx + 1) % len(self.gracze)
                 self.kolej_gracza_idx = next_idx
        return wynik

    def _rozstrzygnij_licytacje_2(self):
        """Wyłania zwycięzcę po fazie LICYTACJA."""
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza: nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza: nowy_grajacy, nowa_akcja = oferty_gorsza[0]
        if nowy_grajacy and nowa_akcja:
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.faza = FazaGry.LUFA
            grajacy_idx_nowy = self._get_player_index(self.grajacy)
            if grajacy_idx_nowy is not None:
                 next_idx = (grajacy_idx_nowy + 1) % len(self.gracze)
                 while self.nieaktywny_gracz and self.gracze[next_idx] == self.nieaktywny_gracz:
                      next_idx = (next_idx + 1) % len(self.gracze)
                 self.kolej_gracza_idx = next_idx
        else:
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
            self.pasujacy_gracze.clear(); self.oferty_przebicia.clear()

    def oblicz_aktualna_stawke(self, mnoznik_dodatkowy: int = 1) -> int:
        """Oblicza potencjalną wartość punktową rozdania."""
        if not self.kontrakt: return 0
        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
        mnoznik_gry = 1
        # Zakładamy najgorszy przypadek dla NORMALNEJ przy obliczaniu potencjalnej stawki
        if self.kontrakt == Kontrakt.NORMALNA: mnoznik_gry = 3
        punkty_meczu *= mnoznik_gry; punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart: punkty_meczu *= 2
        punkty_meczu *= mnoznik_dodatkowy
        return punkty_meczu


# ==========================================================================
# === 4. KLASA ROZDANIE TRZY OSOBY (GRA FFA) ===
# ==========================================================================

class RozdanieTrzyOsoby:
    """Zarządza logiką pojedynczego rozdania w grze 3-osobowej (FFA)."""
    def __init__(self, gracze: list[Gracz], rozdajacy_idx: int):
        if len(gracze) != 3: raise ValueError("Ta klasa obsługuje dokładnie 3 graczy.")
        self.gracze = gracze
        for gracz in self.gracze: # Inicjalizacja graczy
            if not hasattr(gracz, 'punkty_meczu'): gracz.punkty_meczu = 0
            gracz.reka.clear(); gracz.wygrane_karty.clear()
        self.rozdajacy_idx = rozdajacy_idx
        self.talia = Talia()
        self.grajacy: Optional[Gracz] = None; self.obroncy: list[Gracz] = []
        self.lufa_challenger: Optional[Gracz] = None; self.kontrakt: Optional[Kontrakt] = None
        self.atut: Optional[Kolor] = None; self.mnoznik_lufy: int = 1
        self.bonus_z_trzech_kart: bool = False; self.ostatni_podbijajacy: Optional[Gracz] = None
        self.lufa_wstepna: bool = False; self.punkty_w_rozdaniu = {g.nazwa: 0 for g in gracze}
        self.kolej_gracza_idx: Optional[int] = None; self.aktualna_lewa: list[tuple[Gracz, Karta]] = []
        self.zadeklarowane_meldunki: list[tuple[Gracz, Kolor]] = []
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM; self.szczegolowa_historia: list[dict] = []
        self.podsumowanie: dict = {}; self.rozdanie_zakonczone: bool = False
        self.zwyciezca_rozdania_info: dict = {}; self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None
        self.lewa_do_zamkniecia = False; self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None
        self.pasujacy_gracze: list[Gracz] = []; self.oferty_przebicia: list[tuple[Gracz, dict]] = []
        self.kolejka_licytacji: list[int] = []; self.liczba_aktywnych_graczy = 3

    def _get_player_index(self, player_or_name: Union[Gracz, str, None]) -> Optional[int]:
        """Bezpiecznie znajduje indeks gracza wg obiektu lub nazwy."""
        if player_or_name is None: return None
        target_name = player_or_name.nazwa if isinstance(player_or_name, Gracz) else player_or_name
        try:
            return next(i for i, p in enumerate(self.gracze) if p and p.nazwa == target_name)
        except StopIteration:
            print(f"BŁĄD KRYTYCZNY (3p): Nie znaleziono gracza '{target_name}'!")
            return None

    def _dodaj_log(self, typ: str, **kwargs):
        """Dodaje wpis do historii, konwertując Enumy na stringi (pracuje na kopiach)."""
        log_kwargs = kwargs.copy()
        for k, v in log_kwargs.items():
            if isinstance(v, Enum): log_kwargs[k] = v.name
            elif isinstance(v, dict):
                nested_dict_copy = copy.deepcopy(v)
                for k2, v2 in nested_dict_copy.items():
                    if isinstance(v2, Enum): nested_dict_copy[k2] = v2.name
                log_kwargs[k] = nested_dict_copy
            elif isinstance(v, list):
                list_copy = [item.name if isinstance(item, Enum) else item for item in v]
                log_kwargs[k] = list_copy
        log = {'typ': typ, **log_kwargs}
        self.szczegolowa_historia.append(log)

    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        """Ustawia kontrakt i obrońców w grze 3-osobowej."""
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        self.obroncy = [g for g in self.gracze if g != self.grajacy]
        self.ostatni_podbijajacy = self.grajacy
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]: self.atut = None

    def rozpocznij_nowe_rozdanie(self):
        """Przygotowuje rozdanie 3-osobowe."""
        if not (0 <= self.rozdajacy_idx < 3): self.rozdajacy_idx = 0
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa)
        self.rozdaj_karty(4) # W 3p rozdaje się 4+4
        self.faza = FazaGry.DEKLARACJA_1
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % 3

    def rozdaj_karty(self, ilosc: int):
        """Rozdaje karty w grze 3-osobowej."""
        if not (0 <= self.rozdajacy_idx < 3): self.rozdajacy_idx = 0
        start_idx = (self.rozdajacy_idx + 1) % 3
        for _ in range(ilosc):
            for i in range(3):
                idx = (start_idx + i) % 3
                karta = self.talia.rozdaj_karte()
                if karta and self.gracze[idx]: self.gracze[idx].reka.append(karta) # Dodano sprawdzenie gracza
        for gracz in self.gracze:
            if gracz: gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))

    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        """Zwraca możliwe akcje dla gracza w grze 3-osobowej."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx: return []

        # Logika faz identyczna jak w Rozdanie, dostosowana do 3 graczy
        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            for kolor in Kolor:
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.NORMALNA, 'atut': kolor})
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.BEZ_PYTANIA, 'atut': kolor})
            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje

        # Faza lufy wstępnej (przy 4 kartach)
        if self.faza == FazaGry.LUFA and self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4:
            if self.lufa_wstepna and gracz == self.grajacy: # Odpowiedź grającego
                return [{'typ': 'kontra'}, {'typ': 'pas_lufa'}]
            elif gracz in self.obroncy and gracz not in self.pasujacy_gracze: # Możliwość dania lufy
                return [{'typ': 'lufa'}, {'typ': 'pas_lufa'}]
            else: return [] # Inne przypadki (np. drugi pasujący obrońca)

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
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)
            if not has_lepsza:
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                if not has_gorsza:
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            # W 3p każdy może dać lufę
            akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
            return akcje

        if self.faza == FazaGry.LUFA: # Lufa finalna
            if gracz in self.pasujacy_gracze: return []
            if self.lufa_challenger and gracz not in [self.grajacy, self.lufa_challenger]: return []
            if not self.grajacy: return []

            punkty_do_konca = [66 - g.punkty_meczu for g in self.gracze if g]
            max_punkty_do_konca = max([0] + punkty_do_konca)
            potencjalna_wartosc = self.oblicz_aktualna_stawke(mnoznik_dodatkowy=2)

            akcje = []
            if potencjalna_wartosc >= max_punkty_do_konca and max_punkty_do_konca > 0:
                akcje.append({'typ': 'do_konca'})
            else:
                akcja_podbicia = {'typ': 'kontra'} if gracz.druzyna == self.grajacy.druzyna else {'typ': 'lufa'}
                akcje.append(akcja_podbicia)
            akcje.append({'typ': 'pas_lufa'})
            return akcje

        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        """Przetwarza akcję gracza w grze 3-osobowej."""
        gracz_idx = self._get_player_index(gracz)
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
             print(f"OSTRZEŻENIE (3p): Akcja gracza {gracz.nazwa} poza turą."); return

        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)
        # self.historia_licytacji.append((gracz, akcja.copy())) # Opcjonalnie

        # Logika faz (z użyciem _get_player_index)
        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                # Bonus za 4 karty
                if akcja['kontrakt'] in [Kontrakt.LEPSZA, Kontrakt.GORSZA, Kontrakt.BEZ_PYTANIA]:
                    self.bonus_z_trzech_kart = True # Używamy tej samej flagi
                    self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 4 kart (x2)")
                self.faza = FazaGry.LUFA # Przejdź do lufy wstępnej
                grajacy_idx_nowy = self._get_player_index(self.grajacy)
                if grajacy_idx_nowy is not None: self.kolej_gracza_idx = (grajacy_idx_nowy + 1) % 3

        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                self._zakoncz_lufe(); return

            if akcja['typ'] in ['lufa', 'kontra']:
                # Jeśli to pierwsza lufa w rozdaniu przez obrońcę, ustaw go jako pretendenta
                if akcja['typ'] == 'lufa' and not self.lufa_challenger and gracz != self.grajacy:
                    self.lufa_challenger = gracz
                # Sprawdź, czy to lufa wstępna
                if self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4 and akcja['typ'] == 'lufa':
                    self.lufa_wstepna = True
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                # Tura przechodzi na drugą stronę pojedynku
                next_player = None
                if gracz == self.grajacy: next_player = self.lufa_challenger # Odpowiada pretendent
                elif gracz == self.lufa_challenger: next_player = self.grajacy # Odpowiada grający
                else: self.lufa_challenger = gracz; next_player = self.grajacy # Drugi obrońca dołącza/zastępuje
                idx = self._get_player_index(next_player) if next_player else None
                if idx is not None: self.kolej_gracza_idx = idx
                else: print("BŁĄD..."); self._zakoncz_lufe()

            elif akcja['typ'] == 'pas_lufa':
                self.pasujacy_gracze.append(gracz)
                koniec_lufy = False
                if gracz == self.grajacy: koniec_lufy = True # Grający pasuje -> koniec
                elif gracz == self.lufa_challenger: koniec_lufy = True # Pretendent pasuje -> koniec
                # Sprawdź, czy obaj obrońcy spasowali (w dowolnym momencie)
                elif len([p for p in self.pasujacy_gracze if p in self.obroncy]) >= 2:
                    koniec_lufy = True
                # Jeśli pierwszy obrońca spasował (przed wyłonieniem pretendenta), tura na drugiego
                elif not self.lufa_challenger and len(self.pasujacy_gracze) == 1 and gracz in self.obroncy:
                     drugi_obronca = next((o for o in self.obroncy if o != gracz), None)
                     if drugi_obronca:
                          idx = self._get_player_index(drugi_obronca)
                          if idx is not None: self.kolej_gracza_idx = idx
                          else: koniec_lufy = True # Błąd
                     else: koniec_lufy = True # Błąd (powinien być drugi obrońca)

                if koniec_lufy: self._zakoncz_lufe()
                # Jeśli tura nie została zmieniona (np. drugi obrońca myśli), a lufa się nie kończy
                elif self._get_player_index(gracz) == self.kolej_gracza_idx and not koniec_lufy:
                     # Znajdź następnego aktywnego gracza
                     next_idx = (gracz_idx + 1) % 3
                     while self.gracze[next_idx] in self.pasujacy_gracze:
                           next_idx = (next_idx + 1) % 3
                           if next_idx == gracz_idx: koniec_lufy = True; break
                     if koniec_lufy: self._zakoncz_lufe()
                     else: self.kolej_gracza_idx = next_idx


        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.lufa_wstepna = False
                self.faza = FazaGry.LUFA # Przejdź do lufy finalnej
                idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
                if idx is not None: self.kolej_gracza_idx = idx
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
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
                idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
                if idx is not None: self.kolej_gracza_idx = idx
            elif akcja['typ'] == 'graj_normalnie':
                self.faza = FazaGry.ROZGRYWKA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx

        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                self.lufa_challenger = gracz
                self.faza = FazaGry.LUFA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
                self.kolejka_licytacji.clear(); return

            if akcja['typ'] == 'pas': self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie': self.oferty_przebicia.append((gracz, akcja))

            if self.kolejka_licytacji:
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            else: pass # Ostatni obrońca zadecydował

            # Sprawdź, czy obaj obrońcy podjęli decyzję
            if len(self.pasujacy_gracze) + len(self.oferty_przebicia) >= 2:
                self.kolejka_licytacji.clear()
                self._rozstrzygnij_licytacje()


    def _zakoncz_lufe(self):
        """Kończy fazę lufy w grze 3-osobowej."""
        czy_wstepna = self.gracze and self.gracze[0] and len(self.gracze[0].reka) == 4
        if czy_wstepna:
            self.rozdaj_karty(4)
            self.pasujacy_gracze.clear()
            if self.kontrakt == Kontrakt.NORMALNA and not self.lufa_wstepna:
                self.faza = FazaGry.FAZA_PYTANIA_START
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
            else:
                self.faza = FazaGry.ROZGRYWKA
                idx = self._get_player_index(self.grajacy)
                if idx is not None: self.kolej_gracza_idx = idx
        else: # Lufa finalna
            self._dodaj_log('koniec_licytacji', grajacy=self.grajacy.nazwa if self.grajacy else '?', kontrakt=self.kontrakt.name if self.kontrakt else '?')
            self.faza = FazaGry.ROZGRYWKA
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
        self.lufa_wstepna = False # Zresetuj flagę

    def _rozstrzygnij_licytacje(self):
        """Wyłania zwycięzcę po fazie LICYTACJA w grze 3-osobowej."""
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza: nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza: nowy_grajacy, nowa_akcja = oferty_gorsza[0]
        if nowy_grajacy and nowa_akcja: # Ktoś przebił
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            self.faza = FazaGry.LUFA # Przejdź do lufy finalnej
            self.pasujacy_gracze.clear(); self.lufa_challenger = None; self.lufa_wstepna = False
            idx = self._get_player_index(self.obroncy[0]) if self.obroncy else None
            if idx is not None: self.kolej_gracza_idx = idx
        else: # Obaj obrońcy spasowali
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            idx = self._get_player_index(self.grajacy)
            if idx is not None: self.kolej_gracza_idx = idx
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
        if sum(len(g.wygrane_karty) for g in self.gracze if g) == 24: self.zwyciezca_ostatniej_lewy = zwyciezca
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