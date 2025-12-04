# silnik_tysiac.py
"""
Silnik gry w Tysiąca
Implementacja zasad gry w Tysiąca dla 2, 3 i 4 graczy
"""

import random
import copy
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

# ==========================================================================
# SEKCJA 1: PODSTAWOWE DEFINICJE (ENUMY, KARTY, TALIA)
# ==========================================================================

class Kolor(Enum):
    """Reprezentuje kolory kart - TAKIE SAME JAK W GRZ 66"""
    CZERWIEN = auto()  # ♥ Kier - 100 pkt za meldunek
    DZWONEK = auto()   # ♦ Karo - 80 pkt za meldunek  
    ZOLADZ = auto()    # ♣ Trefl - 60 pkt za meldunek
    WINO = auto()      # ♠ Pik - 40 pkt za meldunek

class Ranga(Enum):
    """Reprezentuje rangi kart - TAKIE SAME JAK W GRZE 66"""
    DZIEWIATKA = auto()  # 9 - 0 punktów
    WALET = auto()       # J - 2 punkty
    DAMA = auto()        # Q - 3 punkty
    KROL = auto()        # K - 4 punkty
    DZIESIATKA = auto()  # 10 - 10 punktów
    AS = auto()          # A - 11 punktów

# Wartości punktowe kart - TAKIE SAME JAK W GRZE 66
WARTOSCI_KART = {
    Ranga.AS: 11,
    Ranga.DZIESIATKA: 10,
    Ranga.KROL: 4,
    Ranga.DAMA: 3,
    Ranga.WALET: 2,
    Ranga.DZIEWIATKA: 0,
}

# Słownik do sortowania kart - TAKI SAM JAK W GRZE 66
KOLEJNOSC_KOLOROW_SORT = {
    Kolor.CZERWIEN: 1,
    Kolor.ZOLADZ: 2,
    Kolor.DZWONEK: 3,
    Kolor.WINO: 4,
}

# Wartości meldunków w Tysiącu (para K+D)
WARTOSCI_MELDUNKOW = {
    Kolor.CZERWIEN: 100,  # Czerwień
    Kolor.DZWONEK: 80,    # Dzwonek
    Kolor.ZOLADZ: 60,     # Żołądź
    Kolor.WINO: 40,       # Wino
}



@dataclass(frozen=True)
class Karta:
    """Reprezentuje pojedynczą kartę do gry - TAKA SAMA JAK W GRZE 66"""
    ranga: Ranga
    kolor: Kolor

    @property
    def wartosc(self) -> int:
        """Zwraca wartość punktową karty."""
        return WARTOSCI_KART[self.ranga]

    def __str__(self) -> str:
        """Zwraca czytelną reprezentację karty."""
        return f"{self.ranga.name.capitalize()} {self.kolor.name.capitalize()}"

    def __eq__(self, other):
        if not isinstance(other, Karta):
            return NotImplemented
        return self.ranga == other.ranga and self.kolor == other.kolor

    def __hash__(self):
        return hash((self.ranga, self.kolor))

class Talia:
    """Reprezentuje talię 24 kart - TAKA SAMA JAK W GRZE 66"""
    def __init__(self):
        self.karty = self._stworz_pelna_talie()
        self.tasuj()

    def _stworz_pelna_talie(self) -> List[Karta]:
        """Tworzy standardową talię 24 kart."""
        return [Karta(ranga, kolor) for kolor in Kolor for ranga in Ranga]

    def tasuj(self):
        """Tasuje karty w talii."""
        random.shuffle(self.karty)

    def rozdaj_karte(self) -> Optional[Karta]:
        """Pobiera i zwraca jedną kartę z góry talii."""
        if self.karty:
            return self.karty.pop()
        return None

    def __len__(self) -> int:
        return len(self.karty)

class FazaGry(Enum):
    """Definiuje fazy gry w Tysiąc."""
    PRZED_ROZDANIEM = auto()
    LICYTACJA = auto()
    WYMIANA_MUSZKU = auto()
    DECYZJA_PO_MUSIKU = auto()  # NOWA FAZA: zmiana kontraktu lub bomba
    ROZGRYWKA = auto()
    PODSUMOWANIE_ROZDANIA = auto()
    ZAKONCZONE = auto()

# ==========================================================================
# SEKCJA 2: GRACZE
# ==========================================================================

@dataclass
class Gracz:
    """Reprezentuje pojedynczego gracza - TAKI SAM JAK W GRZE 66"""
    nazwa: str
    reka: List[Karta] = field(default_factory=list)
    wygrane_karty: List[Karta] = field(default_factory=list)
    punkty_meczu: int = 0
    zablokowany_na_800: bool = False  # Specyficzne dla Tysiąca

    def __str__(self) -> str:
        return self.nazwa

# ==========================================================================
# SEKCJA 3: KLASA ROZDANIE TYSIĄC
# ==========================================================================

class RozdanieTysiac:
    """
    Zarządza logiką pojedynczego rozdania w grze Tysiąc.
    Obsługuje 2, 3 i 4 graczy.
    """
    
    def __init__(self, gracze: List[Gracz], rozdajacy_idx: int, tryb: str = '3p'):
        """
        Inicjalizuje nowe rozdanie.
        
        Args:
            gracze: Lista graczy (2, 3 lub 4)
            rozdajacy_idx: Indeks gracza rozdającego
            tryb: '2p', '3p' lub '4p'
        """
        self.gracze = gracze
        self.rozdajacy_idx = rozdajacy_idx
        self.tryb = tryb
        self.talia = Talia()
        
        # Walidacja liczby graczy
        liczba_graczy = len(gracze)
        if tryb == '2p' and liczba_graczy != 2:
            raise ValueError("Tryb 2p wymaga 2 graczy")
        elif tryb == '3p' and liczba_graczy != 3:
            raise ValueError("Tryb 3p wymaga 3 graczy")
        elif tryb == '4p' and liczba_graczy != 4:
            raise ValueError("Tryb 4p wymaga 4 graczy")
        
        # Stan licytacji
        self.minimalna_licytacja = 100
        self.aktualna_licytacja = 0
        self.grajacy: Optional[Gracz] = None
        self.licytujacy_idx: Optional[int] = None
        self.pasujacy_gracze: List[Gracz] = []
        self.licytacja_wymuszona = False  # True jeśli wszyscy spasowali i gracz dostał automatyczny kontrakt
        
        # Muzyk (tylko 4p)
        self.muzyk_idx: Optional[int] = None
        self.muzyk_punkty = 0
        
        # Muskat/Musik
        self.musik_odkryty = False
        self.musik_karty: List[Karta] = []
        if tryb == '2p':
            self.musik_1: List[Karta] = []
            self.musik_2: List[Karta] = []
            self.musik_wybrany: Optional[int] = None
            # Oryginalne karty z muzików (do liczenia punktów na końcu)
            self.musik_1_oryginalny: List[Karta] = []
            self.musik_2_oryginalny: List[Karta] = []
        
        # Stan kontraktu i atutu
        self.kontrakt_wartosc = 0
        self.atut: Optional[Kolor] = None
        self.zadeklarowane_meldunki: List[Tuple[Gracz, Kolor]] = []
        
        # Stan rozgrywki
        self.faza: FazaGry = FazaGry.PRZED_ROZDANIEM
        self.kolej_gracza_idx: Optional[int] = None
        self.aktualna_lewa: List[Tuple[Gracz, Karta]] = []
        self.zwyciezca_ostatniej_lewy: Optional[Gracz] = None
        
        # Punktacja
        self.punkty_w_rozdaniu: Dict[str, int] = {g.nazwa: 0 for g in gracze}
        
        # Bomba
        self.bomba_uzyta: Dict[str, bool] = {g.nazwa: False for g in gracze}
        
        # Zakończenie rozdania
        self.rozdanie_zakonczone = False
        self.podsumowanie: Dict[str, Any] = {}
        
        # Lewa do zamknięcia
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy: Optional[Gracz] = None
        self.ostatnia_lewa = False
        self.karty_ostatniej_lewy: List[Tuple[str, str]] = []
        
        # Historia - TAKA SAMA JAK W GRZE 66
        self.szczegolowa_historia: List[Dict[str, Any]] = []
    
    def _get_player_index(self, player: Optional[Gracz]) -> Optional[int]:
        """Znajduje indeks gracza - TAKIE SAMO JAK W GRZE 66."""
        if player is None:
            return None
        try:
            return next(i for i, p in enumerate(self.gracze) if p.nazwa == player.nazwa)
        except StopIteration:
            return None
    
    def _konwertuj_na_serializowalne(self, obj):
        """
        Rekurencyjnie konwertuje obiekty Karta na stringi.
        Zapewnia że wszystkie dane można zserializować do JSON.
        """
        if isinstance(obj, Karta):
            return str(obj)
        elif isinstance(obj, list):
            return [self._konwertuj_na_serializowalne(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._konwertuj_na_serializowalne(v) for k, v in obj.items()}
        elif isinstance(obj, tuple):
            return tuple(self._konwertuj_na_serializowalne(item) for item in obj)
        elif isinstance(obj, Kolor):
            return obj.name
        elif isinstance(obj, Ranga):
            return obj.name
        elif isinstance(obj, FazaGry):
            return obj.name
        elif isinstance(obj, Gracz):
            return obj.nazwa
        else:
            return obj
    
    def _dodaj_log(self, typ: str, **kwargs):
        """Dodaje wpis do historii - konwertuje wszystkie obiekty na serializowalne."""
        # Rekurencyjnie konwertuj wszystkie obiekty
        kwargs_czyste = self._konwertuj_na_serializowalne(kwargs)
        log = {'typ': typ, **kwargs_czyste}
        self.szczegolowa_historia.append(log)
    
    def rozpocznij_nowe_rozdanie(self):
        """Rozpoczyna nowe rozdanie - rozdaje karty i rozpoczyna licytację."""
        self._dodaj_log('nowe_rozdanie', rozdajacy=self.gracze[self.rozdajacy_idx].nazwa)
        
        # Wyczyść stan graczy
        for gracz in self.gracze:
            gracz.reka.clear()
            gracz.wygrane_karty.clear()
        
        # Resetuj stan licytacji
        self.pasujacy_gracze = []
        self.grajacy = None
        self.kontrakt_wartosc = 0
        self.aktualna_licytacja = 0
        self.licytacja_wymuszona = False
        
        # Resetuj stan musiku
        self.musik_odkryty = False
        self.musik_karty = []
        if self.tryb == '2p':
            self.musik_1 = []
            self.musik_2 = []
            self.musik_wybrany = None
            self.musik_1_oryginalny = []
            self.musik_2_oryginalny = []
        
        # Resetuj stan rozgrywki
        self.atut = None
        self.zadeklarowane_meldunki = []
        self.aktualna_lewa = []
        self.lewa_numer = 0
        self.lewa_do_zamkniecia = False
        self.ostatnia_lewa = False
        self.zwyciezca_lewy = None
        self.wynik_rozdania = None
        
        # Rozdaj karty
        if self.tryb == '2p':
            self._rozdaj_karty_2p()
        elif self.tryb == '3p':
            self._rozdaj_karty_3p()
        elif self.tryb == '4p':
            self._rozdaj_karty_4p()
        
        # Rozpocznij licytację
        self.faza = FazaGry.LICYTACJA
        self.licytujacy_idx = (self.rozdajacy_idx + 1) % len(self.gracze)
        
        # W trybie 2p: upewnij się, że gracz ludzki (nie bot) zaczyna licytację
        if self.tryb == '2p':
            # Sprawdź, kto jest botem a kto graczem ludzkim
            for i, gracz in enumerate(self.gracze):
                # Zakładamy, że bot ma w nazwie 'Bot' lub 'bot'
                if not ('Bot' in gracz.nazwa or 'bot' in gracz.nazwa.lower()):
                    # To jest gracz ludzki, niech on zaczyna
                    self.licytujacy_idx = i
                    break
        
        # W trybie 4p pomiń muzyka
        if self.tryb == '4p':
            self.muzyk_idx = self.rozdajacy_idx
            if self.licytujacy_idx == self.muzyk_idx:
                self.licytujacy_idx = (self.licytujacy_idx + 1) % len(self.gracze)
        
        self.kolej_gracza_idx = self.licytujacy_idx
        self.aktualna_licytacja = self.minimalna_licytacja
    
    def _rozdaj_karty_2p(self):
        """Rozdaje karty w trybie 2 osobowym: 10+10+2+2 (musiki)."""
        for _ in range(10):
            for i in range(2):
                idx = (self.rozdajacy_idx + 1 + i) % 2
                karta = self.talia.rozdaj_karte()
                if karta:
                    self.gracze[idx].reka.append(karta)
        
        self.musik_1 = [self.talia.rozdaj_karte() for _ in range(2) if self.talia.karty]
        self.musik_2 = [self.talia.rozdaj_karte() for _ in range(2) if self.talia.karty]
        self.musik_1 = [k for k in self.musik_1 if k]
        self.musik_2 = [k for k in self.musik_2 if k]
        
        # Zapisz oryginalne karty z muzików (do liczenia punktów na końcu)
        self.musik_1_oryginalny = self.musik_1.copy()
        self.musik_2_oryginalny = self.musik_2.copy()
        
        # Sortuj z KOLEJNOSC_KOLOROW_SORT
        for gracz in self.gracze:
            gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
    
    def _rozdaj_karty_3p(self):
        """Rozdaje karty w trybie 3 osobowym: 7+7+7+3 (musik)."""
        for _ in range(7):
            for i in range(3):
                idx = (self.rozdajacy_idx + 1 + i) % 3
                karta = self.talia.rozdaj_karte()
                if karta:
                    self.gracze[idx].reka.append(karta)
        
        self.musik_karty = [self.talia.rozdaj_karte() for _ in range(3) if self.talia.karty]
        self.musik_karty = [k for k in self.musik_karty if k]
        
        for gracz in self.gracze:
            gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
    
    def _rozdaj_karty_4p(self):
        """Rozdaje karty w trybie 4 osobowym: 7+7+7+3 (musik dla muzyka)."""
        self.muzyk_idx = self.rozdajacy_idx
        
        # Gracze aktywni (wszyscy oprócz muzyka)
        gracze_aktywni = [i for i in range(4) if i != self.muzyk_idx]
        
        # Rozdaj po 7 kart każdemu aktywnemu graczowi
        for _ in range(7):
            for i in gracze_aktywni:
                karta = self.talia.rozdaj_karte()
                if karta:
                    self.gracze[i].reka.append(karta)
        
        # Pozostałe 3 karty to musik
        self.musik_karty = [self.talia.rozdaj_karte() for _ in range(3) if self.talia.karty]
        self.musik_karty = [k for k in self.musik_karty if k]
        
        # Sortuj karty w rękach graczy (włącznie z muzykiem który ma pustą rękę)
        for gracz in self.gracze:
            gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
    
    def _oblicz_meldunki_w_rece(self, gracz: Gracz) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Oblicza sumę możliwych meldunków w ręce gracza.
        
        Returns:
            Tuple: (suma_punktów, lista_meldunków)
            gdzie lista_meldunków to [{'kolor': Kolor, 'punkty': int}, ...]
        """
        suma = 0
        meldunki = []
        for kolor in Kolor:
            ma_krola = any(k.kolor == kolor and k.ranga == Ranga.KROL for k in gracz.reka)
            ma_dame = any(k.kolor == kolor and k.ranga == Ranga.DAMA for k in gracz.reka)
            if ma_krola and ma_dame:
                punkty = WARTOSCI_MELDUNKOW[kolor]
                suma += punkty
                meldunki.append({'kolor': kolor.name, 'punkty': punkty})
        return suma, meldunki
    
    def _oblicz_max_licytacje(self, gracz: Gracz) -> int:
        """
        Oblicza maksymalną możliwą licytację dla gracza.
        Max = 120 (punkty za karty) + suma meldunków w ręce.
        """
        suma_meldunkow, _ = self._oblicz_meldunki_w_rece(gracz)
        max_licytacja = 120 + suma_meldunkow
        # Nie więcej niż 360 (limit gry)
        return min(max_licytacja, 360)
    
    def get_mozliwe_akcje(self, gracz: Gracz) -> List[Dict[str, Any]]:
        """Zwraca możliwe akcje dla gracza."""
        gracz_idx = self._get_player_index(gracz)
        
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
            return []
        
        if self.tryb == '4p' and gracz_idx == self.muzyk_idx:
            return []
        
        # LICYTACJA
        if self.faza == FazaGry.LICYTACJA:
            akcje = []
            
            if gracz not in self.pasujacy_gracze:
                akcje.append({'typ': 'pas'})
            
            # Oblicz max licytację na podstawie meldunków
            max_licytacja = self._oblicz_max_licytacje(gracz)
            
            nastepna_licytacja = self.aktualna_licytacja + 10
            if nastepna_licytacja <= max_licytacja:
                akcje.append({'typ': 'licytuj', 'wartosc': nastepna_licytacja, 'max_wartosc': max_licytacja})
            
            return akcje
        
        # WYMIANA MUSZKU
        if self.faza == FazaGry.WYMIANA_MUSZKU:
            if gracz != self.grajacy:
                return []
            
            akcje = []
            
            if self.tryb == '2p' and not self.musik_odkryty:
                akcje.append({'typ': 'wybierz_musik', 'musik': 1})
                akcje.append({'typ': 'wybierz_musik', 'musik': 2})
                return akcje
            
            if self.musik_odkryty:
                if self.tryb == '2p':
                    akcje.append({'typ': 'oddaj_karty', 'liczba': 2})
                elif self.tryb in ['3p', '4p']:
                    liczba_aktywnych = len(self.gracze) - 1
                    if self.tryb == '4p':
                        liczba_aktywnych -= 1
                    akcje.append({'typ': 'rozdaj_karty', 'liczba': liczba_aktywnych})
                
                # Bomba usunięta z tej fazy - teraz jest w DECYZJA_PO_MUSIKU
                
                return akcje
        
        # DECYZJA PO MUSIKU (zmiana kontraktu / bomba)
        if self.faza == FazaGry.DECYZJA_PO_MUSIKU:
            if gracz != self.grajacy:
                return []
            
            akcje = []
            
            # Oblicz max kontrakt na podstawie meldunków (po wzięciu musiku)
            max_kontrakt = self._oblicz_max_licytacje(gracz)
            suma_meldunkow, lista_meldunkow = self._oblicz_meldunki_w_rece(gracz)
            
            # Opcja 1: Kontynuuj bez zmian
            akcje.append({'typ': 'kontynuuj'})
            
            # Opcja 2: Zmień kontrakt (możliwe wartości od obecnej do max)
            mozliwe_kontrakty = []
            for wartosc in range(self.kontrakt_wartosc + 10, max_kontrakt + 10, 10):
                if wartosc <= max_kontrakt:
                    mozliwe_kontrakty.append(wartosc)
            if mozliwe_kontrakty:
                akcje.append({
                    'typ': 'zmien_kontrakt', 
                    'mozliwe_wartosci': mozliwe_kontrakty,
                    'max_wartosc': max_kontrakt,
                    'meldunki': lista_meldunkow
                })
            
            # Opcja 3: Bomba (jeśli jeszcze nie użyta w tym meczu)
            if not self.bomba_uzyta[gracz.nazwa]:
                akcje.append({'typ': 'bomba'})
            
            return akcje
        
        return []
    
    def wykonaj_akcje(self, gracz: Gracz, akcja: Dict[str, Any]):
        """Wykonuje akcję gracza."""
        gracz_idx = self._get_player_index(gracz)
        
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
            return
        
        self._dodaj_log('akcja', gracz=gracz.nazwa, akcja=akcja)
        
        if self.faza == FazaGry.LICYTACJA:
            if akcja['typ'] == 'pas':
                self.pasujacy_gracze.append(gracz)
                self._sprawdz_koniec_licytacji()
            
            elif akcja['typ'] == 'licytuj':
                wartosc = akcja['wartosc']
                max_licytacja = self._oblicz_max_licytacje(gracz)
                
                # Walidacja licytacji
                if wartosc > max_licytacja:
                    print(f"[BŁĄD] Licytacja {wartosc} przekracza limit gracza ({max_licytacja})")
                    return
                if wartosc <= self.aktualna_licytacja:
                    print(f"[BŁĄD] Licytacja {wartosc} musi być wyższa niż obecna ({self.aktualna_licytacja})")
                    return
                
                self.aktualna_licytacja = wartosc
                self.grajacy = gracz
                self._nastepny_licytujacy()
        
        elif self.faza == FazaGry.WYMIANA_MUSZKU:
            if akcja['typ'] == 'wybierz_musik':
                self._wybierz_musik(gracz, akcja['musik'])
            
            elif akcja['typ'] == 'oddaj_karty':
                karty = akcja.get('karty', [])
                self._oddaj_karty(gracz, karty)
            
            elif akcja['typ'] == 'rozdaj_karty':
                rozdanie = akcja.get('rozdanie', {})
                self._rozdaj_karty_z_reki(gracz, rozdanie)
        
        elif self.faza == FazaGry.DECYZJA_PO_MUSIKU:
            if akcja['typ'] == 'kontynuuj':
                self._kontynuuj_bez_zmian(gracz)
            
            elif akcja['typ'] == 'zmien_kontrakt':
                nowa_wartosc = akcja.get('wartosc', self.kontrakt_wartosc)
                self._zmien_kontrakt(gracz, nowa_wartosc)
            
            elif akcja['typ'] == 'bomba':
                self._rzuc_bombe(gracz)
    
    def _nastepny_licytujacy(self):
        """Przekazuje turę następnemu graczowi w licytacji."""
        if self.licytujacy_idx is None:
            return
        
        aktywni_gracze = len(self.gracze)
        if self.tryb == '4p':
            aktywni_gracze -= 1
        
        # Sprawdź czy to koniec licytacji
        if len(self.pasujacy_gracze) >= aktywni_gracze - 1:
            # Jeśli nikt nie wylicytował, pierwszy gracz po rozdającym dostaje kontrakt na 100
            if not self.grajacy:
                self._zakoncz_licytacje()
            else:
                self._zakoncz_licytacje()
            return
        
        # Znajdź następnego aktywnego gracza
        next_idx = (self.licytujacy_idx + 1) % len(self.gracze)
        petla_count = 0
        while (self.gracze[next_idx] in self.pasujacy_gracze or 
               (self.tryb == '4p' and next_idx == self.muzyk_idx)):
            next_idx = (next_idx + 1) % len(self.gracze)
            petla_count += 1
            if petla_count > len(self.gracze):  # Zabezpieczenie przed nieskończoną pętlą
                self._zakoncz_licytacje()
                return
        
        self.licytujacy_idx = next_idx
        self.kolej_gracza_idx = next_idx
    
    def _sprawdz_koniec_licytacji(self):
        """Sprawdza, czy licytacja się skończyła."""
        aktywni_gracze = len(self.gracze)
        if self.tryb == '4p':
            aktywni_gracze -= 1
        
        if len(self.pasujacy_gracze) >= aktywni_gracze - 1:
            self._zakoncz_licytacje()
    
    def _zakoncz_licytacje(self):
        """Kończy licytację i przechodzi do wymiany muszku."""
        # Sprawdź czy ktoś wylicytował (self.grajacy został ustawiony)
        if not self.grajacy:
            # Wszyscy spasowali - pierwszy gracz po rozdającym dostaje kontrakt na 100
            print("[LICYTACJA] Wszyscy spasowali - kontrakt 100 dla pierwszego gracza")
            
            # Pierwszy gracz po rozdającym (ten który zaczął licytację)
            pierwszy_gracz_idx = (self.rozdajacy_idx + 1) % len(self.gracze)
            
            # W trybie 4p pomiń muzyka
            if self.tryb == '4p' and pierwszy_gracz_idx == self.muzyk_idx:
                pierwszy_gracz_idx = (pierwszy_gracz_idx + 1) % len(self.gracze)
            
            # Przypisz kontrakt
            self.grajacy = self.gracze[pierwszy_gracz_idx]
            self.kontrakt_wartosc = 100  # Minimalny kontrakt
            self.aktualna_licytacja = 100
            self.licytacja_wymuszona = True  # Gracz nie miał wyboru!
            
            self._dodaj_log('wszyscy_spasowali', 
                          grajacy=self.grajacy.nazwa, 
                          kontrakt=100,
                          info="Kontrakt przechodzi automatycznie na 100")
        
        # Standardowe zakończenie licytacji
        if not self.kontrakt_wartosc:
            self.kontrakt_wartosc = self.aktualna_licytacja
        
        self._dodaj_log('koniec_licytacji', grajacy=self.grajacy.nazwa, wartosc=self.kontrakt_wartosc)
        
        self.faza = FazaGry.WYMIANA_MUSZKU
        gracz_idx = self._get_player_index(self.grajacy)
        self.kolej_gracza_idx = gracz_idx
        
        if self.tryb in ['3p', '4p']:
            self._odkryj_musik()
    
    def _wybierz_musik(self, gracz: Gracz, musik_nr: int):
        """Grający wybiera jeden z dwóch musików (tryb 2p)."""
        self.musik_wybrany = musik_nr
        if musik_nr == 1:
            gracz.reka.extend(self.musik_1)
        else:
            gracz.reka.extend(self.musik_2)
        
        gracz.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
        self.musik_odkryty = True
        self._dodaj_log('wybrano_musik', gracz=gracz.nazwa, musik=musik_nr)
    
    def _odkryj_musik(self):
        """Odkrywa musik i dodaje karty do ręki grającego (tryb 3p/4p)."""
        if not self.grajacy:
            return
        
        # Sprawdź bonusy w musiku (tylko tryb 4p)
        bonus_as = 0
        bonus_meldunek = 0
        
        if self.tryb == '4p':
            # Bonus za asy w musiku
            for karta in self.musik_karty:
                if karta.ranga == Ranga.AS:
                    bonus_as += 50  # Każdy as to 50 pkt
            
            # Bonus za pary król-dama w musiku
            for kolor in Kolor:
                ma_krola = any(k.kolor == kolor and k.ranga == Ranga.KROL for k in self.musik_karty)
                ma_dame = any(k.kolor == kolor and k.ranga == Ranga.DAMA for k in self.musik_karty)
                if ma_krola and ma_dame:
                    bonus_meldunek += WARTOSCI_MELDUNKOW[kolor]
            
            # Przyznaj punkty muzykowi
            if self.muzyk_idx is not None:
                muzyk = self.gracze[self.muzyk_idx]
                self.muzyk_punkty = bonus_as + bonus_meldunek
                if self.muzyk_punkty > 0:
                    muzyk.punkty_meczu += self.muzyk_punkty
                    self._dodaj_log('bonus_muzyk', gracz=muzyk.nazwa, punkty=self.muzyk_punkty,
                                  szczegoly={'asy': bonus_as, 'meldunki': bonus_meldunek})
        
        # Dodaj karty z musiku do ręki grającego
        self.grajacy.reka.extend(self.musik_karty)
        self.grajacy.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
        
        # Logowanie odkrycia musiku
        if self.kontrakt_wartosc == 100:
            self._dodaj_log('musik_odkryty', tylko_grajacy=True)
        else:
            self._dodaj_log('musik_odkryty', widoczny_dla_wszystkich=True, karty=[str(k) for k in self.musik_karty])
        
        self.musik_odkryty = True
    
    def _oddaj_karty(self, gracz: Gracz, karty: List[Karta]):
        """Grający odkłada karty do musiku (tryb 2p)."""
        if len(karty) != 2:
            print(f"[BŁĄD] Próba oddania {len(karty)} kart zamiast 2")
            return
        
        # Sprawdź czy karty są w ręce gracza
        for karta in karty:
            if karta not in gracz.reka:
                print(f"[BŁĄD] Karta {karta} nie jest w ręce gracza {gracz.nazwa}")
                return
        
        # Usuń karty z ręki
        for karta in karty:
            gracz.reka.remove(karta)
        
        # Zapisz karty w odpowiednim musiku
        if self.musik_wybrany == 1:
            self.musik_1 = karty
            # Zaktualizuj oryginalny musik (do liczenia punktów)
            self.musik_1_oryginalny = karty.copy()
        else:
            self.musik_2 = karty
            # Zaktualizuj oryginalny musik (do liczenia punktów)
            self.musik_2_oryginalny = karty.copy()
        
        self._dodaj_log('oddano_karty', gracz=gracz.nazwa, liczba=len(karty))
        
        # Przejdź do fazy decyzji (zmiana kontraktu / bomba)
        self._rozpocznij_faze_decyzji()
    
    def _rozdaj_karty_z_reki(self, gracz: Gracz, rozdanie: Dict[str, Karta]):
        """Grający rozdaje karty z ręki pozostałym graczom (tryb 3p/4p)."""
        for nazwa_gracza, karta in rozdanie.items():
            if karta in gracz.reka:
                gracz.reka.remove(karta)
                for g in self.gracze:
                    if g.nazwa == nazwa_gracza:
                        g.reka.append(karta)
                        g.reka.sort(key=lambda k: (KOLEJNOSC_KOLOROW_SORT[k.kolor], -k.ranga.value))
                        break
        
        self._dodaj_log('rozdano_karty', gracz=gracz.nazwa)
        self._rozpocznij_rozgrywke()
    
    def _rzuc_bombe(self, gracz: Gracz):
        """Grający rzuca bombę - anuluje kontrakt."""
        self.bomba_uzyta[gracz.nazwa] = True
        self._dodaj_log('bomba', gracz=gracz.nazwa)
        
        if self.tryb == '2p':
            przeciwnik = next(g for g in self.gracze if g != gracz)
            przeciwnik.punkty_meczu += 120
        else:
            punkty_na_gracza = 60
            for g in self.gracze:
                if g != gracz and (self.tryb == '3p' or g != self.gracze[self.muzyk_idx]):
                    g.punkty_meczu += punkty_na_gracza
        
        self.rozdanie_zakonczone = True
        self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
        self.podsumowanie = {
            'bomba': True,
            'grajacy': gracz.nazwa,
            'przyznane_punkty': 120 if self.tryb == '2p' else 60
        }
    
    def _rozpocznij_faze_decyzji(self):
        """Rozpoczyna fazę decyzji po oddaniu kart (zmiana kontraktu / bomba)."""
        # Jeśli licytacja była wymuszona (wszyscy spasowali), pomiń fazę decyzji
        if self.licytacja_wymuszona:
            print(f"[DECYZJA] Pomijam fazę decyzji - licytacja była wymuszona (kontrakt 100)")
            self._rozpocznij_rozgrywke()
            return
        
        self.faza = FazaGry.DECYZJA_PO_MUSIKU
        gracz_idx = self._get_player_index(self.grajacy)
        self.kolej_gracza_idx = gracz_idx
        self._dodaj_log('faza_decyzji', gracz=self.grajacy.nazwa, kontrakt=self.kontrakt_wartosc)
        print(f"[DECYZJA] Gracz {self.grajacy.nazwa} wybiera: zmiana kontraktu ({self.kontrakt_wartosc}) lub bomba")
    
    def _zmien_kontrakt(self, gracz: Gracz, nowa_wartosc: int):
        """Zmienia wartość kontraktu na nową wartość."""
        if nowa_wartosc < self.kontrakt_wartosc:
            print(f"[BŁĄD] Nowa wartość kontraktu ({nowa_wartosc}) nie może być mniejsza niż obecna ({self.kontrakt_wartosc})")
            return
        
        # Sprawdź max na podstawie meldunków
        max_kontrakt = self._oblicz_max_licytacje(gracz)
        if nowa_wartosc > max_kontrakt:
            print(f"[BŁĄD] Nowa wartość kontraktu ({nowa_wartosc}) przekracza limit ({max_kontrakt}) wynikający z meldunków")
            return
        
        if nowa_wartosc % 10 != 0:
            print(f"[BŁĄD] Wartość kontraktu musi być wielokrotnością 10")
            return
        
        stara_wartosc = self.kontrakt_wartosc
        self.kontrakt_wartosc = nowa_wartosc
        self._dodaj_log('zmiana_kontraktu', gracz=gracz.nazwa, stara_wartosc=stara_wartosc, nowa_wartosc=nowa_wartosc)
        print(f"[DECYZJA] Gracz {gracz.nazwa} zmienia kontrakt: {stara_wartosc} -> {nowa_wartosc}")
        
        # Przejdź do rozgrywki
        self._rozpocznij_rozgrywke()
    
    def _kontynuuj_bez_zmian(self, gracz: Gracz):
        """Kontynuuje grę bez zmiany kontraktu."""
        self._dodaj_log('kontynuuj', gracz=gracz.nazwa, kontrakt=self.kontrakt_wartosc)
        print(f"[DECYZJA] Gracz {gracz.nazwa} kontynuuje z kontraktem {self.kontrakt_wartosc}")
        
        # Przejdź do rozgrywki
        self._rozpocznij_rozgrywke()
    
    def _rozpocznij_rozgrywke(self):
        """Rozpoczyna fazę rozgrywki."""
        self.faza = FazaGry.ROZGRYWKA
        gracz_idx = self._get_player_index(self.grajacy)
        self.kolej_gracza_idx = gracz_idx
        self._dodaj_log('start_rozgrywki', pierwszy_gracz=self.grajacy.nazwa)
    
    def zagraj_karte(self, gracz: Gracz, karta: Karta) -> Dict[str, Any]:
        """Obsługuje zagranie karty przez gracza."""
        if not self._waliduj_ruch(gracz, karta):
            return {}
        
        self._dodaj_log('zagranie_karty', gracz=gracz.nazwa, karta=str(karta))
        
        punkty_z_meldunku = 0
        
        # Sprawdź możliwość meldunku
        if not self.aktualna_lewa:
            if karta.ranga in [Ranga.KROL, Ranga.DAMA]:
                szukana_ranga = Ranga.DAMA if karta.ranga == Ranga.KROL else Ranga.KROL
                if any(k.ranga == szukana_ranga and k.kolor == karta.kolor for k in gracz.reka):
                    if (gracz, karta.kolor) not in self.zadeklarowane_meldunki:
                        punkty_z_meldunku = WARTOSCI_MELDUNKOW[karta.kolor]
                        self.punkty_w_rozdaniu[gracz.nazwa] += punkty_z_meldunku
                        self.zadeklarowane_meldunki.append((gracz, karta.kolor))
                        
                        # Ustaw/zmień atut
                        self.atut = karta.kolor
                        
                        self._dodaj_log('meldunek', gracz=gracz.nazwa, kolor=karta.kolor.name, punkty=punkty_z_meldunku, nowy_atut=self.atut.name)
        
        if karta in gracz.reka:
            gracz.reka.remove(karta)
        
        self.aktualna_lewa.append((gracz, karta))
        
        wynik = {'meldunek_pkt': punkty_z_meldunku}
        
        liczba_aktywnych = len(self.gracze)
        if self.tryb == '4p':
            liczba_aktywnych -= 1
        
        if len(self.aktualna_lewa) == liczba_aktywnych:
            self._zakoncz_lewe()
        else:
            self._nastepny_gracz()
        
        return wynik
    
    def _waliduj_ruch(self, gracz: Gracz, karta: Karta) -> bool:
        """
        Sprawdza, czy zagranie karty jest legalne.
        
        Zasady Tysiąca:
        1. Musisz dać kolor wiodący (jeśli masz)
        2. Musisz przebić (dać wyższą kartę w kolorze) jeśli możesz!
        3. Jeśli nie masz koloru wiodącego, musisz dać atut (jeśli masz)
        4. Jeśli są atuty na stole, musisz przebić atutem (jeśli masz wyższy)
        5. Jeśli nie masz koloru ani atutów - możesz dać cokolwiek
        """
        gracz_idx = self._get_player_index(gracz)
        
        if gracz_idx is None or gracz_idx != self.kolej_gracza_idx:
            return False
        
        if karta not in gracz.reka:
            return False
        
        # Pierwsza karta w lewie - zawsze można zagrać
        if not self.aktualna_lewa:
            return True
        
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        karty_do_koloru = [k for k in gracz.reka if k.kolor == kolor_wiodacy]
        
        # === GRACZ MA KARTY W KOLORZE WIODĄCYM ===
        if karty_do_koloru:
            # Musi zagrać w kolorze wiodącym
            if karta.kolor != kolor_wiodacy:
                return False
            
            # ZASADA PRZEBICIA: znajdź najwyższą kartę w kolorze wiodącym na stole
            karty_wiodace_na_stole = [k for _, k in self.aktualna_lewa if k.kolor == kolor_wiodacy]
            najwyzsza_na_stole = max(karty_wiodace_na_stole, key=lambda k: k.ranga.value)
            
            # Sprawdź czy gracz ma kartę wyższą
            wyzsze_karty = [k for k in karty_do_koloru if k.ranga.value > najwyzsza_na_stole.ranga.value]
            
            if wyzsze_karty:
                # Gracz MA wyższą kartę - MUSI ją zagrać
                return karta in wyzsze_karty
            else:
                # Gracz NIE MA wyższej karty - może zagrać dowolną w kolorze
                return True
        
        # === GRACZ NIE MA KOLORU WIODĄCEGO ===
        # Sprawdź czy ma atuty
        if self.atut:
            atuty_w_rece = [k for k in gracz.reka if k.kolor == self.atut]
            if atuty_w_rece:
                # Gracz ma atuty - musi zagrać atuta
                if karta.kolor != self.atut:
                    return False
                
                # Sprawdź czy musi przebić atuta na stole
                atuty_na_stole = [k for g, k in self.aktualna_lewa if k.kolor == self.atut]
                if atuty_na_stole:
                    najwyzszy_atut = max(atuty_na_stole, key=lambda k: k.ranga.value)
                    wyzsze_atuty = [k for k in atuty_w_rece if k.ranga.value > najwyzszy_atut.ranga.value]
                    if wyzsze_atuty:
                        # Gracz ma wyższe atuty - musi zagrać wyższy
                        return karta in wyzsze_atuty
                    # Gracz nie ma wyższego atuta - może zagrać dowolny atut
                
                return True
        
        # Gracz nie ma ani koloru wiodącego, ani atutów - może zagrać dowolną kartę
        return True
    
    def _zakoncz_lewe(self):
        """Ustala zwycięzcę lewy."""
        if not self.aktualna_lewa:
            return
        
        kolor_wiodacy = self.aktualna_lewa[0][1].kolor
        
        karty_atutowe = []
        if self.atut:
            karty_atutowe = [(g, k) for g, k in self.aktualna_lewa if k.kolor == self.atut]
        
        zwyciezca_pary = None
        if karty_atutowe:
            zwyciezca_pary = max(karty_atutowe, key=lambda p: p[1].ranga.value)
        else:
            karty_wiodace = [p for p in self.aktualna_lewa if p[1].kolor == kolor_wiodacy]
            if karty_wiodace:
                zwyciezca_pary = max(karty_wiodace, key=lambda p: p[1].ranga.value)
        
        if not zwyciezca_pary:
            zwyciezca_pary = self.aktualna_lewa[0]
        
        zwyciezca = zwyciezca_pary[0]
        
        self.lewa_do_zamkniecia = True
        self.zwyciezca_lewy_tymczasowy = zwyciezca
        self.kolej_gracza_idx = None
        
        # Sprawdź czy to ostatnia lewa - zapisz informację
        aktywni_gracze = [g for g in self.gracze if self.tryb != '4p' or self.gracze.index(g) != self.muzyk_idx]
        self.ostatnia_lewa = all(len(g.reka) == 0 for g in aktywni_gracze)
        
        # Zapisz karty z ostatniej lewy do wyświetlenia
        if self.ostatnia_lewa:
            self.karty_ostatniej_lewy = [(g.nazwa, str(k)) for g, k in self.aktualna_lewa]
        
        # NIE finalizuj automatycznie - pozwól frontendowi pokazać karty
    
    def finalizuj_lewe(self):
        """Finalizuje lewę - STRUKTURA JAK W GRZE 66."""
        if not self.zwyciezca_lewy_tymczasowy:
            return
        
        zwyciezca = self.zwyciezca_lewy_tymczasowy
        punkty_w_lewie = sum(k.wartosc for _, k in self.aktualna_lewa)
        
        self._dodaj_log('koniec_lewy', zwyciezca=zwyciezca.nazwa, punkty=punkty_w_lewie)
        
        self.punkty_w_rozdaniu[zwyciezca.nazwa] += punkty_w_lewie
        
        zwyciezca.wygrane_karty.extend([k for _, k in self.aktualna_lewa])
        
        # Sprawdź czy to ostatnia lewa
        kart_wygranych = sum(len(g.wygrane_karty) for g in self.gracze)
        
        # W trybie 2p: 20 kart u graczy (10+10), w trybie 3p/4p: 21 kart
        if self.tryb == '2p' and kart_wygranych == 20:
            # Ostatnia lewa w trybie 2p - dodaj punkty z musików
            self.zwyciezca_ostatniej_lewy = zwyciezca
            punkty_z_muzikow = sum(k.wartosc for k in self.musik_1_oryginalny) + sum(k.wartosc for k in self.musik_2_oryginalny)
            self.punkty_w_rozdaniu[zwyciezca.nazwa] += punkty_z_muzikow
            self._dodaj_log('bonus_musiki', gracz=zwyciezca.nazwa, punkty=punkty_z_muzikow)
            print(f"[MUSIK] Gracz {zwyciezca.nazwa} wygrywa ostatnią lewę i otrzymuje {punkty_z_muzikow} pkt z musików")
        elif self.tryb in ['3p', '4p'] and kart_wygranych == 21:
            # Ostatnia lewa w trybie 3p/4p
            self.zwyciezca_ostatniej_lewy = zwyciezca
        
        self.aktualna_lewa.clear()
        self.lewa_do_zamkniecia = False
        self.zwyciezca_lewy_tymczasowy = None
        
        if not any(g.reka for g in self.gracze):
            self._sprawdz_koniec_rozdania()
            return
        
        zwyciezca_idx = self._get_player_index(zwyciezca)
        self.kolej_gracza_idx = zwyciezca_idx
    
    def _nastepny_gracz(self):
        """Przekazuje turę następnemu graczowi."""
        if self.kolej_gracza_idx is None:
            return
        
        next_idx = (self.kolej_gracza_idx + 1) % len(self.gracze)
        
        if self.tryb == '4p' and next_idx == self.muzyk_idx:
            next_idx = (next_idx + 1) % len(self.gracze)
        
        self.kolej_gracza_idx = next_idx
    
    def _sprawdz_koniec_rozdania(self):
        """Sprawdza, czy rozdanie się skończyło."""
        if self.rozdanie_zakonczone:
            return
        
        if not any(g.reka for g in self.gracze):
            self.rozdanie_zakonczone = True
            self.faza = FazaGry.PODSUMOWANIE_ROZDANIA
            self.rozlicz_rozdanie()
    
    def rozlicz_rozdanie(self):
        """Rozlicza rozdanie i przyznaje punkty."""
        if self.podsumowanie:
            return
        
        punkty_grajacego = self.punkty_w_rozdaniu.get(self.grajacy.nazwa, 0)
        zrobil_kontrakt = punkty_grajacego >= self.kontrakt_wartosc
        
        if zrobil_kontrakt:
            self.grajacy.punkty_meczu += self.kontrakt_wartosc
            self._dodaj_log('zrobil_kontrakt', gracz=self.grajacy.nazwa, punkty=self.kontrakt_wartosc)
        else:
            self.grajacy.punkty_meczu -= self.kontrakt_wartosc
            self._dodaj_log('nie_zrobil_kontraktu', gracz=self.grajacy.nazwa, punkty=-self.kontrakt_wartosc)
        
        for gracz in self.gracze:
            if gracz == self.grajacy:
                continue
            
            if self.tryb == '4p' and gracz == self.gracze[self.muzyk_idx]:
                continue
            
            if gracz.zablokowany_na_800:
                self._dodaj_log('zablokowany_800', gracz=gracz.nazwa)
                continue
            
            punkty_gracza = self.punkty_w_rozdaniu.get(gracz.nazwa, 0)
            if punkty_gracza > 0:
                gracz.punkty_meczu += punkty_gracza
                self._dodaj_log('punkty_przeciwnika', gracz=gracz.nazwa, punkty=punkty_gracza)
                
                if gracz.punkty_meczu >= 800:
                    gracz.zablokowany_na_800 = True
                    self._dodaj_log('osiagnieto_800', gracz=gracz.nazwa)
        
        self.podsumowanie = {
            'grajacy': self.grajacy.nazwa,
            'kontrakt': self.kontrakt_wartosc,
            'zrobil_kontrakt': zrobil_kontrakt,
            'punkty_w_rozdaniu': self.punkty_w_rozdaniu.copy(),
            'punkty_meczu': {g.nazwa: g.punkty_meczu for g in self.gracze}
        }
        
        self._dodaj_log('koniec_rozdania', **self.podsumowanie)
    
    def get_current_player(self) -> Optional[str]:
        """Zwraca nazwę gracza, którego jest tura."""
        if self.kolej_gracza_idx is None:
            return None
        return self.gracze[self.kolej_gracza_idx].nazwa
    
    def is_terminal(self) -> bool:
        """Sprawdza, czy rozdanie się zakończyło."""
        return self.rozdanie_zakonczone
    
    def oblicz_aktualna_stawke(self) -> int:
        """Oblicza aktualną wartość kontraktu."""
        return self.kontrakt_wartosc