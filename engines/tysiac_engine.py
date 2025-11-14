# engines/tysiac_engine.py

import copy
from typing import Optional, Any, Dict, List
from .abstract_game_engine import AbstractGameEngine

# Import silnika Tysiąca
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from silnik_tysiac import (
    RozdanieTysiac, Gracz, Karta, Kolor, Ranga, FazaGry, WARTOSCI_MELDUNKOW
)

def _karta_do_stringa(karta: Karta) -> str:
    """Konwertuje obiekt Karta na string - ZGODNIE Z GRĄ 66"""
    return f"{karta.ranga.name.capitalize()} {karta.kolor.name.capitalize()}"

def _karta_ze_stringa(nazwa_karty: str) -> Karta:
    """Konwertuje string na obiekt Karta - ZGODNIE Z GRĄ 66"""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        ranga = Ranga[ranga_str.upper()]
        kolor = Kolor[kolor_str.upper()]
        return Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e

def _karta_z_dicta(karta_dict: dict) -> Karta:
    """Konwertuje słownik na obiekt Karta - ZGODNIE Z GRĄ 66"""
    try:
        ranga_str = karta_dict['ranga'].upper()
        kolor_str = karta_dict['kolor'].upper()
        ranga = Ranga[ranga_str]
        kolor = Kolor[kolor_str]
        return Karta(ranga=ranga, kolor=kolor)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Nieprawidłowy format słownika karty: {karta_dict}") from e

class TysiacEngine(AbstractGameEngine):
    """
    Adapter implementujący AbstractGameEngine dla gry w Tysiąca.
    """
    
    def __init__(self, player_ids: List[str], settings: Dict[str, Any]):
        """
        Inicjalizuje nową grę w Tysiąca.
        
        Args:
            player_ids: Lista ID graczy
            settings: Ustawienia gry, np. {'tryb': '3p', 'rozdajacy_idx': 0}
        """
        self.player_ids = player_ids
        self.settings = settings
        
        # Stwórz obiekty graczy
        gracze = [Gracz(nazwa=pid) for pid in player_ids]
        tryb = settings.get('tryb', '3p')
        rozdajacy_idx = settings.get('rozdajacy_idx', 0)
        
        # Stwórz instancję gry
        self.game_state = RozdanieTysiac(gracze, rozdajacy_idx, tryb)
        
        # Rozpocznij rozdanie
        self.game_state.rozpocznij_nowe_rozdanie()
    
    def _map_player_id_to_obj(self, player_id: str) -> Optional[Gracz]:
        """Znajduje obiekt Gracz na podstawie ID."""
        for gracz in self.game_state.gracze:
            if gracz.nazwa == player_id:
                return gracz
        return None
    
    def _map_idx_to_player_id(self, index: Optional[int]) -> Optional[str]:
        """Zwraca ID gracza na podstawie indeksu."""
        if index is None or not (0 <= index < len(self.game_state.gracze)):
            return None
        return self.game_state.gracze[index].nazwa
    
    def perform_action(self, player_id: str, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wykonuje akcję gracza."""
        gracz_obj = self._map_player_id_to_obj(player_id)
        if not gracz_obj:
            print(f"BŁĄD: Nie znaleziono gracza {player_id}")
            return None
        
        action_type = action.get('typ')
        
        # Akcja: Zagranie karty
        if action_type == 'zagraj_karte':
            try:
                karta_data = action['karta']
                karta_obj = None
                
                if isinstance(karta_data, str):
                    karta_obj = _karta_ze_stringa(karta_data)
                elif isinstance(karta_data, dict):
                    karta_obj = _karta_z_dicta(karta_data)
                else:
                    raise ValueError(f"Nieznany format danych karty: {karta_data}")
                
                result = self.game_state.zagraj_karte(gracz_obj, karta_obj)
                return result
            except Exception as e:
                print(f"BŁĄD: Błąd podczas zagrywania karty: {e}")
                return None
        
        # Akcja: Finalizacja lewy
        elif action_type == 'finalizuj_lewe':
            if self.game_state.lewa_do_zamkniecia:
                self.game_state.finalizuj_lewe()
            return None
        
        # Inne akcje (licytacja, wybór musiku, itp.)
        else:
            try:
                # Parsuj karty w akcji (jeśli są stringami)
                if action_type == 'oddaj_karty' and 'karty' in action:
                    karty_parsed = []
                    for karta_data in action['karty']:
                        if isinstance(karta_data, str):
                            karty_parsed.append(_karta_ze_stringa(karta_data))
                        elif isinstance(karta_data, dict):
                            karty_parsed.append(_karta_z_dicta(karta_data))
                        elif isinstance(karta_data, Karta):
                            # Już jest obiektem Karta
                            karty_parsed.append(karta_data)
                        else:
                            print(f"Nieznany typ karty: {type(karta_data)}, wartość: {karta_data}")
                    action['karty'] = karty_parsed
                
                # Podobnie dla rozdaj_karty (tryb 3p/4p)
                if action_type == 'rozdaj_karty' and 'rozdanie' in action:
                    rozdanie_parsed = {}
                    for nazwa_gracza, karta_data in action['rozdanie'].items():
                        if isinstance(karta_data, str):
                            rozdanie_parsed[nazwa_gracza] = _karta_ze_stringa(karta_data)
                        elif isinstance(karta_data, dict):
                            rozdanie_parsed[nazwa_gracza] = _karta_z_dicta(karta_data)
                        elif isinstance(karta_data, Karta):
                            rozdanie_parsed[nazwa_gracza] = karta_data
                        else:
                            print(f"Nieznany typ karty dla gracza {nazwa_gracza}: {type(karta_data)}")
                    action['rozdanie'] = rozdanie_parsed
                
                self.game_state.wykonaj_akcje(gracz_obj, action)
            except Exception as e:
                print(f"BŁĄD: Błąd podczas wykonywania akcji: {e}")
                import traceback
                traceback.print_exc()
            return None
    
    def get_legal_actions(self, player_id: str) -> List[Dict[str, Any]]:
        """Zwraca listę legalnych akcji dla gracza."""
        gracz_obj = self._map_player_id_to_obj(player_id)
        if not gracz_obj:
            return []
        
        # W fazie rozgrywki, zwróć grywalne karty
        if self.game_state.faza == FazaGry.ROZGRYWKA:
            current_player_id = self.get_current_player()
            if current_player_id != player_id:
                return []
            
            legal_cards = []
            for karta in gracz_obj.reka:
                if self.game_state._waliduj_ruch(gracz_obj, karta):
                    legal_cards.append(karta)
            
            return [
                {'typ': 'zagraj_karte', 'karta': _karta_do_stringa(karta)}
                for karta in legal_cards
            ]
        
        # Akcja finalizacji lewy
        if self.game_state.lewa_do_zamkniecia:
            return [{'typ': 'finalizuj_lewe'}]
        
        # Inne fazy - użyj metody z silnika
        return self.game_state.get_mozliwe_akcje(gracz_obj)
    
    def get_state_for_player(self, player_id: str) -> Dict[str, Any]:
        """Zwraca stan gry z perspektywy gracza."""
        gracz_obj = self._map_player_id_to_obj(player_id)
        gs = self.game_state
        
        # Ręce graczy
        rece_graczy_data = {}
        for p in gs.gracze:
            if not p:
                continue
            if p.nazwa == player_id:
                rece_graczy_data[p.nazwa] = [_karta_do_stringa(k) for k in p.reka]
            else:
                rece_graczy_data[p.nazwa] = len(p.reka)
        
        # Grywalne karty
        grywalne_karty_data = []
        if gs.faza == FazaGry.ROZGRYWKA and self.get_current_player() == player_id and gracz_obj:
            for karta in gracz_obj.reka:
                if gs._waliduj_ruch(gracz_obj, karta):
                    grywalne_karty_data.append(_karta_do_stringa(karta))
        
        # Karty na stole
        karty_na_stole_data = [
            {'gracz': p.nazwa, 'karta': _karta_do_stringa(k)}
            for p, k in gs.aktualna_lewa
        ]
        
        # Możliwe akcje
        mozliwe_akcje_data = []
        if gs.faza != FazaGry.ROZGRYWKA and self.get_current_player() == player_id and gracz_obj:
            actions = gs.get_mozliwe_akcje(gracz_obj)
            mozliwe_akcje_data = actions
        
        # Historia
        historia_rozdania_data = gs.szczegolowa_historia.copy()
        
        # Musik (widoczność zależy od fazy i gracza)
        musik_data = None
        musik_1_data = None
        musik_2_data = None
        musik_wybrany_data = None  # Informacja który musik został wybrany
        karty_z_musiku_data = []  # Lista kart z musiku (dla wyróżnienia)
        
        # Dla trybu 2p - pokaż musiki
        if gs.tryb == '2p':
            # Sprawdź czy to ostatnia lewa (20 kart wygranych)
            kart_wygranych = sum(len(g.wygrane_karty) for g in gs.gracze)
            czy_ostatnia_lewa = kart_wygranych == 20
            
            # Zawsze przekazuj karty jako stringi (dla PODSUMOWANIA)
            if czy_ostatnia_lewa or gs.faza == FazaGry.PODSUMOWANIE_ROZDANIA:
                # Po ostatniej lewie pokaż karty w musikach
                musik_1_data = [_karta_do_stringa(k) for k in gs.musik_1_oryginalny]
                musik_2_data = [_karta_do_stringa(k) for k in gs.musik_2_oryginalny]
            else:
                # Podczas gry zawsze przekazuj jako stringi dla spójności
                musik_1_data = [_karta_do_stringa(k) for k in (gs.musik_1 if hasattr(gs, 'musik_1') else [])]
                musik_2_data = [_karta_do_stringa(k) for k in (gs.musik_2 if hasattr(gs, 'musik_2') else [])]
            
            # Informacja który musik został wybrany
            if gs.musik_wybrany:
                musik_wybrany_data = gs.musik_wybrany
                
                # Dodaj karty z wybranego musiku do listy (dla wyróżnienia w UI)
                if player_id == gs.grajacy.nazwa and gs.musik_odkryty:
                    # Grający widzi które karty pochodzą z musiku
                    if musik_wybrany_data == 1:
                        # Z musik_1_oryginalny (to są oryginalne karty przed oddaniem)
                        for karta in gs.musik_1_oryginalny:
                            karta_str = _karta_do_stringa(karta)
                            # Sprawdź czy ta karta jest jeszcze w ręce gracza
                            if karta_str in rece_graczy_data.get(player_id, []):
                                karty_z_musiku_data.append(karta_str)
                    else:
                        # Z musik_2_oryginalny
                        for karta in gs.musik_2_oryginalny:
                            karta_str = _karta_do_stringa(karta)
                            if karta_str in rece_graczy_data.get(player_id, []):
                                karty_z_musiku_data.append(karta_str)
                
            # Dla kompatybilności z frontendem - pusta lista jeśli nie ma kart do pokazania
            musik_data = []
        elif gs.musik_odkryty:
            # Dla trybu 3p/4p - pokaż karty w musiku jeśli odkryty
            if gs.kontrakt_wartosc > 100 or (gs.kontrakt_wartosc == 100 and player_id == gs.grajacy.nazwa):
                musik_data = [_karta_do_stringa(k) for k in gs.musik_karty]
            else:
                musik_data = []
        else:
            # Domyślnie pusta lista
            musik_data = []
        
        # Zbuduj stan
        state = {
            'faza': gs.faza.name,
            'tryb': gs.tryb,  # DODANE: Tryb gry (2p/3p/4p)
            'kolej_gracza': self._map_idx_to_player_id(gs.kolej_gracza_idx),
            'grajacy': gs.grajacy.nazwa if gs.grajacy else None,
            'gracz_grajacy': gs.grajacy.nazwa if gs.grajacy else None,  # Alias dla frontendu
            'kontrakt_wartosc': gs.kontrakt_wartosc,
            'atut': gs.atut.name if gs.atut else None,
            'lewa_do_zamkniecia': gs.lewa_do_zamkniecia,
            'podsumowanie': gs.podsumowanie if gs.podsumowanie else None,
            'musik_odkryty': gs.musik_odkryty,  # DODANE: Czy musik odkryty
            
            'rece_graczy': rece_graczy_data,
            'grywalne_karty': grywalne_karty_data,
            'karty_na_stole': karty_na_stole_data,
            'mozliwe_akcje': mozliwe_akcje_data,
            'historia_rozdania': historia_rozdania_data,
            'punkty_w_rozdaniu': gs.punkty_w_rozdaniu,
            'punkty_meczowe': {g.nazwa: g.punkty_meczu for g in gs.gracze},
            'aktualna_stawka': gs.oblicz_aktualna_stawke(),
            'musik': musik_data,  # Zawsze lista (może być pusta)
            'musik_1': musik_1_data,  # DODANE: Musik 1 dla trybu 2p
            'musik_2': musik_2_data,  # DODANE: Musik 2 dla trybu 2p
            'musik_wybrany': musik_wybrany_data,  # DODANE: Który musik wybrany
            'karty_z_musiku': karty_z_musiku_data,  # DODANE: Lista kart z musiku (dla wyróżnienia)
            'muzyk_idx': gs.muzyk_idx if gs.tryb == '4p' else None,
            'zadeklarowane_meldunki': [
                {'gracz': p.nazwa, 'kolor': k.name}
                for p, k in gs.zadeklarowane_meldunki
            ],
            'aktualna_licytacja': gs.aktualna_licytacja,
            'pasujacy_gracze': [p.nazwa for p in gs.pasujacy_gracze],
        }
        
        return state
    
    def get_current_player(self) -> Optional[str]:
        """Zwraca ID gracza, którego jest tura."""
        return self._map_idx_to_player_id(self.game_state.kolej_gracza_idx)
    
    def is_terminal(self) -> bool:
        """Sprawdza, czy rozdanie się zakończyło."""
        return self.game_state.rozdanie_zakonczone
    
    def get_outcome(self) -> Dict[str, float]:
        """Zwraca wyniki rozdania."""
        if not self.is_terminal():
            return {}
        
        outcome = {pid: 0.0 for pid in self.player_ids}
        
        if self.game_state.podsumowanie:
            grajacy_nazwa = self.game_state.grajacy.nazwa
            zrobil_kontrakt = self.game_state.podsumowanie.get('zrobil_kontrakt', False)
            
            if zrobil_kontrakt:
                outcome[grajacy_nazwa] = float(self.game_state.kontrakt_wartosc)
            else:
                outcome[grajacy_nazwa] = -float(self.game_state.kontrakt_wartosc)
            
            for gracz in self.game_state.gracze:
                if gracz.nazwa != grajacy_nazwa:
                    punkty = self.game_state.punkty_w_rozdaniu.get(gracz.nazwa, 0)
                    outcome[gracz.nazwa] = float(punkty)
        
        return outcome
    
    def clone(self) -> 'AbstractGameEngine':
        """Tworzy głęboką kopię silnika."""
        new_engine = TysiacEngine.__new__(TysiacEngine)
        new_engine.player_ids = self.player_ids.copy()
        new_engine.settings = self.settings.copy()
        new_engine.game_state = copy.deepcopy(self.game_state)
        return new_engine