# boty_tysiac.py
"""
Prosty bot dla gry w Tysiąca
"""
import random
from typing import Tuple, Any
from silnik_tysiac import Gracz, Karta, RozdanieTysiac, FazaGry

def wybierz_akcje_dla_bota_testowego_tysiac(bot: Gracz, rozdanie: RozdanieTysiac) -> Tuple[str, Any]:
    """
    Wybiera akcję dla prostego bota w grze w Tysiąca.
    
    Args:
        bot: Obiekt gracza-bota
        rozdanie: Obiekt rozdania w Tysiącu
    
    Returns:
        tuple: (typ_akcji, parametry_akcji)
            - typ_akcji: 'karta', 'licytacja', lub 'brak'
            - parametry_akcji: Karta, dict, lub None
    """
    
    # === FAZA ROZGRYWKI ===
    if rozdanie.faza == FazaGry.ROZGRYWKA:
        # Znajdź grywalne karty
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        
        if grywalne_karty:
            # Wybierz losową kartę
            return 'karta', random.choice(grywalne_karty)
        else:
            return 'brak', None
    
    # === FAZA LICYTACJI ===
    elif rozdanie.faza == FazaGry.LICYTACJA:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        # Prosta strategia: pasuj jeśli możesz
        akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
        if akcja_pas:
            return 'licytacja', akcja_pas
        
        # Jeśli nie możesz spasować, licytuj minimalnie
        akcja_licytuj = next((a for a in mozliwe_akcje if a['typ'] == 'licytuj'), None)
        if akcja_licytuj:
            return 'licytacja', akcja_licytuj
        
        # Fallback: losowa akcja
        return 'licytacja', random.choice(mozliwe_akcje)
    
    # === FAZA WYMIANY MUSZKU ===
    elif rozdanie.faza == FazaGry.WYMIANA_MUSZKU:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        # Obsłuż wybór musiku (tryb 2p)
        if rozdanie.tryb == '2p' and not rozdanie.musik_odkryty:
            # Wybierz losowy musik
            akcja_musik = next((a for a in mozliwe_akcje if a['typ'] == 'wybierz_musik'), None)
            if akcja_musik:
                # Domyślnie wybierz musik 1
                akcja_musik['musik'] = 1
                return 'licytacja', akcja_musik
        
        # Obsłuż oddawanie kart (tryb 2p) lub rozdawanie (tryb 3p/4p)
        if rozdanie.musik_odkryty:
            if rozdanie.tryb == '2p':
                # Oddaj 2 najsłabsze karty
                if len(bot.reka) >= 2:
                    # Sortuj karty wg wartości (rosnąco)
                    karty_posortowane = sorted(bot.reka, key=lambda k: k.wartosc)
                    karty_do_oddania = karty_posortowane[:2]
                    # Przekazuj obiekty Karta bezpośrednio, nie stringi!
                    return 'licytacja', {'typ': 'oddaj_karty', 'karty': karty_do_oddania}
            else:  # 3p lub 4p
                # Rozdaj karty przeciwnikom
                # Oblicz liczbę aktywnych graczy
                liczba_aktywnych = len(rozdanie.gracze)
                if rozdanie.tryb == '4p':
                    liczba_aktywnych -= 1  # Muzyk nie gra
                
                # Prosta strategia: daj każdemu po jednej karcie
                liczba_do_rozdania = liczba_aktywnych - 1  # -1 bo bot sam sobie nie rozdaje
                if len(bot.reka) >= liczba_do_rozdania:
                    karty_posortowane = sorted(bot.reka, key=lambda k: k.wartosc)
                    rozdanie_dict = {}
                    idx = 0
                    for gracz in rozdanie.gracze:
                        if gracz != bot and (rozdanie.tryb != '4p' or rozdanie.muzyk_idx is None or gracz != rozdanie.gracze[rozdanie.muzyk_idx]):
                            if idx < len(karty_posortowane) and idx < liczba_do_rozdania:
                                # Przekazuj obiekt Karta bezpośrednio
                                rozdanie_dict[gracz.nazwa] = karty_posortowane[idx]
                                idx += 1
                    if len(rozdanie_dict) > 0:
                        return 'licytacja', {'typ': 'rozdaj_karty', 'rozdanie': rozdanie_dict}
        
        # Fallback: losowa akcja
        return 'licytacja', random.choice(mozliwe_akcje)
    
    # === INNE FAZY ===
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        # Losowa akcja
        return 'licytacja', random.choice(mozliwe_akcje)
