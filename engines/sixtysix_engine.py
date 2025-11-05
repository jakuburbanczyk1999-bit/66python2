# engines/sixtysix_engine.py

import copy
from typing import Optional, Any, Dict, List, Union
from enum import Enum
import traceback

# Import interfejsu
from .abstract_game_engine import AbstractGameEngine

# Import logiki gry z głównego katalogu
# Używamy ".." aby cofnąć się o jeden katalog w górę
from silnik_gry import (
    Rozdanie, RozdanieTrzyOsoby, Gracz, Druzyna, Karta, 
    Kolor, Ranga, Kontrakt, FazaGry
)

def _karta_do_stringa(karta: Karta) -> str:
    """Konwertuje obiekt Karta na string (np. "As Czerwien")."""
    return f"{karta.ranga.name.capitalize()} {karta.kolor.name.capitalize()}"

def _karta_ze_stringa(nazwa_karty: str) -> Karta:
    """Konwertuje string (np. "As Czerwien") na obiekt Karta."""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        # Mapowanie nazw stringowych na obiekty Enum
        mapowanie_rang = {r.name.capitalize(): r for r in Ranga}
        mapowanie_kolorow = {k.name.capitalize(): k for k in Kolor}
        ranga = mapowanie_rang[ranga_str]
        kolor = mapowanie_kolorow[kolor_str]
        return Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e
    
def _karta_z_dicta(karta_dict: dict) -> Karta:
    """Konwertuje słownik (np. {'ranga': 'AS', ...}) na obiekt Karta."""
    try:
        ranga_str = karta_dict['ranga'].upper() # Upewnij się, że klucze są wielkie
        kolor_str = karta_dict['kolor'].upper()
        
        ranga = Ranga[ranga_str]
        kolor = Kolor[kolor_str]
        return Karta(ranga=ranga, kolor=kolor)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Nieprawidłowy format słownika karty: {karta_dict}") from e

# Typowanie dla ułatwienia
GameInstance = Union[Rozdanie, RozdanieTrzyOsoby]

class SixtySixEngine(AbstractGameEngine):
    """
    Adapter implementujący AbstractGameEngine dla gry w "66".
    Tłumaczy wywołania abstrakcyjne na konkretne metody klas
    Rozdanie i RozdanieTrzyOsoby z pliku silnik_gry.py.
    """
    
    def __init__(self, player_ids: list[str], settings: dict[str, Any]):
        """
        Inicjalizuje nową grę w "66".
        
        :param player_ids: Lista identyfikatorów graczy (stringów, np. nazw użytkowników).
        :param settings: Słownik ustawień gry, np. {'tryb': '4p', 'rozdajacy_idx': 0}
        """
        self.player_ids = player_ids
        self.settings = settings
        self.game_state: GameInstance = self._create_game_instance()
        
        # Rozpocznij pierwsze rozdanie
        self.game_state.rozpocznij_nowe_rozdanie()

    def _create_game_instance(self) -> GameInstance:
        """Tworzy instancję gry (3p lub 4p) na podstawie ustawień."""
        tryb = self.settings.get('tryb', '4p')
        rozdajacy_idx = self.settings.get('rozdajacy_idx', 0)

        if tryb == '4p':
            if len(self.player_ids) != 4:
                raise ValueError("Tryb 4p wymaga dokładnie 4 graczy.")
            
            # === POCZĄTEK POPRAWKI (Wersja 6) ===
            # Pobierz nazwy drużyn z ustawień lub użyj domyślnych
            nazwy_druzyn_mapa = self.settings.get('nazwy_druzyn')
            if nazwy_druzyn_mapa and 'My' in nazwy_druzyn_mapa and 'Oni' in nazwy_druzyn_mapa:
                nazwa_druzyny_1 = nazwy_druzyn_mapa['My']
                nazwa_druzyny_2 = nazwy_druzyn_mapa['Oni']
            else:
                # Fallback, jeśli nazwy nie zostały przekazane
                print("OSTRZEŻENIE (Silnik): Nie przekazano nazw drużyn, używam domyślnych 'Drużyna 1/2'.")
                nazwa_druzyny_1 = "Drużyna 1"
                nazwa_druzyny_2 = "Drużyna 2"
            
            # Stwórz graczy i drużyny
            gracze = [Gracz(nazwa=pid) for pid in self.player_ids]
            # Użyj poprawnych nazw
            druzyna1 = Druzyna(nazwa=nazwa_druzyny_1)
            druzyna2 = Druzyna(nazwa=nazwa_druzyny_2)
            # === KONIEC POPRAWKI ===
            
            druzyna1.dodaj_gracza(gracze[0]) # Gracz 0
            druzyna1.dodaj_gracza(gracze[2]) # Gracz 2
            druzyna2.dodaj_gracza(gracze[1]) # Gracz 1
            druzyna2.dodaj_gracza(gracze[3]) # Gracz 3
            
            druzyna1.przeciwnicy = druzyna2
            druzyna2.przeciwnicy = druzyna1
            
            return Rozdanie(gracze, [druzyna1, druzyna2], rozdajacy_idx)
            
        elif tryb == '3p':
            if len(self.player_ids) != 3:
                raise ValueError("Tryb 3p wymaga dokładnie 3 graczy.")
            
            gracze = [Gracz(nazwa=pid, punkty_meczu=0) for pid in self.player_ids]
            return RozdanieTrzyOsoby(gracze, rozdajacy_idx)
            
        else:
            raise ValueError(f"Nieznany tryb gry: {tryb}")

    # --- Prywatne metody pomocnicze (Mappery i Serializery) ---

    def _map_player_id_to_obj(self, player_id: str) -> Optional[Gracz]:
        """Znajduje obiekt Gracz na podstawie jego ID (nazwy)."""
        for gracz in self.game_state.gracze:
            if gracz.nazwa == player_id:
                return gracz
        return None

    def _map_idx_to_player_id(self, index: Optional[int]) -> Optional[str]:
        """Zwraca ID gracza (nazwę) na podstawie jego indeksu w liście."""
        if index is None or not (0 <= index < len(self.game_state.gracze)):
            return None
        return self.game_state.gracze[index].nazwa

    def _serialize_enum(self, value: Optional[Any]) -> Optional[str]:
        """Konwertuje Enum na jego nazwę (string)."""
        return value.name if isinstance(value, (Kolor, Kontrakt, FazaGry)) else None
    
    def _serialize_action_dict(self, action: dict[str, Any]) -> dict[str, Any]:
        """Konwertuje Enumy w słowniku akcji na stringi (gotowe do JSON)."""
        serialized_action = action.copy()
        if 'kontrakt' in action and isinstance(action['kontrakt'], Enum):
            serialized_action['kontrakt'] = action['kontrakt'].name
        if 'atut' in action and isinstance(action['atut'], Enum):
            serialized_action['atut'] = action['atut'].name
        return serialized_action

    def _deserialize_action_enums(self, action: dict[str, Any]) -> dict[str, Any]:
        """Deserializuje stringi w słowniku akcji na obiekty Enum."""
        deserialized_action = action.copy()
        if 'kontrakt' in action and isinstance(action['kontrakt'], str):
            try:
                deserialized_action['kontrakt'] = Kontrakt[action['kontrakt']]
            except KeyError: # Ignoruj, jeśli to nie jest poprawny Enum
                pass 
        if 'atut' in action and isinstance(action['atut'], str):
            try:
                deserialized_action['atut'] = Kolor[action['atut']]
            except KeyError:
                pass
        return deserialized_action

    # --- Implementacja metod interfejsu AbstractGameEngine ---

    def perform_action(self, player_id: str, action: dict[str, Any]) -> None:
        """
        Wykonuje akcję gracza, mapując ją na odpowiednią metodę silnika.
        Obsługuje dane karty jako string (od człowieka) lub dict (od bota).
        """
        gracz_obj = self._map_player_id_to_obj(player_id)
        if not gracz_obj:
            print(f"BŁĄD (Adapter): Nie znaleziono gracza {player_id}")
            return

        action_type = action.get('typ')
        
        # Akcja: Zagranie karty
        if action_type == 'zagraj_karte':
            try:
                karta_data = action['karta']
                karta_obj = None
                
                if isinstance(karta_data, str):
                    # Akcja od człowieka (np. "As Czerwien")
                    karta_obj = _karta_ze_stringa(karta_data)
                elif isinstance(karta_data, dict):
                    # Akcja od bota (np. {'ranga': 'AS', 'kolor': 'CZERWIEN'})
                    karta_obj = _karta_z_dicta(karta_data)
                else:
                    raise ValueError(f"Nieznany format danych karty: {karta_data}")
                    
                self.game_state.zagraj_karte(gracz_obj, karta_obj)
                
            except Exception as e:
                print(f"BŁĄD (Adapter): Błąd podczas zagrywania karty: {e}")
                traceback.print_exc() # Dodaj pełny traceback, aby zobaczyć błąd
        
        # Akcja: Finalizacja lewy (potrzebna dla klienta)
        elif action_type == 'finalizuj_lewe':
            if self.game_state.lewa_do_zamkniecia:
                self.game_state.finalizuj_lewe()
        
        # Inne akcje (licytacja, pas, lufa itp.)
        else:
            try:
                # Konwertuj stringi (np. 'NORMALNA') na Enumy
                action_with_enums = self._deserialize_action_enums(action)
                self.game_state.wykonaj_akcje(gracz_obj, action_with_enums)
            except Exception as e:
                print(f"BŁĄD (Adapter): Błąd podczas wykonywania akcji licytacji: {e}")

    def get_legal_actions(self, player_id: str) -> list[dict[str, Any]]:
        """
        Zwraca listę legalnych akcji dla gracza.
        """
        gracz_obj = self._map_player_id_to_obj(player_id)
        if not gracz_obj:
            return []

        # 1. Akcje z faz licytacji (zwracane przez silnik)
        if self.game_state.faza not in [FazaGry.ROZGRYWKA, FazaGry.PODSUMOWANIE_ROZDANIA]:
            actions = self.game_state.get_mozliwe_akcje(gracz_obj)
            # Serializuj Enumy do stringów dla JSONa
            serialized_actions = []
            for akcja in actions:
                serialized_akcja = akcja.copy()
                if 'kontrakt' in akcja and isinstance(akcja['kontrakt'], Enum):
                    serialized_akcja['kontrakt'] = akcja['kontrakt'].name
                if 'atut' in akcja and isinstance(akcja['atut'], Enum):
                    serialized_akcja['atut'] = akcja['atut'].name
                serialized_actions.append(serialized_akcja)
            return serialized_actions

        # 2. Akcje z fazy rozgrywki (zagranie karty)
        if self.game_state.faza == FazaGry.ROZGRYWKA:
            current_player_id = self.get_current_player()
            if current_player_id != player_id:
                return []
                
            legal_cards = []
            for karta in gracz_obj.reka:
                if self.game_state._waliduj_ruch(gracz_obj, karta):
                    legal_cards.append(karta)
            
            # Zwróć listę stringów kart (zgodnie z oczekiwaniami script.js)
            # Zamiast listy akcji, script.js oczekuje klucza 'grywalne_karty' w stanie
            # Ta funkcja jest używana przez BOTA, ale także przez get_state_for_player
            # Dla BOTA, zwrócimy stary format (ze stringiem)
            return [
                {'typ': 'zagraj_karte', 'karta': _karta_do_stringa(karta)} 
                for karta in legal_cards
            ]
            
        # 3. Akcja finalizacji lewy (specjalny przypadek)
        if self.game_state.lewa_do_zamkniecia:
             return [{'typ': 'finalizuj_lewe'}]

        return []

    def get_state_for_player(self, player_id: str) -> dict[str, Any]:
        """
        Zbiera i serializuje pełny stan gry dla danego gracza.
        Struktura JSON jest dopasowana do oczekiwań script.js.
        """
        gracz_obj = self._map_player_id_to_obj(player_id)
        gs = self.game_state # Skrót do stanu gry
        
        # --- 1. rece_graczy (Map<string, string[] | number>) ---
        rece_graczy_data = {}
        for p in gs.gracze:
            if not p: continue
            if p.nazwa == player_id:
                # Wyślij listę stringów kart dla gracza
                rece_graczy_data[p.nazwa] = [_karta_do_stringa(k) for k in p.reka]
            else:
                # Wyślij tylko liczbę kart dla innych
                rece_graczy_data[p.nazwa] = len(p.reka)

        # --- 2. grywalne_karty (string[]) ---
        grywalne_karty_data = []
        if gs.faza == FazaGry.ROZGRYWKA and self.get_current_player() == player_id and gracz_obj:
            for karta in gracz_obj.reka:
                if gs._waliduj_ruch(gracz_obj, karta):
                    grywalne_karty_data.append(_karta_do_stringa(karta))

        # --- 3. karty_na_stole (List<object>) ---
        karty_na_stole_data = [
            {'gracz': p.nazwa, 'karta': _karta_do_stringa(k)} 
            for p, k in gs.aktualna_lewa
        ]

        # --- 4. mozliwe_akcje (List<object>) ---
        # (Używamy tej samej logiki co get_legal_actions, ale bez kart)
        mozliwe_akcje_data = []
        if gs.faza != FazaGry.ROZGRYWKA and self.get_current_player() == player_id and gracz_obj:
             actions = gs.get_mozliwe_akcje(gracz_obj)
             for akcja in actions:
                serialized_akcja = akcja.copy()
                if 'kontrakt' in akcja and isinstance(akcja['kontrakt'], Enum):
                    serialized_akcja['kontrakt'] = akcja['kontrakt'].name
                if 'atut' in akcja and isinstance(akcja['atut'], Enum):
                    serialized_akcja['atut'] = akcja['atut'].name
                mozliwe_akcje_data.append(serialized_akcja)
        
        # --- 5. historia_rozdania (List<object>) ---
        # (Musimy przekonwertować Enumy w logach na stringi)
        historia_rozdania_data = []
        for log in gs.szczegolowa_historia:
            log_copy = log.copy()
            if 'gracz' in log_copy and isinstance(log_copy['gracz'], Gracz):
                log_copy['gracz'] = log_copy['gracz'].nazwa
            if 'karta' in log_copy and isinstance(log_copy['karta'], Karta):
                log_copy['karta'] = _karta_do_stringa(log_copy['karta'])
            if 'kolor' in log_copy and isinstance(log_copy['kolor'], Enum):
                log_copy['kolor'] = log_copy['kolor'].name
            
            # Serializacja akcji w logach
            if 'akcja' in log_copy and isinstance(log_copy['akcja'], dict):
                log_copy['akcja'] = self._serialize_action_dict(log_copy['akcja']) 
                
            historia_rozdania_data.append(log_copy)
            
        # --- 6. kontrakt (obiekt) ---
        kontrakt_data = None
        if gs.kontrakt:
            kontrakt_data = {
                'typ': self._serialize_enum(gs.kontrakt),
                'atut': self._serialize_enum(gs.atut)
            }
            
        # --- 7. punkty_w_rozdaniu (Map<string, number>) ---
        punkty_w_rozdaniu_data = gs.punkty_w_rozdaniu

        # === POCZĄTEK POPRAWKI (Wersja 7) ===
        # --- 8. aktualna_stawka (oczekiwana przez script.js) ---
        aktualna_stawka_data = 0
        if gs.faza not in [FazaGry.PRZED_ROZDANIEM, FazaGry.PODSUMOWANIE_ROZDANIA, FazaGry.ZAKONCZONE]:
            # Wywołaj metodę obliczającą stawkę z silnika gry
            try:
                aktualna_stawka_data = gs.oblicz_aktualna_stawke()
            except Exception as e:
                print(f"BŁĄD (Adapter): Nie można obliczyć aktualnej stawki: {e}")
                aktualna_stawka_data = 0 # Fallback
        # === KONIEC POPRAWKI ===

        # --- Zbuduj finalny obiekt stanu (zgodny z script.js) ---
        state = {
            'faza': self._serialize_enum(gs.faza),
            'kolej_gracza': self._map_idx_to_player_id(gs.kolej_gracza_idx),
            'gracz_grajacy': gs.grajacy.nazwa if gs.grajacy else None,
            'kontrakt': kontrakt_data,
            'lewa_do_zamkniecia': gs.lewa_do_zamkniecia,
            'podsumowanie': gs.podsumowanie if gs.podsumowanie else None,
            
            # Klucze oczekiwane przez script.js:
            'rece_graczy': rece_graczy_data,
            'grywalne_karty': grywalne_karty_data,
            'karty_na_stole': karty_na_stole_data,
            'mozliwe_akcje': mozliwe_akcje_data,
            'historia_rozdania': historia_rozdania_data,
            'punkty_w_rozdaniu': punkty_w_rozdaniu_data,
            'aktualna_stawka': aktualna_stawka_data, # <-- DODANO KLUCZ
            
            # Dodatkowe dane (mogą być przydatne, choć script.js ich nie używa)
            'mnoznik_lufy': gs.mnoznik_lufy,
            'zadeklarowane_meldunki': [
                {'gracz': p.nazwa, 'kolor': self._serialize_enum(k)}
                for p, k in gs.zadeklarowane_meldunki
            ]
        }
        
        return state

    def get_current_player(self) -> Optional[str]:
        """Zwraca ID gracza, którego jest tura."""
        return self._map_idx_to_player_id(self.game_state.kolej_gracza_idx)

    def is_terminal(self) -> bool:
        """Sprawdza, czy rozdanie się zakończyło."""
        # Uznajemy, że jest zakończone, gdy pojawi się podsumowanie
        return bool(self.game_state.podsumowanie)

    def get_outcome(self) -> dict[str, float]:
        """
        Zwraca wyniki rozdania. W "66" jest to bardziej złożone niż 1.0 / -1.0.
        Na razie zwrócimy punkty meczowe przyznane w tym rozdaniu.
        """
        if not self.is_terminal():
            return {}

        podsumowanie = self.game_state.podsumowanie
        punkty = podsumowanie.get('przyznane_punkty', 0)
        
        # Inicjalizuj wyniki na 0 dla wszystkich
        outcome = {pid: 0.0 for pid in self.player_ids}

        if isinstance(self.game_state, Rozdanie): # 4p
            wygrana_druzyna_nazwa = podsumowanie.get('wygrana_druzyna')
            for d in self.game_state.druzyny:
                if d.nazwa == wygrana_druzyna_nazwa:
                    for p in d.gracze:
                        outcome[p.nazwa] = float(punkty) # Wszyscy w drużynie dostają "wygraną"
        
        elif isinstance(self.game_state, RozdanieTrzyOsoby): # 3p
            wygrani_gracze_nazwy = podsumowanie.get('wygrani_gracze', [])
            punkty_na_gracza = float(punkty) / len(wygrani_gracze_nazwy) if wygrani_gracze_nazwy else 0.0
            for nazwa in wygrani_gracze_nazwy:
                if nazwa in outcome:
                    outcome[nazwa] = punkty_na_gracza

        return outcome

    def clone(self) -> 'AbstractGameEngine':
        """
        Tworzy głęboką kopię silnika na potrzeby symulacji (MCTS).
        """
        # Stwórz nową, pustą instancję
        new_engine = SixtySixEngine.__new__(SixtySixEngine)
        
        # Skopiuj atrybuty
        new_engine.player_ids = self.player_ids.copy()
        new_engine.settings = self.settings.copy()
        
        # Najważniejsze: stwórz głęboką kopię stanu gry (Rozdanie / RozdanieTrzyOsoby)
        new_engine.game_state = copy.deepcopy(self.game_state)
        
        return new_engine