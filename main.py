# main.py
# WERSJA ZREFAKTORYZOWANA (zgodna z Faza 1 i 2 planu strategicznego)
# + POPRAWKA STRUKTURY JSON DLA FRONTENDU

# ==========================================================================
# SEKCJA 1: IMPORTY I KONFIGURACJA APLIKACJI
# ==========================================================================

# --- Standardowe biblioteki Python ---
import uuid
import random
import json
import asyncio
import string
import traceback
import time
import copy
from typing import Any, Optional, AsyncGenerator, Dict, List
from contextlib import asynccontextmanager

# --- Biblioteki firm trzecich ---
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, 
    HTTPException, status
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import redis.asyncio as aioredis # <-- NOWY IMPORT: Asynchroniczny klient Redis
import cloudpickle                 # <-- NOWY IMPORT: Do serializacji obiektów (silnika)

# --- Biblioteki SQLAlchemy ---
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# --- Moduły lokalne ---
# Używamy zaktualizowanej bazy danych
from database import (
    init_db, async_sessionmaker, User, GameType, PlayerGameStats
) 
from auth_utils import hash_password, verify_password
# Importujemy NOWE silniki i interfejsy
from engines.abstract_game_engine import AbstractGameEngine
from engines.sixtysix_engine import SixtySixEngine 
# Stare importy (wciąż potrzebne do modeli Pydantic, ale nie do logiki gry)
import silnik_gry 
import boty # Wciąż potrzebne do instancji botów, dopóki nie zostaną zrefaktoryzowane
from redis_utils import (   # NOWE: funkcje pomocnicze Redis
    RedisLock, 
    TimerInfo, 
    cleanup_expired_games,
    get_active_game_count
)
from timer_worker import TimerWorker # NOWY: dedykowany worker do zarządzania timerami

# ==========================================================================
# SEKCJA 2: INICJALIZACJA APLIKACJI I ZASOBÓW GLOBALNYCH
# ==========================================================================



# --- Globalny klient Redis ---
# Ta zmienna zostanie zainicjalizowana w funkcji 'lifespan'
redis_client: aioredis.Redis = None
timer_worker_instance: Optional[TimerWorker] = None


# --- Manager cyklu życia aplikacji (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Zarządza zdarzeniami startu i zamknięcia aplikacji FastAPI.
    """
    global redis_client, timer_worker_instance
    print("Serwer startuje...")
    
    # 1. Baza danych
    print("Inicjalizacja bazy danych...")
    await init_db()
    print("Baza danych gotowa.")
    
    # 2. Redis
    print("Inicjalizacja Redis...")
    try:
        redis_client = aioredis.from_url(
            "redis://localhost", 
            decode_responses=False
        )
        await redis_client.ping()
        print("Redis gotowy.")
    except Exception as e:
        print(f"!!! KRYTYCZNY BŁĄD Redis: {e}")
        raise e
    
    # 3. Timer Worker
    print("Uruchamianie Timer Worker...")
    timer_worker_instance = TimerWorker(
        redis_url="redis://localhost",
        check_interval=1.0,
        debug=True
    )
    timer_worker_task = asyncio.create_task(timer_worker_instance.run())
    print("Timer Worker uruchomiony.")
    
    # 4. Menedżer botów
    print("Uruchamianie menedżera botów...")
    asyncio.create_task(elo_world_manager())
    
    # 5. Periodic cleanup
    print("Uruchamianie periodic cleanup...")
    asyncio.create_task(periodic_cleanup())

    yield  # Aplikacja działa

    # Zamykanie
    print("Serwer się zamyka...")
    if timer_worker_instance:
        timer_worker_instance.stop()
        await asyncio.sleep(2)
    if redis_client:
        await redis_client.close()
    print("Serwer zamknięty.")


async def periodic_cleanup():
    """Okresowo czyści stare gry z Redis"""
    await asyncio.sleep(60)  # Poczekaj minutę
    
    while True:
        try:
            print("[Periodic Cleanup] Rozpoczynam...")
            await cleanup_expired_games(redis_client, max_age_seconds=21600)
            active_count = await get_active_game_count(redis_client)
            print(f"[Periodic Cleanup] Aktywnych gier: {active_count}")
        except Exception as e:
            print(f"[Periodic Cleanup] BŁĄD: {e}")
        
        await asyncio.sleep(300)  # Co 5 minut

# --- Główna instancja aplikacji FastAPI ---
app = FastAPI(lifespan=lifespan)

# --- Globalna instancja botów (pozostaje na razie bez zmian) ---
# TODO: To powinno zostać zrefaktoryzowane, gdy 'boty.py' zostanie zaktualizowane
fair_mcts_bot = boty.MCTS_Bot(perfect_information=False)
cheating_mcts_bot = boty.MCTS_Bot(perfect_information=True)
heuristic_bot = boty.AdvancedHeuristicBot()
random_bot = boty.RandomBot()

bot_instances = {
    "mcts": cheating_mcts_bot,
    "mcts_fair": fair_mcts_bot,
    "heuristic": heuristic_bot,
    "random": random_bot
}
default_bot_name = "mcts_fair"

# --- USUNIĘTO globalny słownik 'gry = {}' ---
# Stan jest teraz zarządzany przez Redis.

# --- Stałe ---
NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]
# Klucze Redis
def lobby_key(id_gry: str) -> str: return f"lobby:{id_gry}"
def engine_key(id_gry: str) -> str: return f"engine:{id_gry}"
def channel_key(id_gry: str) -> str: return f"channel:{id_gry}"

# Czas wygaśnięcia stanu gry w Redis (w sekundach)
# 6 godzin - na wypadek zawieszonej gry
GAME_STATE_EXPIRATION_S = 6 * 3600 

# ==========================================================================
# SEKCJA 3: MODELE DANYCH Pydantic (Bez zmian, ale zaktualizowane)
# ==========================================================================

class LocalGameRequest(BaseModel):
    nazwa_gracza: str

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    active_game_id: Optional[str] = None
    settings: Optional[dict] = None

class CreateGameRequest(BaseModel):
    """
    Zaktualizowany model. Docelowo 'tryb_gry' powinien być zastąpiony
    przez 'game_type_id' pobrany z bazy danych.
    """
    nazwa_gracza: str
    # TODO: Zgodnie z planem, to powinno być game_type_id: int
    tryb_gry: str # Na razie zostaje '4p' lub '3p'
    tryb_lobby: str
    publiczna: bool
    haslo: Optional[str] = None
    czy_rankingowa: bool = False
    # TODO: Dodać 'game_type_id'
    # game_type_id: int 

class UserSettings(BaseModel):
    czatUkryty: bool
    historiaUkryta: bool
    partiaHistoriaUkryta: bool
    pasekEwaluacjiUkryty: bool

# ==========================================================================
# SEKCJA 4: NOWE FUNKCJE POMOCNICZE ZARZĄDZANIA STANEM (REDIS)
# ==========================================================================

async def get_lobby_data(id_gry: str) -> Optional[Dict[str, Any]]:
    """Pobiera dane lobby (słownik) z Redis (przechowywane jako JSON)."""
    try:
        json_data = await redis_client.get(lobby_key(id_gry))
        if json_data:
            return json.loads(json_data.decode('utf-8'))
        return None
    except Exception as e:
        print(f"BŁĄD Redis (get_lobby_data) dla {id_gry}: {e}")
        return None

async def save_lobby_data(id_gry: str, lobby_data: Dict[str, Any]):
    """Zapisuje dane lobby (słownik) do Redis jako JSON."""
    try:
        # Usuwamy klucze stanu przejściowego przed zapisem
        lobby_data.pop("timer_task", None)
        lobby_data.pop("bot_loop_lock", None)
        
        json_data = json.dumps(lobby_data)
        await redis_client.set(
            lobby_key(id_gry), 
            json_data, 
            ex=GAME_STATE_EXPIRATION_S
        )
    except Exception as e:
        print(f"BŁĄD Redis (save_lobby_data) dla {id_gry}: {e}")

async def get_game_engine(id_gry: str) -> Optional[AbstractGameEngine]:
    """Pobiera zserializowany obiekt silnika gry (engine) z Redis."""
    try:
        pickled_engine = await redis_client.get(engine_key(id_gry))
        if pickled_engine:
            # Deserializacja obiektu za pomocą cloudpickle
            return cloudpickle.loads(pickled_engine)
        return None
    except Exception as e:
        print(f"BŁĄD Redis (get_game_engine) dla {id_gry}: {e}")
        return None

async def save_game_engine(id_gry: str, engine: AbstractGameEngine):
    """Serializuje i zapisuje obiekt silnika gry (engine) w Redis."""
    try:
        # Serializacja obiektu za pomocą cloudpickle
        pickled_engine = cloudpickle.dumps(engine)
        await redis_client.set(
            engine_key(id_gry), 
            pickled_engine, 
            ex=GAME_STATE_EXPIRATION_S
        )
    except Exception as e:
        print(f"BŁĄD Redis (save_game_engine) dla {id_gry}: {e}")

async def delete_game_state(id_gry: str):
    """Usuwa wszystkie dane gry (lobby i silnik) z Redis."""
    try:
        await redis_client.delete(lobby_key(id_gry), engine_key(id_gry))
        print(f"[Garbage Collector] Usunięto stan gry {id_gry} z Redis.")
    except Exception as e:
        print(f"BŁĄD Redis (delete_game_state) dla {id_gry}: {e}")

# ==========================================================================
# SEKCJA 5: ZARZĄDZANIE CZASOMIERZEM (Logika bez zmian, ale stan w Redis)
# ==========================================================================

async def uruchom_timer_dla_tury(id_gry: str):
    """
    ZREFAKTORYZOWANA: Ustawia timer info w Redis.
    Timer Worker sprawdza timeouty.
    """
    lobby_data = await get_lobby_data(id_gry)
    if (not lobby_data or 
        not lobby_data.get("opcje", {}).get("rankingowa", False) or 
        lobby_data["status_partii"] != "W_TRAKCIE"):
        return

    engine = await get_game_engine(id_gry)
    if not engine:
        return
    
    gracz_w_turze_id = engine.get_current_player()
    if not gracz_w_turze_id:
        lobby_data["timer_info"] = None
        await save_lobby_data(id_gry, lobby_data)
        return
    
    pozostaly_czas = lobby_data.get("timery", {}).get(gracz_w_turze_id, 0)
    if pozostaly_czas <= 0:
        print(f"[{id_gry}] OSTRZEŻENIE: Brak czasu dla {gracz_w_turze_id}")
        pozostaly_czas = 1.0
    
    move_number = lobby_data.get("numer_ruchu_timer", 0) + 1
    lobby_data["numer_ruchu_timer"] = move_number
    
    lobby_data["timer_info"] = TimerInfo.create(
        player_id=gracz_w_turze_id,
        remaining_time=pozostaly_czas,
        move_number=move_number
    )
    
    await save_lobby_data(id_gry, lobby_data)
    print(f"[{id_gry}] Timer: {gracz_w_turze_id} ({pozostaly_czas:.1f}s)")

# ==========================================================================
# SEKCJA 6: LOGIKA RANKINGU ELO (ZAKTUALIZOWANA DLA NOWEJ BAZY)
# ==========================================================================

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

# ==========================================================================
# SEKCJA 7: ZREFRAKTORYZOWANY ConnectionManager (z Redis Pub/Sub)
# ==========================================================================

class ConnectionManager:
    """
    Zarządza połączeniami WebSocket specyficznymi dla TEJ instancji serwera
    I obsługuje globalne nadawanie i nasłuchiwanie przez Redis Pub/Sub.
    """
    def __init__(self):
        # Słownik połączeń lokalnych dla tej instancji serwera
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.pubsub_listener_task: Optional[asyncio.Task] = None

    async def start_pubsub_listener(self):
        """Uruchamia globalnego słuchacza Pub/Sub dla tej instancji."""
        if self.pubsub_listener_task:
            return # Już działa
            
        async def listener():
            if not redis_client:
                print("BŁĄD PubSub: Klient Redis nie jest zainicjalizowany.")
                return
                
            try:
                async with redis_client.pubsub() as pubsub:
                    # Subskrybuj wszystkie kanały gier
                    await pubsub.psubscribe(channel_key("*")) 
                    print("[PubSub] Słuchacz Pub/Sub uruchomiony i subskrybuje kanały gier.")
                    
                    async for message in pubsub.listen():
                        if message["type"] == "pmessage":
                            channel_name = message["channel"].decode('utf-8')
                            id_gry = channel_name.split(":")[-1]
                            data_str = message["data"].decode('utf-8')
                            
                            # Rozszyfruj typ wiadomości
                            try:
                                data_payload = json.loads(data_str)
                                msg_type = data_payload.get("type")
                                
                                if msg_type == "STATE_UPDATE":
                                    # Otrzymano powiadomienie o aktualizacji stanu
                                    # Wyślij spersonalizowany stan do każdego lokalnego klienta
                                    await self.broadcast_state_to_locals(id_gry)
                                elif msg_type == "CHAT":
                                    # Otrzymano wiadomość czatu
                                    # Po prostu przekaż ją dalej do lokalnych klientów
                                    await self.broadcast_raw_json(id_gry, data_str)
                                    
                            except Exception as e:
                                print(f"BŁĄD PubSub: Nie można przetworzyć wiadomości {data_str}: {e}")
            except Exception as e:
                print(f"BŁĄD KRYTYCZNY: Słuchacz PubSub został przerwany: {e}")
                # TODO: Logika ponownego uruchomienia słuchacza
                self.pubsub_listener_task = None

        self.pubsub_listener_task = asyncio.create_task(listener())

    async def connect(self, websocket: WebSocket, id_gry: str, player_id: str):
        """Akceptuje i rejestruje LOKALNE połączenie."""
        await websocket.accept()
        # Zapisz player_id na obiekcie websocket dla łatwego dostępu
        websocket.scope['player_id'] = player_id 
        
        if id_gry not in self.active_connections:
            self.active_connections[id_gry] = []
        self.active_connections[id_gry].append(websocket)
        
        # Upewnij się, że słuchacz Pub/Sub działa
        if not self.pubsub_listener_task or self.pubsub_listener_task.done():
            await self.start_pubsub_listener()

    def disconnect(self, websocket: WebSocket, id_gry: str):
        """Usuwa LOKALNE połączenie."""
        if id_gry in self.active_connections:
            if websocket in self.active_connections[id_gry]:
                self.active_connections[id_gry].remove(websocket)
            if not self.active_connections[id_gry]:
                del self.active_connections[id_gry]

    async def broadcast_raw_json(self, id_gry: str, message_json: str):
        """Wysyła surowy tekst JSON do lokalnych połączeń (np. dla czatu)."""
        if id_gry in self.active_connections:
            connections_copy = self.active_connections[id_gry][:]
            tasks = [conn.send_text(message_json) for conn in connections_copy]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True) # Złap błędy, nie przerywaj

    async def broadcast_state_to_locals(self, id_gry: str):
        """
        Pobiera stan gry i wysyła spersonalizowaną wersję do każdego
        LOKALNEGO klienta w tej grze.
        """
        if id_gry not in self.active_connections:
            return # Brak lokalnych klientów dla tej gry

        lobby_data = await get_lobby_data(id_gry)
        engine = None
        if not lobby_data:
            print(f"INFO (broadcast_state): Brak danych lobby dla {id_gry}. Wysyłanie błędu.")
            # TODO: Wyślij błąd do klientów?
            return
            
        if lobby_data.get("status_partii") == "W_TRAKCIE":
            engine = await get_game_engine(id_gry)
            if not engine:
                print(f"BŁĄD (broadcast_state): Gra {id_gry} jest W_TRAKCIE, ale nie ma silnika w Redis!")
                # TODO: Napraw stan?
                return

        connections_copy = self.active_connections[id_gry][:]
        tasks = []

        for conn in connections_copy:
            player_id = conn.scope.get('player_id', None)
            if not player_id:
                continue # Pomiń połączenie bez ID gracza
                
            # --- Zbuduj stan dla TEGO gracza ---
            try:
                state_message = await self.build_state_for_player(lobby_data, engine, player_id)
                message_json = json.dumps(state_message) # Serializuj do JSON
                tasks.append(conn.send_text(message_json)) # Dodaj zadanie wysyłania
            except Exception as e:
                print(f"BŁĄD (build_state): Nie można zbudować/wysłać stanu dla {player_id}: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True) # Wyślij wszystko równolegle


    async def build_state_for_player(self, lobby_data: dict, engine: Optional[AbstractGameEngine], player_id: str) -> dict:
        """
        NOWA funkcja (zastępuje `pobierz_stan_gry`).
        Buduje pełny stan na podstawie danych z lobby i silnika.
        """
        # 1. Skopiuj bazowe dane lobby
        stan = copy.deepcopy(lobby_data)
        
        # 2. Usuń wrażliwe dane (np. hasło)
        stan.get("opcje", {}).pop("haslo", None)
        
        # 3. Jeśli gra jest w trakcie, pobierz stan z silnika
        if engine and lobby_data.get("status_partii") == "W_TRAKCIE":
            # Pobierz stan spersonalizowany dla gracza z silnika
            engine_state = engine.get_state_for_player(player_id)
            
            # === POCZĄTEK POPRAWKI (Wersja 3) ===
            # Wracamy do zagnieżdżania stanu w 'rozdanie', 
            # ponieważ tego oczekuje 'script.js'.
            
            # stan.update(engine_state) # <-- BŁĘDNA WERSJA
            stan['rozdanie'] = engine_state # <-- POPRAWNA WERSJA
            # === KONIEC POPRAWKI ===
            
            # TODO: Logika paska ewaluacji (wymaga refaktoryzacji boty.py)
            # if 'mcts' in bot_instances:
            #     ocena = bot_instances['mcts'].evaluate_state(engine, ...)
            #     stan['rozdanie']['aktualna_ocena'] = ocena
            
        elif lobby_data.get("status_partii") == "ZAKONCZONA":
            # W stanie ZAKONCZONA, silnik może już nie istnieć
            # Polegamy na danych zapisanych w lobby_data (np. `wynik_elo`)
            pass
            
        elif lobby_data.get("status_partii") == "LOBBY":
            # Stan lobby jest już kompletny
            pass
            
        # 4. Dodaj ID gracza (dla frontendu)
        stan['player_id'] = player_id
        
        return stan

    async def notify_state_update(self, id_gry: str):
        """Publikuje powiadomienie o aktualizacji stanu do Redis."""
        try:
            message = json.dumps({"type": "STATE_UPDATE"})
            await redis_client.publish(channel_key(id_gry), message)
        except Exception as e:
            print(f"BŁĄD PubSub (notify_state_update) dla {id_gry}: {e}")

    async def publish_chat_message(self, id_gry: str, chat_data: dict):
        """Publikuje wiadomość czatu do Redis."""
        try:
            chat_data["type"] = "CHAT" # Upewnij się, że typ jest ustawiony
            message = json.dumps(chat_data)
            await redis_client.publish(channel_key(id_gry), message)
        except Exception as e:
            print(f"BŁĄD PubSub (publish_chat_message) dla {id_gry}: {e}")

# Globalna instancja ConnectionManagera
manager = ConnectionManager()

# ==========================================================================
# SEKCJA 8: FUNKCJE POMOCNICZE (Baza Danych, ID Gry)
# ==========================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Zależność (dependency) FastAPI do uzyskiwania sesji bazy danych."""
    async with async_sessionmaker() as session:
        try:
            yield session
        finally:
            await session.close()

def generuj_krotki_id(dlugosc=6) -> str:
    """Generuje unikalny, krótki (domyślnie 6-znakowy) identyfikator gry."""
    # Ta funkcja musi sprawdzić, czy ID istnieje w Redis, a nie w `gry`
    # TODO: Zaimplementować sprawdzanie w Redis (choć kolizje są rzadkie)
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=dlugosc))
    
async def _zaktualizuj_stan_po_rozdaniu(id_gry: str, lobby_data: Dict[str, Any], engine: AbstractGameEngine) -> bool:
    """
    Pobiera wynik z silnika, aktualizuje punkty meczu w lobby
    i sprawdza, czy mecz się zakończył.
    Zwraca True, jeśli mecz się zakończył, False w przeciwnym razie.
    """
    if not engine.is_terminal():
        return False # Rozdanie się nie skończyło
        
    # Musimy pobrać stan dla hosta (lub kogokolwiek), aby dostać podsumowanie
    # Używamy ID hosta, bo mamy pewność, że istnieje
    podsumowanie = engine.get_state_for_player(lobby_data["host"]).get('podsumowanie')
    if not podsumowanie:
        print(f"BŁĄD ({id_gry}): Silnik jest terminalny, ale nie ma podsumowania.")
        return False
    
    punkty_meczu = lobby_data.get("punkty_meczu", {})
    max_graczy = lobby_data.get("max_graczy", 4)
    
    # === POCZĄTEK POPRAWKI (Wersja 8) ===
    # Celem meczu jest 66 punktów, a nie 7!
    CEL_MECZU = 66
    # === KONIEC POPRAWKI ===
    
    # Zmienna do śledzenia, czy ktoś wygrał
    mecz_zakonczony = False
    
    if max_graczy == 4:
        wygrana_druzyna = podsumowanie.get("wygrana_druzyna")
        if wygrana_druzyna and wygrana_druzyna in punkty_meczu:
            punkty_do_dodania = podsumowanie.get("przyznane_punkty", 0)
            punkty_meczu[wygrana_druzyna] += punkty_do_dodania
            print(f"[{id_gry}] Drużyna {wygrana_druzyna} zdobywa {punkty_do_dodania} pkt.")
            if punkty_meczu[wygrana_druzyna] >= CEL_MECZU:
                mecz_zakonczony = True
        else:
            print(f"OSTRZEŻENIE ({id_gry}): Nie można przyznać punktów drużynie {wygrana_druzyna}.")
    
    else: # 3p
        wygrani_gracze = podsumowanie.get("wygrani_gracze", [])
        punkty_do_dodania = podsumowanie.get("przyznane_punkty", 0)
        
        # W 3p punkty są dzielone (jeśli wygra obrona) lub idą do jednego gracza
        punkty_na_gracza = punkty_do_dodania
        if len(wygrani_gracze) > 1:
            punkty_na_gracza = punkty_do_dodania // len(wygrani_gracze) if wygrani_gracze else 0
            
        for gracz in wygrani_gracze:
            if gracz not in punkty_meczu:
                 punkty_meczu[gracz] = 0 # Zainicjuj, jeśli nie istnieje
                 
            punkty_meczu[gracz] += punkty_na_gracza
            print(f"[{id_gry}] Gracz {gracz} zdobywa {punkty_na_gracza} pkt.")
            if punkty_meczu[gracz] >= CEL_MECZU:
                mecz_zakonczony = True

    # Zapisz zaktualizowane punkty w lobby
    lobby_data["punkty_meczu"] = punkty_meczu
    
    # Jeśli mecz się zakończył, zaktualizuj status
    if mecz_zakonczony:
        print(f"[{id_gry}] Mecz zakończony! Wynik: {punkty_meczu}")
        lobby_data["status_partii"] = "ZAKONCZONA"
        if lobby_data.get("opcje", {}).get("rankingowa", False):
            await zaktualizuj_elo_po_meczu(lobby_data, engine)
            
    return mecz_zakonczony

# ==========================================================================
# SEKCJA 9: KONFIGURACJA PLIKÓW STATYCZNYCH I GŁÓWNYCH ENDPOINTÓW HTTP
# ==========================================================================

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/gra.html")
async def read_game_page(): return FileResponse('static/index.html')
@app.get("/lobby.html")
async def read_lobby_browser_page(): return FileResponse('static/lobby.html')
@app.get("/zasady.html")
async def read_rules_page(): return FileResponse('static/zasady.html')
@app.get("/ranking.html")
async def read_ranking_page(): return FileResponse('static/ranking.html')
@app.get("/", response_class=FileResponse)
async def serve_landing():
    """Nowy landing page"""
    return FileResponse("index.html")

@app.get("/dashboard", response_class=FileResponse)  
async def serve_dashboard():
    """Dashboard (główna strona po zalogowaniu)"""
    return FileResponse("dashboard.html")
@app.get("/zasady", response_class=FileResponse)
async def serve_rules():
    return FileResponse('zasady.html')

# ==========================================================================
# SEKCJA 10: ENDPOINTY UŻYTKOWNIKÓW (Logowanie, Rejestracja, Ustawienia)
# ==========================================================================

@app.get("/ranking/lista")
async def pobierz_ranking_graczy(
    game_type_id: Optional[int] = Query(None), # <-- NOWY filtr
    db: AsyncSession = Depends(get_db)
):
    """
    ZAKTUALIZOWANY endpoint rankingu.
    Pobiera ranking z tabeli 'player_game_stats'.
    Wymaga 'game_type_id' do filtrowania.
    """
    try:
        # Jeśli nie podano ID gry, spróbuj pobrać domyślny (np. '66 4p')
        # TODO: Lepsza obsługa domyślnego rankingu
        if not game_type_id:
            game_type_result = await db.execute(
                select(GameType.id).where(GameType.name == '66 (4p)')
            )
            game_type_id = game_type_result.scalar_one_or_none()
            if not game_type_id:
                # Jeśli nawet domyślny nie istnieje, zwróć pustą listę
                return JSONResponse(content=[]) 

        # Zapytanie do nowej tabeli
        query = (
            select(
                User.username,
                User.settings,
                PlayerGameStats.elo_rating,
                PlayerGameStats.games_played,
                PlayerGameStats.games_won
            )
            .join(User, PlayerGameStats.user_id == User.id) # Połącz z User, aby dostać nazwę
            .where(PlayerGameStats.game_type_id == game_type_id) # Filtruj wg typu gry
            .order_by(PlayerGameStats.elo_rating.desc()) # Sortuj wg Elo
        )
        
        result = await db.execute(query)
        gracze_raw = result.all()
        
        lista_rankingu = []
        for row in gracze_raw:
            jest_botem = False
            if row.settings:
                try:
                    settings = json.loads(row.settings)
                    if settings.get("jest_botem") is True:
                        jest_botem = True
                except (json.JSONDecodeError, TypeError):
                    pass
            
            lista_rankingu.append({
                "username": row.username,
                "elo_rating": row.elo_rating,
                "games_played": row.games_played,
                "games_won": row.games_won,
                "is_bot": jest_botem
            })
            
        return JSONResponse(content=lista_rankingu)
        
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY podczas pobierania rankingu (nowa logika): {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nie udało się pobrać listy rankingu."
        )

@app.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Logika bez zmian
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tej nazwie już istnieje."
        )
    if len(user_data.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hasło musi mieć co najmniej 4 znaki."
        )
    hashed_pass = hash_password(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pass)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return Token(access_token=new_user.username, token_type="bearer", username=new_user.username)

@app.post("/login", response_model=Token)
async def login_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Logika bez zmian, ale sprawdzanie aktywnej gry musi teraz czytać z Redis
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło."
        )

    # --- Sprawdź aktywne gry w Redis ---
    active_game_id_found = None
    try:
        # Przeskanuj klucze lobby w Redis
        async for key in redis_client.scan_iter(lobby_key("*")):
            lobby_data = await get_lobby_data(key.decode('utf-8').split(":")[-1])
            if not lobby_data: continue
            
            if lobby_data.get("status_partii") == "W_TRAKCIE":
                slots = lobby_data.get("slots", [])
                slot_gracza = next((s for s in slots if s.get("nazwa") == user.username and s.get("typ") == "rozlaczony"), None)
                if slot_gracza:
                    active_game_id_found = lobby_data.get("id_gry")
                    break
    except Exception as e:
         print(f"Ostrzeżenie: Błąd Redis podczas skanowania gier dla logowania {user.username}: {e}")

    user_settings = None
    if user.settings:
        try:
            user_settings = json.loads(user.settings)
        except json.JSONDecodeError:
            user_settings = None

    return Token(
        access_token=user.username,
        token_type="bearer",
        username=user.username,
        active_game_id=active_game_id_found,
        settings=user_settings
    )

@app.get("/check_active_game/{username}")
async def check_active_game(username: str):
    # Logika zaktualizowana dla Redis
    active_game_id_found = None
    try:
        async for key in redis_client.scan_iter(lobby_key("*")):
            id_gry = key.decode('utf-8').split(":")[-1]
            lobby_data = await get_lobby_data(id_gry)
            if not lobby_data: continue
            
            if lobby_data.get("status_partii") == "W_TRAKCIE":
                slots = lobby_data.get("slots", [])
                slot_gracza = next((s for s in slots if s.get("nazwa") == username and s.get("typ") in ["rozlaczony", "czlowiek"]), None)
                if slot_gracza:
                    active_game_id_found = id_gry
                    break
    except Exception as e:
         print(f"Ostrzeżenie: Błąd Redis podczas /check_active_game dla {username}: {e}")
         
    return {"active_game_id": active_game_id_found}

@app.post("/save_settings/{username}")
async def save_user_settings(username: str, settings_data: UserSettings, db: AsyncSession = Depends(get_db)):
    # Logika bez zmian
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie znaleziony."
        )
    try:
        settings_json = json.dumps(settings_data.dict())
        user.settings = settings_json
        await db.commit()
        return {"message": "Ustawienia zapisane pomyślnie."}
    except Exception as e:
            await db.rollback()
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Nie udało się zapisać ustawień: {type(e).__name__}"
            )

# ==========================================================================
# SEKCJA 11: ENDPOINTY LOBBY I TWORZENIA GRY (ZREFRAKTORYZOWANE)
# ==========================================================================

@app.get("/gra/lista_lobby")
async def pobierz_liste_lobby(db: AsyncSession = Depends(get_db)):
    """Pobiera listę gier online (lobby lub w trakcie) z Redis."""
    lista_lobby = []
    try:
        # Skanuj klucze lobby w Redis
        async for key in redis_client.scan_iter(lobby_key("*")):
            id_gry = key.decode('utf-8').split(":")[-1]
            partia = await get_lobby_data(id_gry)
            if not partia:
                continue

            opcje = partia.get("opcje", {})
            status = partia.get("status_partii")

            if (status in ["LOBBY", "W_TRAKCIE"] and
                partia.get("tryb_lobby") == "online" and
                opcje.get("publiczna", False)): # Dodano sprawdzanie 'publiczna'

                slots = partia.get("slots", [])
                aktualni_gracze = sum(1 for s in slots if s.get("typ") != "pusty")
                max_gracze = partia.get("max_graczy", 4)
                
                srednie_elo = None
                czy_rankingowa = opcje.get("rankingowa", False)
                game_type_id = partia.get("game_type_id")
                
                if czy_rankingowa and game_type_id:
                    nazwy_graczy = [s.get("nazwa") for s in slots if s.get("nazwa")]
                    if nazwy_graczy:
                        try:
                            # Pobierz Elo z nowej tabeli
                            query = (
                                select(PlayerGameStats.elo_rating)
                                .join(User, PlayerGameStats.user_id == User.id)
                                .where(
                                    User.username.in_(nazwy_graczy),
                                    PlayerGameStats.game_type_id == game_type_id
                                )
                            )
                            result = (await db.execute(query)).scalars().all()
                            if result:
                                srednie_elo = sum(result) / len(result)
                        except Exception as db_err:
                            print(f"Błąd DB (lista_lobby) dla {id_gry}: {db_err}")
                
                lobby_info = {
                    "id_gry": id_gry,
                    "host": partia.get("host", "Brak hosta"),
                    "tryb_gry": opcje.get("tryb_gry", "4p"),
                    "ma_haslo": bool(opcje.get("haslo")),
                    "aktualni_gracze": aktualni_gracze,
                    "max_gracze": max_gracze,
                    "status": status,
                    "gracze": [s.get("nazwa") for s in slots if s.get("nazwa")],
                    "rankingowa": czy_rankingowa,
                    "srednie_elo": srednie_elo
                }
                lista_lobby.append(lobby_info)
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY podczas pobierania listy lobby z Redis: {e}")
        traceback.print_exc()

    return {"lobby_list": lista_lobby}

@app.post("/gra/stworz")
async def stworz_gre(request: CreateGameRequest, db: AsyncSession = Depends(get_db)):
    """
    ZREFRAKTORYZOWANE: Tworzy tylko dane LOBBY i zapisuje je w Redis.
    Nie tworzy silnika gry.
    """
    id_gry = generuj_krotki_id()
    nazwa_gracza = request.nazwa_gracza
    
    # --- Pobierz GameType ID z bazy danych ---
    # TODO: 'request.tryb_gry' powinien być zastąpiony przez 'request.game_type_id'
    # Na razie hardkodujemy mapowanie
    game_type_name = '66 (4p)' if request.tryb_gry == '4p' else '66 (3p)'
    game_type_result = await db.execute(select(GameType.id).where(GameType.name == game_type_name))
    game_type_id = game_type_result.scalar_one_or_none()
    
    if not game_type_id:
        # TODO: Stwórz GameType, jeśli nie istnieje?
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Typ gry '{game_type_name}' nie został znaleziony w bazie danych."
        )

    # --- Stwórz słownik lobby (`partia`) ---
    partia = {
        "id_gry": id_gry,
        "czas_stworzenia": time.time(),
        "status_partii": "LOBBY",
        "host": nazwa_gracza,
        "tryb_lobby": request.tryb_lobby,
        "max_graczy": 4 if request.tryb_gry == '4p' else 3,
        "game_type_id": game_type_id, # <-- WAŻNE: Zapisujemy ID typu gry
        "numer_rozdania": 1,
        "historia_partii": [],
        "kicked_players": [],
        "gracze_gotowi": [],
        "opcje": {
            "tryb_gry": request.tryb_gry,
            "publiczna": request.publiczna,
            "haslo": request.haslo if request.haslo else None,
            "rankingowa": request.czy_rankingowa
        },
        "timery": {},
        "numer_ruchu_timer": 0,
        "tura_start_czas": None,
        "wynik_elo": None,
        "elo_obliczone": False,
    }

    if request.tryb_gry == '4p':
        nazwy = random.sample(NAZWY_DRUZYN, 2)
        nazwy_mapa = {"My": nazwy[0], "Oni": nazwy[1]}
        partia.update({
            "nazwy_druzyn": nazwy_mapa,
            "punkty_meczu": {nazwy_mapa["My"]: 0, nazwy_mapa["Oni"]: 0},
            "slots": [
                {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
                {"slot_id": 1, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
                {"slot_id": 2, "nazwa": None, "typ": "pusty", "druzyna": "My"},
                {"slot_id": 3, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
            ]
        })
    else: # 3p
         partia.update({
            "punkty_meczu": {},
            "slots": [
                {"slot_id": 0, "nazwa": None, "typ": "pusty"},
                {"slot_id": 1, "nazwa": None, "typ": "pusty"},
                {"slot_id": 2, "nazwa": None, "typ": "pusty"},
            ]
        })

    # --- Umieść hosta w pierwszym slocie ---
    bot_data = next((bot for bot in AKTYWNE_BOTY_ELO_WORLD if bot[0] == nazwa_gracza), None)
    if bot_data:
        bot_algorytm = bot_data[1]
        partia["slots"][0].update({
            "nazwa": nazwa_gracza, 
            "typ": "bot",
            "bot_algorithm": bot_algorytm
        })
    else:
        partia["slots"][0].update({"nazwa": nazwa_gracza, "typ": "czlowiek"})

    # --- Zapisz lobby w Redis ---
    await save_lobby_data(id_gry, partia)
    
    # --- Zainicjuj stan przejściowy (lock) ---

    return {"id_gry": id_gry}


@app.get("/gra/sprawdz/{id_gry}")
async def sprawdz_gre(id_gry: str):
    """Sprawdza, czy gra (lobby) istnieje w Redis."""
    exists = await redis_client.exists(lobby_key(id_gry))
    return {"exists": bool(exists)}

# ==========================================================================
# SEKCJA 12: GŁÓWNA LOGIKA GRY (ZREFRAKTORYZOWANA)
# ==========================================================================

# --- USUNIĘTO `pobierz_stan_gry` ---
# Zostało zastąpione przez `manager.build_state_for_player`

async def przetworz_akcje_gracza(data: dict, id_gry: str):
    """
    NOWA GŁÓWNA FUNKCJA LOGIKI.
    Pobiera stan z Redis, modyfikuje go, i zapisuje z powrotem.
    """
    lobby_data = await get_lobby_data(id_gry)
    if not lobby_data:
        print(f"BŁĄD (przetworz_akcje_gracza): Nie znaleziono lobby {id_gry}")
        return
        
    engine = await get_game_engine(id_gry) # Może być None, jeśli gra w lobby
    
    gracz_akcji_nazwa = data.get("gracz")
    stan_zmieniony = False # Flaga, czy trzeba zapisać stan

    try:
        # --- Obsługa Akcji w Lobby ---
        if lobby_data["status_partii"] == "LOBBY":
            akcja = data.get("akcja_lobby")
            if not akcja: return

            if akcja == "dolacz_do_slota":
                slot_id = data.get("slot_id")
                slot_gracza = next((s for s in lobby_data["slots"] if s["nazwa"] == gracz_akcji_nazwa), None)
                slot_docelowy = next((s for s in lobby_data["slots"] if s["slot_id"] == slot_id), None)
                if slot_gracza and slot_docelowy and slot_docelowy["typ"] == "pusty":
                    slot_docelowy.update({"nazwa": slot_gracza["nazwa"], "typ": slot_gracza["typ"]})
                    slot_gracza.update({"nazwa": None, "typ": "pusty"})
                    stan_zmieniony = True

            elif akcja == "zmien_slot" and lobby_data["host"] == gracz_akcji_nazwa:
                slot_id = data.get("slot_id")
                nowy_typ = data.get("nowy_typ")
                wybrany_algorytm = data.get("bot_algorithm")
                slot = next((s for s in lobby_data["slots"] if s["slot_id"] == slot_id), None)

                if slot and slot["nazwa"] != lobby_data["host"]:
                    if (nowy_typ == "bot" and lobby_data.get("opcje", {}).get("rankingowa", False)):
                         return # Nie dodawaj botów do rank.
                    
                    if nowy_typ == "pusty":
                        if slot["typ"] == "czlowiek" and slot["nazwa"]:
                            lobby_data.setdefault("kicked_players", []).append(slot["nazwa"])
                        slot.update({"nazwa": None, "typ": "pusty", "bot_algorithm": None})
                        stan_zmieniony = True
                    elif nowy_typ == "bot":
                        algorytm_do_zapisu = wybrany_algorytm if wybrany_algorytm in bot_instances else default_bot_name
                        slot.update({
                            "nazwa": f"Bot_{slot_id}",
                            "typ": "bot",
                            "bot_algorithm": algorytm_do_zapisu
                        })
                        stan_zmieniony = True
                        
            elif akcja == "start_gry" and lobby_data["host"] == gracz_akcji_nazwa:
                if not all(s["typ"] != "pusty" for s in lobby_data["slots"]):
                    return # Puste sloty

                player_ids = [s["nazwa"] for s in lobby_data["slots"]]
                
                # --- INICJALIZACJA SILNIKA GRY ---
                try:
                    # Przekazujemy nazwy drużyn z lobby do silnika
                    settings = {
                        'tryb': lobby_data['opcje']['tryb_gry'],
                        'rozdajacy_idx': 0,
                        'nazwy_druzyn': lobby_data.get('nazwy_druzyn') # Przekaż nazwy
                    }
                    
                    engine = SixtySixEngine(player_ids, settings)
                    
                    # Zapisz nowy silnik w Redis
                    await save_game_engine(id_gry, engine)
                    
                    # Zaktualizuj stan lobby
                    lobby_data["status_partii"] = "W_TRAKCIE"
                    lobby_data["numer_rozdania"] = 1
                    lobby_data["historia_partii"] = []
                    
                    # Zresetuj punkty (jeśli to restart)
                    if lobby_data['opcje']['tryb_gry'] == '4p':
                        nazwy = lobby_data["nazwy_druzyn"]
                        lobby_data["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
                    else:
                        lobby_data["punkty_meczu"] = {pid: 0 for pid in player_ids}
                    
                    # Inicjalizacja Timerów
                    if lobby_data.get("opcje", {}).get("rankingowa", False):
                        czas_startowy = 300 # 5 minut
                        lobby_data["timery"] = {pid: czas_startowy for pid in player_ids}
                    
                    stan_zmieniony = True
                    print(f"[{id_gry}] Gra rozpoczęta. Silnik SixtySixEngine utworzony i zapisany w Redis.")

                    # Uruchamiamy pętlę botów PO tym, jak gra została 
                    # pomyślnie uruchomiona i zapisana.
                    asyncio.create_task(uruchom_petle_botow(id_gry))

                except Exception as init_err:
                    print(f"BŁĄD KRYTYCZNY (start_gry): Nie można zainicjalizować silnika gry: {init_err}")
                    traceback.print_exc()
                    return # Nie zmieniaj stanu

        # --- Obsługa Akcji w Trakcie Gry ---
        elif lobby_data["status_partii"] == "W_TRAKCIE":
            if not engine:
                print(f"BŁĄD (przetworz_akcje_gracza): Gra {id_gry} jest W_TRAKCIE, ale nie ma silnika!")
                return
            
            akcja = data.get('akcja')
            if not akcja: return
            typ_akcji = akcja.get('typ')
            
            # --- Logika Timerów (Odejmowanie czasu) ---
            if (lobby_data.get("opcje", {}).get("rankingowa", False) and
                typ_akcji not in ['nastepne_rozdanie', 'finalizuj_lewe']):
                
                timer_info = lobby_data.get("timer_info")
                if timer_info and timer_info.get("player_id") == gracz_akcji_nazwa:
                    # Oblicz zużyty czas
                    czas_zuzyty = time.time() - timer_info.get("started_at", time.time())
                    
                    # Zaktualizuj pozostały czas
                    if gracz_akcji_nazwa in lobby_data.get("timery", {}):
                        lobby_data["timery"][gracz_akcji_nazwa] -= czas_zuzyty
                        if lobby_data["timery"][gracz_akcji_nazwa] < 0:
                            lobby_data["timery"][gracz_akcji_nazwa] = 0
                    
                    lobby_data["timer_info"] = None
                    stan_zmieniony = True
                        # Anuluj stary timer (lokalnie)


            # --- Wykonaj Akcję w Silniku Gry ---
            if typ_akcji == 'nastepne_rozdanie':
                if gracz_akcji_nazwa not in lobby_data.get("gracze_gotowi", []):
                    lobby_data.setdefault("gracze_gotowi", []).append(gracz_akcji_nazwa)
                    stan_zmieniony = True

                liczba_ludzi = sum(1 for s in lobby_data["slots"] if s["typ"] == "czlowiek")
                
                wszyscy_gotowi = False
                if liczba_ludzi > 0:
                    gotowi_ludzie = [
                        nazwa for nazwa in lobby_data.get("gracze_gotowi", []) 
                        if any(s["nazwa"] == nazwa and s["typ"] == "czlowiek" for s in lobby_data["slots"])
                    ]
                    if len(gotowi_ludzie) >= liczba_ludzi:
                        wszyscy_gotowi = True
                else: # 0 ludzi
                    if len(lobby_data.get("gracze_gotowi", [])) >= lobby_data["max_graczy"]:
                        wszyscy_gotowi = True

                if wszyscy_gotowi:
                    lobby_data["gracze_gotowi"] = []
                    
                    # === POCZĄTEK POPRAWKI (Wersja 7) ===
                    # Sprawdź stan meczu na podstawie już zapisanych punktów.
                    # NIE wywołuj ponownie _zaktualizuj_stan_po_rozdaniu.
                    mecz_zakonczony = lobby_data["status_partii"] == "ZAKONCZONA"
                    # === KONIEC POPRAWKI ===
                    
                    if mecz_zakonczony:
                        # Nie rób nic więcej, status już jest ZAKONCZONA
                        stan_zmieniony = True
                    else:
                        # Mecz trwa, dodaj czas (jeśli rankingowa)
                        if lobby_data.get("opcje", {}).get("rankingowa", False):
                            for pid in lobby_data.get("timery", {}):
                                lobby_data["timery"][pid] += 15.0

                        # Stwórz NOWY silnik dla następnego rozdania
                        lobby_data["numer_rozdania"] += 1
                        player_ids = [s["nazwa"] for s in lobby_data["slots"]]
                        nowy_rozdajacy_idx = (lobby_data.get("numer_rozdania", 1) - 1) % lobby_data.get("max_graczy", 4)
                        
                        # Przekazujemy nazwy drużyn z lobby do silnika
                        settings = {
                            'tryb': lobby_data['opcje']['tryb_gry'],
                            'rozdajacy_idx': nowy_rozdajacy_idx,
                            'nazwy_druzyn': lobby_data.get('nazwy_druzyn') # Przekaż nazwy
                        }
                        
                        engine = SixtySixEngine(player_ids, settings)
                        # Zapisz NOWY silnik
                        await save_game_engine(id_gry, engine)
                        stan_zmieniony = True
            
            else: # Inna akcja (zagraj kartę, licytuj, itp.)
                try:
                    # Przekaż akcję bezpośrednio do silnika
                    engine.perform_action(gracz_akcji_nazwa, akcja)
                    
                    # Sprawdź, czy ta akcja zakończyła rozdanie
                    if engine.is_terminal():
                        # === POCZĄTEK POPRAWKI (Wersja 7) ===
                        # Sprawdź, czy punkty nie zostały już przyznane dla tego stanu
                        # (To zapobiega podwójnemu przyznaniu, jeśli jakimś cudem 
                        #  funkcja zostanie wywołana wielokrotnie dla tego samego stanu)
                        if not lobby_data.get("punkty_przyznane_dla_rozdania", 0) == lobby_data.get("numer_rozdania", 0):
                            await _zaktualizuj_stan_po_rozdaniu(id_gry, lobby_data, engine)
                            lobby_data["punkty_przyznane_dla_rozdania"] = lobby_data.get("numer_rozdania", 0)
                            stan_zmieniony = True 
                        # === KONIEC POPRAWKI ===
                        
                    # Zapisz ZMIENIONY silnik (i lobby) z powrotem w Redis
                    await save_game_engine(id_gry, engine)
                         
                except Exception as e:
                    print(f"BŁĄD (perform_action) dla {gracz_akcji_nazwa} w {id_gry}: {e}")
                    traceback.print_exc()
                    return # Nie wysyłaj aktualizacji, jeśli akcja się nie powiodła
        
        # --- Obsługa Akcji po Zakończeniu Gry ---
        elif lobby_data["status_partii"] == "ZAKONCZONA":
            akcja = data.get('akcja')
            if akcja and akcja.get('typ') == 'powrot_do_lobby' and lobby_data["host"] == gracz_akcji_nazwa:
                # Zresetuj stan lobby do ponownej gry
                lobby_data["status_partii"] = "LOBBY"
                lobby_data["gracze_gotowi"] = []
                lobby_data["wynik_elo"] = None
                lobby_data["elo_obliczone"] = False
                lobby_data["punkty_przyznane_dla_rozdania"] = 0 # Zresetuj flagę
                # Usuń stary silnik gry
                await redis_client.delete(engine_key(id_gry))
                stan_zmieniony = True

        # --- Zapisz zmiany i powiadom klientów ---
        if stan_zmieniony:
            await save_lobby_data(id_gry, lobby_data)
        
        # Zawsze uruchom timer dla następnego gracza (jeśli gra trwa)
        if lobby_data["status_partii"] == "W_TRAKCIE":
            await uruchom_timer_dla_tury(id_gry)
            
        # Zawsze powiadamiaj klientów o zmianie
        await manager.notify_state_update(id_gry)

        # Po KAŻDEJ akcji (człowieka lub bota), uruchom pętlę botów.
        # Pętla sama sprawdzi, czy jest zablokowana lub czyja jest tura.
        if lobby_data["status_partii"] == "W_TRAKCIE":
            asyncio.create_task(uruchom_petle_botow(id_gry))

    except Exception as e:
        print(f"BŁĄD KRYTYCZNY (przetworz_akcje_gracza) dla {id_gry}: {e}")
        traceback.print_exc()

# ==========================================================================
# SEKCJA 13: PĘTLA BOTA (ZREFRAKTORYZOWANA)
# ==========================================================================

async def uruchom_petle_botow(id_gry: str):
    """ZREFAKTORYZOWANA: Używa RedisLock"""
    lock_key = f"bot_loop_lock:{id_gry}"
    lock = RedisLock(redis_client, lock_key, timeout=30)
    
    if not await lock.acquire(blocking=False):
        return  # Inny proces już obsługuje
    
    try:
        while True: 
            lobby_data = await get_lobby_data(id_gry)
            if not lobby_data or lobby_data["status_partii"] != "W_TRAKCIE":
                break
            
            engine = await get_game_engine(id_gry)
            if not engine:
                print(f"BŁĄD (bot): Brak silnika {id_gry}")
                break
            
            if engine.is_terminal():
                break
            
            player_id = engine.get_current_player()
            if not player_id:
                break
            
            slot_gracza = next((s for s in lobby_data["slots"] if s["nazwa"] == player_id), None)
            if not slot_gracza or slot_gracza["typ"] != "bot":
                break
            
            # TURA BOTA
            print(f"[{id_gry}] Tura bota: {player_id}")
            
            bot_algorithm_name = slot_gracza.get("bot_algorithm", default_bot_name)
            bot_instance = bot_instances.get(bot_algorithm_name, bot_instances[default_bot_name])

            try:
                cloned_engine = engine.clone() 
                akcja_bota = await asyncio.to_thread(
                    bot_instance.znajdz_najlepszy_ruch,
                    cloned_engine,
                    player_id
                )
                
                if not akcja_bota or 'typ' not in akcja_bota:
                    break
                
                engine.perform_action(player_id, akcja_bota)
                await save_game_engine(id_gry, engine)
                
                if engine.is_terminal():
                    if not lobby_data.get("punkty_przyznane_dla_rozdania") == lobby_data.get("numer_rozdania"):
                        await _zaktualizuj_stan_po_rozdaniu(id_gry, lobby_data, engine)
                        lobby_data["punkty_przyznane_dla_rozdania"] = lobby_data.get("numer_rozdania")
                        await save_lobby_data(id_gry, lobby_data)

            except Exception as e:
                print(f"BŁĄD bota: {e}")
                traceback.print_exc()
                break

            await manager.notify_state_update(id_gry)
            await uruchom_timer_dla_tury(id_gry)
            await asyncio.sleep(0.5)
    
    finally:
        await lock.release()

# ==========================================================================
# SEKCJA 14: MENEDŻER BOTÓW "ELO WORLD" (ZREFRAKTORYZOWANY DLA REDIS)
# ==========================================================================

AKTYWNE_BOTY_ELO_WORLD: list[tuple[str, str]] = []
MAX_GAMES_HOSTED_BY_BOTS = 5
MAX_TOTAL_GAMES_ON_SERVER = 20
ELO_WORLD_TICK_RATE = 15.0

async def zaladuj_aktywne_boty_z_bazy():
    # Logika bez zmian
    global AKTYWNE_BOTY_ELO_WORLD
    print("[Elo World] Ładowanie kont botów z bazy danych...")
    AKTYWNE_BOTY_ELO_WORLD.clear()
    try:
        async with async_sessionmaker() as session:
            query = select(User.username, User.settings).where(User.settings.like('%"jest_botem": true%'))
            result = await session.execute(query)
            bot_users = result.all()
            for username, settings_json in bot_users:
                try:
                    settings = json.loads(settings_json)
                    algorytm = settings.get("algorytm")
                    if algorytm and algorytm in bot_instances:
                        AKTYWNE_BOTY_ELO_WORLD.append((username, algorytm))
                except (json.JSONDecodeError, TypeError):
                    pass
        print(f"[Elo World] Załadowano {len(AKTYWNE_BOTY_ELO_WORLD)} aktywnych botów.")
        if not AKTYWNE_BOTY_ELO_WORLD:
            print("[Elo World] Uruchom skrypt 'create_bots.py'.")
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY (ładowanie botów): {e}")

async def elo_world_manager():
    """Główna pętla Menedżera Botów, zrefaktoryzowana dla Redis."""
    await asyncio.sleep(5.0) 
    await zaladuj_aktywne_boty_z_bazy()
    print("[Elo World] Menedżer botów (Redis) uruchomiony.")
    
    while True:
        try:
            await asyncio.sleep(ELO_WORLD_TICK_RATE)
            
            if not AKTYWNE_BOTY_ELO_WORLD or not redis_client:
                continue

            gry_w_redis = []
            boty_w_grze = set()
            boty_hostujace_lobby = set()
            boty_w_podsumowaniu = {} # {bot_name: id_gry}

            wszystkie_aktywne_boty = {bot[0] for bot in AKTYWNE_BOTY_ELO_WORLD}

            # Skanuj wszystkie aktywne gry w Redis
            async for key in redis_client.scan_iter(lobby_key("*")):
                id_gry = key.decode('utf-8').split(":")[-1]
                partia = await get_lobby_data(id_gry)
                if not partia:
                    continue
                
                gry_w_redis.append(partia) # Dodaj do listy do przetworzenia
                status_gry = partia.get("status_partii")

                # --- 1. Garbage Collector dla starych gier ---
                CZAS_ZYCIA_ZAKONCZONEJ_GRY_S = 60
                if status_gry == "ZAKONCZONA":
                    if "czas_zakonczenia_gry" not in partia:
                        partia["czas_zakonczenia_gry"] = time.time()
                        await save_lobby_data(id_gry, partia) # Zapisz timestamp
                    else:
                        if (time.time() - partia["czas_zakonczenia_gry"]) > CZAS_ZYCIA_ZAKONCZONEJ_GRY_S:
                            print(f"[Garbage Collector] Usuwam starą grę {id_gry} z Redis.")
                            await delete_game_state(id_gry) # Usuń lobby i silnik
                            continue # Pomiń resztę pętli dla tej gry

                # --- 2. Sprawdź stan botów w aktywnych grach ---
                if status_gry == "LOBBY" or status_gry == "W_TRAKCIE":
                    if status_gry == "LOBBY" and partia["host"] in wszystkie_aktywne_boty:
                        boty_hostujace_lobby.add(partia["host"])

                    for slot in partia.get("slots", []):
                        bot_name = slot.get("nazwa")
                        if bot_name in wszystkie_aktywne_boty: 
                            boty_w_grze.add(bot_name)
                             
                # --- 3. Sprawdź boty czekające na 'nastepne_rozdanie' ---
                if status_gry == "W_TRAKCIE":
                    engine = await get_game_engine(id_gry)
                    if engine and engine.is_terminal():
                        gotowi = partia.get("gracze_gotowi", [])
                        for slot in partia.get("slots", []):
                            if slot.get("nazwa") in wszystkie_aktywne_boty and slot.get("nazwa") not in gotowi:
                                boty_w_podsumowaniu[slot["nazwa"]] = id_gry

            # --- AKCJE MENEDŻERA ---
            
            # 1. Obsłuż boty czekające na następne rozdanie
            for bot_name, id_gry in boty_w_podsumowaniu.items():
                if await redis_client.exists(lobby_key(id_gry)):
                    print(f"[Elo World] Bot {bot_name} klika 'Następne rozdanie' w {id_gry}")
                    await asyncio.sleep(random.uniform(1.0, 5.0))
                    dane_akcji = {"gracz": bot_name, "akcja": {"typ": "nastepne_rozdanie"}}
                    # Przetwórz akcję (co zapisze stan i wyśle update)
                    await przetworz_akcje_gracza(dane_akcji, id_gry) 

            # 2. Sprawdź, czy boty-hosty mogą rozpocząć gry
            for bot_host_name in boty_hostujace_lobby:
                partia = next((p for p in gry_w_redis if p.get("host") == bot_host_name and p.get("status_partii") == "LOBBY"), None)
                if partia and all(s["typ"] != "pusty" for s in partia["slots"]):
                        id_gry = partia['id_gry']
                        print(f"[Elo World] Bot-host {bot_host_name} uruchamia grę {id_gry}!")
                        dane_akcji = {"gracz": bot_host_name, "akcja_lobby": "start_gry"}
                        await przetworz_akcje_gracza(dane_akcji, id_gry) # To uruchomi grę
            
            # 3. Przydziel "bezrobotne" boty
            boty_bezrobotne = [bot for bot in AKTYWNE_BOTY_ELO_WORLD if bot[0] not in boty_w_grze]
            liczba_lobby_botow = len(boty_hostujace_lobby)
            
            if not boty_bezrobotne:
                continue # Wszystkie boty zajęte

            random.shuffle(boty_bezrobotne)
            
            # --- 3A. Spróbuj dołączyć do istniejącego lobby ---
            lobby_do_dolaczenia = None
            slot_do_zajecia = None
            for partia in gry_w_redis:
                if (partia.get("status_partii") == "LOBBY" and 
                    partia.get("opcje", {}).get("rankingowa", False) and 
                    not partia.get("opcje", {}).get("haslo")):
                    
                    puste_sloty = [s for s in partia["slots"] if s["typ"] == "pusty"]
                    if puste_sloty:
                        lobby_do_dolaczenia = partia
                        slot_do_zajecia = puste_sloty[0]
                        break
            
            if lobby_do_dolaczenia and slot_do_zajecia:
                bot_name, bot_algorytm = boty_bezrobotne.pop(0)
                id_gry = lobby_do_dolaczenia['id_gry']
                print(f"[Elo World] Bot {bot_name} dołącza do lobby {id_gry} (slot {slot_do_zajecia['slot_id']})")
                slot_do_zajecia.update({
                    "nazwa": bot_name, "typ": "bot", "bot_algorithm": bot_algorytm
                })
                await save_lobby_data(id_gry, lobby_do_dolaczenia)
                await manager.notify_state_update(id_gry)

            # --- 3B. Spróbuj stworzyć nowe lobby ---
            elif (liczba_lobby_botow < MAX_GAMES_HOSTED_BY_BOTS and 
                  len(gry_w_redis) < MAX_TOTAL_GAMES_ON_SERVER and
                  boty_bezrobotne):
                
                bot_name, bot_algorytm = boty_bezrobotne.pop(0)
                print(f"[Elo World] Bot {bot_name} tworzy nowe lobby rankingowe...")
                try:
                    tryb_gry_bota = '3p' if random.random() < 0.33 else '4p'
                    request_bota = CreateGameRequest(
                        nazwa_gracza=bot_name,
                        tryb_gry=tryb_gry_bota,
                        tryb_lobby='online',
                        publiczna=True,
                        haslo=None,
                        czy_rankingowa=True
                    )
                    # Musimy `await` na funkcję `async`
                    await stworz_gre(request_bota, async_sessionmaker()) 
                except Exception as e:
                    print(f"BŁĄD KRYTYCZNY: Bot {bot_name} nie mógł stworzyć gry: {e}")
                    traceback.print_exc()

        except asyncio.CancelledError:
            print("[Elo World] Menedżer botów zatrzymany (CancelledError).")
            break
        except Exception as e:
            print(f"BŁĄD KRYTYCZNY w pętli Menedżera Botów (Redis): {e}")
            traceback.print_exc()
            await asyncio.sleep(60.0)

# ==========================================================================
# SEKCJA 15: GŁÓWNY ENDPOINT WEBSOCKET (ZREFRAKTORYZOWANY)
# ==========================================================================

@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str, haslo: Optional[str] = Query(None)):
    """
    ZREFRAKTORYZOWANY endpoint WebSocket.
    Korzysta z Redis i ConnectionManagera (Pub/Sub).
    """
    lobby_data = await get_lobby_data(id_gry)

    # --- 1. Sprawdzenie istnienia gry i hasła ---
    if not lobby_data:
        await websocket.accept()
        await websocket.close(code=1008, reason="Gra nie istnieje.")
        return

    opcje = lobby_data.get("opcje", {})
    haslo_lobby = opcje.get("haslo")
    if haslo_lobby and (haslo is None or haslo != haslo_lobby):
        await websocket.accept()
        await websocket.close(code=1008, reason="Nieprawidłowe hasło.")
        return

    # --- 2. Połączenie ---
    await manager.connect(websocket, id_gry, nazwa_gracza)
    print(f"INFO: {nazwa_gracza} połączył się z WebSocket dla gry {id_gry}.") # Dodatkowy log
    
    if nazwa_gracza in lobby_data.get("kicked_players", []):
        await websocket.close(code=1008, reason="Zostałeś wyrzucony z lobby.")
        manager.disconnect(websocket, id_gry)
        return

    stan_zmieniony = False # Flaga, czy trzeba zapisać stan lobby

    try:
        # --- 3. Obsługa Dołączania do Lobby / Powrotu do Gry ---
        if lobby_data["status_partii"] == "LOBBY":
            if not any(s['nazwa'] == nazwa_gracza for s in lobby_data['slots']):
                 slot = next((s for s in lobby_data["slots"] if s["typ"] == "pusty"), None)
                 if slot:
                     slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                     if not lobby_data["host"]: lobby_data["host"] = nazwa_gracza
                     stan_zmieniony = True
                 else:
                     await websocket.close(code=1008, reason="Lobby jest pełne.")
                     manager.disconnect(websocket, id_gry)
                     return

        elif lobby_data["status_partii"] == "W_TRAKCIE":
            slot_gracza = next((s for s in lobby_data["slots"] if s["nazwa"] == nazwa_gracza), None)
            if not slot_gracza:
                await websocket.close(code=1008, reason="Gra jest w toku.")
                manager.disconnect(websocket, id_gry)
                return
            
            if slot_gracza.get("typ") == "rozlaczony":
                print(f"[{id_gry}] Gracz {nazwa_gracza} dołączył ponownie.")
                slot_gracza["typ"] = "czlowiek"
                slot_gracza["disconnect_time"] = None
                stan_zmieniony = True
                
                # Anuluj timer zastępujący bota (z `transient_game_state`)
                # Timery zastępujące już nie używane (Redis system)
                
                # Uruchom timer tury, jeśli to była tura tego gracza
                await uruchom_timer_dla_tury(id_gry)

        # --- 4. Zapisz zmiany i wyślij aktualizację stanu ---
        if stan_zmieniony:
            await save_lobby_data(id_gry, lobby_data)
            await manager.notify_state_update(id_gry)
        else:
            # Jeśli stan się nie zmienił, wyślij stan tylko do tego klienta
            state_message = await manager.build_state_for_player(lobby_data, await get_game_engine(id_gry), nazwa_gracza)
            await websocket.send_text(json.dumps(state_message))

        # === POCZĄTEK POPRAWKI (Wersja 2) ===
        # Wywołanie pętli botów przy połączeniu WS (na wypadek, gdyby gra już trwała)
        if lobby_data["status_partii"] == "W_TRAKCIE":
             print(f"INFO (WS Connect): Gra {id_gry} jest w toku, uruchamiam pętlę botów (na wszelki wypadek).")
             asyncio.create_task(uruchom_petle_botow(id_gry))
        # === KONIEC POPRAWKI ===

        # --- 5. Główna Pętla Odbierania Wiadomości ---
        while True:
            data = await websocket.receive_json()
            
            # Sprawdź, czy gra nadal istnieje
            lobby_data = await get_lobby_data(id_gry)
            if not lobby_data:
                break # Gra usunięta, zakończ pętlę

            if data.get("typ_wiadomosci") == "czat":
                 if any(s['nazwa'] == data.get("gracz") for s in lobby_data['slots']):
                      await manager.publish_chat_message(id_gry, data) # Publikuj czat przez Redis
                 continue

            # --- Przekaż akcję do głównej funkcji logiki ---
            # Nie musimy tu sprawdzać tury, `przetworz_akcje_gracza`
            # i silnik gry zrobią to za nas.
            await przetworz_akcje_gracza(data, id_gry)
            # `przetworz_akcje_gracza` sam zapisze stan i wywoła 
            # `manager.notify_state_update(id_gry)`, co spowoduje
            # wysłanie nowego stanu do WSZYSTKICH klientów (w tym tego).

    # --- 6. Obsługa Rozłączenia Klienta ---
    except WebSocketDisconnect:
        print(f"[{id_gry}] Gracz {nazwa_gracza} rozłączył się.")
        manager.disconnect(websocket, id_gry)
        lobby_data = await get_lobby_data(id_gry)
        stan_zmieniony = False
        lobby_usunięte = False

        if lobby_data:
            if lobby_data["status_partii"] == "LOBBY":
                 slot_gracza = next((s for s in lobby_data["slots"] if s["nazwa"] == nazwa_gracza), None)
                 if slot_gracza:
                     slot_gracza.update({"typ": "pusty", "nazwa": None, "bot_algorithm": None})
                     if lobby_data["host"] == nazwa_gracza:
                         nowy_host = next((s["nazwa"] for s in lobby_data["slots"] if s["typ"] == "czlowiek"), None)
                         if not nowy_host:
                             nowy_host = next((s["nazwa"] for s in lobby_data["slots"] if s["typ"] == "bot"), None)
                         lobby_data["host"] = nowy_host
                     stan_zmieniony = True

                 if lobby_data.get("tryb_lobby") == "online":
                     czy_lobby_puste = all(s.get("typ") == "pusty" for s in lobby_data.get("slots", []))
                     if czy_lobby_puste:
                         print(f"Lobby {id_gry} jest puste. Usuwanie...")
                         await delete_game_state(id_gry) # Usuń z Redis
                         lobby_usunięte = True
                         stan_zmieniony = False 
                         
            elif lobby_data["status_partii"] == "W_TRAKCIE":
                slot_gracza = next((s for s in lobby_data["slots"] if s["nazwa"] == nazwa_gracza), None)

                # Wstrzymaj timer tury
                # Timer zarządzany przez Timer Worker

                if slot_gracza and slot_gracza.get('typ') == 'czlowiek':
                     slot_gracza['typ'] = 'rozlaczony'
                     slot_gracza['disconnect_time'] = time.time()
                     stan_zmieniony = True
                     
                         

        if stan_zmieniony and not lobby_usunięte:
             await save_lobby_data(id_gry, lobby_data)
             await manager.notify_state_update(id_gry)

    except Exception as e:
        print(f"!!! KRYTYCZNY BŁĄD WEBSOCKET DLA {id_gry} / {nazwa_gracza} !!!")
        traceback.print_exc()
        manager.disconnect(websocket, id_gry)

# Zrefaktoryzowany timer zastępujący (dla Redis)
async def replacement_timer_redis(id_gry: str, slot_id: int):
    lobby_data = await get_lobby_data(id_gry)
    if not lobby_data or lobby_data.get("opcje", {}).get("rankingowa", False):
        return

    print(f"[{id_gry}] Uruchomiono 60s timer zastępujący bota (Redis) dla slotu {slot_id}...")
    await asyncio.sleep(60)

    lobby_po_czasie = await get_lobby_data(id_gry)
    if not lobby_po_czasie or lobby_po_czasie["status_partii"] != "W_TRAKCIE":
        return

    slot = next((s for s in lobby_po_czasie["slots"] if s["slot_id"] == slot_id), None)

    if slot and slot.get("typ") == "rozlaczony":
        stara_nazwa = slot.get("nazwa", f"Gracz_{slot_id}")
        nowa_nazwa_bota = f"Bot_{stara_nazwa[:8]}"
        print(f"[{id_gry}] Gracz {stara_nazwa} (slot {slot_id}) zastąpiony botem {nowa_nazwa_bota}.")

        slot["nazwa"] = nowa_nazwa_bota
        slot["typ"] = "bot"
        slot["bot_algorithm"] = default_bot_name
        
        # Zapisz zmiany i powiadom
        await save_lobby_data(id_gry, lobby_po_czasie)
        await manager.notify_state_update(id_gry)
        asyncio.create_task(uruchom_petle_botow(id_gry))