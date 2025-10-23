# ZAKTUALIZOWANY PLIK: silnik_gry.py
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Union, Optional

# Krok 1: Definiujemy "atomy" gry
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
    ranga: Ranga
    kolor: Kolor

    @property
    def wartosc(self) -> int:
        return WARTOSCI_KART[self.ranga]

    def __str__(self) -> str:
        return f"{self.ranga.name.capitalize()} {self.kolor.name.capitalize()}"

class Talia:
    def __init__(self):
        self.karty = self._stworz_pelna_talie()
        self.tasuj()

    def _stworz_pelna_talie(self) -> list['Karta']:
        return [Karta(ranga, kolor) for kolor in Kolor for ranga in Ranga]

    def tasuj(self):
        random.shuffle(self.karty)

    def rozdaj_karte(self) -> Union['Karta', None]:
        if self.karty:
            return self.karty.pop()
        return None

    def __len__(self) -> int:
        return len(self.karty)

@dataclass
class Gracz:
    """Reprezentuje pojedynczego gracza."""
    nazwa: str
    reka: list[Karta] = field(default_factory=list)
    druzyna: Optional['Druzyna'] = None
    wygrane_karty: list[Karta] = field(default_factory=list)

    def __str__(self) -> str:
        return self.nazwa

@dataclass
class Druzyna:
    """Reprezentuje drużynę złożoną z  dwóch graczy."""
    nazwa: str
    gracze: list[Gracz] = field(default_factory=list)
    punkty_meczu: int = 0
    przeciwnicy: 'Druzyna' = None 
    def dodaj_gracza(self, gracz: Gracz):
        """Dodaje gracza do drużyny i ustawia mu referencję do tej drużyny."""
        if len(self.gracze) < 2:
            self.gracze.append(gracz)
            gracz.druzyna = self

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
    # --- ZMIANY TUTAJ ---
    FAZA_PYTANIA_START = auto() # Zamiast FAZA_PYTANIA
    FAZA_DECYZJI_PO_PASACH = auto() # Nowa faza

STAWKI_KONTRAKTOW = {
    Kontrakt.NORMALNA: 1, 
    Kontrakt.BEZ_PYTANIA: 6,
    Kontrakt.GORSZA: 6,
    Kontrakt.LEPSZA: 12,
}

class Rozdanie:
    def __init__(self, gracze: list[Gracz], druzyny: list[Druzyna], rozdajacy_idx: int):
        self.gracze = gracze; self.druzyny = druzyny; self.rozdajacy_idx = rozdajacy_idx
        self.talia = Talia()
        self.kontrakt: Optional[Kontrakt] = None; self.grajacy: Optional[Gracz] = None
        self.atut: Optional[Kolor] = None; 
        self.stawka = 0
        self.mnoznik_lufy: int = 1
        self.punkty_w_rozdaniu = {druzyny[0].nazwa: 0, druzyny[1].nazwa: 0}
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
        self.nieaktywny_gracz: Optional[Gracz] = None
        self.liczba_aktywnych_graczy = 4
        self.ostatni_podbijajacy: Optional[Gracz] = None
        self.lufa_challenger: Optional[Gracz] = None
        self.podsumowanie = {}
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None
        self.bonus_z_trzech_kart: bool = False
        self.kolejka_licytacji: list[int] = [] # NOWE: Do zarządzania kolejnością licytacji
    def _sprawdz_koniec_rozdania(self):
        """Sprawdza, czy rozdanie powinno się zakończyć i jeśli tak, dokonuje rozliczenia."""
        
        # --- OSTATECZNA POPRAWKA ---
        # Tworzymy listę aktywnych graczy, ignorując tego, który nie bierze udziału w grze.
        aktywni_gracze = [gracz for gracz in self.gracze if gracz != self.nieaktywny_gracz]
        
        # Sprawdzamy, czy wszyscy AKTYWNI gracze zagrali już swoje karty.
        if not any(gracz.reka for gracz in aktywni_gracze):
            self.rozdanie_zakonczone = True
            self.powod_zakonczenia = "Rozegrano wszystkie lewy."
            
            if self.kontrakt == Kontrakt.GORSZA and not any(k for g in self.grajacy.druzyna.gracze for k in g.wygrane_karty):
                self.zwyciezca_rozdania = self.grajacy.druzyna
                self.powod_zakonczenia = f"spełnienie kontraktu Gorsza przez gracza {self.grajacy.nazwa}"

        # Reszta funkcji pozostaje bez zmian
        if self.rozdanie_zakonczone:
            self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            druzyna_wygrana, punkty, mnoznik_gry, mnoznik_lufy = self.rozlicz_rozdanie()
            self.podsumowanie = {
                "wygrana_druzyna": druzyna_wygrana.nazwa,
                "przyznane_punkty": punkty,
                "kontrakt": self.kontrakt.name,
                "atut": self.atut.name if self.atut else "Brak",
                "mnoznik_gry": mnoznik_gry,
                "mnoznik_lufy": mnoznik_lufy,
                "wynik_w_kartach": self.punkty_w_rozdaniu,
                "powod": self.powod_zakonczenia,
                "bonus_z_trzech_kart": self.bonus_z_trzech_kart
            }
        
    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        self.ostatni_podbijajacy = self.grajacy
        
        self.nieaktywny_gracz = None
        self.liczba_aktywnych_graczy = 4
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]:
            self.atut = None
            self.liczba_aktywnych_graczy = 3
            for p in self.grajacy.druzyna.gracze:
                if p != self.grajacy:
                    self.nieaktywny_gracz = p
                    break
    def _dodaj_log(self, typ: str, **kwargs):
        """Dodaje wpis do szczegółowej historii rozdania."""
        log = {'typ': typ, **kwargs}
        self.szczegolowa_historia.append(log)

    def _zakoncz_faze_lufy(self):
        """Kończy fazę lufy, rozdaje karty i przechodzi do następnej fazy."""
        self.pasujacy_gracze.clear()
        self.lufa_challenger = None
        
        if len(self.gracze[0].reka) == 3:
            self.rozdaj_karty(3)

        # --- ZMIANA TUTAJ ---
        if self.kontrakt == Kontrakt.NORMALNA and self.mnoznik_lufy == 1:
            self.faza = FazaGry.FAZA_PYTANIA_START # Zamiast FAZA_PYTANIA
        else:
            self.faza = FazaGry.ROZGRYWKA

        self.kolej_gracza_idx = self.gracze.index(self.grajacy)

    def rozpocznij_nowe_rozdanie(self):
        """Przygotowuje rozdanie do pierwszej decyzji licytacyjnej."""
        self.rozdaj_karty(3)
        self.faza = FazaGry.DEKLARACJA_1
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % 4
        
    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        """Zwraca listę możliwych do wykonania akcji dla danego gracza."""
        if gracz != self.gracze[self.kolej_gracza_idx]: return []

        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            for kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                for kolor in Kolor:
                    akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': kolor})
            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje

        # --- ZMIANA TUTAJ ---
        if self.faza == FazaGry.FAZA_PYTANIA_START:
            return [
                {'typ': 'pytanie'},
                {'typ': 'nie_pytam'},
            ]
        
        # --- NOWA FAZA ---
        if self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            return [
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'graj_normalnie'},
            ]
        
        if self.faza == FazaGry.LICYTACJA:
            akcje = [{'typ': 'pas'}]
            
            # Sprawdzamy, co już zostało zadeklarowane
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)

            # Jeśli nikt nie dał 'Lepsza', można ją dać
            if not has_lepsza:
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                # Jeśli nikt nie dał 'Gorsza' (i 'Lepsza'), można ją dać
                if not has_gorsza:
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            
            # Partner grającego nie może dać lufy
            if self.grajacy and gracz.druzyna != self.grajacy.druzyna:
                # Dodajemy kontekst (co licytujemy) do akcji 'lufa'
                akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
                
            return akcje
        
        if self.faza == FazaGry.LUFA:
            punkty_do_konca_a = 66 - self.druzyny[0].punkty_meczu
            punkty_do_konca_b = 66 - self.druzyny[1].punkty_meczu
            # ZMIANA: Bierzemy większą z wartości (drużynę, która ma mniej punktów)
            max_punkty_do_konca = max(punkty_do_konca_a, punkty_do_konca_b)

            wartosc_bazowa = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
            if self.kontrakt == Kontrakt.NORMALNA:
                wartosc_bazowa *= 3 
            
            potencjalna_wartosc = wartosc_bazowa * (self.mnoznik_lufy * 2)
            if self.bonus_z_trzech_kart:
                potencjalna_wartosc *= 2

            if potencjalna_wartosc >= max_punkty_do_konca:
                return [{'typ': 'do_konca'}, {'typ': 'pas_lufa'}]
            
            druzyna_grajacego = self.grajacy.druzyna
            akcja_podbicia = {'typ': 'kontra'} if gracz.druzyna == druzyna_grajacego else {'typ': 'lufa'}
            return [akcja_podbicia, {'typ': 'pas_lufa'}]
            
        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        """Przetwarza JEDNĄ akcję gracza i aktualizuje stan gry."""
        self.historia_licytacji.append((gracz, akcja))
        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)

        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                kontrakt_specjalny = akcja['kontrakt'] in [Kontrakt.BEZ_PYTANIA, Kontrakt.LEPSZA, Kontrakt.GORSZA]
                if len(gracz.reka) == 3 and kontrakt_specjalny:
                    self.bonus_z_trzech_kart = True
                    self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 3 kart (x2)")
                
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
                if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                    self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4

        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz
                self._zakoncz_faze_lufy()
                return

            druzyna_grajacego = self.grajacy.druzyna
            if self.lufa_challenger:
                if gracz not in [self.grajacy, self.lufa_challenger]:
                    return
                if akcja['typ'] in ['lufa', 'kontra']:
                    self.mnoznik_lufy *= 2
                    self.ostatni_podbijajacy = gracz
                    self.kolej_gracza_idx = self.gracze.index(self.lufa_challenger if gracz == self.grajacy else self.grajacy)
                elif akcja['typ'] == 'pas_lufa':
                    self._zakoncz_faze_lufy()
            else:
                if gracz.druzyna == druzyna_grajacego:
                    return
                if akcja['typ'] == 'lufa':
                    self.mnoznik_lufy *= 2
                    self.ostatni_podbijajacy = gracz
                    self.lufa_challenger = gracz
                    self.kolej_gracza_idx = self.gracze.index(self.grajacy)
                elif akcja['typ'] == 'pas_lufa':
                    self.pasujacy_gracze.append(gracz)
                    aktywni_przeciwnicy = [p for p in druzyna_grajacego.przeciwnicy.gracze if p != self.nieaktywny_gracz]
                    if all(p in self.pasujacy_gracze for p in aktywni_przeciwnicy):
                        self._zakoncz_faze_lufy()
                    else:
                        partner_idx = (self.gracze.index(gracz) + 2) % 4
                        self.kolej_gracza_idx = partner_idx
        
        # --- ZMIANA BLOKU ---
        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                # Traktujemy to jako zmianę kontraktu na BEZ_PYTANIA
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear()
                self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
                if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                    self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
                # --- NOWA KOLEJNOŚĆ LICYTACJI (Oponent1, Oponent2, Partner) ---
                grajacy_idx = self.gracze.index(self.grajacy)
                opp1_idx = (grajacy_idx + 1) % 4
                opp2_idx = (grajacy_idx + 3) % 4
                partner_idx = (grajacy_idx + 2) % 4
                self.kolejka_licytacji = [opp1_idx, opp2_idx, partner_idx]
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)

        # --- NOWY BLOK ---
        elif self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            if akcja['typ'] == 'zmiana_kontraktu':
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], None) # Atut=None dla Lepsza/Gorsza
                self.pasujacy_gracze.clear()
                self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
                if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                    self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            elif akcja['typ'] == 'graj_normalnie':
                self.faza = FazaGry.ROZGRYWKA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)


        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                self.mnoznik_lufy *= 2
                self.faza = FazaGry.ROZGRYWKA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)
                self.kolejka_licytacji.clear() # Czyścimy kolejkę
                return

            if akcja['typ'] == 'pas':
                self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie':
                self.oferty_przebicia.append((gracz, akcja))
            
            # --- ZMIENIONA LOGIKA KOLEJKI ---
            if self.kolejka_licytacji:
                # Bierzemy następnego gracza z ustalonej kolejki
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            else:
                # To się wydarzy po decyzji ostatniego gracza (Partnera)
                # _rozstrzygnij_licytacje_2 zostanie wywołane poniżej
                pass
            
            liczba_decyzji = len(self.pasujacy_gracze) + len(self.oferty_przebicia)
            if liczba_decyzji == 3:
                self.kolejka_licytacji.clear() # Czyścimy kolejkę
                self._rozstrzygnij_licytacje_2()
           
    def rozdaj_karty(self, ilosc: int):
        start_idx = (self.rozdajacy_idx + 1) % 4
        for _ in range(ilosc):
            for i in range(4):
                idx = (start_idx + i) % 4
                karta = self.talia.rozdaj_karte()
                if karta: self.gracze[idx].reka.append(karta)
        for gracz in self.gracze:
            # Sortuj po kolorze (wg słownika), a następnie po randze (malejąco)
            gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
    
    def rozlicz_rozdanie(self) -> tuple[Druzyna, int, int, int]:
        mnoznik_gry = 1
        druzyna_wygrana = None
    
        if self.rozdanie_zakonczone and self.zwyciezca_rozdania:
            druzyna_wygrana = self.zwyciezca_rozdania
        elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy:
            druzyna_wygrana = self.zwyciezca_ostatniej_lewy.druzyna
        elif self.kontrakt == Kontrakt.GORSZA and not any(self.grajacy.wygrane_karty):
            druzyna_wygrana = self.grajacy.druzyna
        else:
            punkty_grajacego = self.punkty_w_rozdaniu[self.grajacy.druzyna.nazwa]
            punkty_przeciwnikow = self.punkty_w_rozdaniu[self.grajacy.druzyna.przeciwnicy.nazwa]
            if punkty_grajacego > punkty_przeciwnikow:
                druzyna_wygrana = self.grajacy.druzyna
            else:
                druzyna_wygrana = self.grajacy.druzyna.przeciwnicy

        druzyna_przegrana = druzyna_wygrana.przeciwnicy
        punkty_przegranego = self.punkty_w_rozdaniu[druzyna_przegrana.nazwa]
        
        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)

        if self.kontrakt == Kontrakt.NORMALNA:
            if punkty_przegranego < 33:
                mnoznik_gry = 2
                if not any(gracz.wygrane_karty for gracz in druzyna_przegrana.gracze):
                    mnoznik_gry = 3
            punkty_meczu *= mnoznik_gry
        
        punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart:
            punkty_meczu *= 2
        druzyna_wygrana.punkty_meczu += punkty_meczu
        self._dodaj_log('koniec_rozdania',
                        wygrana_druzyna=druzyna_wygrana.nazwa,
                        punkty_meczu=punkty_meczu,
                        wynik_w_rozdaniu=self.punkty_w_rozdaniu,
                        powod=self.powod_zakonczenia) # Dodajemy log
        return druzyna_wygrana, punkty_meczu, mnoznik_gry, self.mnoznik_lufy
        
    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        if gracz != self.gracze[self.kolej_gracza_idx]: return False
        if karta not in gracz.reka: return False

        if not self.aktualna_lewa:
            return True # Pierwszy ruch w lewie jest zawsze dozwolony.

        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        reka_gracza = gracz.reka
        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]

        # --- SCENARIUSZ 1: Gracz MA karty do koloru wiodącego ---
        if karty_do_koloru:
            if karta.kolor != kolor_wiodacy:
                return False  # Błąd: Gracz musi dołożyć do koloru.

            # --- POCZĄTEK POPRAWKI ---
            # Sprawdzamy, czy lewa została już przebita przez kogoś innego atutem
            # (ma to znaczenie tylko wtedy, gdy kolor wiodący nie jest atutem)
            zostało_przebite = False
            if kolor_wiodacy != self.atut and self.atut:
                if any(k.kolor == self.atut for _, k in self.aktualna_lewa):
                    zostało_przebite = True

            # Obowiązek przebicia w kolorze znika TYLKO wtedy, gdy ktoś już przebił lewę atutem.
            # Jeśli kolor wiodący jest atutem, obowiązek ZAWSZE pozostaje.
            if zostało_przebite:
                return True # Można dołożyć dowolną kartę do koloru.

            # Jeśli nie zostało przebite (lub kolor wiodący to atut), musisz przebić, jeśli możesz.
            najwyzsza_karta_wiodaca = max(
                [k for _, k in self.aktualna_lewa if k.kolor == kolor_wiodacy],
                key=lambda c: c.ranga.value
            )
            wyzsze_karty_w_rece = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_karta_wiodaca.ranga.value]

            if wyzsze_karty_w_rece:
                return karta in wyzsze_karty_w_rece # Musisz zagrać jedną z wyższych kart.
            else:
                return True # Nie masz wyższej karty, więc każda do koloru jest OK.
            # --- KONIEC POPRAWKI ---

        # --- SCENARIUSZ 2: Gracz NIE MA kart do koloru wiodącego ---
        atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut]
        if self.atut and atuty_w_rece:
            if karta.kolor != self.atut:
                return False # Błąd: Gracz musi zagrać atut.

            atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
            if not atuty_na_stole:
                return True # Jesteś pierwszy, który przebija - każdy atut jest OK.

            najwyzszy_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
            wyzsze_atuty_w_rece = [k for k in atuty_w_rece if k.ranga.value > najwyzszy_atut_na_stole.ranga.value]

            if wyzsze_atuty_w_rece:
                return karta in wyzsze_atuty_w_rece # Musisz zagrać wyższy atut.
            else:
                return True # Nie masz wyższego atutu, więc zagrywasz dowolny posiadany.

        # --- SCENARIUSZ 3: Gracz nie ma ani koloru wiodącego, ani atutów ---
        return True # Może zagrać dowolną kartę.

    def _zakoncz_lewe(self):
        """Rozpoczyna proces zamykania lewy: znajduje zwycięzcę i ustawia flagę."""
        if not self.aktualna_lewa: return

        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]

        zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value) if karty_atutowe else \
                        max([p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy], key=lambda p: p[1].ranga.value)

        zwyciezca_lewy = zwyciezca_pary[0]
        punkty_w_lewie = sum(karta.wartosc for _, karta in self.aktualna_lewa)
        self._dodaj_log('koniec_lewy', 
                        zwyciezca=zwyciezca_lewy.nazwa, 
                        punkty=punkty_w_lewie,
                        karty=[str(k[1]) for k in self.aktualna_lewa])

        druzyna_zwyciezcy = zwyciezca_lewy.druzyna
        self.punkty_w_rozdaniu[druzyna_zwyciezcy.nazwa] += punkty_w_lewie

        # --- KLUCZOWA ZMIANA: Ustawiamy flagi zamiast czyścić stół ---
        self.lewa_do_zamkniecia = True
        self.zwyciezca_lewy_tymczasowy = zwyciezca_lewy
        self.kolej_gracza_idx = None # Wstrzymujemy ruch

        # Sprawdzamy warunki końca rozdania już teraz
        druzyna_grajacego = self.grajacy.druzyna
        if not self.rozdanie_zakonczone:
            if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
                if self.punkty_w_rozdaniu[druzyna_zwyciezcy.nazwa] >= 66:
                    self.rozdanie_zakonczone = True
                    self.zwyciezca_rozdania = druzyna_zwyciezcy
                    self.powod_zakonczenia = f"osiągnięcie {self.punkty_w_rozdaniu[druzyna_zwyciezcy.nazwa]} punktów"

            if self.kontrakt == Kontrakt.BEZ_PYTANIA and zwyciezca_lewy != self.grajacy:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania = druzyna_grajacego.przeciwnicy
                self.powod_zakonczenia = f"przejęcie lewy przez gracza {zwyciezca_lewy.nazwa}"
            elif self.kontrakt == Kontrakt.LEPSZA and druzyna_zwyciezcy != druzyna_grajacego:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania = druzyna_grajacego.przeciwnicy
                self.powod_zakonczenia = f"przejęcie lewy przez gracza {zwyciezca_lewy.nazwa}"
            elif self.kontrakt == Kontrakt.GORSZA and zwyciezca_lewy == self.grajacy:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania = druzyna_grajacego.przeciwnicy
                self.powod_zakonczenia = f"wzięcie lewy przez gracza {self.grajacy.nazwa}"

      
            

    def finalizuj_lewe(self):
        """Finalizuje lewę: czyści stół, przypisuje karty i ustawia kolejnego gracza."""
        if not self.zwyciezca_lewy_tymczasowy:
            return

        zwyciezca_lewy = self.zwyciezca_lewy_tymczasowy
        zwyciezca_lewy.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])

        # Sprawdzenie ostatniej lewy
        if sum(len(g.wygrane_karty) for g in self.gracze) == 24:
            self.zwyciezca_ostatniej_lewy = zwyciezca_lewy

        # Resetowanie stanu
        self.aktualna_lewa.clear()
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy = None
        self.kolej_gracza_idx = self.gracze.index(zwyciezca_lewy)
        self._sprawdz_koniec_rozdania()
        
    def zagraj_karte(self, gracz: Gracz, karta: Karta) -> dict:
        if not self._waliduj_ruch(gracz, karta):
            print(f"BŁĄD: Ruch gracza {gracz} kartą {karta} jest nielegalny!")
            return {}
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta)) # Dodajemy log
        punkty_z_meldunku = 0
        
        # Poprawka 1 (już istniała): Meldunki działają tylko w Normalnej i Bez Pytania
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty_z_meldunku = 40 if karta.kolor == self.atut else 20
                        self.punkty_w_rozdaniu[gracz.druzyna.nazwa] += punkty_z_meldunku
                        self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                        self._dodaj_log('meldunek', gracz=gracz.nazwa, punkty=punkty_z_meldunku)

                        # --- POPRAWKA 2: Natychmiastowe sprawdzenie >= 66 ---
                        if self.punkty_w_rozdaniu[gracz.druzyna.nazwa] >= 66 and not self.rozdanie_zakonczone:
                            self.rozdanie_zakonczone = True
                            self.zwyciezca_rozdania = gracz.druzyna
                            self.powod_zakonczenia = f"osiągnięcie {self.punkty_w_rozdaniu[gracz.druzyna.nazwa]} pkt po meldunku"
                        # --- KONIEC POPRAWKI 2 ---

        gracz.reka.remove(karta)
        self.aktualna_lewa.append((gracz, karta))
        
        wynik = {'meldunek_pkt': punkty_z_meldunku}
        
        if len(self.aktualna_lewa) == self.liczba_aktywnych_graczy:
            self._zakoncz_lewe()
        else:
            self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            while self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            
        return wynik
    
    # --- ZMIANA W TEJ FUNKCJI ---
    def _rozstrzygnij_licytacje_2(self):
        """Wyłania zwycięzcę po zakończeniu fazy przebicia LUB przechodzi do decyzji gracza, jeśli wszyscy spasowali."""
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza:
            nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza:
                nowy_grajacy, nowa_akcja = oferty_gorsza[0]

        if nowy_grajacy:
            # --- Scenariusz 1: Ktoś przebił ---
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            
            self.pasujacy_gracze.clear()
            self.lufa_challenger = None
            self.faza = FazaGry.LUFA
            self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
            if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                 self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
        else:
            # --- Scenariusz 2: Wszyscy spasowali (brak ofert) ---
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            self.kolej_gracza_idx = self.gracze.index(self.grajacy) # Tura wraca do pierwotnego grającego
            self.pasujacy_gracze.clear() # Czyścimy listę pasujących
            self.oferty_przebicia.clear() # Czyścimy listę ofert

    def oblicz_aktualna_stawke(self) -> int:
        """Oblicza i zwraca aktualną potencjalną wartość punktową rozdania."""
        if not self.kontrakt:
            return 0

        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)

        # Oblicz mnożnik gry dla kontraktu NORMALNA
        mnoznik_gry = 1
        if self.kontrakt == Kontrakt.NORMALNA:
            if self.grajacy:
                druzyna_przeciwna = self.grajacy.druzyna.przeciwnicy
                punkty_przeciwnika = self.punkty_w_rozdaniu[druzyna_przeciwna.nazwa]

                if punkty_przeciwnika < 33:
                    mnoznik_gry = 2
                    # Sprawdzamy, czy przeciwnik wziął jakąkolwiek lewę
                    if not any(gracz.wygrane_karty for gracz in druzyna_przeciwna.gracze):
                        mnoznik_gry = 3
            punkty_meczu *= mnoznik_gry

        # Zastosuj mnożnik lufy
        punkty_meczu *= self.mnoznik_lufy

        # Zastosuj bonus za 3 karty
        if self.bonus_z_trzech_kart:
            punkty_meczu *= 2

        return punkty_meczu
    



class RozdanieTrzyOsoby:
    def __init__(self, gracze: list[Gracz], rozdajacy_idx: int):
        if len(gracze) != 3:
            raise ValueError("Ta klasa obsługuje dokładnie 3 graczy.")
        
        self.gracze = gracze
        for gracz in self.gracze:
            if not hasattr(gracz, 'punkty_meczu'):
                gracz.punkty_meczu = 0

        self.rozdajacy_idx = rozdajacy_idx
        self.talia = Talia()
        
        self.grajacy: Optional[Gracz] = None
        self.obroncy: list[Gracz] = []
        self.lufa_challenger: Optional[Gracz] = None

        self.kontrakt: Optional[Kontrakt] = None
        self.atut: Optional[Kolor] = None
        self.mnoznik_lufy: int = 1
        self.bonus_z_trzech_kart: bool = False
        self.ostatni_podbijajacy: Optional[Gracz] = None
        
        self.lufa_wstepna: bool = False

        self.punkty_w_rozdaniu = {gracz.nazwa: 0 for gracz in self.gracze}
        self.kolej_gracza_idx: Optional[int] = None
        self.aktualna_lewa: list[tuple[Gracz, Karta]] = []
        self.zadeklarowane_meldunki: list[tuple[Gracz, Kolor]] = []
        
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM
        self.szczegolowa_historia: list[dict] = []
        self.podsumowanie = {}
        self.rozdanie_zakonczone: bool = False
        self.zwyciezca_rozdania_info: dict = {}
        self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None
        
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None
        
        self.pasujacy_gracze: list[Gracz] = []
        self.oferty_przebicia: list[tuple[Gracz, dict]] = []
        self.kolejka_licytacji: list[int] = [] # --- NOWE ---


    def _dodaj_log(self, typ: str, **kwargs):
        log = {'typ': typ, **kwargs}
        self.szczegolowa_historia.append(log)

    def _ustaw_kontrakt(self, gracz_grajacy: Gracz, kontrakt: Kontrakt, atut: Optional[Kolor]):
        self.grajacy = gracz_grajacy
        self.kontrakt = kontrakt
        self.atut = atut
        self.obroncy = [g for g in self.gracze if g != self.grajacy]
        self.ostatni_podbijajacy = self.grajacy
        
        if self.kontrakt in [Kontrakt.LEPSZA, Kontrakt.GORSZA]:
            self.atut = None
    
    def rozpocznij_nowe_rozdanie(self):
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa)
        self.rozdaj_karty(4)
        self.faza = FazaGry.DEKLARACJA_1
        self.kolej_gracza_idx = (self.rozdajacy_idx + 1) % 3

    def rozdaj_karty(self, ilosc: int):
        start_idx = (self.rozdajacy_idx + 1) % 3
        for _ in range(ilosc):
            for i in range(3):
                idx = (start_idx + i) % 3
                karta = self.talia.rozdaj_karte()
                if karta: self.gracze[idx].reka.append(karta)
        for gracz in self.gracze:
            # Sortuj po kolorze (wg słownika), a następnie po randze (malejąco)
            gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))

    def get_mozliwe_akcje(self, gracz: Gracz) -> list[dict]:
        if not self.gracze or self.kolej_gracza_idx is None or gracz != self.gracze[self.kolej_gracza_idx]:
            return []

        if self.faza == FazaGry.DEKLARACJA_1:
            akcje = []
            for kolor in Kolor:
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.NORMALNA, 'atut': kolor})
                akcje.append({'typ': 'deklaracja', 'kontrakt': Kontrakt.BEZ_PYTANIA, 'atut': kolor})

            for kontrakt in [Kontrakt.GORSZA, Kontrakt.LEPSZA]:
                akcje.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
            return akcje
        

        if self.faza == FazaGry.LUFA and len(self.gracze[0].reka) == 4: # Wstępna faza lufy
            if self.lufa_wstepna and gracz == self.grajacy:
                return [{'typ': 'kontra'}, {'typ': 'pas_lufa'}]
            elif gracz in self.obroncy and gracz not in self.pasujacy_gracze:
                return [{'typ': 'lufa'}, {'typ': 'pas_lufa'}]

        # --- ZMIANA BLOKU ---
        if self.faza == FazaGry.FAZA_PYTANIA_START:
            return [
                {'typ': 'pytanie'},
                {'typ': 'nie_pytam'},
            ]
        
        # --- NOWY BLOK ---
        if self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            return [
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'graj_normalnie'},
            ]
        
        if self.faza == FazaGry.LICYTACJA:
            akcje = [{'typ': 'pas'}]

            # Sprawdzamy, co już zostało zadeklarowane
            has_lepsza = any(o[1]['kontrakt'] == Kontrakt.LEPSZA for o in self.oferty_przebicia)
            has_gorsza = any(o[1]['kontrakt'] == Kontrakt.GORSZA for o in self.oferty_przebicia)

            # Jeśli nikt nie dał 'Lepsza', można ją dać
            if not has_lepsza:
                akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA})
                # Jeśli nikt nie dał 'Gorsza' (i 'Lepsza'), można ją dać
                if not has_gorsza:
                    akcje.append({'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA})
            
            # Dodajemy kontekst (co licytujemy) do akcji 'lufa'
            akcje.append({'typ': 'lufa', 'kontrakt': self.kontrakt, 'atut': self.atut})
            return akcje
        
        if self.faza == FazaGry.LUFA: # Finalna faza lufy
            if gracz in self.pasujacy_gracze: return []
            if self.lufa_challenger and gracz not in [self.grajacy, self.lufa_challenger]:
                return []

            
            punkty_do_konca = [66 - g.punkty_meczu for g in self.gracze]
            max_punkty_do_konca = max(punkty_do_konca) if punkty_do_konca else 0

            # Obliczamy, ile będzie warta gra PO NASTĘPNYM podbiciu
            potencjalna_wartosc = self.oblicz_aktualna_stawke(mnoznik_dodatkowy=2)

            if potencjalna_wartosc >= max_punkty_do_konca:
                return [{'typ': 'do_konca'}, {'typ': 'pas_lufa'}]
           

            akcja_podbicia = {'typ': 'kontra'} if gracz == self.grajacy else {'typ': 'lufa'}
            return [akcja_podbicia, {'typ': 'pas_lufa'}]
            
        return []

    def wykonaj_akcje(self, gracz: Gracz, akcja: dict):
        self._dodaj_log('akcja_licytacyjna', gracz=gracz.nazwa, akcja=akcja)

        if self.faza == FazaGry.DEKLARACJA_1:
            if akcja['typ'] == 'deklaracja':
                self._ustaw_kontrakt(gracz, akcja['kontrakt'], akcja.get('atut'))
                if akcja['kontrakt'] in [Kontrakt.LEPSZA, Kontrakt.GORSZA, Kontrakt.BEZ_PYTANIA]:
                    self.bonus_z_trzech_kart = True
                    self._dodaj_log('bonus', gracz=gracz.nazwa, opis="Z 4 kart (x2)")
                self.faza = FazaGry.LUFA
                grajacy_idx = self.gracze.index(self.grajacy)
                self.kolej_gracza_idx = (grajacy_idx + 1) % 3

        elif self.faza == FazaGry.LUFA:
            if akcja['typ'] == 'do_konca':
                self.mnoznik_lufy *= 2 
                self.ostatni_podbijajacy = gracz
                self._zakoncz_lufe()
                return
            if akcja['typ'] in ['lufa', 'kontra']:
                # Jeśli to pierwsza lufa w rozdaniu, ustawiamy pretendenta
                if akcja['typ'] == 'lufa' and not self.lufa_challenger:
                    self.lufa_challenger = gracz

                # Sprawdzamy, czy to lufa na etapie 4 kart
                if len(self.gracze[0].reka) == 4 and akcja['typ'] == 'lufa':
                    self.lufa_wstepna = True
                
                self.mnoznik_lufy *= 2
                self.ostatni_podbijajacy = gracz

                # Przekazanie tury: zawsze do drugiej strony pojedynku
                if gracz == self.grajacy:
                    self.kolej_gracza_idx = self.gracze.index(self.lufa_challenger)
                else: # Obrońca dał lufę/kontr-lufę
                    self.kolej_gracza_idx = self.gracze.index(self.grajacy)

            elif akcja['typ'] == 'pas_lufa':
                self.pasujacy_gracze.append(gracz)
                
                # Koniec licytacji, jeśli spasuje rozgrywający lub pretendent
                if gracz == self.grajacy or gracz == self.lufa_challenger:
                    self._zakoncz_lufe()
                else:
                    # To obrońca spasował, ZANIM wyłoniono pretendenta. Tura przechodzi na drugiego obrońcę.
                    inny_obronca = next((o for o in self.obroncy if o not in self.pasujacy_gracze), None)
                    if inny_obronca:
                        self.kolej_gracza_idx = self.gracze.index(inny_obronca)
                    else: # Obaj obrońcy spasowali, zanim zaczęła się "wojna"
                        self._zakoncz_lufe()
        

        # --- ZMIANA BLOKU ---
        elif self.faza == FazaGry.FAZA_PYTANIA_START:
            if akcja['typ'] == 'nie_pytam':
                self._ustaw_kontrakt(self.grajacy, Kontrakt.BEZ_PYTANIA, self.atut)
                self.pasujacy_gracze.clear()
                self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = self.gracze.index(self.obroncy[0]) if self.obroncy else (self.rozdajacy_idx + 1) % 3
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
                # --- NOWA KOLEJNOŚĆ LICYTACJI (Oponent1, Oponent2) ---
                grajacy_idx = self.gracze.index(self.grajacy)
                opp1_idx = (grajacy_idx + 1) % 3
                opp2_idx = (grajacy_idx + 2) % 3
                self.kolejka_licytacji = [opp1_idx, opp2_idx]
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)

        # --- NOWY BLOK ---
        elif self.faza == FazaGry.FAZA_DECYZJI_PO_PASACH:
            if akcja['typ'] == 'zmiana_kontraktu':
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], None) 
                self.pasujacy_gracze.clear()
                self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = self.gracze.index(self.obroncy[0]) if self.obroncy else (self.rozdajacy_idx + 1) % 3
            elif akcja['typ'] == 'graj_normalnie':
                self.faza = FazaGry.ROZGRYWKA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)

        # --- ZMIANA BLOKU ---
        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                self.mnoznik_lufy *= 2; self.ostatni_podbijajacy = gracz
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)
                self.kolejka_licytacji.clear() # Czyścimy kolejkę
                return
            if akcja['typ'] == 'pas': self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie': self.oferty_przebicia.append((gracz, akcja))
            
            # --- ZMIENIONA LOGIKA KOLEJKI ---
            if self.kolejka_licytacji:
                self.kolej_gracza_idx = self.kolejka_licytacji.pop(0)
            else:
                pass # Ostatni gracz (opp2) zadecydował
            
            if len(self.pasujacy_gracze) + len(self.oferty_przebicia) >= 2:
                self.kolejka_licytacji.clear() # Czyścimy kolejkę
                self._rozstrzygnij_licytacje()
    
    def _zakoncz_lufe(self):
        """Kończy fazę lufy i decyduje co dalej (dobieranie kart czy rozgrywka)."""
        if len(self.gracze[0].reka) == 4:
            # Licytacja zakończyła się przy 4 kartach - dobieramy resztę.
            self.rozdaj_karty(4)
            self.pasujacy_gracze.clear()
            
           # Jeśli kontrakt jest normalny i nikt nie dał lufy, idziemy do fazy pytania
            if self.kontrakt == Kontrakt.NORMALNA and not self.lufa_wstepna:
                self.faza = FazaGry.FAZA_PYTANIA_START # Zmieniono z FAZA_PYTANIA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)
            else:
                # W każdym innym przypadku (gra specjalna LUB padła lufa) przechodzimy do rozgrywki
                self.faza = FazaGry.ROZGRYWKA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)
            # --- KONIEC ZMIENIONEJ LOGIKI ---

        else:
            # Licytacja zakończyła się przy 8 kartach - zaczynamy rozgrywkę.
            self._dodaj_log('koniec_licytacji', grajacy=self.grajacy.nazwa, kontrakt=self.kontrakt.name)
            self.faza = FazaGry.ROZGRYWKA
            self.kolej_gracza_idx = self.gracze.index(self.grajacy)

    # --- ZMIANA W TEJ FUNKCJI ---
    def _rozstrzygnij_licytacje(self):
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza: nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza: nowy_grajacy, nowa_akcja = oferty_gorsza[0]
        
        if nowy_grajacy:
            # --- Scenariusz 1: Ktoś przebił ---
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            
            # --- POPRAWKA: USUNIĘCIE BŁĘDNEGO PRZYZNAWANIA BONUSU ---
            # Ten blok kodu błędnie przyznawał bonus za przebicie z 8 kartami.
            # if len(nowy_grajacy.reka) == 8: # Bonus za 8 kart
            #     self.bonus_z_trzech_kart = True 
            #     self._dodaj_log('bonus', gracz=nowy_grajacy.nazwa, opis="Z 8 kart (x2)")
            # --- KONIEC POPRAWKI ---
            
            self.faza = FazaGry.LUFA
            self.pasujacy_gracze.clear()
            self.lufa_challenger = None
            self.kolej_gracza_idx = self.gracze.index(self.obroncy[0]) if self.obroncy else (self.rozdajacy_idx + 1) % 3

        else:
            # --- Scenariusz 2: Wszyscy (obaj) spasowali (brak ofert) ---
            self.faza = FazaGry.FAZA_DECYZJI_PO_PASACH
            self.kolej_gracza_idx = self.gracze.index(self.grajacy) # Tura wraca do pierwotnego grającego
            self.pasujacy_gracze.clear()
            self.oferty_przebicia.clear()
        
        
    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        if self.kolej_gracza_idx is None or gracz != self.gracze[self.kolej_gracza_idx]: return False
        if karta not in gracz.reka: return False
        if not self.aktualna_lewa: return True
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        reka_gracza = gracz.reka
        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]
        if karty_do_koloru:
            if karta.kolor != kolor_wiodacy: return False
            zostało_przebite = False
            if kolor_wiodacy != self.atut and self.atut and any(k.kolor == self.atut for _, k in self.aktualna_lewa):
                zostało_przebite = True
            if zostało_przebite: return True
            najwyzsza_karta_wiodaca = max([k for _, k in self.aktualna_lewa if k.kolor == kolor_wiodacy], key=lambda c: c.ranga.value)
            wyzsze_karty_w_rece = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_karta_wiodaca.ranga.value]
            return karta in wyzsze_karty_w_rece if wyzsze_karty_w_rece else True
        atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut]
        if self.atut and atuty_w_rece:
            if karta.kolor != self.atut: return False
            atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
            if not atuty_na_stole: return True
            najwyzszy_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
            wyzsze_atuty_w_rece = [k for k in atuty_w_rece if k.ranga.value > najwyzszy_atut_na_stole.ranga.value]
            return karta in wyzsze_atuty_w_rece if wyzsze_atuty_w_rece else True
        return True

    def zagraj_karte(self, gracz: Gracz, karta: Karta):
        if not self._waliduj_ruch(gracz, karta): return
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta))
        
        # --- POPRAWKA 1: Logika meldunku (3 os.) ---
        # Kontrakty GORSZA/LEPSZA są wyłączone z meldunków
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty = 40 if karta.kolor == self.atut else 20
                        self.punkty_w_rozdaniu[gracz.nazwa] += punkty
                        self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                        self._dodaj_log('meldunek', gracz=gracz.nazwa, punkty=punkty)

                        # --- POPRAWKA 2: Natychmiastowe sprawdzenie >= 66 (3 os.) ---
                        if self.punkty_w_rozdaniu[gracz.nazwa] >= 66 and not self.rozdanie_zakonczone:
                            self.rozdanie_zakonczone = True
                            if gracz == self.grajacy:
                                self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': f"osiągnięcie {self.punkty_w_rozdaniu[gracz.nazwa]} pkt po meldunku"}
                            else: # Obrońca meldował i wygrał
                                self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': f"osiągnięcie {self.punkty_w_rozdaniu[gracz.nazwa]} pkt po meldunku obrońcy"}
                        # --- KONIEC POPRAWKI 2 ---
        # --- KONIEC POPRAWKI 1 ---
                        
        gracz.reka.remove(karta)
        self.aktualna_lewa.append((gracz, karta))
        if len(self.aktualna_lewa) == 3:
            self._zakoncz_lewe()
        else:
            self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 3

    def _zakoncz_lewe(self):
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]
        zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value) if karty_atutowe else \
                        max([p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy], key=lambda p: p[1].ranga.value)
        zwyciezca = zwyciezca_pary[0]
        self.lewa_do_zamkniecia = True
        self.zwyciezca_lewy_tymczasowy = zwyciezca
        self.kolej_gracza_idx = None
        if not self.rozdanie_zakonczone:
            przegrana_grajacego = False
            powod = ""
            if self.kontrakt == Kontrakt.LEPSZA and zwyciezca in self.obroncy:
                przegrana_grajacego = True; powod = f"przejęcie lewy przez obronę"
            elif self.kontrakt == Kontrakt.GORSZA and zwyciezca == self.grajacy:
                przegrana_grajacego = True; powod = f"wzięcie lewy przez rozgrywającego"
            elif self.kontrakt == Kontrakt.BEZ_PYTANIA and zwyciezca in self.obroncy:
                przegrana_grajacego = True; powod = f"przejęcie lewy przez obronę"
            if przegrana_grajacego:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': powod}
        
    def finalizuj_lewe(self):
        if not self.zwyciezca_lewy_tymczasowy: return
        zwyciezca = self.zwyciezca_lewy_tymczasowy
        punkty_w_lewie = sum(karta.wartosc for _, karta in self.aktualna_lewa)
        self._dodaj_log('koniec_lewy', zwyciezca=zwyciezca.nazwa, punkty=punkty_w_lewie, karty=[str(k[1]) for k in self.aktualna_lewa])
        self.punkty_w_rozdaniu[zwyciezca.nazwa] += punkty_w_lewie
        zwyciezca.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])
        if sum(len(g.wygrane_karty) for g in self.gracze) == 24:
            self.zwyciezca_ostatniej_lewy = zwyciezca
        self.aktualna_lewa.clear()
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy = None
        if not self.rozdanie_zakonczone:
            self.kolej_gracza_idx = self.gracze.index(zwyciezca)
        self._sprawdz_koniec_rozdania()

    def _sprawdz_koniec_rozdania(self):
        if self.rozdanie_zakonczone:
            if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA:
                self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
                self.rozlicz_rozdanie()
            return

        if self.grajacy and not self.rozdanie_zakonczone:
            for obronca in self.obroncy:
                punkty_obroncy = self.punkty_w_rozdaniu.get(obronca.nazwa, 0)
                if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA] and punkty_obroncy >= 66:
                    self.rozdanie_zakonczone = True
                    
                    # BŁĄD BYŁ TUTAJ:
                    # Poprzednia logika mogła przypisywać wygraną tylko jednemu obrońcy.
                    # Prawidłowo: Zwycięstwo należy się OBU obrońcom.
                    self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': f"osiągnięcie {punkty_obroncy} punktów przez obronę"}
                    # --- KONIEC POPRAWKI ---
                    
                    break # Wystarczy, że jeden wygra
            
            if self.rozdanie_zakonczone: 
                 if self.faza != FazaGry.PODSUMOWANIE_ROZDANIA:
                    self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
                    self.rozlicz_rozdanie()
                 return

            punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0)
            if self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA] and punkty_grajacego >= 66:
                self.rozdanie_zakonczone = True
                self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': f"osiągnięcie {punkty_grajacego} punktów"}

        if not any(gracz.reka for gracz in self.gracze):
            self.rozdanie_zakonczone = True
            if not self.zwyciezca_rozdania_info:
                punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0)
                punkty_obrony = sum(self.punkty_w_rozdaniu.get(o.nazwa, 0) for o in self.obroncy)
                
                if self.kontrakt == Kontrakt.GORSZA:
                    self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "nie wzięcie żadnej lewy"}
                elif self.kontrakt == Kontrakt.LEPSZA:
                     self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "wzięcie wszystkich lew"}
                

                elif self.kontrakt == Kontrakt.NORMALNA and self.zwyciezca_ostatniej_lewy:
                    if self.zwyciezca_ostatniej_lewy == self.grajacy:
                        self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "wzięcie ostatniej lewy"}
                    else:
                        # Wygrywają obaj obrońcy, jeśli jeden z nich wziął ostatnią lewę
                        self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': "wzięcie ostatniej lewy przez obronę"}

                elif punkty_grajacego > punkty_obrony: # Domyślna logika dla np. BEZ_PYTANIA
                    self.zwyciezca_rozdania_info = {'wygrani': [self.grajacy], 'przegrani': self.obroncy, 'powod': "więcej punktów na koniec"}
                else:
                    self.zwyciezca_rozdania_info = {'wygrani': self.obroncy, 'przegrani': [self.grajacy], 'powod': "mniej punktów na koniec"}
        if self.rozdanie_zakonczone:
            self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            self.rozlicz_rozdanie()

    def rozlicz_rozdanie(self):
        if not self.zwyciezca_rozdania_info or 'wygrani' not in self.zwyciezca_rozdania_info:
            self.podsumowanie = {"powod": "Błąd rozdania.", "przyznane_punkty": 0, "wygrani_gracze": []}
            return
        wygrani = self.zwyciezca_rozdania_info['wygrani']
        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0) if self.kontrakt else 0
        mnoznik_gry = 1
        if self.kontrakt == Kontrakt.NORMALNA:
            if self.grajacy in wygrani:
                punkty_obrony = sum(self.punkty_w_rozdaniu[o.nazwa] for o in self.obroncy)
                if punkty_obrony < 33: mnoznik_gry = 2
                if punkty_obrony == 0: mnoznik_gry = 3
            else:
                punkty_grajacego = sum(self.punkty_w_rozdaniu[g.nazwa] for g in self.gracze if g == self.grajacy)
                if punkty_grajacego < 33: mnoznik_gry = 2
                if punkty_grajacego == 0: mnoznik_gry = 3
        punkty_meczu *= mnoznik_gry
        punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart: punkty_meczu *= 2
        if self.grajacy in wygrani:
            # Jeśli wygrał rozgrywający, dostaje pełną pulę
            self.grajacy.punkty_meczu += punkty_meczu
        elif len(wygrani) > 0:
            # Jeśli wygrali obrońcy, dzielą pulę
            punkty_dla_obroncy = punkty_meczu // 2
            for obronca in wygrani: # Iterujemy po liście wygranych, która zawiera obrońców
                obronca.punkty_meczu += punkty_dla_obroncy
        self._dodaj_log('koniec_rozdania', wygrani=[g.nazwa for g in wygrani], punkty=punkty_meczu, powod=self.zwyciezca_rozdania_info.get('powod', ''))
        self.podsumowanie = {
            "wygrani_gracze": [g.nazwa for g in wygrani], "przyznane_punkty": punkty_meczu,
            "kontrakt": self.kontrakt.name if self.kontrakt else "Brak", "atut": self.atut.name if self.atut else "Brak",
            "powod": self.zwyciezca_rozdania_info.get('powod', 'Koniec kart'), "mnoznik_lufy": self.mnoznik_lufy,
            "bonus_z_trzech_kart": self.bonus_z_trzech_kart
        }
    def oblicz_aktualna_stawke(self, mnoznik_dodatkowy: int = 1) -> int:
        """Oblicza i zwraca aktualną potencjalną wartość punktową rozdania."""
        if not self.kontrakt:
            return 0

        punkty_meczu = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
        mnoznik_gry = 1

        # Mnożnik za ugraną grę (1/2/3 pkt) ma zastosowanie tylko w grach normalnych
        if self.kontrakt in [Kontrakt.NORMALNA]:
            # Domyślnie zakładamy najwyższy mnożnik, bo to potencjalna stawka
            mnoznik_gry = 3

        punkty_meczu *= mnoznik_gry
        punkty_meczu *= self.mnoznik_lufy
        if self.bonus_z_trzech_kart:
            punkty_meczu *= 2

        # Stosujemy dodatkowy mnożnik do sprawdzenia "co by było gdyby"
        punkty_meczu *= mnoznik_dodatkowy

        return punkty_meczu