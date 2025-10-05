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
    ZAKONCZONE = auto()
    FAZA_PYTANIA = auto()

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

        if self.kontrakt == Kontrakt.NORMALNA and self.mnoznik_lufy == 1:
            self.faza = FazaGry.FAZA_PYTANIA
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

        if self.faza == FazaGry.FAZA_PYTANIA:
            return [
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'zmiana_kontraktu', 'kontrakt': Kontrakt.BEZ_PYTANIA},
                {'typ': 'pytanie'},
            ]
        
        if self.faza == FazaGry.LICYTACJA:
            return [
                {'typ': 'pas'},
                {'typ': 'przebicie', 'kontrakt': Kontrakt.LEPSZA},
                {'typ': 'przebicie', 'kontrakt': Kontrakt.GORSZA},
                {'typ': 'lufa'},
            ]
        
        if self.faza == FazaGry.LUFA:
            punkty_do_konca_a = 66 - self.druzyny[0].punkty_meczu
            punkty_do_konca_b = 66 - self.druzyny[1].punkty_meczu
            # ZMIANA: Bierzemy większą z wartości (drużynę, która ma mniej punktów)
            max_punkty_do_konca = max(punkty_do_konca_a, punkty_do_konca_b)

            wartosc_bazowa = STAWKI_KONTRAKTOW.get(self.kontrakt, 0)
            if self.kontrakt == Kontrakt.NORMALNA:
                wartosc_bazowa *= 3 
            
            potencjalna_wartosc = wartosc_bazowa * (self.mnoznik_lufy * 2)

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

        elif self.faza == FazaGry.FAZA_PYTANIA:
            if akcja['typ'] == 'zmiana_kontraktu':
                self._ustaw_kontrakt(self.grajacy, akcja['kontrakt'], self.atut)
                self.pasujacy_gracze.clear()
                self.lufa_challenger = None
                self.faza = FazaGry.LUFA
                self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
                if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                    self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            elif akcja['typ'] == 'pytanie':
                self.faza = FazaGry.LICYTACJA
                self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
                while self.gracze[self.kolej_gracza_idx] == self.grajacy:
                    self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4

        elif self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'lufa':
                self.mnoznik_lufy *= 2
                self.faza = FazaGry.ROZGRYWKA
                self.kolej_gracza_idx = self.gracze.index(self.grajacy)
                return

            if akcja['typ'] == 'pas':
                self.pasujacy_gracze.append(gracz)
            elif akcja['typ'] == 'przebicie':
                self.oferty_przebicia.append((gracz, akcja))
            
            self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            while self.gracze[self.kolej_gracza_idx] == self.grajacy:
                 self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
            
            liczba_decyzji = len(self.pasujacy_gracze) + len(self.oferty_przebicia)
            if liczba_decyzji == 3:
                self._rozstrzygnij_licytacje_2()
           
    def rozdaj_karty(self, ilosc: int):
        start_idx = (self.rozdajacy_idx + 1) % 4
        for _ in range(ilosc):
            for i in range(4):
                idx = (start_idx + i) % 4
                karta = self.talia.rozdaj_karte()
                if karta: self.gracze[idx].reka.append(karta)
    
    def rozlicz_rozdanie(self) -> tuple[Druzyna, int, int, int]:
        mnoznik_gry = 1
        druzyna_wygrana = None

        if not self.rozdanie_zakonczone and self.zwyciezca_ostatniej_lewy:
            druzyna_bonus = self.zwyciezca_ostatniej_lewy.druzyna
            self.punkty_w_rozdaniu[druzyna_bonus.nazwa] += 12
        
        if self.rozdanie_zakonczone and self.zwyciezca_rozdania:
            druzyna_wygrana = self.zwyciezca_rozdania
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
            return True

        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        reka_gracza = gracz.reka

        karty_do_koloru = [k for k in reka_gracza if k.kolor == kolor_wiodacy]
        
        if karty_do_koloru:
            if karta.kolor != kolor_wiodacy:
                return False  # Twarda zasada: musisz dołożyć do koloru, jeśli możesz.

            is_trumped = False
            if self.atut:
                if any(k.kolor == self.atut for _, k in self.aktualna_lewa):
                    is_trumped = True
            
            # Jeśli lewa jest przebita atutem, obowiązek przebijania w kolorze znika.
            # Wystarczy dołożyć dowolną kartę do koloru.
            if is_trumped:
                return True

            # Jeśli lewa nie jest przebita, obowiązuje zasada przebijania w kolorze.
            karty_wiodace_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == kolor_wiodacy]
            najwyzsza_karta_na_stole = max(karty_wiodace_na_stole, key=lambda c: c.ranga.value)
            
            wyzsze_karty_w_rece = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_karta_na_stole.ranga.value]

            if wyzsze_karty_w_rece:
                # Jeśli masz czym przebić, musisz użyć jednej z tych kart.
                return karta in wyzsze_karty_w_rece
            else:
                # Jeśli nie masz czym przebić, dowolna karta do koloru jest OK.
                return True
        
        # Logika dla braku kart do koloru (obowiązek atutu) pozostaje bez zmian.
        if self.atut and any(k.kolor == self.atut for k in reka_gracza):
            if karta.kolor != self.atut:
                return False

            atuty_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == self.atut]
            if not atuty_na_stole:
                return True

            najwyzszy_atut_na_stole = max(atuty_na_stole, key=lambda c: c.ranga.value)
            wyzsze_atuty_w_rece = [k for k in reka_gracza if k.kolor == self.atut and k.ranga.value > najwyzszy_atut_na_stole.ranga.value]

            if wyzsze_atuty_w_rece:
                return karta in wyzsze_atuty_w_rece
            else:
                return True
        
        # Jeśli nie masz kart do koloru ani atutów (lub nie ma atutów w grze), możesz zagrać cokolwiek.
        return True

    def _zakoncz_lewe(self):
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
                        karty=[str(k[1]) for k in self.aktualna_lewa]) # Dodajemy log
        
        druzyna_zwyciezcy = zwyciezca_lewy.druzyna
        self.punkty_w_rozdaniu[druzyna_zwyciezcy.nazwa] += punkty_w_lewie
        zwyciezca_lewy.wygrane_karty.extend([karta for _, karta in self.aktualna_lewa])
        
        if sum(len(g.wygrane_karty) for g in self.gracze) == 24:
            self.zwyciezca_ostatniej_lewy = zwyciezca_lewy

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

        self.aktualna_lewa.clear()
        self.kolej_gracza_idx = self.gracze.index(zwyciezca_lewy)
        
    def zagraj_karte(self, gracz: Gracz, karta: Karta) -> dict:
        if not self._waliduj_ruch(gracz, karta):
            print(f"BŁĄD: Ruch gracza {gracz} kartą {karta} jest nielegalny!")
            return {}
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta)) # Dodajemy log
        punkty_z_meldunku = 0
        if not self.aktualna_lewa and self.kontrakt in [Kontrakt.NORMALNA, Kontrakt.BEZ_PYTANIA]:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty_z_meldunku = 40 if karta.kolor == self.atut else 20
                        self.punkty_w_rozdaniu[gracz.druzyna.nazwa] += punkty_z_meldunku
                        self.zadeklarowane_meldunki.append((gracz, karta.kolor))

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
        
    def _rozstrzygnij_licytacje_2(self):
        """Wyłania zwycięzcę po zakończeniu fazy przebicia."""
        oferty_lepsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.LEPSZA]
        nowy_grajacy, nowa_akcja = (None, None)
        if oferty_lepsza:
            nowy_grajacy, nowa_akcja = oferty_lepsza[0]
        else:
            oferty_gorsza = [o for o in self.oferty_przebicia if o[1]['kontrakt'] == Kontrakt.GORSZA]
            if oferty_gorsza:
                nowy_grajacy, nowa_akcja = oferty_gorsza[0]

        if nowy_grajacy:
            print(f"  INFO: Licytację przebił {nowy_grajacy.nazwa} z kontraktem {nowa_akcja['kontrakt'].name}.")
            self._ustaw_kontrakt(nowy_grajacy, nowa_akcja['kontrakt'], None)
            
            self.pasujacy_gracze.clear()
            self.lufa_challenger = None
            self.faza = FazaGry.LUFA
            self.kolej_gracza_idx = (self.gracze.index(self.grajacy) + 1) % 4
            if self.gracze[self.kolej_gracza_idx] == self.nieaktywny_gracz:
                 self.kolej_gracza_idx = (self.kolej_gracza_idx + 1) % 4
        else:
            print("  INFO: Wszyscy spasowali, pierwotny kontrakt zostaje.")
            self.faza = FazaGry.ROZGRYWKA
            self.kolej_gracza_idx = self.gracze.index(self.grajacy)