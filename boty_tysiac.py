# boty_tysiac.py
"""
Bot dla gry w Tysiąca - tryb 2-osobowy
Strategia oparta na ocenie siły ręki, meldunków i rozgrywce taktycznej.
"""
import random
from typing import Tuple, Any, List, Optional, Dict
from silnik_tysiac import Gracz, Karta, RozdanieTysiac, FazaGry, Kolor, Ranga, WARTOSCI_MELDUNKOW, WARTOSCI_KART

# =============================================================================
# POMOCNICZE FUNKCJE ANALIZY RĘKI
# =============================================================================

def oblicz_meldunki(reka: List[Karta]) -> Tuple[int, List[Kolor]]:
    """
    Oblicza sumę meldunków i listę kolorów z meldunkami.
    
    Returns:
        (suma_punktów, lista_kolorów_z_meldunkami)
    """
    suma = 0
    kolory = []
    for kolor in Kolor:
        ma_krola = any(k.kolor == kolor and k.ranga == Ranga.KROL for k in reka)
        ma_dame = any(k.kolor == kolor and k.ranga == Ranga.DAMA for k in reka)
        if ma_krola and ma_dame:
            suma += WARTOSCI_MELDUNKOW[kolor]
            kolory.append(kolor)
    return suma, kolory


def oblicz_sile_reki(reka: List[Karta]) -> int:
    """
    Oblicza siłę ręki (suma wartości kart).
    Max możliwe = 120 punktów w talii.
    """
    return sum(k.wartosc for k in reka)


def policz_asy(reka: List[Karta]) -> int:
    """Liczy asy w ręce."""
    return sum(1 for k in reka if k.ranga == Ranga.AS)


def policz_dziesiatki(reka: List[Karta]) -> int:
    """Liczy dziesiątki w ręce."""
    return sum(1 for k in reka if k.ranga == Ranga.DZIESIATKA)


def policz_karty_w_kolorze(reka: List[Karta], kolor: Kolor) -> int:
    """Liczy karty w danym kolorze."""
    return sum(1 for k in reka if k.kolor == kolor)


def najwyzsza_karta_w_kolorze(reka: List[Karta], kolor: Kolor) -> Optional[Karta]:
    """Zwraca najwyższą kartę w danym kolorze."""
    karty = [k for k in reka if k.kolor == kolor]
    if not karty:
        return None
    return max(karty, key=lambda k: k.ranga.value)


def najnizsza_karta_w_kolorze(reka: List[Karta], kolor: Kolor) -> Optional[Karta]:
    """Zwraca najniższą kartę w danym kolorze."""
    karty = [k for k in reka if k.kolor == kolor]
    if not karty:
        return None
    return min(karty, key=lambda k: k.ranga.value)


def znajdz_karty_do_meldunku(reka: List[Karta]) -> List[Karta]:
    """Znajduje karty będące częścią meldunku (K lub D z pary)."""
    karty_meldunkowe = []
    for kolor in Kolor:
        krol = next((k for k in reka if k.kolor == kolor and k.ranga == Ranga.KROL), None)
        dama = next((k for k in reka if k.kolor == kolor and k.ranga == Ranga.DAMA), None)
        if krol and dama:
            karty_meldunkowe.extend([krol, dama])
    return karty_meldunkowe


def ocen_sile_do_licytacji(reka: List[Karta]) -> Dict[str, Any]:
    """
    Ocenia siłę ręki do licytacji.
    
    Returns:
        Dict z informacjami o sile ręki
    """
    suma_meldunkow, kolory_meldunkow = oblicz_meldunki(reka)
    sila_kart = oblicz_sile_reki(reka)
    asy = policz_asy(reka)
    dziesiatki = policz_dziesiatki(reka)
    
    # Szacowany wynik = punkty z kart które możemy zdobyć + meldunki
    # Zakładamy że zdobędziemy ~50-70% punktów z ręki jeśli mamy silne karty
    
    # Bonus za asy (pewne punkty)
    bonus_asy = asy * 8  # Każdy as to prawie pewne 11 pkt
    
    # Bonus za dziesiątki z asem w tym samym kolorze
    bonus_dziesiatki = 0
    for kolor in Kolor:
        ma_asa = any(k.kolor == kolor and k.ranga == Ranga.AS for k in reka)
        ma_dziesiatke = any(k.kolor == kolor and k.ranga == Ranga.DZIESIATKA for k in reka)
        if ma_asa and ma_dziesiatke:
            bonus_dziesiatki += 8  # Zabezpieczona dziesiątka
    
    # Szacowany bezpieczny kontrakt
    bezpieczny_kontrakt = suma_meldunkow + bonus_asy + bonus_dziesiatki + 20
    
    # Zaokrąglij do dziesiątek w dół
    bezpieczny_kontrakt = (bezpieczny_kontrakt // 10) * 10
    
    # Nie mniej niż 100
    bezpieczny_kontrakt = max(100, bezpieczny_kontrakt)
    
    # Max = 120 + meldunki
    max_kontrakt = 120 + suma_meldunkow
    
    return {
        'suma_meldunkow': suma_meldunkow,
        'kolory_meldunkow': kolory_meldunkow,
        'sila_kart': sila_kart,
        'asy': asy,
        'dziesiatki': dziesiatki,
        'bezpieczny_kontrakt': min(bezpieczny_kontrakt, max_kontrakt),
        'max_kontrakt': min(max_kontrakt, 360)
    }


# =============================================================================
# STRATEGIA LICYTACJI
# =============================================================================

def wybierz_licytacje(bot: Gracz, rozdanie: RozdanieTysiac, mozliwe_akcje: List[Dict]) -> Dict:
    """Wybiera akcję licytacji."""
    
    ocena = ocen_sile_do_licytacji(bot.reka)
    aktualna = rozdanie.aktualna_licytacja
    
    akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
    akcja_licytuj = next((a for a in mozliwe_akcje if a['typ'] == 'licytuj'), None)
    
    # Nie możemy licytować wyżej niż pozwalają meldunki
    if not akcja_licytuj:
        if akcja_pas:
            return akcja_pas
        return mozliwe_akcje[0] if mozliwe_akcje else {'typ': 'pas'}
    
    max_licytacja = akcja_licytuj.get('max_wartosc', 120)
    nastepna_wartosc = akcja_licytuj.get('wartosc', aktualna + 10)
    
    # Strategia:
    # 1. Jeśli następna licytacja > bezpieczny kontrakt -> pasuj
    # 2. Jeśli mamy silną rękę (dużo meldunków) -> licytuj agresywniej
    # 3. Dodaj losowość żeby bot nie był przewidywalny
    
    bezpieczny = ocena['bezpieczny_kontrakt']
    
    # Jeśli licytacja przekracza nasz bezpieczny poziom - pasuj
    if nastepna_wartosc > bezpieczny + 20:  # +20 margines ryzyka
        if akcja_pas:
            return akcja_pas
    
    # Jeśli mamy świetną rękę (meldunki >= 100) - licytuj odważniej
    if ocena['suma_meldunkow'] >= 100:
        if nastepna_wartosc <= bezpieczny + 40 and random.random() < 0.8:
            return {'typ': 'licytuj', 'wartosc': nastepna_wartosc}
    
    # Jeśli mamy dobre meldunki (>= 60) - licytuj
    if ocena['suma_meldunkow'] >= 60:
        if nastepna_wartosc <= bezpieczny + 20 and random.random() < 0.7:
            return {'typ': 'licytuj', 'wartosc': nastepna_wartosc}
    
    # Jeśli mamy jakieś meldunki - czasami licytuj
    if ocena['suma_meldunkow'] > 0:
        if nastepna_wartosc <= bezpieczny and random.random() < 0.5:
            return {'typ': 'licytuj', 'wartosc': nastepna_wartosc}
    
    # Bez meldunków - bardzo rzadko licytuj (tylko na 100-110)
    if ocena['suma_meldunkow'] == 0:
        if nastepna_wartosc <= 110 and ocena['asy'] >= 2 and random.random() < 0.3:
            return {'typ': 'licytuj', 'wartosc': nastepna_wartosc}
    
    # Domyślnie pasuj
    if akcja_pas:
        return akcja_pas
    
    # Musimy licytować (nie możemy spasować)
    return {'typ': 'licytuj', 'wartosc': nastepna_wartosc}


# =============================================================================
# STRATEGIA WYBORU MUSIKU
# =============================================================================

def wybierz_musik(bot: Gracz, rozdanie: RozdanieTysiac) -> Dict:
    """Wybiera musik (losowo, bo nie znamy zawartości)."""
    # Losowy wybór - nie mamy informacji który jest lepszy
    return {'typ': 'wybierz_musik', 'musik': random.choice([1, 2])}


# =============================================================================
# STRATEGIA ODDAWANIA KART
# =============================================================================

def wybierz_karty_do_oddania(bot: Gracz, rozdanie: RozdanieTysiac) -> Dict:
    """
    Wybiera 2 karty do oddania do musiku.
    Strategia:
    1. Nigdy nie oddawaj kart z meldunku
    2. Oddaj najsłabsze karty (9, W)
    3. Preferuj oddawanie z kolorów gdzie mamy mało kart
    """
    if len(bot.reka) < 2:
        return {'typ': 'oddaj_karty', 'karty': bot.reka[:2] if bot.reka else []}
    
    # Znajdź karty które są częścią meldunku - nie oddawaj ich!
    karty_meldunkowe = znajdz_karty_do_meldunku(bot.reka)
    
    # Karty które możemy oddać
    karty_do_oddania = [k for k in bot.reka if k not in karty_meldunkowe]
    
    if len(karty_do_oddania) < 2:
        # Musimy oddać jakieś karty z meldunku - oddaj najsłabsze
        karty_do_oddania = sorted(bot.reka, key=lambda k: k.wartosc)
        return {'typ': 'oddaj_karty', 'karty': karty_do_oddania[:2]}
    
    # Oceń każdą kartę - im niższa ocena, tym lepiej ją oddać
    def ocena_karty(karta: Karta) -> float:
        score = 0
        
        # Podstawowa wartość karty (9=0, W=2, D=3, K=4, 10=10, A=11)
        score += karta.wartosc * 2
        
        # Bonus za asy - nie oddawaj
        if karta.ranga == Ranga.AS:
            score += 50
        
        # Bonus za dziesiątki - raczej nie oddawaj
        if karta.ranga == Ranga.DZIESIATKA:
            score += 30
        
        # Bonus jeśli mamy więcej kart w tym kolorze (siła w kolorze)
        karty_w_kolorze = policz_karty_w_kolorze(bot.reka, karta.kolor)
        score += karty_w_kolorze * 3
        
        # Bonus jeśli mamy asa w tym kolorze (kolor jest zabezpieczony)
        ma_asa = any(k.kolor == karta.kolor and k.ranga == Ranga.AS for k in bot.reka)
        if ma_asa and karta.ranga != Ranga.AS:
            score += 5
        
        return score
    
    # Sortuj karty wg oceny (rosnąco = najgorsze pierwsze)
    karty_do_oddania.sort(key=ocena_karty)
    
    return {'typ': 'oddaj_karty', 'karty': karty_do_oddania[:2]}


# =============================================================================
# STRATEGIA DECYZJI PO MUSIKU
# =============================================================================

def wybierz_decyzje_po_musiku(bot: Gracz, rozdanie: RozdanieTysiac, mozliwe_akcje: List[Dict]) -> Dict:
    """
    Decyduje czy podwyższyć kontrakt po zobaczeniu musiku.
    """
    ocena = ocen_sile_do_licytacji(bot.reka)
    obecny_kontrakt = rozdanie.kontrakt_wartosc
    
    # Znajdź akcję zmiany kontraktu
    akcja_zmien = next((a for a in mozliwe_akcje if a['typ'] == 'zmien_kontrakt'), None)
    
    # Jeśli bezpieczny kontrakt > obecny -> rozważ podwyższenie
    if akcja_zmien and ocena['bezpieczny_kontrakt'] > obecny_kontrakt:
        mozliwe_wartosci = akcja_zmien.get('mozliwe_wartosci', [])
        
        # Wybierz wartość bliską bezpiecznemu kontraktowi
        for wartosc in mozliwe_wartosci:
            if wartosc <= ocena['bezpieczny_kontrakt']:
                # Podwyższ z pewnym prawdopodobieństwem
                if random.random() < 0.6:
                    return {'typ': 'zmien_kontrakt', 'wartosc': wartosc}
    
    # Sprawdź bombę - użyj tylko gdy ręka jest bardzo słaba
    akcja_bomba = next((a for a in mozliwe_akcje if a['typ'] == 'bomba'), None)
    if akcja_bomba:
        # Bomba gdy: kontrakt wysoki, a ręka słaba
        if obecny_kontrakt >= 140 and ocena['bezpieczny_kontrakt'] < obecny_kontrakt - 30:
            if random.random() < 0.3:  # Rzadko używaj bomby
                return {'typ': 'bomba'}
    
    # Domyślnie kontynuuj
    return {'typ': 'kontynuuj'}


# =============================================================================
# STRATEGIA ROZGRYWKI
# =============================================================================

def wybierz_karte_do_zagrania(bot: Gracz, rozdanie: RozdanieTysiac, grywalne_karty: List[Karta]) -> Karta:
    """
    Wybiera kartę do zagrania.
    """
    if not grywalne_karty:
        return None
    
    if len(grywalne_karty) == 1:
        return grywalne_karty[0]
    
    aktualna_lewa = rozdanie.aktualna_lewa
    atut = rozdanie.atut
    
    # === PIERWSZA KARTA W LEWIE ===
    if not aktualna_lewa:
        return wybierz_karte_jako_pierwszy(bot, rozdanie, grywalne_karty)
    
    # === DRUGA KARTA W LEWIE (2p) ===
    else:
        return wybierz_karte_jako_drugi(bot, rozdanie, grywalne_karty)


def wybierz_karte_jako_pierwszy(bot: Gracz, rozdanie: RozdanieTysiac, grywalne_karty: List[Karta]) -> Karta:
    """Wybiera kartę gdy bot jest pierwszy w lewie."""
    
    atut = rozdanie.atut
    
    # 1. Sprawdź czy możemy zagrać meldunek
    karty_meldunkowe = znajdz_karty_do_meldunku(bot.reka)
    zadeklarowane_kolory = [kolor for _, kolor in rozdanie.zadeklarowane_meldunki if _ == bot]
    
    for karta in grywalne_karty:
        if karta in karty_meldunkowe:
            # Sprawdź czy ten meldunek już był zadeklarowany
            if karta.kolor not in zadeklarowane_kolory:
                # Zagraj meldunek!
                return karta
    
    # 2. Graj asy (zdobywają punkty)
    asy = [k for k in grywalne_karty if k.ranga == Ranga.AS]
    if asy:
        # Preferuj asy z koloru gdzie mamy też dziesiątkę
        for as_karta in asy:
            ma_dziesiatke = any(k.kolor == as_karta.kolor and k.ranga == Ranga.DZIESIATKA for k in bot.reka)
            if ma_dziesiatke:
                return as_karta
        return random.choice(asy)
    
    # 3. Graj z długiego koloru (gdzie mamy dużo kart)
    kolory_z_kartami = {}
    for karta in grywalne_karty:
        if karta.kolor not in kolory_z_kartami:
            kolory_z_kartami[karta.kolor] = []
        kolory_z_kartami[karta.kolor].append(karta)
    
    # Najdłuższy kolor (nie atut)
    najdluzszy_kolor = None
    max_kart = 0
    for kolor, karty in kolory_z_kartami.items():
        if kolor != atut and len(karty) > max_kart:
            max_kart = len(karty)
            najdluzszy_kolor = kolor
    
    if najdluzszy_kolor and max_kart >= 2:
        karty_koloru = kolory_z_kartami[najdluzszy_kolor]
        # Graj najwyższą z długiego koloru
        return max(karty_koloru, key=lambda k: k.ranga.value)
    
    # 4. Zagraj wysoką kartę z dowolnego koloru (nie atut)
    karty_nie_atut = [k for k in grywalne_karty if k.kolor != atut]
    if karty_nie_atut:
        return max(karty_nie_atut, key=lambda k: k.ranga.value)
    
    # 5. Fallback - losowa karta
    return random.choice(grywalne_karty)


def wybierz_karte_jako_drugi(bot: Gracz, rozdanie: RozdanieTysiac, grywalne_karty: List[Karta]) -> Karta:
    """Wybiera kartę gdy bot jest drugi w lewie (odpowiada na kartę przeciwnika)."""
    
    atut = rozdanie.atut
    karta_przeciwnika = rozdanie.aktualna_lewa[0][1]
    kolor_wiodacy = karta_przeciwnika.kolor
    
    # Karty w kolorze wiodącym
    karty_w_kolorze = [k for k in grywalne_karty if k.kolor == kolor_wiodacy]
    
    # Karty atutowe
    karty_atutowe = [k for k in grywalne_karty if k.kolor == atut] if atut else []
    
    # Punkty do zdobycia w tej lewie
    punkty_w_lewie = karta_przeciwnika.wartosc
    
    # === MAMY KOLOR WIODĄCY ===
    if karty_w_kolorze:
        # Karty które biją kartę przeciwnika
        karty_bijace = [k for k in karty_w_kolorze if k.ranga.value > karta_przeciwnika.ranga.value]
        
        if karty_bijace:
            # Mamy czym bić
            if punkty_w_lewie >= 10:
                # Warto bić - graj najniższą bijącą
                return min(karty_bijace, key=lambda k: k.ranga.value)
            else:
                # Mało punktów - graj najniższą bijącą lub najniższą ogólnie
                if random.random() < 0.7:
                    return min(karty_bijace, key=lambda k: k.ranga.value)
                else:
                    return min(karty_w_kolorze, key=lambda k: k.ranga.value)
        else:
            # Nie mamy czym bić - daj najniższą
            return min(karty_w_kolorze, key=lambda k: k.ranga.value)
    
    # === NIE MAMY KOLORU WIODĄCEGO ===
    
    # Sprawdź czy przeciwnik grał atutem
    przeciwnik_gral_atut = karta_przeciwnika.kolor == atut
    
    # Mamy atuty i przeciwnik nie grał atutem
    if karty_atutowe and not przeciwnik_gral_atut:
        if punkty_w_lewie >= 10:
            # Warto przebić atutem - graj najniższy atut
            return min(karty_atutowe, key=lambda k: k.ranga.value)
        else:
            # Mało punktów - czasami przebij
            if random.random() < 0.4:
                return min(karty_atutowe, key=lambda k: k.ranga.value)
    
    # Mamy atuty i przeciwnik grał atutem - musimy dać atuta
    if karty_atutowe and przeciwnik_gral_atut:
        karty_bijace = [k for k in karty_atutowe if k.ranga.value > karta_przeciwnika.ranga.value]
        if karty_bijace:
            return min(karty_bijace, key=lambda k: k.ranga.value)
        else:
            return min(karty_atutowe, key=lambda k: k.ranga.value)
    
    # Nie mamy ani koloru ani atutów - daj najsłabszą kartę
    return min(grywalne_karty, key=lambda k: k.wartosc)


# =============================================================================
# GŁÓWNA FUNKCJA BOTA
# =============================================================================

def wybierz_akcje_dla_bota_testowego_tysiac(bot: Gracz, rozdanie: RozdanieTysiac) -> Tuple[str, Any]:
    """
    Główna funkcja wyboru akcji dla bota w Tysiącu.
    
    Args:
        bot: Obiekt gracza-bota
        rozdanie: Obiekt rozdania
    
    Returns:
        tuple: (typ_akcji, parametry_akcji)
    """
    
    # === FAZA ROZGRYWKI ===
    if rozdanie.faza == FazaGry.ROZGRYWKA:
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        
        if grywalne_karty:
            karta = wybierz_karte_do_zagrania(bot, rozdanie, grywalne_karty)
            return 'karta', karta
        else:
            return 'brak', None
    
    # === FAZA LICYTACJI ===
    elif rozdanie.faza == FazaGry.LICYTACJA:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        akcja = wybierz_licytacje(bot, rozdanie, mozliwe_akcje)
        return 'licytacja', akcja
    
    # === FAZA WYMIANY MUSZKU ===
    elif rozdanie.faza == FazaGry.WYMIANA_MUSZKU:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        # Wybór musiku (tryb 2p)
        if rozdanie.tryb == '2p' and not rozdanie.musik_odkryty:
            akcja = wybierz_musik(bot, rozdanie)
            return 'licytacja', akcja
        
        # Oddawanie kart (tryb 2p)
        if rozdanie.musik_odkryty and rozdanie.tryb == '2p':
            akcja = wybierz_karty_do_oddania(bot, rozdanie)
            return 'licytacja', akcja
        
        # Tryb 3p/4p - rozdawanie kart (uproszczone)
        if rozdanie.musik_odkryty and rozdanie.tryb in ['3p', '4p']:
            # Daj najsłabsze karty przeciwnikom
            liczba_aktywnych = len(rozdanie.gracze) - (1 if rozdanie.tryb == '4p' else 0)
            liczba_do_rozdania = liczba_aktywnych - 1
            
            karty_posortowane = sorted(bot.reka, key=lambda k: k.wartosc)
            rozdanie_dict = {}
            idx = 0
            for gracz in rozdanie.gracze:
                if gracz != bot and (rozdanie.tryb != '4p' or rozdanie.muzyk_idx is None or gracz != rozdanie.gracze[rozdanie.muzyk_idx]):
                    if idx < len(karty_posortowane) and idx < liczba_do_rozdania:
                        rozdanie_dict[gracz.nazwa] = karty_posortowane[idx]
                        idx += 1
            
            if rozdanie_dict:
                return 'licytacja', {'typ': 'rozdaj_karty', 'rozdanie': rozdanie_dict}
        
        # Fallback
        return 'licytacja', mozliwe_akcje[0] if mozliwe_akcje else {'typ': 'pas'}
    
    # === FAZA DECYZJI PO MUSIKU ===
    elif rozdanie.faza == FazaGry.DECYZJA_PO_MUSIKU:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'licytacja', {'typ': 'kontynuuj'}
        
        akcja = wybierz_decyzje_po_musiku(bot, rozdanie, mozliwe_akcje)
        return 'licytacja', akcja
    
    # === INNE FAZY ===
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        
        if not mozliwe_akcje:
            return 'brak', None
        
        return 'licytacja', random.choice(mozliwe_akcje)
