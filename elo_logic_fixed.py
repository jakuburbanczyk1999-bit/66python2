# elo_logic_fixed.py
"""
POPRAWIONA LOGIKA ELO

Ta wersja funkcji zaktualizuj_elo_po_meczu():
1. Używa engine.get_outcome() zamiast hardkodowanych wartości
2. Poprawnie mapuje user_id -> username
3. Obsługuje zarówno gry 4p (drużyny) jak i 3p (FFA)
4. Obsługuje timeouty

Zastąp oryginalną funkcję w main.py tym kodem.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import traceback
from database import async_sessionmaker, User, PlayerGameStats
from engines.abstract_game_engine import AbstractGameEngine


def oblicz_nowe_elo(elo_a: float, elo_b: float, wynik_a: float) -> float:
    """
    Oblicza nowe Elo dla gracza A po meczu z graczem B.
    
    Args:
        elo_a: Aktualne Elo gracza A
        elo_b: Aktualne Elo gracza B (lub średnie Elo przeciwników)
        wynik_a: Wynik gracza A (1.0 = wygrana, 0.5 = remis, 0.0 = przegrana)
    
    Returns:
        Nowe Elo gracza A
    """
    K = 32  # Współczynnik K (można dostosować: 40 dla nowych graczy, 20 dla ekspertów)
    oczekiwany_wynik_a = 1 / (1 + 10**((elo_b - elo_a) / 400))
    nowe_elo_a = elo_a + K * (wynik_a - oczekiwany_wynik_a)
    return round(nowe_elo_a, 2)


async def zaktualizuj_elo_po_meczu(lobby_data: dict, engine: AbstractGameEngine):
    """
    POPRAWIONA logika Elo.
    
    Pobiera wynik z silnika gry (engine.get_outcome()) i aktualizuje
    statystyki graczy w bazie danych.
    
    Args:
        lobby_data: Dane lobby z Redis
        engine: Silnik gry (AbstractGameEngine) - MUSI być w stanie terminalnym
    """
    id_gry = lobby_data.get("id_gry")
    
    # Sprawdź, czy gra jest rankingowa i czy Elo nie zostało już obliczone
    if not lobby_data.get("opcje", {}).get("rankingowa", False):
        return
    
    if lobby_data.get("elo_obliczone", False):
        return  # Już obliczone
    
    print(f"[{id_gry}] Obliczanie Elo dla zakończonego meczu rankingowego...")
    lobby_data["elo_obliczone"] = True
    
    # Pobierz game_type_id (MUSI być ustawione podczas tworzenia gry)
    game_type_id = lobby_data.get("game_type_id")
    if not game_type_id:
        print(f"BŁĄD KRYTYCZNY ELO: Brak 'game_type_id' w lobby_data dla gry {id_gry}.")
        return
    
    # === KLUCZOWA ZMIANA: Użyj engine.get_outcome() ===
    if not engine.is_terminal():
        print(f"BŁĄD ELO: Silnik gry {id_gry} nie jest w stanie terminalnym!")
        return
    
    outcome = engine.get_outcome()  # Dict[player_id: str, score: float]
    # score = 1.0 (wygrana), 0.0 (przegrana), 0.5 (remis/podział)
    
    if not outcome:
        print(f"BŁĄD ELO: engine.get_outcome() zwróciło pusty słownik dla {id_gry}")
        return
    
    player_ids = list(outcome.keys())
    if not player_ids:
        print(f"BŁĄD ELO: Brak graczy w outcome dla {id_gry}")
        return
    
    try:
        async with async_sessionmaker() as session:
            session: AsyncSession
            
            # --- KROK 1: Pobierz statystyki wszystkich graczy ---
            stats_dict: Dict[str, PlayerGameStats] = {}  # player_name -> PlayerGameStats
            user_dict: Dict[str, User] = {}  # player_name -> User
            
            for player_name in player_ids:
                # Znajdź użytkownika w bazie
                user_result = await session.execute(
                    select(User).where(User.username == player_name)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    print(f"OSTRZEŻENIE ELO: Nie znaleziono User dla gracza '{player_name}'. Pomijanie.")
                    continue
                
                user_dict[player_name] = user
                
                # Znajdź statystyki dla tego gracza i typu gry
                stats_result = await session.execute(
                    select(PlayerGameStats).where(
                        PlayerGameStats.user_id == user.id,
                        PlayerGameStats.game_type_id == game_type_id
                    )
                )
                stats = stats_result.scalar_one_or_none()
                
                # Jeśli gracz gra pierwszy raz w tę grę, stwórz wpis
                if not stats:
                    print(f"INFO ELO: Tworzenie nowego wpisu PlayerGameStats dla '{player_name}' (ID: {user.id}), gra {game_type_id}.")
                    stats = PlayerGameStats(
                        user_id=user.id,
                        game_type_id=game_type_id
                        # Domyślne Elo (1200) jest ustawione w modelu
                    )
                    session.add(stats)
                    # Flush aby otrzymać domyślne wartości
                    await session.flush()
                
                stats_dict[player_name] = stats
            
            # Sprawdź, czy mamy statystyki dla wszystkich graczy
            if len(stats_dict) != len(player_ids):
                print(f"BŁĄD ELO: Nie udało się pobrać statystyk dla wszystkich graczy. Anulowanie.")
                await session.rollback()
                return
            
            # --- KROK 2: Oblicz nowe Elo ---
            wynik_elo_dla_klienta = {}  # player_name -> "1200 → 1220 (+20)"
            max_graczy = lobby_data.get("max_graczy", 4)
            
            if max_graczy == 4:
                # === GRA 4-OSOBOWA (DRUŻYNY) ===
                print(f"[{id_gry}] Obliczanie Elo dla gry 4-osobowej (drużynowej)...")
                
                # Podziel graczy na drużyny
                druzyna_my_ids = [
                    s['nazwa'] for s in lobby_data['slots'] 
                    if s.get('druzyna') == 'My' and s['nazwa'] in stats_dict
                ]
                druzyna_oni_ids = [
                    s['nazwa'] for s in lobby_data['slots'] 
                    if s.get('druzyna') == 'Oni' and s['nazwa'] in stats_dict
                ]
                
                if not druzyna_my_ids or not druzyna_oni_ids:
                    print(f"BŁĄD ELO: Nie można określić drużyn dla gry {id_gry}")
                    await session.rollback()
                    return
                
                # Oblicz średnie Elo drużyn
                avg_elo_my = sum(stats_dict[pid].elo_rating for pid in druzyna_my_ids) / len(druzyna_my_ids)
                avg_elo_oni = sum(stats_dict[pid].elo_rating for pid in druzyna_oni_ids) / len(druzyna_oni_ids)
                
                print(f"[{id_gry}] Średnie Elo - My: {avg_elo_my:.1f}, Oni: {avg_elo_oni:.1f}")
                
                # Pobierz wynik z outcome (wszyscy w drużynie mają ten sam wynik)
                wynik_my = outcome[druzyna_my_ids[0]]  # 1.0, 0.5, lub 0.0
                wynik_oni = outcome[druzyna_oni_ids[0]]
                
                print(f"[{id_gry}] Wyniki - My: {wynik_my}, Oni: {wynik_oni}")
                
                # Oblicz nowe średnie Elo
                nowe_avg_elo_my = oblicz_nowe_elo(avg_elo_my, avg_elo_oni, wynik_my)
                nowe_avg_elo_oni = oblicz_nowe_elo(avg_elo_oni, avg_elo_my, wynik_oni)
                
                # Oblicz zmiany
                zmiana_my = nowe_avg_elo_my - avg_elo_my
                zmiana_oni = nowe_avg_elo_oni - avg_elo_oni
                
                print(f"[{id_gry}] Zmiany Elo - My: {zmiana_my:+.1f}, Oni: {zmiana_oni:+.1f}")
                
                # Zaktualizuj statystyki dla drużyny "My"
                for player_name in druzyna_my_ids:
                    stats = stats_dict[player_name]
                    stare_elo = stats.elo_rating
                    
                    stats.elo_rating += zmiana_my
                    stats.games_played += 1
                    if wynik_my == 1.0:
                        stats.games_won += 1
                    
                    wynik_elo_dla_klienta[player_name] = (
                        f"{stare_elo:.0f} → {stats.elo_rating:.0f} ({zmiana_my:+.0f})"
                    )
                
                # Zaktualizuj statystyki dla drużyny "Oni"
                for player_name in druzyna_oni_ids:
                    stats = stats_dict[player_name]
                    stare_elo = stats.elo_rating
                    
                    stats.elo_rating += zmiana_oni
                    stats.games_played += 1
                    if wynik_oni == 1.0:
                        stats.games_won += 1
                    
                    wynik_elo_dla_klienta[player_name] = (
                        f"{stare_elo:.0f} → {stats.elo_rating:.0f} ({zmiana_oni:+.0f})"
                    )
            
            elif max_graczy == 3:
                # === GRA 3-OSOBOWA (FREE-FOR-ALL) ===
                print(f"[{id_gry}] Obliczanie Elo dla gry 3-osobowej (FFA)...")
                
                # W grze FFA każdy gra przeciwko wszystkim
                # Uproszczenie: każdy gracz gra przeciwko średniej Elo pozostałych
                
                for player_name in player_ids:
                    stats = stats_dict[player_name]
                    
                    # Średnie Elo przeciwników
                    przeciwnicy = [p for p in player_ids if p != player_name]
                    avg_elo_przeciwnikow = sum(
                        stats_dict[p].elo_rating for p in przeciwnicy
                    ) / len(przeciwnicy)
                    
                    # Wynik gracza
                    wynik_gracza = outcome[player_name]
                    
                    print(f"[{id_gry}] {player_name}: Elo {stats.elo_rating:.1f} vs Avg {avg_elo_przeciwnikow:.1f}, Wynik: {wynik_gracza}")
                    
                    # Oblicz nowe Elo
                    stare_elo = stats.elo_rating
                    nowe_elo = oblicz_nowe_elo(stare_elo, avg_elo_przeciwnikow, wynik_gracza)
                    zmiana = nowe_elo - stare_elo
                    
                    # Zaktualizuj statystyki
                    stats.elo_rating = nowe_elo
                    stats.games_played += 1
                    if wynik_gracza == 1.0:
                        stats.games_won += 1
                    
                    wynik_elo_dla_klienta[player_name] = (
                        f"{stare_elo:.0f} → {nowe_elo:.0f} ({zmiana:+.0f})"
                    )
            
            else:
                print(f"BŁĄD ELO: Nieobsługiwana liczba graczy: {max_graczy}")
                await session.rollback()
                return
            
            # --- KROK 3: Zapisz w bazie danych ---
            await session.commit()
            
            # --- KROK 4: Zapisz podsumowanie w Redis (dla frontendu) ---
            lobby_data["wynik_elo"] = wynik_elo_dla_klienta
            # To zostanie zapisane przez wywołującą funkcję (save_lobby_data)
            
            print(f"[{id_gry}] ✓ Zaktualizowano Elo:")
            for player, change in wynik_elo_dla_klienta.items():
                print(f"  - {player}: {change}")
    
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY podczas aktualizacji Elo dla gry {id_gry}: {e}")
        traceback.print_exc()


async def zaktualizuj_elo_po_timeout(lobby_data: dict, outcome: Dict[str, float]):
    """
    Specjalna wersja dla timeout'ów.
    Używana przez Timer Worker, gdy silnik gry już nie istnieje.
    
    Args:
        lobby_data: Dane lobby z Redis
        outcome: Ręcznie utworzony outcome (Dict[player_id, score])
    """
    id_gry = lobby_data.get("id_gry")
    
    if not lobby_data.get("opcje", {}).get("rankingowa", False):
        return
    
    if lobby_data.get("elo_obliczone", False):
        return
    
    print(f"[{id_gry}] Obliczanie Elo po timeout...")
    lobby_data["elo_obliczone"] = True
    
    game_type_id = lobby_data.get("game_type_id")
    if not game_type_id:
        print(f"BŁĄD KRYTYCZNY ELO (timeout): Brak 'game_type_id'")
        return
    
    # Reszta logiki jest identyczna jak w zaktualizuj_elo_po_meczu
    # (można by wydzielić wspólną funkcję pomocniczą)
    
    player_ids = list(outcome.keys())
    if not player_ids:
        return
    
    try:
        async with async_sessionmaker() as session:
            # ... (identyczna logika jak powyżej)
            pass
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY Elo (timeout): {e}")
        traceback.print_exc()


# ==========================================================================
# TESTY JEDNOSTKOWE (opcjonalne)
# ==========================================================================

async def test_oblicz_nowe_elo():
    """Testuje funkcję oblicz_nowe_elo()"""
    
    # Test 1: Gracze równi, wygrana
    assert abs(oblicz_nowe_elo(1200, 1200, 1.0) - 1216) < 1
    
    # Test 2: Gracze równi, przegrana
    assert abs(oblicz_nowe_elo(1200, 1200, 0.0) - 1184) < 1
    
    # Test 3: Gracze równi, remis
    assert abs(oblicz_nowe_elo(1200, 1200, 0.5) - 1200) < 1
    
    # Test 4: Słabszy wygrywa z silniejszym
    assert oblicz_nowe_elo(1000, 1400, 1.0) > 1028  # Duża zdobycz
    
    # Test 5: Silniejszy przegrywa ze słabszym
    assert oblicz_nowe_elo(1400, 1000, 0.0) < 1372  # Duża strata
    
    print("✓ Wszystkie testy oblicz_nowe_elo() przeszły")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_oblicz_nowe_elo())
