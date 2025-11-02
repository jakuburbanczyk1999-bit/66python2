# main.py

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
from typing import Any, Optional, AsyncGenerator
from contextlib import asynccontextmanager

# --- Biblioteki FastAPI i powiązane ---
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# --- Biblioteki SQLAlchemy ---
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# --- Moduły lokalne ---
from database import init_db, async_sessionmaker, User # Obsługa bazy danych i modelu User
from auth_utils import hash_password, verify_password   # Funkcje do hashowania i weryfikacji haseł
import silnik_gry                                      # Główny silnik logiki gry 66
import boty                                            # Implementacja botów (MCTS)

# ==========================================================================
# SEKCJA 2: INICJALIZACJA APLIKACJI FASTAPI I ZASOBÓW GLOBALNYCH
# ==========================================================================

# --- Manager cyklu życia aplikacji (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Zarządza zdarzeniami startu i zamknięcia aplikacji FastAPI.
    Inicjalizuje bazę danych przy starcie.
    """
    print("Serwer startuje... Inicjalizacja bazy danych (lifespan).")
    await init_db()
    print("Baza danych jest gotowa (lifespan).")

    # Uruchom menedżera botów "Elo World" w tle
    asyncio.create_task(elo_world_manager())

    yield # Aplikacja działa

    print("Serwer się zamyka.")

# --- Główna instancja aplikacji FastAPI ---
# Używamy managera 'lifespan' do obsługi startu/zamknięcia.
app = FastAPI(lifespan=lifespan)

# --- Globalna instancja botów ---
# Tworzymy jedną instancję botów, która będzie używana przez wszystkie gry.
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



# --- Przechowywanie stanu gier ---
# Główny słownik przechowujący stan wszystkich aktywnych gier w pamięci serwera.
# Kluczem jest ID gry (string), wartością jest słownik reprezentujący stan gry (`partia`).
gry = {}

# --- Stałe ---
# Lista przykładowych nazw drużyn do losowania.
NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]

# ==========================================================================
# SEKCJA 3: MODELE DANYCH Pydantic (Walidacja Danych API)
# ==========================================================================
# Modele Pydantic definiują strukturę i typy danych oczekiwanych
# w żądaniach HTTP i odpowiedziach API. FastAPI używa ich do automatycznej
# walidacji i dokumentacji.

class LocalGameRequest(BaseModel):
    """Model żądania do stworzenia gry lokalnej (już nieużywany?)."""
    nazwa_gracza: str

class UserCreate(BaseModel):
    """Model danych do rejestracji i logowania użytkownika."""
    username: str
    password: str

class Token(BaseModel):
    """Model odpowiedzi po udanym logowaniu/rejestracji."""
    access_token: str # Obecnie używamy nazwy użytkownika jako tokena
    token_type: str   # Typ tokena (zawsze "bearer")
    username: str     # Nazwa zalogowanego użytkownika
    active_game_id: Optional[str] = None # ID gry, do której użytkownik może wrócić
    settings: Optional[dict] = None      # Ustawienia interfejsu użytkownika pobrane z bazy

class CreateGameRequest(BaseModel):
    """Model danych żądania do stworzenia nowej gry (endpoint /gra/stworz)."""
    nazwa_gracza: str     # Nazwa gracza tworzącego grę (hosta)
    tryb_gry: str         # Tryb gry ('4p' lub '3p')
    tryb_lobby: str       # Typ lobby ('online' lub 'lokalna')
    publiczna: bool       # Czy lobby ma być widoczne w przeglądarce
    haslo: Optional[str] = None # Hasło do lobby (jeśli prywatne)
    czy_rankingowa: bool = False # Czy gra ma być rankingowa (wpływa na Elo)

class UserSettings(BaseModel):
    """Model danych do zapisywania ustawień interfejsu użytkownika."""
    czatUkryty: bool
    historiaUkryta: bool
    partiaHistoriaUkryta: bool
    pasekEwaluacjiUkryty: bool

# ==========================================================================
# SEKCJA 4: ZARZĄDZANIE CZASOMIERZEM (Gra Rankingowa)
# ==========================================================================

async def czekaj_na_ruch(id_gry: str, nazwa_gracza: str, numer_ruchu: int):
    """
    Zadanie w tle (asyncio.Task) uruchamiane dla gracza w turze w grze rankingowej.
    Czeka na upłynięcie pozostałego czasu gracza. Jeśli czas minie *przed* wykonaniem ruchu
    (sprawdzane przez `numer_ruchu_timer`), kończy grę i rozlicza Elo.
    """
    partia = gry.get(id_gry)
    if not partia: return # Gra już nie istnieje

    pozostaly_czas = partia.get("timery", {}).get(nazwa_gracza, 0)

    try:
        # Czekaj asynchronicznie na upłynięcie czasu
        await asyncio.sleep(pozostaly_czas)

        # --- CZAS MINĄŁ ---
        # Sprawdź ponownie stan gry po upłynięciu czasu
        partia_po_czasie = gry.get(id_gry)
        # Sprawdź, czy gra nadal trwa i czy numer ruchu się zgadza
        # (jeśli gracz się ruszył, numer_ruchu_timer zostałby zmieniony)
        if (partia_po_czasie and partia_po_czasie["status_partii"] == "W_TRAKCIE" and
            partia_po_czasie.get("numer_ruchu_timer") == numer_ruchu):

            print(f"[{id_gry}] Gracz {nazwa_gracza} przegrał na czas!")

            # --- Logika Zakończenia Gry przez Timeout ---
            # 1. Ustal zwycięzców i przegranych, wymuś punkty dla obliczeń Elo
            if partia_po_czasie.get("max_graczy", 4) == 4: # Gra 4-osobowa
                gracz_obj = next((g for g in partia_po_czasie.get("gracze_engine", []) if g.nazwa == nazwa_gracza), None)
                if gracz_obj and gracz_obj.druzyna and gracz_obj.druzyna.przeciwnicy:
                    zwycieska_druzyna = gracz_obj.druzyna.przeciwnicy
                    zwycieska_druzyna.punkty_meczu = 66 # Wymuś 66 pkt dla zwycięzcy
                    print(f"[{id_gry}] Drużyna '{zwycieska_druzyna.nazwa}' wygrywa przez timeout.")
                else:
                    print(f"BŁĄD Timeout 4p: Nie można znaleźć gracza {nazwa_gracza} lub jego drużyny.")
                    return # Przerwij, aby uniknąć błędów
            elif partia_po_czasie.get("max_graczy", 3) == 3: # Gra 3-osobowa
                rozdanie = partia_po_czasie.get("aktualne_rozdanie")
                if rozdanie and rozdanie.grajacy:
                    if nazwa_gracza == rozdanie.grajacy.nazwa: # Grający przegrał na czas
                        for obronca in rozdanie.obroncy: obronca.punkty_meczu = 66 # Obrońcy wygrywają
                    else: # Obrońca przegrał na czas
                        rozdanie.grajacy.punkty_meczu = 66 # Grający wygrywa
                else:
                    print(f"BŁĄD Timeout 3p: Nie można znaleźć rozdania lub grającego.")
                    return

            # 2. Zmień status partii na zakończoną
            partia_po_czasie["status_partii"] = "ZAKONCZONA"

            # 3. Oblicz i zapisz zmiany Elo
            await zaktualizuj_elo_po_meczu(partia_po_czasie)

            # 4. Wyślij finalny stan gry (z podsumowaniem) do wszystkich klientów
            finalny_stan = pobierz_stan_gry(id_gry)
            await manager.broadcast(id_gry, finalny_stan)

            # 5. Wyślij informację o przegranej na czas na czat systemowy
            await manager.broadcast(id_gry, {"typ_wiadomosci": "czat", "gracz": "System", "tresc": f"Gracz {nazwa_gracza} przegrał na czas!"})

    except asyncio.CancelledError:
        # Ten wyjątek jest oczekiwany, gdy gracz wykona ruch na czas,
        # a zadanie `czekaj_na_ruch` zostanie anulowane przez `uruchom_timer_dla_tury`
        # lub `przetworz_akcje_gracza`.
        pass
    except Exception as e:
        # Złap inne potencjalne błędy w zadaniu timera
        print(f"BŁĄD w zadaniu czekaj_na_ruch dla {nazwa_gracza} w grze {id_gry}: {e}")
        traceback.print_exc()

async def uruchom_timer_dla_tury(id_gry: str):
    """
    Anuluje poprzednie zadanie timera (jeśli istniało) i uruchamia nowe
    dla gracza, którego jest aktualnie tura (tylko w grach rankingowych).
    Zapisuje również czas rozpoczęcia tury (`tura_start_czas`).
    """
    partia = gry.get(id_gry)
    # Sprawdź, czy gra istnieje, jest rankingowa i w trakcie
    if not partia or not partia.get("opcje", {}).get("rankingowa", False) or partia["status_partii"] != "W_TRAKCIE":
        return

    # Zapisz czas rozpoczęcia tury (używane do obliczenia zużytego czasu)
    partia["tura_start_czas"] = time.time()

    # Anuluj poprzednie zadanie timera, jeśli jeszcze działa
    if partia.get("timer_task") and not partia["timer_task"].done():
        partia["timer_task"].cancel()

    # Sprawdź, czy jest gracz w turze
    rozdanie = partia.get("aktualne_rozdanie")
    if not rozdanie or rozdanie.kolej_gracza_idx is None:
        partia["timer_task"] = None # Brak tury, nie uruchamiaj timera
        return

    # Sprawdź poprawność indeksu gracza
    if not (0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze)):
        print(f"BŁĄD: Nieprawidłowy indeks gracza {rozdanie.kolej_gracza_idx} w uruchom_timer_dla_tury.")
        partia["timer_task"] = None
        return

    gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx]
    if not gracz_w_turze:
        print(f"BŁĄD: Brak obiektu gracza dla indeksu {rozdanie.kolej_gracza_idx} w uruchom_timer_dla_tury.")
        partia["timer_task"] = None
        return


    # Inkrementuj licznik ruchów (służy do walidacji timera w `czekaj_na_ruch`)
    partia["numer_ruchu_timer"] = partia.get("numer_ruchu_timer", 0) + 1

    # Uruchom nowe zadanie `czekaj_na_ruch` w tle
    partia["timer_task"] = asyncio.create_task(
        czekaj_na_ruch(id_gry, gracz_w_turze.nazwa, partia["numer_ruchu_timer"])
    )

# ==========================================================================
# SEKCJA 5: LOGIKA RANKINGU ELO (Gra Rankingowa)
# ==========================================================================

def oblicz_nowe_elo(elo_a: float, elo_b: float, wynik_a: float) -> float:
    """
    Oblicza nową ocenę Elo dla gracza/drużyny A na podstawie standardowego wzoru.

    Args:
        elo_a: Aktualne Elo gracza/drużyny A.
        elo_b: Aktualne Elo gracza/drużyny B.
        wynik_a: Wynik meczu dla A (1.0 za wygraną, 0.5 za remis, 0.0 za przegraną).

    Returns:
        Nowa wartość Elo dla gracza/drużyny A, zaokrąglona do 2 miejsc po przecinku.
    """
    K = 32 # Współczynnik K (wpływa na szybkość zmian Elo)
    oczekiwany_wynik_a = 1 / (1 + 10**((elo_b - elo_a) / 400)) # Oczekiwany wynik A vs B
    nowe_elo_a = elo_a + K * (wynik_a - oczekiwany_wynik_a) # Wzór na nowe Elo
    return round(nowe_elo_a, 2)

async def zaktualizuj_elo_po_meczu(partia: dict):
    """
    Pobiera dane graczy z zakończonego meczu rankingowego, oblicza zmiany Elo
    i zapisuje je z powrotem w bazie danych. Zapisuje również podsumowanie zmian
    w stanie gry (`partia["wynik_elo"]`) do wysłania klientom.
    """
    # Wykonaj tylko dla gier rankingowych, które nie były jeszcze rozliczone
    if not partia.get("opcje", {}).get("rankingowa", False) or partia.get("elo_obliczone", False):
        return

    print(f"[{partia['id_gry']}] Obliczanie Elo dla zakończonego meczu rankingowego...")
    partia["elo_obliczone"] = True # Ustaw flagę, aby nie liczyć ponownie
    wynik_elo_dla_klienta = {} # Słownik na podsumowanie zmian dla klientów

    try:
        # Otwórz sesję bazy danych
        async with async_sessionmaker() as session:
            if partia.get("max_graczy", 4) == 4: # Logika dla gry 4-osobowej
                # Znajdź obiekty drużyn z silnika gry
                druzyna_my = next((d for d in partia["druzyny_engine"] if d.nazwa == partia["nazwy_druzyn"]["My"]), None)
                druzyna_oni = next((d for d in partia["druzyny_engine"] if d.nazwa == partia["nazwy_druzyn"]["Oni"]), None)
                if not druzyna_my or not druzyna_oni:
                     print(f"BŁĄD Elo 4p: Nie znaleziono obiektów drużyn w stanie gry {partia['id_gry']}.")
                     return

                gracze_my_nazwy = [g.nazwa for g in druzyna_my.gracze]
                gracze_oni_nazwy = [g.nazwa for g in druzyna_oni.gracze]

                # Pobierz obiekty User (z bazy danych) dla graczy obu drużyn
                query_my = select(User).where(User.username.in_(gracze_my_nazwy))
                query_oni = select(User).where(User.username.in_(gracze_oni_nazwy))
                users_my = (await session.execute(query_my)).scalars().all()
                users_oni = (await session.execute(query_oni)).scalars().all()

                # Sprawdź, czy znaleziono wszystkich graczy w bazie
                if len(users_my) != len(gracze_my_nazwy) or len(users_oni) != len(gracze_oni_nazwy):
                    print(f"BŁĄD Elo 4p [{partia['id_gry']}]: Nie wszyscy gracze zostali znalezieni w bazie danych.")
                    return

                # Oblicz średnie Elo dla każdej drużyny
                avg_elo_my = sum(u.elo_rating for u in users_my) / len(users_my)
                avg_elo_oni = sum(u.elo_rating for u in users_oni) / len(users_oni)

                # Ustal wynik meczu (1.0 dla wygranej 'My', 0.0 dla przegranej)
                wynik_my = 1.0 if druzyna_my.punkty_meczu >= 66 else 0.0

                # Oblicz nowe średnie Elo dla obu drużyn
                nowe_avg_elo_my = oblicz_nowe_elo(avg_elo_my, avg_elo_oni, wynik_my)
                nowe_avg_elo_oni = oblicz_nowe_elo(avg_elo_oni, avg_elo_my, 1.0 - wynik_my)

                # Oblicz zmianę Elo dla każdej drużyny
                zmiana_my = nowe_avg_elo_my - avg_elo_my
                zmiana_oni = nowe_avg_elo_oni - avg_elo_oni

                # Zastosuj zmianę Elo do każdego gracza i przygotuj podsumowanie
                for user in users_my:
                    stare_elo = user.elo_rating
                    user.elo_rating += zmiana_my
                    user.games_played += 1 # Inkrementuj liczbę gier
                    if wynik_my == 1.0: # Jeśli drużyna "My" wygrała
                        user.games_won += 1 # Inkrementuj wygrane
                    wynik_elo_dla_klienta[user.username] = f"{stare_elo:.0f} → {user.elo_rating:.0f} ({zmiana_my:+.0f})"
                
                for user in users_oni:
                    stare_elo = user.elo_rating
                    user.elo_rating += zmiana_oni
                    user.games_played += 1 # Inkrementuj liczbę gier
                    if wynik_my == 0.0: # Jeśli drużyna "Oni" wygrała
                        user.games_won += 1 # Inkrementuj wygrane
                    wynik_elo_dla_klienta[user.username] = f"{stare_elo:.0f} → {user.elo_rating:.0f} ({zmiana_oni:+.0f})"

            else: # Logika dla gry 3-osobowej
                print(f"[{partia['id_gry']}] Obliczanie Elo dla 3 graczy...")
                gracze_engine = partia.get("gracze_engine")
                if not gracze_engine or len(gracze_engine) != 3:
                    print(f"BŁĄD Elo 3p: Nieprawidłowa liczba graczy ({len(gracze_engine) if gracze_engine else 0}) w stanie gry.")
                    return

                # Pobierz obiekty User z bazy danych dla wszystkich 3 graczy
                nazwy_graczy = [g.nazwa for g in gracze_engine]
                query = select(User).where(User.username.in_(nazwy_graczy))
                users = (await session.execute(query)).scalars().all()

                if len(users) != 3:
                    print(f"BŁĄD Elo 3p [{partia['id_gry']}]: Nie wszyscy gracze ({len(users)}/{len(nazwy_graczy)}) zostali znalezieni w bazie danych.")
                    return

                # Stwórz mapowanie nazwa -> (user_obj, punkty_meczu) dla łatwiejszego dostępu
                gracze_data = {
                    g.nazwa: (next(u for u in users if u.username == g.nazwa), g.punkty_meczu)
                    for g in gracze_engine
                }

                zmiany_elo = {nazwa: 0.0 for nazwa in nazwy_graczy} # Słownik na sumaryczne zmiany Elo

                # --- Przeprowadź wirtualne pojedynki 1vs1 ---
                gracze_list = list(gracze_data.items()) # Lista krotek (nazwa, (user, punkty))

                for i in range(3):
                    for j in range(i + 1, 3):
                        nazwa_a, (user_a, punkty_a) = gracze_list[i]
                        nazwa_b, (user_b, punkty_b) = gracze_list[j]

                        # Ustal wynik pojedynku A vs B
                        wynik_a = 0.5 # Domyślnie remis
                        if punkty_a > punkty_b:
                            wynik_a = 1.0 # A wygrał
                        elif punkty_b > punkty_a:
                            wynik_a = 0.0 # A przegrał (B wygrał)

                        # Oblicz zmianę Elo dla A w tym pojedynku
                        zmiana_a = oblicz_nowe_elo(user_a.elo_rating, user_b.elo_rating, wynik_a) - user_a.elo_rating
                        # Oblicz zmianę Elo dla B w tym pojedynku (wynik B = 1.0 - wynik A)
                        zmiana_b = oblicz_nowe_elo(user_b.elo_rating, user_a.elo_rating, 1.0 - wynik_a) - user_b.elo_rating

                        # Dodaj zmiany do sumarycznych zmian dla obu graczy
                        zmiany_elo[nazwa_a] += zmiana_a
                        zmiany_elo[nazwa_b] += zmiana_b

                # --- Zastosuj sumaryczne zmiany Elo i przygotuj podsumowanie ---
                najwyzszy_wynik = max(punkty for _, punkty in gracze_data.values())
                
                for nazwa, (user, punkty_gracza) in gracze_data.items():
                    stare_elo = user.elo_rating
                    zmiana_finalna = zmiany_elo[nazwa] 

                    user.elo_rating += zmiana_finalna
                    user.games_played += 1 # Zawsze inkrementuj liczbę gier
                    
                    # Przyznaj wygraną graczowi(om) z najwyższym wynikiem
                    if punkty_gracza == najwyzszy_wynik and najwyzszy_wynik >= 66:
                        user.games_won += 1
                        
                    wynik_elo_dla_klienta[nazwa] = f"{stare_elo:.0f} → {user.elo_rating:.0f} ({zmiana_finalna:+.0f})"

            # Zapisz zmiany w bazie danych
            await session.commit()
            # Zapisz podsumowanie zmian Elo w stanie gry
            partia["wynik_elo"] = wynik_elo_dla_klienta
            print(f"[{partia['id_gry']}] Zaktualizowano Elo: {wynik_elo_dla_klienta}")

    except Exception as e:
        # Złap potencjalne błędy podczas operacji na bazie danych lub obliczeń
        print(f"BŁĄD KRYTYCZNY podczas aktualizacji Elo dla gry {partia.get('id_gry', 'N/A')}: {e}")
        traceback.print_exc()

# ==========================================================================
# SEKCJA 6: ZARZĄDZANIE POŁĄCZENIAMI WebSocket (ConnectionManager)
# ==========================================================================

class ConnectionManager:
    """Klasa pomocnicza do zarządzania aktywnymi połączeniami WebSocket dla każdej gry."""
    def __init__(self):
        # Słownik, gdzie kluczem jest ID gry, a wartością lista aktywnych obiektów WebSocket.
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        """Akceptuje nowe połączenie WebSocket i dodaje je do odpowiedniej gry."""
        await websocket.accept()
        # Jeśli to pierwsze połączenie dla tej gry, stwórz nową listę
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        # Dodaj połączenie do listy
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        """Usuwa połączenie WebSocket z listy dla danej gry."""
        if game_id in self.active_connections:
            # Usuń bezpiecznie, nawet jeśli połączenie już zostało usunięte
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            # Jeśli lista stała się pusta, można usunąć wpis gry (opcjonalnie)
            # if not self.active_connections[game_id]:
            #     del self.active_connections[game_id]

    async def broadcast(self, game_id: str, message: dict):
        """
        Wysyła wiadomość (słownik Python) do wszystkich podłączonych graczy w danej grze.
        Automatycznie serializuje słownik do JSON, obsługując typy Enum i Karta z silnika gry.
        """
        if game_id in self.active_connections:
            # Własna funkcja serializująca dla typów niestandardowych (Enum, Karta, etc.)
            def safe_serializer(o):
                if isinstance(o, (silnik_gry.Kolor, silnik_gry.Kontrakt, silnik_gry.FazaGry, silnik_gry.Ranga)):
                    return o.name # Zwróć nazwę Enum (string)
                if isinstance(o, silnik_gry.Karta):
                    return str(o) # Zwróć stringową reprezentację karty
                if isinstance(o, (silnik_gry.Gracz, silnik_gry.Druzyna)):
                    return o.nazwa # Zwróć nazwę gracza/drużyny
                # Awaryjnie dla innych nieznanych typów
                return f"<Nieserializowalny: {type(o).__name__}>"

            try:
                # Serializuj wiadomość do JSON
                message_json = json.dumps(message, default=safe_serializer)
                # Stwórz kopię listy połączeń (ważne, bo lista może się zmienić podczas wysyłania)
                connections_copy = self.active_connections[game_id][:]
                # Przygotuj listę zadań wysyłania (jedno dla każdego połączenia)
                tasks = [connection.send_text(message_json) for connection in connections_copy]
                # Wykonaj wszystkie zadania wysyłania asynchronicznie i równolegle
                if tasks:
                    await asyncio.gather(*tasks)
            except Exception as e:
                # Złap błędy serializacji lub wysyłania
                print(f"BŁĄD podczas serializacji lub broadcastu dla gry {game_id}: {e}")
                # Rozważ dodanie traceback.print_exc() dla dokładniejszego debugowania

# Globalna instancja ConnectionManagera
manager = ConnectionManager()

# ==========================================================================
# SEKCJA 7: FUNKCJE POMOCNICZE (Baza Danych, ID Gry, Reset, Konwersje)
# ==========================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Zależność (dependency) FastAPI do uzyskiwania sesji bazy danych.
    Automatycznie zarządza otwieraniem i zamykaniem sesji dla każdego żądania.
    """
    async with async_sessionmaker() as session:
        try:
            yield session # Udostępnij sesję endpointowi
        finally:
            await session.close() # Zamknij sesję po zakończeniu żądania

def generuj_krotki_id(dlugosc=6) -> str:
    """Generuje unikalny, krótki (domyślnie 6-znakowy) identyfikator gry (np. 'A1B2C3')."""
    chars = string.ascii_uppercase + string.digits # Znaki do użycia: A-Z, 0-9
    while True:
        # Wygeneruj losowy kod
        kod = ''.join(random.choices(chars, k=dlugosc))
        # Sprawdź, czy kod nie jest już używany w aktywnych grach
        if kod not in gry:
            return kod # Zwróć unikalny kod

def resetuj_gre_do_lobby(partia: dict):
    """Resetuje stan gry (`partia`) z powrotem do stanu początkowego lobby."""
    partia["status_partii"] = "LOBBY"
    # Wyczyść dane związane z rozgrywką
    partia["gracze_engine"] = []
    partia["druzyny_engine"] = []
    partia["aktualne_rozdanie"] = None
    partia["pelna_historia"] = [] # Czy to jest używane? Może do usunięcia?
    partia["numer_rozdania"] = 1
    partia["historia_partii"] = []
    partia["kicked_players"] = [] # Wyczyść listę wyrzuconych
    partia["gracze_gotowi"] = []
    partia['aktualna_ocena'] = None
    # Resetuj timery i stan Elo
    partia["timery"] = {}
    partia["timer_task"] = None # Anuluj zadanie timera (jeśli istnieje) - TODO: dodać anulowanie
    partia["wynik_elo"] = None
    partia["elo_obliczone"] = False
    partia["tura_start_czas"] = None

    # Zresetuj punkty meczu
    if partia.get("max_graczy", 4) == 4:
        nazwy = partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
        partia["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
    else: # 3 graczy
        # Zresetuj punkty dla graczy, którzy są aktualnie w slotach
        partia["punkty_meczu"] = {slot['nazwa']: 0 for slot in partia['slots'] if slot.get('nazwa')}

    print(f"Gra {partia.get('id_gry', 'N/A')} wraca do lobby.")

def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    """Konwertuje string reprezentujący kartę (np. "As Czerwien") na obiekt Karta."""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        # Mapowanie nazw stringowych na obiekty Enum
        mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
        mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
        # Znajdź odpowiednie Enumy
        ranga = mapowanie_rang[ranga_str]
        kolor = mapowanie_kolorow[kolor_str]
        # Stwórz i zwróć obiekt Karta
        return silnik_gry.Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        # Złap błędy parsowania lub nieznanych nazw
        print(f"BŁĄD: Nie można przekonwertować stringa '{nazwa_karty}' na kartę: {e}")
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e

def sprawdz_koniec_partii(partia: dict) -> bool:
    """
    Sprawdza, czy którakolwiek drużyna (4p) lub gracz (3p) osiągnął
    wymaganą liczbę punktów (domyślnie 66), aby zakończyć mecz.
    Jeśli tak, ustawia `status_partii` na "ZAKONCZONA".
    """
    max_graczy = partia.get("max_graczy", 4)
    gracze_engine = partia.get("gracze_engine") # Obiekty Gracz z silnika
    druzyny_engine = partia.get("druzyny_engine") # Obiekty Druzyna z silnika

    # --- Logika dla 4 graczy ---
    if max_graczy == 4 and druzyny_engine:
        for druzyna in druzyny_engine:
            if druzyna.punkty_meczu >= 66:
                partia["status_partii"] = "ZAKONCZONA"
                return True # Znaleziono zwycięzcę
    # --- Logika dla 3 graczy ---
    elif max_graczy == 3 and gracze_engine:
        # Znajdź graczy, którzy przekroczyli próg
        gracze_powyzej_progu = [g for g in gracze_engine if g.punkty_meczu >= 66]
        if not gracze_powyzej_progu:
            return False # Nikt nie przekroczył progu
        if len(gracze_powyzej_progu) == 1:
            # Tylko jeden gracz przekroczył próg - koniec gry
            partia["status_partii"] = "ZAKONCZONA"
            return True
        # Obsługa remisu w 3p (więcej niż 1 gracz >= 66)
        najwyzszy_wynik = max(g.punkty_meczu for g in gracze_powyzej_progu)
        # Znajdź graczy z najwyższym wynikiem
        gracze_z_najwyzszym_wynikiem = [g for g in gracze_powyzej_progu if g.punkty_meczu == najwyzszy_wynik]
        # Jeśli tylko jeden ma najwyższy wynik, kończy grę
        if len(gracze_z_najwyzszym_wynikiem) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True
        else: # Jeśli jest remis na najwyższym wyniku >= 66, gra również się kończy
            partia["status_partii"] = "ZAKONCZONA"
            print(f"INFO: Remis w grze 3p (ID: {partia.get('id_gry')}) - kilku graczy >= 66 z tym samym wynikiem.")
            return True

    # Jeśli żaden warunek końca nie został spełniony
    return False

# ==========================================================================
# SEKCJA 8: KONFIGURACJA PLIKÓW STATYCZNYCH I GŁÓWNYCH ENDPOINTÓW HTTP
# ==========================================================================

# Udostępnij folder 'static' (zawierający CSS, JS, obrazki, dźwięki) pod ścieżką URL '/static'
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    """Zwraca główną stronę startową (menu)."""
    return FileResponse('static/start.html')

@app.get("/gra.html")
async def read_game_page():
    """Zwraca stronę interfejsu gry."""
    return FileResponse('static/index.html')

@app.get("/lobby.html")
async def read_lobby_browser_page():
    """Zwraca stronę przeglądarki lobby."""
    return FileResponse('static/lobby.html')

@app.get("/zasady.html")
async def read_rules_page():
    """Zwraca stronę z zasadami gry."""
    return FileResponse('static/zasady.html')

@app.get("/ranking.html")
async def read_ranking_page():
    """Zwraca stronę rankingu graczy."""
    return FileResponse('static/ranking.html')

# ==========================================================================
# SEKCJA 9: ENDPOINTY UŻYTKOWNIKÓW I USTAWIEŃ (Rejestracja, Logowanie)
# ==========================================================================

@app.get("/ranking/lista")
async def pobierz_ranking_graczy(db: AsyncSession = Depends(get_db)):
    """
    Pobiera listę wszystkich graczy (ludzi i botów) posortowaną według Elo
    wraz z ich statystykami gier.
    """
    try:
        # Zapytanie do bazy o potrzebne kolumny, sortowanie malejąco wg Elo
        query = (
            select(
                User.username,
                User.elo_rating,
                User.games_played,
                User.games_won,
                User.settings # Pobieramy ustawienia, by oznaczyć boty
            )
            .order_by(User.elo_rating.desc())
        )
        
        result = await db.execute(query)
        gracze_raw = result.all()
        
        # Przetwórz dane do formatu JSON
        lista_rankingu = []
        for row in gracze_raw:
            # Sprawdź, czy to bot
            jest_botem = False
            if row.settings:
                try:
                    settings = json.loads(row.settings)
                    if settings.get("jest_botem") is True:
                        jest_botem = True
                except (json.JSONDecodeError, TypeError):
                    pass # Ignoruj błędy parsowania
            
            lista_rankingu.append({
                "username": row.username,
                "elo_rating": row.elo_rating,
                "games_played": row.games_played,
                "games_won": row.games_won,
                "is_bot": jest_botem # Dodaj flagę dla frontendu
            })
            
        return JSONResponse(content=lista_rankingu)
        
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY podczas pobierania rankingu: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nie udało się pobrać listy rankingu."
        )

@app.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Rejestruje nowego użytkownika w bazie danych."""
    # Sprawdź, czy użytkownik o tej nazwie już istnieje
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tej nazwie już istnieje."
        )
    # Prosta walidacja długości hasła
    if len(user_data.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hasło musi mieć co najmniej 4 znaki."
        )

    # Hashuj hasło przed zapisem
    hashed_pass = hash_password(user_data.password)
    # Stwórz nowy obiekt User
    new_user = User(username=user_data.username, hashed_password=hashed_pass)
    # Dodaj i zapisz w bazie
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user) # Odśwież obiekt, aby uzyskać np. ID
    # Zwróć token (obecnie tylko nazwa użytkownika)
    return Token(access_token=new_user.username, token_type="bearer", username=new_user.username)

@app.post("/login", response_model=Token)
async def login_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Loguje istniejącego użytkownika."""
    # Znajdź użytkownika w bazie
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # Sprawdź, czy użytkownik istnieje i czy hasło się zgadza
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło."
        )

    # --- Sprawdź, czy gracz ma aktywną grę do powrotu ---
    active_game_id_found = None
    try:
        # Przejrzyj aktywne gry (użyj kopii listy wartości, aby uniknąć błędów modyfikacji)
        gry_copy = list(gry.values())
        for partia in gry_copy:
            # Sprawdź tylko gry w trakcie
            if partia.get("status_partii") == "W_TRAKCIE":
                slots = partia.get("slots", [])
                # Znajdź slot tego gracza, który jest oznaczony jako rozłączony
                slot_gracza = next((s for s in slots if s.get("nazwa") == user.username and s.get("typ") == "rozlaczony"), None)
                if slot_gracza:
                    active_game_id_found = partia.get("id_gry")
                    break # Znaleziono grę, przerwij pętlę
    except RuntimeError:
         # Ten błąd może wystąpić, jeśli słownik `gry` zostanie zmodyfikowany podczas iteracji
         print("Ostrzeżenie: Słownik gier zmienił się podczas sprawdzania statusu logowania.")

    # --- Pobierz ustawienia użytkownika z bazy ---
    user_settings = None
    if user.settings:
        try:
            # Spróbuj sparsować JSON zapisany w bazie
            user_settings = json.loads(user.settings)
        except json.JSONDecodeError:
            # Błąd, jeśli zapisane ustawienia nie są poprawnym JSONem
            print(f"Błąd dekodowania JSON ustawień dla użytkownika {user.username}")
            user_settings = None # Ignoruj błędne ustawienia

    # Zwróć token wraz z informacją o grze do powrotu i ustawieniami
    return Token(
        access_token=user.username,
        token_type="bearer",
        username=user.username,
        active_game_id=active_game_id_found,
        settings=user_settings
    )

@app.get("/check_active_game/{username}")
async def check_active_game(username: str):
    """
    Sprawdza (bez logowania), czy dany użytkownik ma aktywną grę, do której może wrócić.
    Używane przez frontend do pokazania przycisku "Wróć do gry".
    """
    active_game_id_found = None
    try:
        gry_copy = list(gry.values())
        for partia in gry_copy:
            if partia.get("status_partii") == "W_TRAKCIE":
                slots = partia.get("slots", [])
                # Szukaj slotu gracza, który jest rozłączony LUB nadal aktywny (na wypadek problemów z rozłączeniem)
                slot_gracza = next((s for s in slots if s.get("nazwa") == username and s.get("typ") in ["rozlaczony", "czlowiek"]), None)
                if slot_gracza:
                    active_game_id_found = partia.get("id_gry")
                    break
    except RuntimeError:
         print("Ostrzeżenie: Słownik gier zmienił się podczas sprawdzania /check_active_game.")
    # Zwróć tylko ID gry (lub None)
    return {"active_game_id": active_game_id_found}

@app.post("/save_settings/{username}")
async def save_user_settings(username: str, settings_data: UserSettings, db: AsyncSession = Depends(get_db)):
    """Zapisuje ustawienia interfejsu użytkownika w bazie danych."""
    # Znajdź użytkownika
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie znaleziony."
        )
    try:
        # Skonwertuj obiekt Pydantic na JSON string
        settings_json = json.dumps(settings_data.dict())
        # Zapisz JSON w kolumnie 'settings'
        user.settings = settings_json
        # Zatwierdź zmiany w bazie
        await db.commit()
        return {"message": "Ustawienia zapisane pomyślnie."}
    except Exception as e:
            # W razie błędu wycofaj transakcję
            await db.rollback()
            print(f"!!! KRYTYCZNY BŁĄD podczas zapisywania ustawień dla {username} !!!")
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Nie udało się zapisać ustawień z powodu błędu serwera: {type(e).__name__}"
            )

# ==========================================================================
# SEKCJA 10: ENDPOINTY LOBBY I TWORZENIA GRY
# ==========================================================================

@app.get("/gra/lista_lobby")
async def pobierz_liste_lobby(db: AsyncSession = Depends(get_db)):
    """Pobiera listę gier online (w lobby lub w trakcie) do wyświetlenia w przeglądarce lobby."""
    lista_lobby = []
    try:
        # Utwórz kopię listy wartości słownika gier, aby uniknąć błędów modyfikacji podczas iteracji
        gry_copy = list(gry.values())
    except RuntimeError:
        # Błąd, jeśli słownik `gry` jest modyfikowany w innym wątku podczas tworzenia listy
        return {"lobby_list": []}

    # Przetwórz każdą aktywną grę
    for partia in gry_copy:
        try:
            opcje = partia.get("opcje", {})
            status = partia.get("status_partii")

            # Wybierz tylko gry online, które są w lobby lub w trakcie
            if (status in ["LOBBY", "W_TRAKCIE"] and
                partia.get("tryb_lobby") == "online"): # Używamy poprawnego klucza "tryb_lobby"

                slots = partia.get("slots", [])
                aktualni_gracze = sum(1 for s in slots if s.get("typ") != "pusty")
                max_gracze = partia.get("max_graczy", 4)

                # --- Pobieranie średniego Elo dla gier rankingowych ---
                srednie_elo = None
                czy_rankingowa = opcje.get("rankingowa", False)
                if czy_rankingowa:
                    # Zbierz nazwy graczy aktualnie w lobby/grze
                    nazwy_graczy = [s.get("nazwa") for s in slots if s.get("nazwa")]
                    if nazwy_graczy:
                        try:
                            # Pobierz Elo tych graczy z bazy danych
                            query = select(User.elo_rating).where(User.username.in_(nazwy_graczy))
                            result = (await db.execute(query)).scalars().all()
                            if result: # Oblicz średnią, jeśli znaleziono Elo
                                srednie_elo = sum(result) / len(result)
                        except Exception as db_err:
                            # Złap potencjalne błędy bazy danych przy pobieraniu Elo
                            print(f"Błąd DB podczas pobierania Elo dla lobby {partia.get('id_gry')}: {db_err}")
                            srednie_elo = None # Ustaw na None w razie błędu

                # Stwórz słownik informacji o lobby do wysłania klientowi
                lobby_info = {
                    "id_gry": partia.get("id_gry"),
                    "host": partia.get("host", "Brak hosta"),
                    "tryb_gry": opcje.get("tryb_gry", "4p"), # '4p' lub '3p'
                    "ma_haslo": bool(opcje.get("haslo")),
                    "aktualni_gracze": aktualni_gracze,
                    "max_gracze": max_gracze,
                    "status": status,
                    "gracze": [s.get("nazwa") for s in slots if s.get("nazwa")], # Lista nazw graczy
                    "rankingowa": czy_rankingowa, # Czy gra jest rankingowa
                    "srednie_elo": srednie_elo    # Średnie Elo graczy (lub None)
                }
                lista_lobby.append(lobby_info)
        except Exception as e:
            # Złap błędy przetwarzania pojedynczego lobby, aby nie zatrzymać całej listy
            print(f"Błąd podczas przetwarzania lobby {partia.get('id_gry')} na listę: {e}")
            traceback.print_exc() # Dodaj traceback dla lepszego debugowania
            continue # Przejdź do następnej gry

    return {"lobby_list": lista_lobby}

@app.post("/gra/stworz")
def stworz_gre(request: CreateGameRequest):
    """Tworzy nową grę (lokalną lub online) na podstawie opcji z żądania."""
    # Usunięto log żądania (już niepotrzebny)
    # print(f"Otrzymano żądanie /gra/stworz: {request}")

    id_gry = generuj_krotki_id() # Wygeneruj unikalne ID
    nazwa_gracza = request.nazwa_gracza # Host gry

    # --- Stwórz główny słownik stanu gry (`partia`) ---
    partia = {
        # --- Podstawowe informacje ---
        "id_gry": id_gry,
        "czas_stworzenia": time.time(),
        "status_partii": "LOBBY", # Gra zaczyna w lobby
        "host": nazwa_gracza,
        "tryb_lobby": request.tryb_lobby, # 'online' lub 'lokalna'
        "max_graczy": 4 if request.tryb_gry == '4p' else 3,

        # --- Stan silnika gry (inicjalizowane później) ---
        "gracze_engine": [], "druzyny_engine": [], "aktualne_rozdanie": None,

        # --- Stan meczu ---
        "numer_rozdania": 1,
        "historia_partii": [], # Lista stringów podsumowujących rozdania

        # --- Stan lobby ---
        "kicked_players": [], # Lista wyrzuconych graczy
        "gracze_gotowi": [], # Gracze gotowi na następne rozdanie

        # --- Opcje gry (z żądania) ---
        "opcje": {
            "tryb_gry": request.tryb_gry, # '4p' lub '3p'
            "publiczna": request.publiczna, # Czy widoczna w lobby
            "haslo": request.haslo if request.haslo else None, # Hasło (jeśli prywatna)
            "rankingowa": request.czy_rankingowa # Czy gra rankingowa
        },

        # --- Stan timera (dla gier rankingowych) ---
        "timery": {},             # Słownik {nazwa_gracza: pozostaly_czas_s}
        "timer_task": None,       # Referencja do zadania asyncio timera
        "numer_ruchu_timer": 0,   # Licznik do walidacji timera
        "tura_start_czas": None,  # Timestamp rozpoczęcia tury

        # --- Stan Elo (dla gier rankingowych) ---
        "wynik_elo": None,        # Podsumowanie zmian Elo po meczu
        "elo_obliczone": False,   # Flaga zapobiegająca podwójnemu liczeniu Elo

        # --- Inne ---
        'aktualna_ocena': None, # Ostatnia ocena stanu przez MCTS (dla paska ewaluacji)
        "pelna_historia": [],   # Czy to jest używane? Potencjalnie do usunięcia.
        "bot_loop_lock": asyncio.Lock(), # Lock do synchronizacji pętli botów
    }
    # Usunięto log opcji (już niepotrzebny)
    # print(f"Utworzono grę {id_gry}, opcje: {partia.get('opcje')}")

    # --- Zainicjalizuj sloty i punkty w zależności od trybu gry ---
    if request.tryb_gry == '4p':
        nazwy = random.sample(NAZWY_DRUZYN, 2) # Wylosuj nazwy drużyn
        nazwy_mapa = {"My": nazwy[0], "Oni": nazwy[1]}
        partia.update({
            "nazwy_druzyn": nazwy_mapa,
            "punkty_meczu": {nazwy_mapa["My"]: 0, nazwy_mapa["Oni"]: 0}, # Inicjalizacja punktów drużyn
            "slots": [ # 4 sloty z przypisaniem do drużyn
                {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
                {"slot_id": 1, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
                {"slot_id": 2, "nazwa": None, "typ": "pusty", "druzyna": "My"},
                {"slot_id": 3, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
            ]
        })
    else: # Gra 3-osobowa
         partia.update({
            "punkty_meczu": {}, # Punkty graczy inicjalizowane przy starcie gry
            "slots": [ # 3 sloty bez drużyn
                {"slot_id": 0, "nazwa": None, "typ": "pusty"},
                {"slot_id": 1, "nazwa": None, "typ": "pusty"},
                {"slot_id": 2, "nazwa": None, "typ": "pusty"},
            ]
        })

    # --- Specjalna obsługa gry lokalnej (startuje od razu z botami) ---
    if request.tryb_lobby == 'lokalna':
        partia["status_partii"] = "W_TRAKCIE" # Ustaw status od razu na grę
        partia["slots"][0].update({"nazwa": nazwa_gracza, "typ": "czlowiek"}) # Umieść gracza w slocie 0
        try:
            # --- Inicjalizacja silnika gry dla gry lokalnej ---
            if request.tryb_gry == '4p':
                # Dodaj boty do pozostałych slotów
                partia["slots"][1].update({"nazwa": "Bot_1", "typ": "bot", "druzyna": "Oni"})
                partia["slots"][2].update({"nazwa": "Bot_2", "typ": "bot", "druzyna": "My"})
                partia["slots"][3].update({"nazwa": "Bot_3", "typ": "bot", "druzyna": "Oni"})
                # Stwórz obiekty silnika gry (Druzyna, Gracz)
                d_my = silnik_gry.Druzyna(partia["nazwy_druzyn"]["My"])
                d_oni = silnik_gry.Druzyna(partia["nazwy_druzyn"]["Oni"])
                d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                gracze_tmp = [None] * 4
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    gracze_tmp[slot["slot_id"]] = g
                    (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)
                # Zapisz obiekty silnika w stanie gry
                partia.update({"gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni]})
                # Stwórz obiekt Rozdanie
                rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], 0) # Rozdającym jest slot 0
            else: # Gra 3-osobowa lokalna
                partia["slots"][1].update({"nazwa": "Bot_1", "typ": "bot"})
                partia["slots"][2].update({"nazwa": "Bot_2", "typ": "bot"})
                # Stwórz obiekty Gracz
                gracze_tmp = [None] * 3
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    g.punkty_meczu = 0 # Zainicjalizuj punkty meczu
                    gracze_tmp[slot["slot_id"]] = g
                # Zapisz graczy i zainicjalizuj punkty meczu w stanie gry
                partia.update({"gracze_engine": gracze_tmp, "punkty_meczu": {g.nazwa: 0 for g in gracze_tmp}})
                # Stwórz obiekt RozdanieTrzyOsoby
                rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], 0)

            # --- Rozpocznij pierwsze rozdanie ---
            if rozdanie:
                rozdanie.rozpocznij_nowe_rozdanie()
                partia["aktualne_rozdanie"] = rozdanie # Zapisz obiekt rozdania w stanie gry
            else:
                 # To nie powinno się zdarzyć
                 raise ValueError("Nie udało się zainicjalizować obiektu rozdania dla gry lokalnej.")
        except Exception as e:
            # Złap błędy podczas inicjalizacji gry lokalnej
            print(f"!!! KRYTYCZNY BŁĄD podczas tworzenia gry lokalnej {id_gry} !!!")
            traceback.print_exc()
            # Zwróć błąd HTTP 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Błąd serwera podczas inicjalizacji gry lokalnej: {e}"
            )
    elif request.tryb_lobby == 'online':
            # Sprawdź, czy host (nazwa_gracza) to jeden z naszych botów Elo World
            bot_data = next((bot for bot in AKTYWNE_BOTY_ELO_WORLD if bot[0] == nazwa_gracza), None)
            
            if bot_data:
                # Hostem jest bot
                bot_algorytm = bot_data[1]
                partia["slots"][0].update({
                    "nazwa": nazwa_gracza, 
                    "typ": "bot", # Ustawiamy typ 'bot' dla logiki serwera
                    "bot_algorithm": bot_algorytm
                })
            else:
                # Hostem jest człowiek
                partia["slots"][0].update({
                    "nazwa": nazwa_gracza, 
                    "typ": "czlowiek"
                })

    # Dodaj nowo utworzoną grę do globalnego słownika gier
    gry[id_gry] = partia
    # Zwróć ID nowej gry
    return {"id_gry": id_gry}

@app.get("/gra/sprawdz/{id_gry}")
def sprawdz_gre(id_gry: str):
    """Sprawdza, czy gra o podanym ID istnieje w pamięci serwera."""
    return {"exists": id_gry in gry}

# ==========================================================================
# SEKCJA 11: GŁÓWNA LOGIKA GRY (Pobieranie Stanu / Przetwarzanie Akcji)
# ==========================================================================
# Ta sekcja zawiera kluczowe funkcje obsługujące logikę gry w czasie rzeczywistym,
# wywoływane głównie przez endpoint WebSocket.

def pobierz_stan_gry(id_gry: str) -> dict:
    """
    Pobiera aktualny stan gry o podanym ID, formatuje go w sposób zrozumiały
    dla klienta (frontend JavaScript) i zwraca jako słownik.
    """
    partia = gry.get(id_gry)
    if not partia:
        return {"error": "Gra nie istnieje"} # Zwróć błąd, jeśli gra nie istnieje
    slots_dla_klienta = copy.deepcopy(partia["slots"])

    # Pobieramy nazwy naszych aktywnych botów (te z bazy danych)
    aktywne_boty_nazwy = {bot[0] for bot in AKTYWNE_BOTY_ELO_WORLD}

    for slot in slots_dla_klienta:
        # Jeśli slot to 'bot' I jest to jeden z naszych botów Elo World
        if slot.get("typ") == "bot" and slot.get("nazwa") in aktywne_boty_nazwy:
            slot["typ"] = "czlowiek" # Zmień typ na "czlowiek" dla klienta
            slot.pop("bot_algorithm", None) # Usuń informację o algorytmie

    # --- Stwórz podstawowy słownik stanu (wspólny dla wszystkich faz) ---
    stan_podstawowy = {
        "status_partii": partia["status_partii"], # "LOBBY", "W_TRAKCIE", "ZAKONCZONA"
        "tryb_lobby": partia.get("tryb_lobby", "online"), # 'online' lub 'lokalna'
        "max_graczy": partia.get("max_graczy", 4), # 4 lub 3
        "slots": slots_dla_klienta,           # Lista slotów z informacjami o graczach
        "host": partia["host"],             # Nazwa hosta gry
        "gracze_gotowi": partia.get("gracze_gotowi", []), # Gracze gotowi na nast. rozdanie
        "nazwy_druzyn": partia.get("nazwy_druzyn", {}), # Nazwy drużyn (dla 4p)
        "historia_partii": partia.get("historia_partii", []), # Podsumowanie poprzednich rozdań
        "timery": partia.get("timery"), # Aktualny stan timerów (dla gier rankingowych)
        "opcje": partia.get("opcje", {}) # Opcje gry (w tym flaga 'rankingowa')
    }

    # --- Dostosuj stan w zależności od fazy gry ---
    if partia['status_partii'] == 'LOBBY':
        stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {}) # Wyślij puste punkty
        return stan_podstawowy

    elif partia['status_partii'] == 'ZAKONCZONA':
        # Pobierz końcowe punkty meczu z obiektów silnika (jeśli istnieją)
        if partia.get("max_graczy", 4) == 4:
            stan_podstawowy["punkty_meczu"] = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])} if partia.get("druzyny_engine") else partia.get("punkty_meczu", {})
        else: # 3 graczy
            stan_podstawowy["punkty_meczu"] = {g.nazwa: g.punkty_meczu for g in partia.get("gracze_engine", [])} if partia.get("gracze_engine") else partia.get("punkty_meczu", {})
        # Dodaj podsumowanie zmian Elo
        stan_podstawowy["wynik_elo"] = partia.get("wynik_elo")
        return stan_podstawowy

    elif partia['status_partii'] == 'W_TRAKCIE':
        rozdanie = partia.get("aktualne_rozdanie") # Pobierz obiekt aktualnego rozdania
        if not rozdanie: # Jeśli rozdanie nie istnieje (błąd?), zwróć stan podstawowy
            stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {})
            print(f"OSTRZEŻENIE: Brak obiektu rozdania w stanie W_TRAKCIE dla gry {id_gry}")
            return stan_podstawowy

        # --- Obliczanie Oceny Silnika (dla paska ewaluacji) ---
        aktualna_ocena = None
        # Ocena jest liczona tylko w fazie rozgrywki, przed podsumowaniem
        if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA and not rozdanie.podsumowanie:
            gracz_perspektywa = rozdanie.grajacy # Ocena z perspektywy grającego
            if gracz_perspektywa:
                try:
                    # Wywołaj metodę ewaluacji bota MCTS
                    aktualna_ocena = cheating_mcts_bot.evaluate_state(
                        stan_gry=rozdanie,
                        nazwa_gracza_perspektywa=gracz_perspektywa.nazwa,
                        limit_symulacji=500 # Liczba symulacji do oceny
                    )
                except Exception as e:
                    # Złap błędy podczas oceny
                    print(f"BŁĄD podczas obliczania ewaluacji dla gry {id_gry}: {e}")
                    aktualna_ocena = None # Ustaw na None w razie błędu

        # --- Pobierz aktualne punkty z obiektów silnika ---
        if partia.get("max_graczy", 4) == 4:
            punkty_meczu = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])}
            punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu # Punkty w kartach w tym rozdaniu
        else: # 3 graczy
            punkty_meczu = {g.nazwa: g.punkty_meczu for g in rozdanie.gracze if g}
            punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu

        # --- Znajdź gracza w turze ---
        gracz_w_turze_obj = None
        if rozdanie.kolej_gracza_idx is not None and rozdanie.gracze and 0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze):
             gracz_w_turze_obj = rozdanie.gracze[rozdanie.kolej_gracza_idx]

        # --- Zaktualizuj stan podstawowy danymi specyficznymi dla rozdania ---
        stan_podstawowy.update({
            "punkty_meczu": punkty_meczu, # Aktualne punkty meczu
            "rozdanie": { # Słownik zawierający szczegóły bieżącego rozdania
                "faza": rozdanie.faza, # Aktualna faza gry (Enum jako string)
                "kolej_gracza": gracz_w_turze_obj.nazwa if gracz_w_turze_obj else None, # Nazwa gracza w turze
                # Ręce graczy (tylko nazwy kart jako stringi)
                "rece_graczy": {g.nazwa: [str(k) for k in g.reka] for g in rozdanie.gracze if g},
                # Karty zagrane w bieżącej lewie
                "karty_na_stole": [{"gracz": g.nazwa, "karta": str(k)} for g, k in rozdanie.aktualna_lewa],
                "grywalne_karty": [], # Lista legalnych kart do zagrania (wypełniana poniżej)
                "mozliwe_akcje": [],  # Lista możliwych akcji licytacyjnych (wypełniana poniżej)
                "punkty_w_rozdaniu": punkty_w_rozdaniu, # Punkty zdobyte w kartach w tym rozdaniu
                "kontrakt": {"typ": rozdanie.kontrakt, "atut": rozdanie.atut}, # Aktualny kontrakt i atut
                "aktualna_stawka": rozdanie.oblicz_aktualna_stawke() if hasattr(rozdanie, 'oblicz_aktualna_stawke') else 0, # Stawka punktowa rozdania
                "gracz_grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None, # Kto gra kontrakt
                "historia_rozdania": rozdanie.szczegolowa_historia, # Lista logów z tego rozdania
                "podsumowanie": rozdanie.podsumowanie, # Wynik rozdania (gdy faza to PODSUMOWANIE)
                "lewa_do_zamkniecia": rozdanie.lewa_do_zamkniecia, # Czy lewa czeka na finalizację
                "aktualna_ocena": aktualna_ocena # Ocena stanu przez MCTS (lub None)
            }
            # Timery są już w stanie podstawowym
        })

        # --- Dodaj grywalne karty lub możliwe akcje dla gracza w turze ---
        if gracz_w_turze_obj:
            if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
                 # W rozgrywce znajdź legalne karty do zagrania
                 stan_podstawowy['rozdanie']['grywalne_karty'] = [
                     str(k) for k in gracz_w_turze_obj.reka
                     if rozdanie._waliduj_ruch(gracz_w_turze_obj, k)
                 ]
            else: # W fazach licytacyjnych pobierz możliwe akcje
                 stan_podstawowy['rozdanie']['mozliwe_akcje'] = rozdanie.get_mozliwe_akcje(gracz_w_turze_obj)

        return stan_podstawowy
    else: # Nieznany status partii
        print(f"OSTRZEŻENIE: Nieznany status partii '{partia.get('status_partii')}' dla gry {id_gry}")
        stan_podstawowy["error"] = f"Nieznany status partii: {partia.get('status_partii')}"
        return stan_podstawowy

async def przetworz_akcje_gracza(data: dict, partia: dict):
    """
    Przetwarza akcję otrzymaną od gracza przez WebSocket.
    Obsługuje zarówno akcje w lobby (zmiana slotu, start gry),
    jak i akcje w trakcie gry (licytacja, zagranie karty).
    Wywołuje odpowiednie metody obiektu Rozdanie z silnika gry.
    """
    gracz_akcji_nazwa = data.get("gracz") # Nazwa gracza wykonującego akcję
    id_gry = partia.get("id_gry", "N/A")

    try:
        # --- Obsługa Akcji w Lobby ---
        if partia["status_partii"] == "LOBBY":
            akcja = data.get("akcja_lobby") # Typ akcji lobby

            if akcja == "dolacz_do_slota": # Gracz zmienia swoje miejsce
                slot_id = data.get("slot_id") # ID slotu docelowego
                # Znajdź obecny slot gracza i slot docelowy
                slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_akcji_nazwa), None)
                slot_docelowy = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
                # Przenieś gracza, jeśli slot docelowy jest pusty
                if slot_gracza and slot_docelowy and slot_docelowy["typ"] == "pusty":
                    slot_docelowy.update({"nazwa": slot_gracza["nazwa"], "typ": slot_gracza["typ"]})
                    slot_gracza.update({"nazwa": None, "typ": "pusty"}) # Opróżnij stary slot

            elif akcja == "zmien_slot" and partia["host"] == gracz_akcji_nazwa: # Host zmienia typ slotu
                slot_id = data.get("slot_id") # ID slotu do zmiany
                nowy_typ = data.get("nowy_typ") # "pusty" lub "bot"
                wybrany_algorytm = data.get("bot_algorithm") # Algorytm bota (jeśli dotyczy)
                slot = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)

                # Sprawdź, czy host nie próbuje zmienić swojego slotu lub czy slot istnieje
                if slot and slot["nazwa"] != partia["host"]:
                    # Sprawdź blokadę dodawania botów w grach rankingowych
                    if (nowy_typ == "bot" and partia.get("opcje", {}).get("rankingowa", False)):
                         print(f"[{id_gry}] Odrzucono próbę dodania bota do gry rankingowej.")
                         return # Zignoruj akcję


                    if nowy_typ == "pusty": # Wyrzucenie gracza/bota
                        # Jeśli wyrzucamy człowieka, dodaj go do listy wyrzuconych
                        if slot["typ"] == "czlowiek" and slot["nazwa"]:
                            partia.setdefault("kicked_players", []).append(slot["nazwa"])
                        slot.update({"nazwa": None, "typ": "pusty"})
                    elif nowy_typ == "bot": # Dodanie bota
                        # Użyj algorytmu z żądania lub domyślnego z `bot_instances`
                        algorytm_do_zapisu = wybrany_algorytm if wybrany_algorytm in bot_instances else default_bot_name
                        slot.update({
                            "nazwa": f"Bot_{slot_id}",
                            "typ": "bot",
                            "bot_algorithm": algorytm_do_zapisu # Zapisz algorytm w slocie
                        })
                        print(f"[{id_gry}] Slot {slot_id} zmieniony na Bota ({algorytm_do_zapisu.upper()})")

            elif akcja == "start_gry" and partia["host"] == gracz_akcji_nazwa: # Host rozpoczyna grę
                # Sprawdź, czy wszystkie sloty są zajęte
                if not all(s["typ"] != "pusty" for s in partia["slots"]):
                    print(f"[{id_gry}] Próba startu gry z pustymi slotami odrzucona.")
                    return # Nie startuj, jeśli są puste sloty

                liczba_graczy = len(partia["slots"])
                # Stwórz tymczasową listę obiektów Gracz z silnika
                gracze_tmp = [None] * liczba_graczy
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    gracze_tmp[slot["slot_id"]] = g

                # Zaktualizuj stan gry: gracze silnika, status na W_TRAKCIE
                partia.update({"gracze_engine": gracze_tmp, "status_partii": "W_TRAKCIE"})
                rozdanie = None # Zainicjalizuj zmienną rozdania

                # --- Inicjalizacja Timerów dla Gry Rankingowej ---
                if partia.get("opcje", {}).get("rankingowa", False):
                    czas_startowy = partia.get("opcje", {}).get("czas_na_gre", 300) # Domyślnie 5 minut
                    partia["timery"] = {g.nazwa: czas_startowy for g in gracze_tmp}

                # --- Inicjalizacja Silnika Gry (Rozdanie / RozdanieTrzyOsoby) ---
                try:
                    if liczba_graczy == 3: # Gra 3-osobowa
                        # Zainicjalizuj punkty meczu dla graczy
                        for gracz in gracze_tmp: gracz.punkty_meczu = 0
                        partia["punkty_meczu"] = {g.nazwa: 0 for g in gracze_tmp}
                        # Stwórz obiekt RozdanieTrzyOsoby
                        rozdanie = silnik_gry.RozdanieTrzyOsoby(gracze_tmp, 0) # Gracz 0 rozdaje
                    else: # Gra 4-osobowa
                        # Stwórz obiekty Druzyna
                        nazwy = partia["nazwy_druzyn"]
                        d_my, d_oni = silnik_gry.Druzyna(nazwy["My"]), silnik_gry.Druzyna(nazwy["Oni"])
                        d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                        # Dodaj graczy do drużyn
                        for slot in partia["slots"]:
                            gracz_obj = next((g for g in gracze_tmp if g.nazwa == slot["nazwa"]), None)
                            if gracz_obj:
                                (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(gracz_obj)
                        # Zapisz drużyny w stanie gry
                        partia.update({"druzyny_engine": [d_my, d_oni]})
                        # Stwórz obiekt Rozdanie
                        rozdanie = silnik_gry.Rozdanie(gracze_tmp, [d_my, d_oni], 0)

                    # --- Rozpocznij pierwsze rozdanie ---
                    if rozdanie:
                        rozdanie.rozpocznij_nowe_rozdanie()
                        partia["aktualne_rozdanie"] = rozdanie # Zapisz obiekt rozdania
                        # Uruchom timer dla pierwszego gracza (jeśli rankingowa)
                        await uruchom_timer_dla_tury(id_gry)
                    else:
                        raise ValueError("Nie udało się utworzyć obiektu rozdania.")
                except Exception as init_err:
                    # Złap błędy inicjalizacji silnika, przywróć stan LOBBY
                    print(f"BŁĄD KRYTYCZNY podczas inicjalizacji silnika gry {id_gry}: {init_err}")
                    traceback.print_exc()
                    partia["status_partii"] = "LOBBY" # Cofnij status
                    partia["gracze_engine"] = []
                    # TODO: Rozważ wysłanie wiadomości o błędzie do graczy
                    return

        # --- Obsługa Akcji w Trakcie Gry ---
        elif partia["status_partii"] == "W_TRAKCIE":
            akcja = data.get('akcja')
            typ_akcji = akcja.get('typ') if akcja else None
            slot_gracza = next((s for s in partia.get("slots", []) if s.get("nazwa") == gracz_akcji_nazwa), None)

            # --- Odejmowanie Czasu dla Gracza (jeśli rankingowa) ---
            if (partia.get("opcje", {}).get("rankingowa", False) and
                slot_gracza and slot_gracza.get("typ") == "czlowiek" and
                typ_akcji not in ['nastepne_rozdanie', 'finalizuj_lewe'] and # Ignoruj akcje systemowe
                partia.get("tura_start_czas") is not None and
                gracz_akcji_nazwa in partia.get("timery", {})):

                czas_teraz = time.time()
                czas_zuzyty = czas_teraz - partia["tura_start_czas"]
                partia["timery"][gracz_akcji_nazwa] -= czas_zuzyty # Odejmij zużyty czas
                partia["tura_start_czas"] = None # Zresetuj czas startu tury
                # print(f"[{id_gry}] Gracz {gracz_akcji_nazwa} zużył {czas_zuzyty:.2f}s. Pozostało: {partia['timery'][gracz_akcji_nazwa]:.2f}s.")

            # Anuluj zadanie timera poprzedniego gracza (jeśli istniało)
            if partia.get("timer_task") and not partia["timer_task"].done():
                partia["timer_task"].cancel()

            # Pobierz obiekt rozdania i gracza wykonującego akcję
            rozdanie = partia.get("aktualne_rozdanie")
            if not akcja or not rozdanie: return # Ignoruj, jeśli brak akcji lub rozdania
            # typ_akcji = akcja.get('typ') # Już pobrane
            gracz_obj = next((g for g in rozdanie.gracze if g and g.nazwa == gracz_akcji_nazwa), None)
            if not gracz_obj: return # Ignoruj, jeśli nie znaleziono gracza

            # --- Wykonaj Akcję w Silniku Gry ---
            if typ_akcji == 'nastepne_rozdanie': # Gracz jest gotowy na następne rozdanie
                # Dodaj gracza do listy gotowych
                if gracz_akcji_nazwa not in partia.get("gracze_gotowi", []):
                    partia.setdefault("gracze_gotowi", []).append(gracz_akcji_nazwa)
                
                # Sprawdź, ilu ludzi jest w grze
                liczba_ludzi = sum(1 for s in partia["slots"] if s["typ"] == "czlowiek")
                
                wszyscy_gotowi = False
                if liczba_ludzi > 0:
                    # TRYB Z LUDŹMI: Czekaj na wszystkich ludzi
                    gotowi_ludzie = [nazwa for nazwa in partia.get("gracze_gotowi", []) if any(s["nazwa"] == nazwa and s["typ"] == "czlowiek" for s in partia["slots"])]
                    if len(gotowi_ludzie) >= liczba_ludzi:
                        wszyscy_gotowi = True
                else:
                    # TRYB 0 LUDZI (np. 4 boty): Czekaj na wszystkich graczy
                    liczba_graczy_w_partii = len(partia.get("slots", []))
                    if len(partia.get("gracze_gotowi", [])) >= liczba_graczy_w_partii:
                        wszyscy_gotowi = True

                if wszyscy_gotowi: # Wszyscy gotowi
                    partia["gracze_gotowi"] = [] # Wyczyść listę gotowych
                    # Jeśli było podsumowanie, zapisz je w historii partii
                    if rozdanie.podsumowanie:
                        pod = rozdanie.podsumowanie
                        nr = partia.get("numer_rozdania", 1)
                        gral = rozdanie.grajacy.nazwa if rozdanie.grajacy else "Brak"
                        kontrakt_nazwa = pod.get("kontrakt", "Brak")
                        atut_nazwa = pod.get("atut", "")
                        if atut_nazwa and atut_nazwa != "Brak": kontrakt_nazwa = f"{kontrakt_nazwa} ({atut_nazwa[0]})" # Dodaj symbol atutu
                        wygrani = pod.get("wygrana_druzyna", ", ".join(pod.get("wygrani_gracze", [])))
                        punkty = pod.get("przyznane_punkty", 0)
                        # Stwórz wpis do historii partii
                        wpis = (f"R{nr} | G:{gral} | K:{kontrakt_nazwa} | "
                                f"W:{wygrani} | P:{punkty} pkt")
                        partia["historia_partii"].append(wpis)
                        partia["numer_rozdania"] = nr + 1 # Zwiększ numer następnego rozdania
                        partia.pop("czas_konca_rundy", None)
                        partia.pop("wymuszono_nastepna_runde", None)

                        # --- Dodaj 15 sekund do timerów na koniec rozdania (jeśli rankingowa) ---
                        if partia.get("opcje", {}).get("rankingowa", False):
                            czas_dodatkowy = 15
                            print(f"[{id_gry}] Koniec rozdania. Dodawanie {czas_dodatkowy}s do timerów.")
                            for gracz_nazwa in partia.get("timery", {}):
                                partia["timery"][gracz_nazwa] = partia["timery"].get(gracz_nazwa, 0) + czas_dodatkowy

                    # Sprawdź, czy gra się zakończyła (osiągnięto 66 pkt)
                    if not sprawdz_koniec_partii(partia):
                        # Jeśli nie, przygotuj następne rozdanie
                        # Wyczyść ręce i wygrane karty graczy
                        for gracz in partia["gracze_engine"]:
                            gracz.reka.clear(); gracz.wygrane_karty.clear()
                        # Ustal nowego rozdającego
                        nowy_idx = (rozdanie.rozdajacy_idx + 1) % len(partia["gracze_engine"])
                        # Stwórz nowy obiekt Rozdanie/RozdanieTrzyOsoby
                        if partia.get("max_graczy", 4) == 4:
                            nowe_rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], nowy_idx)
                        else:
                            nowe_rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], nowy_idx)
                        # Rozpocznij nowe rozdanie
                        nowe_rozdanie.rozpocznij_nowe_rozdanie()
                        partia["aktualne_rozdanie"] = nowe_rozdanie # Zapisz nowy obiekt rozdania
                    else: # Gra się zakończyła
                        # Oblicz i zapisz zmiany Elo (jeśli rankingowa)
                        await zaktualizuj_elo_po_meczu(partia)

            elif typ_akcji == 'finalizuj_lewe': # Akcja systemowa - finalizacja lewy
                rozdanie.finalizuj_lewe()

            elif typ_akcji == 'zagraj_karte': # Gracz zagrywa kartę
                karta_str = akcja.get('karta') # Pobierz nazwę karty (string)
                if not karta_str: return # Ignoruj, jeśli brak nazwy karty
                karta_obj = karta_ze_stringa(karta_str) # Skonwertuj string na obiekt Karta
                rozdanie.zagraj_karte(gracz_obj, karta_obj) # Wywołaj metodę silnika

            else: # Akcja licytacyjna (deklaracja, pas, lufa, kontra, etc.)
                # Skopiuj słownik akcji, aby nie modyfikować oryginału
                akcja_do_wykonania = akcja.copy()
                # Skonwertuj stringi 'atut' i 'kontrakt' na obiekty Enum (jeśli istnieją)
                atut_val = akcja_do_wykonania.get('atut')
                if atut_val and isinstance(atut_val, str):
                    try: akcja_do_wykonania['atut'] = silnik_gry.Kolor[atut_val]
                    except KeyError: print(f"BŁĄD: Nieprawidłowa nazwa atutu '{atut_val}' w akcji."); return
                kontrakt_val = akcja_do_wykonania.get('kontrakt')
                if kontrakt_val and isinstance(kontrakt_val, str):
                    try: akcja_do_wykonania['kontrakt'] = silnik_gry.Kontrakt[kontrakt_val]
                    except KeyError: print(f"BŁĄD: Nieprawidłowa nazwa kontraktu '{kontrakt_val}' w akcji."); return
                # Wywołaj metodę silnika
                rozdanie.wykonaj_akcje(gracz_obj, akcja_do_wykonania)

        # --- Obsługa Akcji po Zakończeniu Gry ---
        elif partia["status_partii"] == "ZAKONCZONA":
            akcja = data.get('akcja')
            # Tylko host może wrócić do lobby
            if akcja and akcja.get('typ') == 'powrot_do_lobby' and partia["host"] == gracz_akcji_nazwa:
                resetuj_gre_do_lobby(partia) # Zresetuj stan gry

        # --- Uruchom Timer dla Następnego Gracza (jeśli gra trwa) ---
        if partia["status_partii"] == "W_TRAKCIE":
            await uruchom_timer_dla_tury(id_gry)

    except Exception as e:
        # Złap potencjalne błędy podczas przetwarzania akcji
        print(f"BŁĄD KRYTYCZNY podczas przetwarzania akcji gracza {gracz_akcji_nazwa} w grze {id_gry}: {e}")
        traceback.print_exc()

async def replacement_timer(id_gry: str, slot_id: int):
    """
    Zadanie w tle (asyncio.Task) uruchamiane, gdy gracz się rozłączy w trakcie gry (nierankingowej).
    Czeka 60 sekund. Jeśli gracz nie wróci, zastępuje go botem.
    """
    partia = gry.get(id_gry)
    if not partia: return # Gra już nie istnieje

    # Nie zastępuj botem w grach rankingowych
    if partia.get("opcje", {}).get("rankingowa", False):
        print(f"[{id_gry}] Gra rankingowa, timer zastępujący bota anulowany dla slotu {slot_id}.")
        return

    print(f"[{id_gry}] Uruchomiono 60s timer zastępujący bota dla slotu {slot_id}...")
    await asyncio.sleep(60) # Czekaj 60 sekund

    # Sprawdź stan gry ponownie po odczekaniu
    partia_po_czasie = gry.get(id_gry)
    if not partia_po_czasie or partia_po_czasie["status_partii"] != "W_TRAKCIE":
        print(f"[{id_gry}] Timer zastępujący bota dla slotu {slot_id} anulowany (gra zakończona/wróciła do lobby).")
        return

    # Znajdź slot, którego dotyczył timer
    slot = next((s for s in partia_po_czasie["slots"] if s["slot_id"] == slot_id), None)

    # Jeśli slot nadal jest rozłączony, zastąp gracza botem
    if slot and slot.get("typ") == "rozlaczony":
        stara_nazwa = slot.get("nazwa", f"Gracz_{slot_id}")
        nowa_nazwa_bota = f"Bot_{stara_nazwa[:8]}" # Użyj części starej nazwy dla identyfikacji
        print(f"[{id_gry}] Gracz {stara_nazwa} (slot {slot_id}) nie wrócił. Zastępowanie botem {nowa_nazwa_bota}.")

        # Zaktualizuj slot
        slot["nazwa"] = nowa_nazwa_bota
        slot["typ"] = "bot"
        slot["disconnect_task"] = None # Usuń referencję do tego zadania

        # Zaktualizuj nazwę gracza w silniku gry (jeśli istnieje)
        if partia_po_czasie.get("gracze_engine"):
            gracz_obj = next((g for g in partia_po_czasie["gracze_engine"] if g.nazwa == stara_nazwa), None)
            if gracz_obj:
                gracz_obj.nazwa = nowa_nazwa_bota

        # Sprawdź, czy w grze zostali jeszcze jacyś ludzie
        pozostali_ludzie = any(s.get("typ") == "czlowiek" for s in partia_po_czasie.get("slots", []))
        if not pozostali_ludzie:
            # Jeśli nie ma już ludzi, zakończ i usuń grę
            print(f"[{id_gry}] Brak graczy ludzkich po zastąpieniu {stara_nazwa}. Usuwanie gry.")
            try:
                # Zamknij połączenia WebSocket (jeśli istnieją)
                if id_gry in manager.active_connections:
                    connections_copy = manager.active_connections[id_gry][:]
                    for conn in connections_copy:
                        await conn.close(code=1000, reason="Gra zakończona - brak graczy.")
                    del manager.active_connections[id_gry]
                # Usuń grę ze słownika `gry`
                del gry[id_gry]
            except KeyError:
                # Błąd, jeśli gra została już usunięta
                print(f"[{id_gry}] Nie można było usunąć gry (może już usunięta).")
            return # Zakończ funkcję

        # Jeśli są jeszcze ludzie, kontynuuj grę
        print(f"[{id_gry}] Zostali gracze ludzcy. Kontynuowanie gry.")
        # Wyślij zaktualizowany stan (z botem)
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        # Uruchom pętlę botów (może to teraz tura nowego bota)
        asyncio.create_task(uruchom_petle_botow(id_gry))
    else:
        # Gracz wrócił na czas lub slot został zmieniony
        print(f"[{id_gry}] Timer zastępujący bota dla slotu {slot_id} anulowany (gracz wrócił lub slot zmieniony).")

# ==========================================================================
# SEKCJA 12: PĘTLA BOTA (MCTS)
# ==========================================================================

async def uruchom_petle_botow(id_gry: str):
    """
    Asynchroniczna pętla, która cyklicznie sprawdza, czy aktualnie jest tura bota.
    Uruchamia się TYLKO RAZ dzięki blokadzie i działa, dopóki nie nadejdzie
    tura człowieka lub gra się nie zakończy.
    """
    partia = gry.get(id_gry)
    if not partia: return

    lock = partia.get("bot_loop_lock")
    if not lock: # Awaryjny fallback, jeśli gra została stworzona przed tą zmianą
        lock = asyncio.Lock()
        partia["bot_loop_lock"] = lock
    
    # Spróbuj zdobyć blokadę BEZ CZEKANIA
    if not lock.locked():
        async with lock:
            # print(f"[{id_gry}] ZDOBYTO BLOKADĘ. Uruchamiam pętlę botów.") # Opcjonalny log
            while True: 
                # Sprawdź stan partii *wewnątrz* pętli
                partia_w_petli = gry.get(id_gry)
                if not partia_w_petli or partia_w_petli["status_partii"] != "W_TRAKCIE": 
                    # print(f"[{id_gry}] Gra zakończona lub nie istnieje. ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break # Zakończ pętlę, zwolnij blokadę
                
                rozdanie = partia_w_petli.get("aktualne_rozdanie")
                if not rozdanie or not rozdanie.gracze: 
                    # print(f"[{id_gry}] Błąd rozdania. ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break
                if rozdanie.podsumowanie:
                    # print(f"[{id_gry}] Wykryto podsumowanie. Zatrzymuję pętlę botów.") # Opcjonalny log
                    break # Zakończ pętlę i zwolnij blokadę
                
                # --- BLOK: AUTOMATYCZNA FINALIZACJA LEWY ---
                if rozdanie.lewa_do_zamkniecia:
                    try:
                        # print(f"[{id_gry}] Pętla botów finalizuje lewę...")
                        rozdanie.finalizuj_lewe()
                        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
                        await uruchom_timer_dla_tury(id_gry) 
                        await asyncio.sleep(0.5) 
                        continue # Wróć na początek pętli
                    except Exception as e_fin:
                        print(f"BŁĄD KRYTYCZNY: Pętla botów nie mogła sfinalizować lewy w {id_gry}: {e_fin}")
                        traceback.print_exc()
                        break # Zakończ pętlę, zwolnij blokadę
                
                if rozdanie.kolej_gracza_idx is None: 
                    # print(f"[{id_gry}] Brak gracza w turze (podsumowanie?). ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break
                if not (0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze)): 
                    # print(f"[{id_gry}] Błędny indeks gracza. ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break 
                
                gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx]
                if not gracz_w_turze: 
                    # print(f"[{id_gry}] Błąd obiektu gracza. ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break 

                slot_gracza = next((s for s in partia_w_petli["slots"] if s["nazwa"] == gracz_w_turze.nazwa), None)

                # Jeśli to nie jest tura bota, przerwij pętlę
                if not slot_gracza or slot_gracza["typ"] == "czlowiek":
                    # print(f"[{id_gry}] Tura człowieka ({gracz_w_turze.nazwa}). ZWALNIAM BLOKADĘ.") # Opcjonalny log
                    break # Zakończ pętlę, zwolnij blokadę

                # --- TURA BOTA ---
                # (Reszta kodu... od 'print(f"[{id_gry}] Tura bota..." do końca)
                print(f"[{id_gry}] Tura gracza: {gracz_w_turze.nazwa}")

                # Anuluj timer poprzedniego gracza (jeśli istniał - boty nie mają timerów)
                if partia_w_petli.get("timer_task") and not partia_w_petli["timer_task"].done():
                    partia_w_petli["timer_task"].cancel()

                # Małe opóźnienie, aby dać UI czas na odświeżenie (opcjonalne)
                await asyncio.sleep(0.1)
                #Logika wyboru ruchu bota 
                bot_algorithm_name = slot_gracza.get("bot_algorithm", default_bot_name)
                bot_instance = bot_instances.get(bot_algorithm_name, bot_instances[default_bot_name]) # Pobierz instancję
                if not bot_instance: # Fallback do domyślnego, jeśli nazwa jest nieprawidłowa
                    print(f"OSTRZEŻENIE: Nieznany algorytm bota '{bot_algorithm_name}', używam domyślnego '{default_bot_name}'.")
                    bot_instance = bot_instances[default_bot_name]
                # --- Wywołaj logikę bota ---
                akcja_bota = None
                try:
                    # print(f"BOT ({bot_algorithm_name.upper()}) ({gracz_w_turze.nazwa}): Myślenie...")
                    start_time = time.time()
                    # print(f"BOT ({bot_algorithm_name.upper()}) ({gracz_w_turze.nazwa}): Myślenie...")
                    # Wywołaj metodę bota, aby znaleźć najlepszy ruch
                    akcja_bota = await asyncio.to_thread(
                        bot_instance.znajdz_najlepszy_ruch,
                        poczatkowy_stan_gry=rozdanie,
                        nazwa_gracza_bota=gracz_w_turze.nazwa
                    )
                    end_time = time.time()
                    # print(f"BOT ({bot_algorithm_name.upper()}) ({gracz_w_turze.nazwa}): Wybrana akcja: {akcja_bota} (Czas: {end_time - start_time:.3f}s)")
                except Exception as e:
                    # Złap błędy z logiki bota
                    print(f"!!! KRYTYCZNY BŁĄD BOTA MCTS dla {gracz_w_turze.nazwa} w grze {id_gry}: {e}")
                    traceback.print_exc()
                    break # Przerwij pętlę w razie błędu bota

                # --- Obsługa przypadku, gdy bot nie zwrócił akcji ---
                if not akcja_bota or 'typ' not in akcja_bota:
                    print(f"INFO: Bot {gracz_w_turze.nazwa} nie miał ruchu (MCTS zwrócił pustą akcję). Faza: {rozdanie.faza}")
                    # Spróbuj wymusić PAS w fazach licytacyjnych jako fallback
                    if rozdanie.faza not in [silnik_gry.FazaGry.ROZGRYWKA, silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]:
                        mozliwe_akcje_bota = rozdanie.get_mozliwe_akcje(gracz_w_turze)
                        akcja_pas_bota = next((a for a in mozliwe_akcje_bota if 'pas' in a.get('typ','')), None)
                        if akcja_pas_bota:
                            print(f"INFO: Bot {gracz_w_turze.nazwa} wymusza PAS.")
                            akcja_bota = akcja_pas_bota # Użyj akcji PAS
                        else:
                            break # Jeśli even PAS nie jest możliwy, przerwij
                    else: # W rozgrywce brak ruchu oznacza błąd
                         break

                # --- Odejmowanie Czasu dla Bota (jeśli rankingowa) ---
                if (partia_w_petli.get("opcje", {}).get("rankingowa", False) and
                    partia_w_petli.get("tura_start_czas") is not None and
                    gracz_w_turze.nazwa in partia_w_petli.get("timery", {})):

                    czas_teraz = time.time()
                    czas_zuzyty = czas_teraz - partia_w_petli["tura_start_czas"]
                    partia_w_petli["timery"][gracz_w_turze.nazwa] -= czas_zuzyty # Odejmij zużyty czas
                    partia_w_petli["tura_start_czas"] = None # Zresetuj czas startu tury
                    # print(f"[{id_gry}] Bot {gracz_w_turze.nazwa} zużył {czas_zuzyty:.2f}s.") # Opcjonalny log

                # Anuluj zadanie timera bota (jeśli istniało)
                if partia_w_petli.get("timer_task") and not partia_w_petli["timer_task"].done():
                    partia_w_petli["timer_task"].cancel()

                # --- Wykonaj akcję bota w silniku gry ---
                try:
                    if akcja_bota['typ'] == 'zagraj_karte':
                        # Znajdź obiekt karty w ręce bota
                        karta_do_zagrania = next((k for k in gracz_w_turze.reka if k == akcja_bota.get('karta_obj')), None)
                        # Sprawdź legalność (dodatkowe zabezpieczenie)
                        if karta_do_zagrania and rozdanie._waliduj_ruch(gracz_w_turze, karta_do_zagrania):
                            rozdanie.zagraj_karte(gracz_w_turze, karta_do_zagrania)
                        else: # Jeśli bot wybrał nielegalną kartę (błąd MCTS?)
                            print(f"OSTRZEŻENIE: Bot {gracz_w_turze.nazwa} próbował zagrać nielegalną kartę: {akcja_bota.get('karta_obj')}. Wybieram losową legalną.")
                            # Wybierz losową legalną kartę jako fallback
                            legalne_karty = [k for k in gracz_w_turze.reka if rozdanie._waliduj_ruch(gracz_w_turze, k)]
                            if legalne_karty:
                                losowa_karta = random.choice(legalne_karty)
                                rozdanie.zagraj_karte(gracz_w_turze, losowa_karta)
                            else: # Jeśli nie ma legalnych kart (bardzo rzadki błąd)
                                print(f"BŁĄD KRYTYCZNY: Bot {gracz_w_turze.nazwa} nie ma legalnych kart do zagrania.")
                                break # Przerwij pętlę
                    else: # Akcja licytacyjna bota
                        # Sprawdź legalność akcji (dodatkowe zabezpieczenie)
                        legalne_akcje = rozdanie.get_mozliwe_akcje(gracz_w_turze)
                        # Porównaj słowniki akcji (typ, kontrakt, atut)
                        czy_legalna = any(
                            a['typ'] == akcja_bota.get('typ') and
                            a.get('kontrakt') == akcja_bota.get('kontrakt') and
                            a.get('atut') == akcja_bota.get('atut')
                            for a in legalne_akcje
                        )
                        if czy_legalna:
                            rozdanie.wykonaj_akcje(gracz_w_turze, akcja_bota)
                        else: # Jeśli bot wybrał nielegalną akcję
                            print(f"OSTRZEŻENIE: Bot {gracz_w_turze.nazwa} próbował wykonać nielegalną akcję licytacyjną: {akcja_bota}. Wybieram losową legalną.")
                            # Wybierz losową legalną akcję jako fallback
                            if legalne_akcje:
                                 losowa_akcja = random.choice(legalne_akcje)
                                 rozdanie.wykonaj_akcje(gracz_w_turze, losowa_akcja)
                            else: # Jeśli nie ma legalnych akcji (błąd)
                                print(f"BŁĄD KRYTYCZNY: Bot {gracz_w_turze.nazwa} nie ma legalnych akcji licytacyjnych.")
                                break # Przerwij pętlę
                except Exception as e:
                    # Złap błędy podczas wykonywania akcji przez silnik gry
                    print(f"BŁĄD podczas wykonywania akcji BOTA {gracz_w_turze.nazwa} w grze {id_gry}: {e}. Akcja: {akcja_bota}")
                    traceback.print_exc()
                    break # Przerwij pętlę

                # --- Po ruchu bota ---
                # Wyślij zaktualizowany stan gry do wszystkich klientów
                await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))

                # Uruchom timer dla następnego gracza (jeśli jest człowiekiem i gra rankingowa)
                await uruchom_timer_dla_tury(id_gry)

                # Krótka pauza przed następną iteracją (dla płynności i uniknięcia 100% CPU)
                await asyncio.sleep(0.5) # Zmniejszono pauzę dla szybszej gry botów
        
        # Blokada 'async with lock:' została automatycznie zwolniona
        # print(f"[{id_gry}] Pętla botów zakończona, blokada zwolniona.") # Opcjonalny log
    
    else:
        # print(f"[{id_gry}] Pętla botów już działa (lock zajęty). Pomijam.") # Opcjonalny log
        pass # Pętla już działa, nic nie rób


# ==========================================================================
# SEKCJA 12.5: MENEDŻER BOTÓW "ELO WORLD"
# ==========================================================================

# --- KONFIGURACJA MENEDŻERA BOTÓW "ELO WORLD" ---
# Ta lista będzie zawierać nazwy użytkowników botów, którzy mają aktywnie
# wyszukiwać i tworzyć gry. Pobierzemy ją z bazy danych przy starcie serwera.
AKTYWNE_BOTY_ELO_WORLD: list[tuple[str, str]] = [] # Lista krotek (nazwa_bota, algorytm)

# Maksymalna liczba gier, które boty mogą hostować jednocześnie
MAX_GAMES_HOSTED_BY_BOTS = 5
# Maksymalna liczba wszystkich gier (ludzkich + botów), zanim boty przestaną tworzyć nowe
MAX_TOTAL_GAMES_ON_SERVER = 20
# Co ile sekund menedżer botów ma sprawdzać stan gier
ELO_WORLD_TICK_RATE = 15.0 # (w sekundach)


async def zaladuj_aktywne_boty_z_bazy():
    """
    Pobiera listę botów (z ich algorytmami) z bazy danych przy starcie serwera.
    """
    global AKTYWNE_BOTY_ELO_WORLD
    print("[Elo World] Ładowanie kont botów z bazy danych...")
    AKTYWNE_BOTY_ELO_WORLD.clear()
    
    try:
        # Używamy poprawnej nazwy 'async_sessionmaker'
        async with async_sessionmaker() as session:
            # Używamy User.settings do identyfikacji botów i ich algorytmów
            query = select(User.username, User.settings).where(User.settings.like('%"jest_botem": true%'))
            result = await session.execute(query)
            bot_users = result.all()
            
            for username, settings_json in bot_users:
                try:
                    settings = json.loads(settings_json)
                    algorytm = settings.get("algorytm")
                    if algorytm and algorytm in bot_instances: # Sprawdź, czy algorytm jest wspierany
                        AKTYWNE_BOTY_ELO_WORLD.append((username, algorytm))
                    else:
                        print(f"  - Ostrzeżenie: Bot {username} ma nieznany algorytm: {algorytm}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  - Błąd: Nie można sparsować ustawień JSON dla bota {username} (Ustawienia: {settings_json})")
                    
        print(f"[Elo World] Załadowano {len(AKTYWNE_BOTY_ELO_WORLD)} aktywnych botów.")
        if not AKTYWNE_BOTY_ELO_WORLD:
            print("[Elo World] Ostrzeżenie: Nie znaleziono żadnych kont botów w bazie danych.")
            print("[Elo World] Uruchom skrypt 'create_bots.py', aby je stworzyć.")
            
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY podczas ładowania botów z bazy danych: {e}")
        traceback.print_exc()


async def elo_world_manager():
    """
    Główna pętla Menedżera Botów. Działa w tle, tworzy lobby, dołącza do gier
    i zarządza stanem gotowości botów.
    """
    # Poczekaj chwilę na pełny start serwera
    await asyncio.sleep(5.0) 
    
    # Najpierw załaduj boty z bazy
    await zaladuj_aktywne_boty_z_bazy()

    print("[Elo World] Menedżer botów uruchomiony.")
    
    while True:
        try:
            # Poczekaj na następny "tick"
            await asyncio.sleep(ELO_WORLD_TICK_RATE)
            CZAS_ZYCIA_ZAKONCZONEJ_GRY_S = 10 # 10 se kund
            
            # Użyj list(gry.items()), aby bezpiecznie modyfikować słownik gry podczas iteracji
            for id_gry, partia in list(gry.items()):
                if partia.get("status_partii") == "ZAKONCZONA":
                    
                    if "czas_zakonczenia_gry" not in partia:
                        # Gra właśnie się zakończyła, ustaw jej timestamp
                        partia["czas_zakonczenia_gry"] = time.time()
                    else:
                        # Gra ma timestamp, sprawdź, czy jest wystarczająco stara
                        if (time.time() - partia["czas_zakonczenia_gry"]) > CZAS_ZYCIA_ZAKONCZONEJ_GRY_S:
                            print(f"[Garbage Collector] Usuwam starą zakończoną grę: {id_gry}")
                            try:
                                # Usuń z globalnego słownika gier
                                del gry[id_gry] 
                                
                                # Usuń również z menedżera połączeń (jeśli istnieją wiszące)
                                if id_gry in manager.active_connections:
                                    del manager.active_connections[id_gry]
                            except KeyError:
                                pass # Bez problemu, jeśli już usunięto
            
            if not AKTYWNE_BOTY_ELO_WORLD:
                # Jeśli nie ma botów, nie rób nic
                continue

            # Użyj kopii listy gier, aby uniknąć problemów z jednoczesną modyfikacją
            gry_copy = list(gry.values())
            CZAS_NA_GOTOWOSC_S = 30.0 # Czas w sekundach na kliknięcie "Gotowy"
            
            for partia in gry_copy:
                rozdanie = partia.get("aktualne_rozdanie")
                # Sprawdź, czy gra jest W_TRAKCIE, ma podsumowanie i nie była już wymuszona
                if (partia.get("status_partii") == "W_TRAKCIE" and 
                    rozdanie and rozdanie.podsumowanie and 
                    not partia.get("wymuszono_nastepna_runde", False)): # Flaga, by zrobić to tylko raz
                    
                    if "czas_konca_rundy" not in partia:
                        # Runda właśnie się zakończyła, ustaw timer
                        partia["czas_konca_rundy"] = time.time()
                    else:
                        # Timer już tyka, sprawdź czy minął
                        if (time.time() - partia["czas_konca_rundy"]) > CZAS_NA_GOTOWOSC_S:
                            print(f"[Elo World] Wykryto AFK w lobby {partia['id_gry']}. Wymuszam następną rundę.")
                            
                            # Znajdź wszystkich ludzi, którzy NIE są gotowi
                            ludzie_afk = [
                                s["nazwa"] for s in partia["slots"] 
                                if s["typ"] == "czlowiek" and s["nazwa"] not in partia.get("gracze_gotowi", [])
                            ]
                            
                            # "Kliknij" za każdego AFK-era
                            for afk_player in ludzie_afk:
                                partia.setdefault("gracze_gotowi", []).append(afk_player)
                            
                            # Ustaw flagę, aby nie robić tego wielokrotnie w tej rundzie
                            partia["wymuszono_nastepna_runde"] = True 
                            
                            # Wykonawcą akcji musi być ktoś z gry (np. host)
                            wykonawca_akcji = partia.get("host")
                            if not wykonawca_akcji: # Awaryjny fallback
                                wykonawca_akcji = partia["slots"][0]["nazwa"]

                            # Wywołaj akcję (teraz warunek gotowości powinien być spełniony)
                            if wykonawca_akcji:
                                dane_akcji = {"gracz": wykonawca_akcji, "akcja": {"typ": "nastepne_rozdanie"}}
                                await przetworz_akcje_gracza(dane_akcji, partia)
                                await manager.broadcast(partia["id_gry"], pobierz_stan_gry(partia["id_gry"]))
                                asyncio.create_task(uruchom_petle_botow(partia["id_gry"]))
            
            # --- Zidentyfikuj "bezrobotne" boty ---
            boty_w_grze = set()
            boty_hostujace_lobby = set()
            boty_w_podsumowaniu = {} # Mapa {bot_name: partia}
            boty_w_lobby_goscia = set()

            # Zbierz nazwy wszystkich aktywnych botów (dla szybszego sprawdzania)
            wszystkie_aktywne_boty = {bot[0] for bot in AKTYWNE_BOTY_ELO_WORLD}

            for partia in gry_copy:
                status_gry = partia.get("status_partii")

                # Zliczaj boty jako "zajęte" tylko jeśli gra jest aktywna
                if status_gry == "LOBBY" or status_gry == "W_TRAKCIE":

                    if status_gry == "LOBBY" and partia["host"] in wszystkie_aktywne_boty:
                        boty_hostujace_lobby.add(partia["host"])

                    for slot in partia.get("slots", []):
                        bot_name = slot.get("nazwa")
                        if bot_name in wszystkie_aktywne_boty: 
                            boty_w_grze.add(bot_name) # Dodaj do ogólnej puli zajętych
                            if status_gry == "LOBBY" and bot_name != partia.get("host"):
                                 boty_w_lobby_goscia.add(bot_name)
                             
                # Sprawdź boty, które muszą kliknąć "Następne rozdanie"
                rozdanie = partia.get("aktualne_rozdanie")
                if partia.get("status_partii") == "W_TRAKCIE" and rozdanie and rozdanie.podsumowanie:
                    gotowi = partia.get("gracze_gotowi", [])
                    for slot in partia.get("slots", []):
                        # Sprawdzamy sloty typu 'bot' LUB sloty naszych aktywnych botów
                        # (na wypadek, gdyby typ się jeszcze nie zaktualizował)
                        if slot.get("nazwa") in wszystkie_aktywne_boty and slot.get("nazwa") not in gotowi:
                            boty_w_podsumowaniu[slot["nazwa"]] = partia

            # Boty bezrobotne = Wszystkie boty - Boty w grze/lobby
            boty_bezrobotne = [bot for bot in AKTYWNE_BOTY_ELO_WORLD if bot[0] not in boty_w_grze]
            liczba_lobby_botow = len(boty_hostujace_lobby)

            # --- AKCJE MENEDŻERA ---

            # 1. Obsłuż boty czekające na następne rozdanie
            for bot_name, partia in boty_w_podsumowaniu.items():
                if partia.get("id_gry") in gry: # Sprawdź, czy gra nadal istnieje
                    print(f"[Elo World] Bot {bot_name} klika 'Następne rozdanie' w grze {partia['id_gry']}")
                    await asyncio.sleep(random.uniform(1.0, 5.0))
                    dane_akcji = {"gracz": bot_name, "akcja": {"typ": "nastepne_rozdanie"}}
                    await przetworz_akcje_gracza(dane_akcji, partia) # Wywołaj akcję
                    # Po tej akcji może nastąpić broadcast i uruchomienie pętli botów
                    await manager.broadcast(partia["id_gry"], pobierz_stan_gry(partia["id_gry"]))
                    asyncio.create_task(uruchom_petle_botow(partia["id_gry"]))


            # 2. Sprawdź, czy boty-hosty mogą rozpocząć swoje gry
            for bot_host_name in boty_hostujace_lobby:
                partia = next((p for p in gry_copy if p.get("host") == bot_host_name and p.get("status_partii") == "LOBBY"), None)
            
                # Teraz sprawdzamy już tylko, czy lobby jest pełne
                if partia and all(s["typ"] != "pusty" for s in partia["slots"]):
                        print(f"[Elo World] Bot-host {bot_host_name} uruchamia grę {partia['id_gry']}!")
                        dane_akcji = {"gracz": bot_host_name, "akcja_lobby": "start_gry"}
                        await przetworz_akcje_gracza(dane_akcji, partia) # Wywołaj akcję
                        await manager.broadcast(partia["id_gry"], pobierz_stan_gry(partia["id_gry"]))
                        asyncio.create_task(uruchom_petle_botow(partia["id_gry"]))
            
            # 3. Przydziel "bezrobotne" boty
            random.shuffle(boty_bezrobotne) # Losowa kolejność
            for bot_name, bot_algorytm in boty_bezrobotne:
                
                # --- A. Spróbuj dołączyć do istniejącego lobby ---
                lobby_do_dolaczenia = None
                for partia in gry_copy:
                    if (partia.get("status_partii") == "LOBBY" and 
                        partia.get("opcje", {}).get("rankingowa", False) and # Tylko rankingowe
                        not partia.get("opcje", {}).get("haslo")): # Tylko publiczne
                        
                        puste_sloty = [s for s in partia["slots"] if s["typ"] == "pusty"]
                        if puste_sloty:
                            lobby_do_dolaczenia = partia
                            slot_do_zajecia = puste_sloty[0] # Weź pierwszy wolny
                            break
                            
                if lobby_do_dolaczenia:
                    print(f"[Elo World] Gracz {bot_name} dołącza do lobby {lobby_do_dolaczenia['id_gry']} (slot {slot_do_zajecia['slot_id']})")
                    # Ręcznie zaktualizuj slot, bo bot nie ma Websocketa
                    slot_do_zajecia.update({
                        "nazwa": bot_name, 
                        "typ": "bot", # Ważne: oznaczamy jako 'bot'
                        "bot_algorithm": bot_algorytm
                    })
                    # Poinformuj wszystkich o zmianie w lobby
                    await manager.broadcast(lobby_do_dolaczenia["id_gry"], pobierz_stan_gry(lobby_do_dolaczenia["id_gry"]))
                    await asyncio.sleep(random.uniform(2.0, 7.0)) # Losowe opóźnienie 2-7 sekund
                    continue # Przejdź do następnego bezrobotnego bota

                # --- B. Jeśli nie dołączył, spróbuj stworzyć nowe lobby ---
                if (liczba_lobby_botow < MAX_GAMES_HOSTED_BY_BOTS and 
                    len(gry) < MAX_TOTAL_GAMES_ON_SERVER):
                    
                    print(f"[Elo World] Gracz {bot_name} tworzy nowe lobby rankingowe...")
                    try:
                        # Użyj logiki z endpointu /gra/stworz
                        tryb_gry_bota = '3p' if random.random() < 0.33 else '4p' # 33% szansy na 3p
                        request_bota = CreateGameRequest(
                            nazwa_gracza=bot_name,
                            tryb_gry=tryb_gry_bota, # Boty domyślnie grają 4p
                            tryb_lobby='online',
                            publiczna=True,
                            haslo=None,
                            czy_rankingowa=True
                        )
                        # Wywołaj funkcję synchroniczną bezpośrednio
                        stworz_gre(request_bota) 
                        liczba_lobby_botow += 1
                        await asyncio.sleep(random.uniform(2.0, 15.0)) # Opóźnienie stworzenia lobby
                    except Exception as e:
                        print(f"BŁĄD KRYTYCZNY: Bot {bot_name} nie mógł stworzyć gry: {e}")
                        traceback.print_exc()

        except asyncio.CancelledError:
            print("[Elo World] Menedżer botów zatrzymany (CancelledError).")
            break
        except Exception as e:
            print(f"BŁĄD KRYTYCZNY w pętli Menedżera Botów: {e}")
            traceback.print_exc()
            # Poczekaj dłużej po błędzie, aby uniknąć pętli błędów
            await asyncio.sleep(60.0)

# ==========================================================================
# SEKCJA 13: GŁÓWNY ENDPOINT WEBSOCKET
# ==========================================================================

@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str, haslo: Optional[str] = Query(None)):
    """
    Główna funkcja obsługująca połączenie WebSocket dla pojedynczego gracza.
    Zarządza dołączaniem do gry/lobby, powrotem do gry, odbieraniem i przetwarzaniem
    akcji gracza oraz rozłączaniem.
    """
    partia = gry.get(id_gry)

    # --- Sprawdzenie istnienia gry i hasła ---
    if not partia:
        await websocket.accept() # Zaakceptuj, aby wysłać powód zamknięcia
        await websocket.close(code=1008, reason="Gra nie istnieje.")
        return

    opcje = partia.get("opcje", {})
    haslo_lobby = opcje.get("haslo")
    # Jeśli lobby ma hasło, sprawdź podane hasło
    if haslo_lobby and (haslo is None or haslo != haslo_lobby):
        await websocket.accept()
        await websocket.close(code=1008, reason="Nieprawidłowe hasło.")
        return

    # --- Połączenie ---
    await manager.connect(websocket, id_gry) # Dodaj do ConnectionManagera
    # Sprawdź, czy gracz nie został wcześniej wyrzucony
    if nazwa_gracza in partia.get("kicked_players", []):
        await websocket.close(code=1008, reason="Zostałeś wyrzucony z lobby.")
        manager.disconnect(websocket, id_gry) # Usuń z managera
        return

    try:
        # --- Obsługa Dołączania do Lobby ---
        if partia["status_partii"] == "LOBBY":
            # Sprawdź, czy gracz nie jest już w lobby (np. otworzył drugą kartę)
            if not any(s['nazwa'] == nazwa_gracza for s in partia['slots']):
                 # Znajdź pierwszy wolny slot
                 slot = next((s for s in partia["slots"] if s["typ"] == "pusty"), None)
                 if slot: # Jeśli znaleziono wolny slot
                     slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                     # Jeśli lobby było puste, ustaw gracza jako hosta
                     if not partia["host"]: partia["host"] = nazwa_gracza
                     # Wyślij zaktualizowany stan lobby do wszystkich
                     await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
                 else: # Lobby jest pełne
                     await websocket.close(code=1008, reason="Lobby jest pełne.")
                     manager.disconnect(websocket, id_gry)
                     return

        # --- Obsługa Powrotu do Gry (Reconnect) ---
        elif partia["status_partii"] == "W_TRAKCIE":
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)

            # Jeśli gracz nie był częścią tej gry, odrzuć połączenie
            if not slot_gracza:
                await websocket.close(code=1008, reason="Gra jest w toku, nie możesz dołączyć.")
                manager.disconnect(websocket, id_gry) # Usuń z managera
                return

            typ_slotu = slot_gracza.get("typ")

            if typ_slotu == "rozlaczony": # Gracz wraca po rozłączeniu
                print(f"[{id_gry}] Gracz {nazwa_gracza} dołączył ponownie.")
                # Zmień status slotu z powrotem na 'czlowiek'
                slot_gracza["typ"] = "czlowiek"
                slot_gracza["disconnect_time"] = None # Wyczyść czas rozłączenia

                # Anuluj zadanie zastępujące bota (jeśli działało)
                task = slot_gracza.get("disconnect_task")
                if task and not task.done():
                    task.cancel()
                    print(f"[{id_gry}] Anulowano timer zastępujący bota dla slotu {slot_gracza.get('slot_id')}.")
                    slot_gracza["disconnect_task"] = None

                # Uruchom ponownie timer tury, jeśli to była tura tego gracza i gra jest rankingowa
                await uruchom_timer_dla_tury(id_gry)

            elif typ_slotu == "czlowiek": # Gracz połączył się ponownie (np. odświeżył stronę)
                print(f"[{id_gry}] Gracz {nazwa_gracza} połączył się ponownie (status W_TRAKCIE).")
            # Jeśli typ_slotu to 'bot', nie pozwól człowiekowi dołączyć na jego miejsce (chociaż to nie powinno się zdarzyć)

        # --- Wysyłanie Stanu Początkowego / Uruchomienie Pętli Botów ---
        # Wyślij aktualny stan gry do nowo podłączonego gracza (i pozostałych)
        # (W lobby stan jest wysyłany przy dołączaniu do slotu)
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))

        # Uruchom pętlę botów (jeśli jest tura bota)
        asyncio.create_task(uruchom_petle_botow(id_gry))

        # --- Główna Pętla Odbierania Wiadomości od Klienta ---
        while True:
            data = await websocket.receive_json() # Czekaj na wiadomość od klienta
            partia = gry.get(id_gry) # Odśwież referencję do stanu gry (mógł się zmienić)
            if not partia: break # Jeśli gra została usunięta, zakończ pętlę

            # --- Obsługa Wiadomości Czatowych ---
            if data.get("typ_wiadomosci") == "czat":
                 # Sprawdź, czy nadawca jest faktycznie w grze
                 if any(s['nazwa'] == data.get("gracz") for s in partia['slots']):
                      await manager.broadcast(id_gry, data) # Rozgłoś wiadomość czatu
                 continue # Przejdź do następnej iteracji pętli

            # --- Obsługa Akcji Gry/Lobby ---
            # Sprawdź, czy akcja pochodzi od gracza, którego jest aktualnie tura
            aktualne_rozdanie = partia.get("aktualne_rozdanie")
            gracz_w_turze_nazwa = None
            if aktualne_rozdanie and aktualne_rozdanie.kolej_gracza_idx is not None:
                # Zabezpieczenie przed błędnym indeksem
                if 0 <= aktualne_rozdanie.kolej_gracza_idx < len(aktualne_rozdanie.gracze):
                    gracz_w_turze_nazwa = aktualne_rozdanie.gracze[aktualne_rozdanie.kolej_gracza_idx].nazwa

            # Zezwalaj na akcje systemowe, akcje lobby, lub akcje od gracza w turze
            akcja_systemowa = data.get('akcja', {}).get('typ') in ['nastepne_rozdanie', 'finalizuj_lewe']
            akcja_lobby = 'akcja_lobby' in data
            czyj_ruch = data.get("gracz") == gracz_w_turze_nazwa
            akcja_po_grze = partia["status_partii"] == "ZAKONCZONA"

            if czyj_ruch or akcja_systemowa or akcja_lobby or partia["status_partii"] == "LOBBY" or akcja_po_grze:
                # 1. Przetwórz akcję gracza (wywołuje logikę silnika gry)
                await przetworz_akcje_gracza(data, partia)

                # 2. Pobierz NOWY stan gry po przetworzeniu akcji
                nowy_stan = pobierz_stan_gry(id_gry)

                # 3. Wyślij nowy stan do wszystkich podłączonych graczy
                await manager.broadcast(id_gry, nowy_stan)

                # 4. Uruchom pętlę botów (jeśli teraz jest tura bota)
                asyncio.create_task(uruchom_petle_botow(id_gry))
            else:
                 # Odrzuć akcję, jeśli nie spełnia warunków
                 print(f"[{id_gry}] Odrzucono akcję od {data.get('gracz')}. Tura: {gracz_w_turze_nazwa}")

    # --- Obsługa Rozłączenia Klienta ---
    except WebSocketDisconnect:
        print(f"[{id_gry}] Gracz {nazwa_gracza} rozłączył się.")
        manager.disconnect(websocket, id_gry) # Usuń z ConnectionManagera
        partia = gry.get(id_gry) # Pobierz stan gry ponownie

        stan_zmieniony = False # Flaga, czy trzeba wysłać broadcast
        lobby_usunięte = False # Flaga, czy lobby zostało usunięte

        if partia: # Sprawdź, czy gra nadal istnieje
            if partia["status_partii"] == "LOBBY": # Rozłączenie w lobby
                 slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
                 
                 if slot_gracza: # Jeśli gracz zajmował slot
                     # Opróżnij slot
                     slot_gracza.update({"typ": "pusty", "nazwa": None, "bot_algorithm": None})
                     
                     # Logika przekazywania hosta
                     if partia["host"] == nazwa_gracza:
                         # 1. Spróbuj przekazać innemu człowiekowi
                         nowy_host = next((s["nazwa"] for s in partia["slots"] if s["typ"] == "czlowiek"), None)
                         
                         if not nowy_host:
                             # 2. Jeśli nie ma ludzi, przekaż botowi (naszemu 'elo world' LUB zwykłemu)
                             nowy_host = next((s["nazwa"] for s in partia["slots"] if s["typ"] == "bot"), None)
                         
                         partia["host"] = nowy_host # Może być None, jeśli lobby jest puste
                         
                     stan_zmieniony = True

                 # Sprawdź, czy lobby jest teraz CAŁKOWICIE puste
                 if partia.get("tryb_lobby") == "online":
                     # Sprawdzamy, czy WSZYSTKIE sloty są "pusty"
                     czy_lobby_puste = all(s.get("typ") == "pusty" for s in partia.get("slots", []))
                     
                     if czy_lobby_puste:
                         OKRES_OCHRONNY_S = 10 # 10 sekund
                         czas_stworzenia = partia.get("czas_stworzenia", 0)
                         
                         if (time.time() - czas_stworzenia) < OKRES_OCHRONNY_S:
                             # Lobby jest w okresie ochronnym, nie usuwaj go
                             print(f"[{id_gry}] Lobby jest w 10s okresie ochronnym. Ignorowanie rozłączenia (prawdopodobnie hosta).")
                         else:
                             # Lobby jest stare i puste, usuń je
                             print(f"Lobby {id_gry} (host: {partia.get('host')}) jest teraz całkowicie puste. Usuwanie...")
                             try:
                                 del gry[id_gry] # Usuń grę
                                 lobby_usunięte = True
                                 stan_zmieniony = False 
                                 if id_gry in manager.active_connections:
                                      del manager.active_connections[id_gry]
                             except KeyError:
                                 print(f"[{id_gry}] Nie można było usunąć lobby (może już usunięte).")
            elif partia["status_partii"] == "W_TRAKCIE": # Rozłączenie w trakcie gry
                print(f"Gracz {nazwa_gracza} rozłączył się w trakcie gry {id_gry}.")
                slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)

                # --- Zarządzanie Timerami przy Rozłączeniu ---
                # Wstrzymaj timer tury (jeśli gra rankingowa i timer działał)
                if partia.get("opcje", {}).get("rankingowa", False):
                    if partia.get("timer_task") and not partia["timer_task"].done():
                        partia["timer_task"].cancel()
                        print(f"[{id_gry}] Timer tury wstrzymany z powodu rozłączenia gracza.")

                # Oznacz slot jako rozłączony i uruchom timer zastępujący bota (dla gier nierankingowych)
                if slot_gracza and slot_gracza.get('typ') == 'czlowiek':
                     slot_gracza['typ'] = 'rozlaczony'
                     slot_gracza['disconnect_time'] = time.time() # Zapisz czas rozłączenia
                     # Uruchom `replacement_timer` tylko jeśli gra NIE jest rankingowa
                     if not partia.get("opcje", {}).get("rankingowa", False):
                         task = asyncio.create_task(replacement_timer(id_gry, slot_gracza["slot_id"]))
                         slot_gracza['disconnect_task'] = task # Zapisz referencję do zadania
                     else:
                         print(f"[{id_gry}] Gra rankingowa, gracz {nazwa_gracza} nie zostanie zastąpiony botem.")
                     stan_zmieniony = True

        # --- Wyslij aktualizację stanu po rozłączeniu (jeśli trzeba) ---
        if stan_zmieniony and not lobby_usunięte and partia:
             try:
                 # Wyślij zaktualizowany stan do pozostałych graczy
                 await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
                 # Uruchom pętlę botów (może to teraz tura bota zastępującego)
                 asyncio.create_task(uruchom_petle_botow(id_gry))
             except Exception as broadcast_error:
                 # Błąd broadcastu może wystąpić, jeśli wszyscy się rozłączyli
                 print(f"INFO: Nie udało się wysłać broadcastu po rozłączeniu gracza {nazwa_gracza} w grze {id_gry}: {broadcast_error}")

    # --- Obsługa Niespodziewanych Błędów WebSocket ---
    except Exception as e:
        print(f"!!! KRYTYCZNY BŁĄD WEBSOCKET DLA GRY {id_gry} !!! Gracz: {nazwa_gracza}")
        print(f"Typ błędu: {type(e).__name__}")
        traceback.print_exc() # Wydrukuj pełny traceback błędu

        # Spróbuj wysłać informację o błędzie do pozostałych graczy
        try:
            if id_gry in manager.active_connections:
                 await manager.broadcast(id_gry, {"error": "Krytyczny błąd serwera. Gra może być niestabilna.", "details": str(e)})
        except Exception as broadcast_error:
            print(f"BŁĄD podczas broadcastu błędu krytycznego: {broadcast_error}")

        # Spróbuj zamknąć problematyczne połączenie
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except RuntimeError as close_error:
            # Błąd może wystąpić, jeśli połączenie jest już zamknięte
            print(f"Info: Błąd podczas zamykania websocket po krytycznym błędzie: {close_error}")

        # Zawsze usuń połączenie z managera po błędzie
        manager.disconnect(websocket, id_gry)