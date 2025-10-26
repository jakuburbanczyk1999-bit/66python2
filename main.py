# main.py
import uuid
import random
import json
import asyncio
import string
import traceback
import time
from typing import Any, Optional, AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel 
from database import init_db, async_session_maker, User
from auth_utils import hash_password, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager

import silnik_gry
import boty  # Import modułu botów

# --- Modele danych ---
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
    nazwa_gracza: str
    tryb_gry: str # '4p' lub '3p'
    tryb_lobby: str # 'online' lub 'lokalna'
    publiczna: bool # NOWE
    haslo: Optional[str] = None # NOWE

class UserSettings(BaseModel):
    czatUkryty: bool
    historiaUkryta: bool
    partiaHistoriaUkryta: bool
    pasekEwaluacjiUkryty: bool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kod uruchamiany przy starcie (dawny 'startup')
    print("Serwer startuje... Inicjalizacja bazy danych.")
    await init_db()
    print("Baza danych jest gotowa.")

    yield # W tym miejscu aplikacja działa

    # Kod uruchamiany przy wyłączeniu (dawny 'shutdown')
    print("Serwer się zamyka.")
# --- Aplikacja FastAPI ---
app = FastAPI()
mcts_bot = boty.MCTS_Bot()  # Globalna instancja bota MCTS

@app.on_event("startup")
async def on_startup():
    """Inicjalizuje bazę danych przy starcie serwera."""
    print("Serwer startuje... Inicjalizacja bazy danych.")
    await init_db()
    print("Baza danych jest gotowa.")

# --- Przechowywanie stanu gier ---
gry = {}

# --- Stałe ---
NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]

# === Zarządzanie Połączeniami WebSocket ===
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]: # POPRAWKA: Sprawdź, czy websocket istnieje
                self.active_connections[game_id].remove(websocket)
            # Opcjonalnie: Dodaj logikę czyszczenia gry, jeśli nie ma już graczy

    async def broadcast(self, game_id: str, message: dict):
        if game_id in self.active_connections:
            # Własny serializator JSON dla obiektów gry
            def safe_serializer(o):
                if isinstance(o, (silnik_gry.Kolor, silnik_gry.Kontrakt, silnik_gry.FazaGry, silnik_gry.Ranga)):
                    return o.name
                if isinstance(o, silnik_gry.Karta):
                    return str(o)
                if isinstance(o, (silnik_gry.Gracz, silnik_gry.Druzyna)):
                    return o.nazwa
                # Obsłuż elegancko obiekty, których nie można serializować
                return f"<Nieserializowalny: {type(o).__name__}>"

            try:
                message_json = json.dumps(message, default=safe_serializer)
                # Użyj kopii listy, na wypadek gdyby disconnect zmienił ją w trakcie iteracji
                connections_copy = self.active_connections[game_id][:]
                tasks = [connection.send_text(message_json) for connection in connections_copy]
                if tasks: # POPRAWKA: Sprawdź, czy są jakieś zadania
                    await asyncio.gather(*tasks) # Wyślij równolegle
            except Exception as e:
                print(f"BŁĄD podczas serializacji lub broadcastu dla gry {game_id}: {e}")
                # Usunięto traceback, aby uniknąć potencjalnych problemów z zagnieżdżeniem wyjątków

manager = ConnectionManager()

# === Funkcje Pomocnicze ===

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Funkcja 'zależności' (dependency) FastAPI do zarządzania sesją bazy danych."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

def generuj_krotki_id(dlugosc=6) -> str:
    """Generuje unikalny, krótki identyfikator gry."""
    chars = string.ascii_uppercase + string.digits
    while True:
        kod = ''.join(random.choices(chars, k=dlugosc))
        if kod not in gry:
            return kod

def resetuj_gre_do_lobby(partia: dict):
    """Resetuje stan gry z powrotem do lobby."""
    partia["status_partii"] = "LOBBY"
    partia["gracze_engine"] = []
    partia["druzyny_engine"] = []
    partia["aktualne_rozdanie"] = None
    partia["pelna_historia"] = []
    partia["numer_rozdania"] = 1
    partia["historia_partii"] = []
    partia["kicked_players"] = []
    partia["gracze_gotowi"] = []
    partia['aktualna_ocena'] = None # POPRAWKA: Jawne czyszczenie oceny przy resecie

    if partia.get("max_graczy", 4) == 4:
        nazwy = partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
        partia["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
    else:
        # Upewnij się, że punkty są resetowane dla wszystkich slotów, które mają nazwę
        partia["punkty_meczu"] = {slot['nazwa']: 0 for slot in partia['slots'] if slot.get('nazwa')}

    print(f"Gra {partia.get('id_gry', 'N/A')} wraca do lobby.")


def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    """Konwertuje string karty (np. "As Czerwien") na obiekt Karta."""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
        mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
        ranga = mapowanie_rang[ranga_str]
        kolor = mapowanie_kolorow[kolor_str]
        return silnik_gry.Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        print(f"BŁĄD: Nie można przekonwertować stringa '{nazwa_karty}' na kartę: {e}")
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e

def sprawdz_koniec_partii(partia: dict) -> bool:
    """Sprawdza, czy gra osiągnęła warunek zwycięstwa (66 punktów)."""
    max_graczy = partia.get("max_graczy", 4)
    gracze_engine = partia.get("gracze_engine")
    druzyny_engine = partia.get("druzyny_engine")

    if max_graczy == 4 and druzyny_engine:
        for druzyna in druzyny_engine:
            if druzyna.punkty_meczu >= 66:
                partia["status_partii"] = "ZAKONCZONA"
                return True
    elif max_graczy == 3 and gracze_engine:
        gracze_powyzej_progu = [g for g in gracze_engine if g.punkty_meczu >= 66]
        if not gracze_powyzej_progu:
            return False
        if len(gracze_powyzej_progu) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True
        # Obsługa remisu w 3p: wygrywa najwyższy wynik
        najwyzszy_wynik = max(g.punkty_meczu for g in gracze_powyzej_progu)
        gracze_z_najwyzszym_wynikiem = [g for g in gracze_powyzej_progu if g.punkty_meczu == najwyzszy_wynik]
        if len(gracze_z_najwyzszym_wynikiem) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True
        else:
            # Prawdziwy remis, ale gra musi się skończyć - wybierzmy arbitralnie
            partia["status_partii"] = "ZAKONCZONA" # POPRAWKA: Zakończ grę przy remisie
            return True

    return False

# === Konfiguracja Plików Statycznych ===
app.mount("/static", StaticFiles(directory="static"), name="static")

# === Endpointy HTTP ===

@app.get("/")
def read_root():
    """Zwraca stronę startową (menu)."""
    return FileResponse('static/start.html')

@app.get("/gra.html")
def read_game_page():
    """Zwraca główną stronę gry."""
    return FileResponse('static/index.html')

@app.get("/lobby.html")
def read_lobby_browser_page():
    """Zwraca stronę przeglądarki lobby."""
    # Upewnij się, że ścieżka jest poprawna
    return FileResponse('static/lobby.html')

@app.get("/zasady.html")
def read_rules_page():
    """Zwraca stronę z zasadami gry."""
    return FileResponse('static/zasady.html')


@app.post("/register")
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Rejestruje nowego użytkownika."""

    # 1. Sprawdź, czy użytkownik już istnieje
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tej nazwie już istnieje."
        )

    # 2. Sprawdź hasło
    if len(user_data.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hasło musi mieć co najmniej 4 znaki."
        )

    # 3. Stwórz nowego użytkownika
    hashed_pass = hash_password(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pass)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # 4. Zwróć sukces (i "token" do logowania)
    # Na razie nasz "token" to po prostu nazwa użytkownika
    return Token(access_token=new_user.username, token_type="bearer", username=new_user.username)

@app.post("/login")
async def login_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Loguje istniejącego użytkownika i sprawdza, czy jest w aktywnej grze."""

    # 1. Znajdź użytkownika (bez zmian)
    query = select(User).where(User.username == user_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. Sprawdź użytkownika i hasło (bez zmian)
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło."
        )

    active_game_id_found = None
    try:
        gry_copy = list(gry.values()) # Bezpieczna kopia do iteracji
        for partia in gry_copy:
            if partia.get("status_partii") == "W_TRAKCIE":
                slots = partia.get("slots", [])
                # Szukaj slotu z TĄ nazwą użytkownika ORAZ statusem 'rozlaczony'
                slot_gracza = next((s for s in slots if s.get("nazwa") == user.username and s.get("typ") == "rozlaczony"), None)
                if slot_gracza:
                    active_game_id_found = partia.get("id_gry")
                    print(f"Użytkownik {user.username} znaleziony w aktywnej grze {active_game_id_found}")
                    break # Znaleziono grę, przerwij pętlę
    except RuntimeError:
         print("Ostrzeżenie: Słownik gier zmienił się podczas sprawdzania statusu logowania.")
    
    user_settings = None
    if user.settings:
        try:
            user_settings = json.loads(user.settings)
        except json.JSONDecodeError:
            print(f"Błąd dekodowania JSON ustawień dla użytkownika {user.username}")
            user_settings = None # Użyj domyślnych


    # 3. Zwróć sukces (i "token" oraz ID gry, jeśli znaleziono)
    return Token(
        access_token=user.username, 
        token_type="bearer", 
        username=user.username,
        active_game_id=active_game_id_found, # <-- DODANE ID GRY
        settings=user_settings
    )

@app.get("/check_active_game/{username}")
async def check_active_game(username: str):
    """Sprawdza, czy dany użytkownik ma aktywną grę, do której może wrócić."""
    active_game_id_found = None
    try:
        gry_copy = list(gry.values()) # Bezpieczna kopia
        for partia in gry_copy:
            if partia.get("status_partii") == "W_TRAKCIE":
                slots = partia.get("slots", [])
                # Szukaj slotu z TĄ nazwą użytkownika ORAZ statusem 'rozlaczony' LUB 'czlowiek'
                # (Jeśli jest 'czlowiek', ale połączenie WS nie istnieje, też może wrócić)
                slot_gracza = next((s for s in slots if s.get("nazwa") == username and s.get("typ") in ["rozlaczony", "czlowiek"]), None)
                if slot_gracza:
                    # Dodatkowo sprawdźmy, czy gracz faktycznie NIE jest połączony przez WebSocket
                    # (proste sprawdzenie - czy w ogóle są jakieś połączenia dla tej gry?)
                    # Lepsze byłoby śledzenie połączeń per użytkownik, ale to uproszczenie
                    jest_polaczony_ws = False
                    if partia.get("id_gry") in manager.active_connections:
                        # Tutaj przydałoby się bardziej szczegółowe sprawdzenie
                        # Na razie zakładamy, że jeśli slot istnieje, a gracz nie jest botem, to może wrócić
                        pass # Uproszczenie - pozwalamy wrócić, jeśli slot istnieje

                    if not jest_polaczony_ws: # Jeśli nie jest aktywnie połączony
                        active_game_id_found = partia.get("id_gry")
                        print(f"Znaleziono potencjalną grę do powrotu dla {username}: {active_game_id_found}")
                        break
    except RuntimeError:
         print("Ostrzeżenie: Słownik gier zmienił się podczas sprawdzania /check_active_game.")

    return {"active_game_id": active_game_id_found}

@app.get("/gra/lista_lobby")
def pobierz_liste_lobby():
    """Pobiera listę publicznych, otwartych lobby online."""
    lista_publiczna = []
    
    # Przeglądamy kopię wartości, aby uniknąć problemów z równoczesną modyfikacją
    try:
        gry_copy = list(gry.values())
    except RuntimeError:
        # Słownik zmienił się w trakcie iteracji, spróbuj ponownie za chwilę
        # W praktyce, przy małym ruchu, to się nie zdarzy, ale to bezpieczne
        return {"lobby_list": []} 

    for partia in gry_copy:
        try:
            opcje = partia.get("opcje", {})
            # Sprawdzamy warunki: LOBBY, online i publiczna
            status = partia.get("status_partii")
            if (status in ["LOBBY", "W_TRAKCIE"] and
                partia.get("tryb_gry") == "online"):
                
                # Zlicz ilu graczy jest w lobby
                slots = partia.get("slots", [])
                aktualni_gracze = sum(1 for s in slots if s.get("typ") != "pusty")
                max_gracze = partia.get("max_graczy", 4)

                # Zbuduj obiekt do wysłania
                lobby_info = {
                    "id_gry": partia.get("id_gry"),
                    "host": partia.get("host", "Brak hosta"),
                    "tryb_gry": opcje.get("tryb_gry", "4p"), # '4p' lub '3p'
                    "ma_haslo": bool(opcje.get("haslo")),
                    "aktualni_gracze": aktualni_gracze,
                    "max_gracze": max_gracze,
                    "status": status,  # <-- NOWE POLE
                    "gracze": [s.get("nazwa") for s in slots if s.get("nazwa")]
                }
                lista_publiczna.append(lobby_info)
        except Exception as e:
            print(f"Błąd podczas przetwarzania lobby {partia.get('id_gry')} na listę: {e}")
            # Pomiń to lobby, jeśli ma uszkodzone dane
            continue
            
    return {"lobby_list": lista_publiczna}

@app.post("/save_settings/{username}")
async def save_user_settings(username: str, settings_data: UserSettings, db: AsyncSession = Depends(get_db)):
    """Zapisuje ustawienia interfejsu użytkownika."""

    # Znajdź użytkownika
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie znaleziony."
        )

    # Zapisz ustawienia jako JSON string
    try:
        settings_json = json.dumps(settings_data.dict())
        user.settings = settings_json
        await db.commit()
        return {"message": "Ustawienia zapisane pomyślnie."}
    except Exception as e:
            await db.rollback() # Wycofaj zmiany w razie błędu
            print(f"!!! KRYTYCZNY BŁĄD podczas zapisywania ustawień dla {username} !!!")
            import traceback # Upewnij się, że traceback jest zaimportowany na górze pliku
            traceback.print_exc() # Wydrukuj pełny ślad błędu
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Nie udało się zapisać ustawień z powodu błędu serwera: {type(e).__name__}" # Dodaj typ błędu do komunikatu
            )

# --- Endpoint Tworzenia Gier ---

@app.post("/gra/stworz")
def stworz_gre(request: CreateGameRequest):
    """Tworzy nową grę (lokalną lub online) na podstawie opcji."""
    id_gry = generuj_krotki_id()
    nazwa_gracza = request.nazwa_gracza

    partia = {
        "id_gry": id_gry,
        "status_partii": "LOBBY",
        "host": nazwa_gracza,
        "tryb_gry": request.tryb_lobby, # 'online' lub 'lokalna'
        "max_graczy": 4 if request.tryb_gry == '4p' else 3,
        "gracze_engine": [], "druzyny_engine": [], "aktualne_rozdanie": None,
        "numer_rozdania": 1, "historia_partii": [],
        "pelna_historia": [], "kicked_players": [], "gracze_gotowi": [],
        'aktualna_ocena': None,
        # Zapisujemy nowe opcje na później
        "opcje": {
            "tryb_gry": request.tryb_gry, # '4p' / '3p'
            "publiczna": request.publiczna, # Użyj wartości z żądania
            "haslo": request.haslo if request.haslo else None # Zapisz hasło (lub None)
        }
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

    # Jeśli lobby jest LOKALNE, od razu je wypełnij i wystartuj grę
    if request.tryb_lobby == 'lokalna':
        partia["status_partii"] = "W_TRAKCIE"
        partia["slots"][0].update({"nazwa": nazwa_gracza, "typ": "czlowiek"})

        try: # --- Dodany blok try ---
            if request.tryb_gry == '4p':
                partia["slots"][1].update({"nazwa": "Bot_1", "typ": "bot", "druzyna": "Oni"})
                partia["slots"][2].update({"nazwa": "Bot_2", "typ": "bot", "druzyna": "My"})
                partia["slots"][3].update({"nazwa": "Bot_3", "typ": "bot", "druzyna": "Oni"})

                d_my = silnik_gry.Druzyna(partia["nazwy_druzyn"]["My"])
                d_oni = silnik_gry.Druzyna(partia["nazwy_druzyn"]["Oni"])
                d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                gracze_tmp = [None] * 4
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    gracze_tmp[slot["slot_id"]] = g
                    (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)

                partia.update({"gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni]})
                print(f"[{id_gry}] Tworzenie lokalnego rozdania 4p...")
                rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], 0)
                print(f"[{id_gry}] Rozdanie 4p stworzone.")

            else: # 3p lokalna
                partia["slots"][1].update({"nazwa": "Bot_1", "typ": "bot"})
                partia["slots"][2].update({"nazwa": "Bot_2", "typ": "bot"})

                gracze_tmp = [None] * 3
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    g.punkty_meczu = 0
                    gracze_tmp[slot["slot_id"]] = g

                partia.update({"gracze_engine": gracze_tmp, "punkty_meczu": {g.nazwa: 0 for g in gracze_tmp}})
                print(f"[{id_gry}] Tworzenie lokalnego rozdania 3p...")
                rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], 0)
                print(f"[{id_gry}] Rozdanie 3p stworzone.")

            # Wywołaj rozpoczęcie rozdania tylko jeśli zostało poprawnie stworzone
            if rozdanie:
                print(f"[{id_gry}] Rozpoczynanie nowego rozdania...")
                rozdanie.rozpocznij_nowe_rozdanie()
                print(f"[{id_gry}] Rozdanie rozpoczęte.")
                partia["aktualne_rozdanie"] = rozdanie
            else:
                 raise ValueError("Nie udało się zainicjalizować obiektu rozdania.")

        except Exception as e: # --- Dodany blok except ---
            print(f"!!! KRYTYCZNY BŁĄD podczas tworzenia gry lokalnej {id_gry} !!!")
            traceback.print_exc()
            # Zwróć błąd zamiast pozwalać na Internal Server Error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Błąd serwera podczas inicjalizacji gry lokalnej: {e}"
            )


    gry[id_gry] = partia
    return {"id_gry": id_gry}

# --- Endpoint Sprawdzania Gry ---
@app.get("/gra/sprawdz/{id_gry}")
def sprawdz_gre(id_gry: str):
    """Sprawdza, czy gra o podanym ID istnieje."""
    return {"exists": id_gry in gry}

# === Pobieranie Stanu Gry ===
def pobierz_stan_gry(id_gry: str):
    """Pobiera i formatuje aktualny stan gry dla klienta."""
    partia = gry.get(id_gry)
    if not partia:
        return {"error": "Gra nie istnieje"}

    # Podstawowy stan, niezależny od fazy gry
    stan_podstawowy = {
        "status_partii": partia["status_partii"],
        "tryb_gry": partia.get("tryb_gry", "online"),
        "max_graczy": partia.get("max_graczy", 4),
        "slots": partia["slots"],
        "host": partia["host"],
        "gracze_gotowi": partia.get("gracze_gotowi", []),
        "nazwy_druzyn": partia.get("nazwy_druzyn", {}),
        "historia_partii": partia.get("historia_partii", []),
    }

    # Obsługa stanu LOBBY
    if partia['status_partii'] == 'LOBBY':
        stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {})
        return stan_podstawowy

    # Obsługa stanu ZAKONCZONA
    if partia['status_partii'] == 'ZAKONCZONA':
        if partia.get("max_graczy", 4) == 4:
            stan_podstawowy["punkty_meczu"] = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])} if partia.get("druzyny_engine") else partia.get("punkty_meczu", {})
        else:
            stan_podstawowy["punkty_meczu"] = {g.nazwa: g.punkty_meczu for g in partia.get("gracze_engine", [])} if partia.get("gracze_engine") else partia.get("punkty_meczu", {})
        return stan_podstawowy

    # Obsługa stanu W_TRAKCIE
    rozdanie = partia.get("aktualne_rozdanie")
    if not rozdanie:
        stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {})
        return stan_podstawowy

    # --- Obliczanie Oceny Silnika ---
    aktualna_ocena = None # POPRAWKA: Zawsze inicjalizuj
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA and not rozdanie.podsumowanie:
        # Upewnij się, że jest gracz rozgrywający (na wszelki wypadek)
        gracz_perspektywa = rozdanie.grajacy
        if gracz_perspektywa:
            print(f"Pobierz stan: Obliczanie ewaluacji dla {gracz_perspektywa.nazwa} (Faza: ROZGRYWKA, brak podsumowania)...")
            try:
                # evaluate_state powinno poprawnie obsłużyć stan, gdzie lewa czeka
                aktualna_ocena = mcts_bot.evaluate_state(
                    stan_gry=rozdanie,
                    nazwa_gracza_perspektywa=gracz_perspektywa.nazwa,
                    limit_symulacji=500
                )
                print(f"Pobierz stan: Nowa ocena: {aktualna_ocena}")
            except Exception as e:
                print(f"BŁĄD podczas obliczania ewaluacji: {e}")
                aktualna_ocena = None
    # --- Koniec Obliczania Oceny ---


    # Pobierz aktualne wyniki z obiektów silnika
    if partia.get("max_graczy", 4) == 4:
        punkty_meczu = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])}
        punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu
    else: # 3 graczy
        punkty_meczu = {g.nazwa: g.punkty_meczu for g in rozdanie.gracze if g}
        punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu

    # Znajdź gracza w turze
    gracz_w_turze_obj = None
    if rozdanie.kolej_gracza_idx is not None and rozdanie.gracze and 0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze):
         gracz_w_turze_obj = rozdanie.gracze[rozdanie.kolej_gracza_idx]

    # Zaktualizuj stan podstawowy danymi specyficznymi dla rozdania
    stan_podstawowy.update({
        "punkty_meczu": punkty_meczu,
        "rozdanie": {
            "faza": rozdanie.faza,
            "kolej_gracza": gracz_w_turze_obj.nazwa if gracz_w_turze_obj else None,
            "rece_graczy": {g.nazwa: [str(k) for k in g.reka] for g in rozdanie.gracze if g},
            "karty_na_stole": [{"gracz": g.nazwa, "karta": str(k)} for g, k in rozdanie.aktualna_lewa],
            "grywalne_karty": [],
            "mozliwe_akcje": [],
            "punkty_w_rozdaniu": punkty_w_rozdaniu,
            "kontrakt": {"typ": rozdanie.kontrakt, "atut": rozdanie.atut},
            "aktualna_stawka": rozdanie.oblicz_aktualna_stawke() if hasattr(rozdanie, 'oblicz_aktualna_stawke') else 0,
            "gracz_grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None,
            "historia_rozdania": rozdanie.szczegolowa_historia,
            "podsumowanie": rozdanie.podsumowanie,
            "lewa_do_zamkniecia": rozdanie.lewa_do_zamkniecia,
            "aktualna_ocena": aktualna_ocena # Dodajemy obliczoną ocenę
        }
    })

    # Dodaj grywalne karty / możliwe akcje dla gracza w turze
    if gracz_w_turze_obj:
        if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
             stan_podstawowy['rozdanie']['grywalne_karty'] = [
                 str(k) for k in gracz_w_turze_obj.reka
                 if rozdanie._waliduj_ruch(gracz_w_turze_obj, k)
             ]
        else:
             stan_podstawowy['rozdanie']['mozliwe_akcje'] = rozdanie.get_mozliwe_akcje(gracz_w_turze_obj)

    return stan_podstawowy

# === Przetwarzanie Akcji Gracza ===
def przetworz_akcje_gracza(data: dict, partia: dict):
    """Przetwarza akcję otrzymaną od gracza (lobby lub gra)."""
    gracz_akcji_nazwa = data.get("gracz")

    try:
        if partia["status_partii"] == "LOBBY":
            akcja = data.get("akcja_lobby")
            if akcja == "dolacz_do_slota": # PRZYWRÓCONA LOGIKA
                slot_id = data.get("slot_id")
                slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_akcji_nazwa), None)
                slot_docelowy = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
                if slot_gracza and slot_docelowy and slot_docelowy["typ"] == "pusty":
                    slot_docelowy.update({"nazwa": slot_gracza["nazwa"], "typ": slot_gracza["typ"]})
                    slot_gracza.update({"nazwa": None, "typ": "pusty"})
                    # Stan się zmienił, zostanie wysłany
            elif akcja == "zmien_slot" and partia["host"] == gracz_akcji_nazwa: # PRZYWRÓCONA LOGIKA
                slot_id = data.get("slot_id")
                nowy_typ = data.get("nowy_typ")
                slot = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
                if slot and slot["nazwa"] != partia["host"]:
                    if nowy_typ == "pusty":
                        if slot["typ"] == "czlowiek" and slot["nazwa"]:
                            partia.setdefault("kicked_players", []).append(slot["nazwa"])
                        slot.update({"nazwa": None, "typ": "pusty"})
                    elif nowy_typ == "bot":
                        slot.update({"nazwa": f"Bot_{slot_id}", "typ": "bot"})
                    # Stan się zmienił, zostanie wysłany
            elif akcja == "start_gry" and partia["host"] == gracz_akcji_nazwa and all(s["typ"] != "pusty" for s in partia["slots"]): # PRZYWRÓCONA LOGIKA
                liczba_graczy = len(partia["slots"])
                gracze_tmp = [None] * liczba_graczy
                for slot in partia["slots"]:
                    g = silnik_gry.Gracz(slot["nazwa"])
                    gracze_tmp[slot["slot_id"]] = g

                partia.update({"gracze_engine": gracze_tmp, "status_partii": "W_TRAKCIE"})
                rozdanie = None
                if liczba_graczy == 3:
                    for gracz in gracze_tmp: gracz.punkty_meczu = 0
                    partia["punkty_meczu"] = {g.nazwa: 0 for g in gracze_tmp}
                    rozdanie = silnik_gry.RozdanieTrzyOsoby(gracze_tmp, 0)
                else: # 4 graczy
                    nazwy = partia["nazwy_druzyn"]
                    d_my, d_oni = silnik_gry.Druzyna(nazwy["My"]), silnik_gry.Druzyna(nazwy["Oni"])
                    d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                    for slot in partia["slots"]:
                        # POPRAWKA: Upewnij się, że gracz_obj istnieje
                        gracz_obj = next((g for g in gracze_tmp if g.nazwa == slot["nazwa"]), None)
                        if gracz_obj:
                            (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(gracz_obj)
                    partia.update({"druzyny_engine": [d_my, d_oni]})
                    rozdanie = silnik_gry.Rozdanie(gracze_tmp, [d_my, d_oni], 0)

                if rozdanie:
                    rozdanie.rozpocznij_nowe_rozdanie()
                    partia["aktualne_rozdanie"] = rozdanie
                # Stan się zmienił, zostanie wysłany

        elif partia["status_partii"] == "W_TRAKCIE":
            akcja = data.get('akcja')
            rozdanie = partia.get("aktualne_rozdanie")
            if not akcja or not rozdanie: return
            typ_akcji = akcja.get('typ')
            gracz_obj = next((g for g in rozdanie.gracze if g and g.nazwa == gracz_akcji_nazwa), None)
            if not gracz_obj: return

            # Wykonaj akcję silnika gry
            if typ_akcji == 'nastepne_rozdanie': # PRZYWRÓCONA LOGIKA
                if gracz_akcji_nazwa not in partia.get("gracze_gotowi", []):
                    partia.setdefault("gracze_gotowi", []).append(gracz_akcji_nazwa)
                liczba_ludzi = sum(1 for s in partia["slots"] if s["typ"] == "czlowiek")
                gotowi_ludzie = [nazwa for nazwa in partia.get("gracze_gotowi", []) if any(s["nazwa"] == nazwa and s["typ"] == "czlowiek" for s in partia["slots"])]
                if len(gotowi_ludzie) >= liczba_ludzi:
                    partia["gracze_gotowi"] = []
                    if rozdanie.podsumowanie:
                        pod = rozdanie.podsumowanie
                        nr = partia.get("numer_rozdania", 1)
                        gral = rozdanie.grajacy.nazwa if rozdanie.grajacy else "Brak"
                        kontrakt_nazwa = pod.get("kontrakt", "Brak")
                        atut_nazwa = pod.get("atut", "")
                        if atut_nazwa and atut_nazwa != "Brak": kontrakt_nazwa = f"{kontrakt_nazwa} ({atut_nazwa[0]})"
                        wygrani = pod.get("wygrana_druzyna", ", ".join(pod.get("wygrani_gracze", [])))
                        punkty = pod.get("przyznane_punkty", 0)
                        wpis = (f"R{nr} | G:{gral} | K:{kontrakt_nazwa} | "
                                f"W:{wygrani} | P:{punkty} pkt")
                        partia["historia_partii"].append(wpis)
                        partia["numer_rozdania"] = nr + 1
                    if not sprawdz_koniec_partii(partia):
                        for gracz in partia["gracze_engine"]:
                            gracz.reka.clear(); gracz.wygrane_karty.clear()
                        nowy_idx = (rozdanie.rozdajacy_idx + 1) % len(partia["gracze_engine"])
                        if partia.get("max_graczy", 4) == 4:
                            nowe_rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], nowy_idx)
                        else:
                            nowe_rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], nowy_idx)
                        nowe_rozdanie.rozpocznij_nowe_rozdanie()
                        partia["aktualne_rozdanie"] = nowe_rozdanie
            elif typ_akcji == 'finalizuj_lewe': # PRZYWRÓCONA LOGIKA
                rozdanie.finalizuj_lewe()
            elif typ_akcji == 'zagraj_karte': # PRZYWRÓCONA LOGIKA
                karta_str = akcja.get('karta')
                if not karta_str: return
                karta_obj = karta_ze_stringa(karta_str)
                rozdanie.zagraj_karte(gracz_obj, karta_obj)
            else: # Akcja licytacyjna # PRZYWRÓCONA LOGIKA
                akcja_do_wykonania = akcja.copy()
                atut_val = akcja_do_wykonania.get('atut')
                if atut_val and isinstance(atut_val, str):
                    try: # POPRAWKA: Obsługa błędu, gdy atut nie jest prawidłową nazwą
                        akcja_do_wykonania['atut'] = silnik_gry.Kolor[atut_val]
                    except KeyError:
                         print(f"BŁĄD: Nieprawidłowa nazwa atutu '{atut_val}' w akcji.")
                         return # Przerwij przetwarzanie
                kontrakt_val = akcja_do_wykonania.get('kontrakt')
                if kontrakt_val and isinstance(kontrakt_val, str):
                    try: # POPRAWKA: Obsługa błędu, gdy kontrakt nie jest prawidłową nazwą
                        akcja_do_wykonania['kontrakt'] = silnik_gry.Kontrakt[kontrakt_val]
                    except KeyError:
                         print(f"BŁĄD: Nieprawidłowa nazwa kontraktu '{kontrakt_val}' w akcji.")
                         return # Przerwij przetwarzanie
                rozdanie.wykonaj_akcje(gracz_obj, akcja_do_wykonania)

        elif partia["status_partii"] == "ZAKONCZONA":
            akcja = data.get('akcja')
            if akcja and akcja.get('typ') == 'powrot_do_lobby' and partia["host"] == gracz_akcji_nazwa: # PRZYWRÓCONA LOGIKA
                resetuj_gre_do_lobby(partia)

    except Exception as e:
        print(f"BŁĄD podczas przetwarzania akcji gracza {gracz_akcji_nazwa}: {e}")
        traceback.print_exc()

async def replacement_timer(id_gry: str, slot_id: int):
    """
    Czeka 60 sekund i zastępuje gracza botem, jeśli nadal jest rozłączony.
    """
    print(f"[{id_gry}] Uruchomiono 60s timer dla slotu {slot_id}...")
    await asyncio.sleep(60)
    
    partia = gry.get(id_gry)
    if not partia or partia["status_partii"] != "W_TRAKCIE":
        print(f"[{id_gry}] Timer anulowany (gra zakończona lub wróciła do lobby).")
        return # Gra już nie istnieje lub wróciła do lobby

    slot = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
    
    # Jeśli po 60s gracz wciąż jest rozłączony
    if slot and slot.get("typ") == "rozlaczony":
        stara_nazwa = slot.get("nazwa", "Gracz")
        nowa_nazwa_bota = f"Bot_{stara_nazwa[:8]}"
        print(f"[{id_gry}] Gracz {stara_nazwa} nie wrócił. Zastępowanie botem {nowa_nazwa_bota}.")

        slot["nazwa"] = nowa_nazwa_bota
        slot["typ"] = "bot"
        slot["disconnect_task"] = None # Wyczyść zadanie

        # Zaktualizuj nazwę gracza w silniku gry!
        if partia.get("gracze_engine"):
            gracz_obj = next((g for g in partia["gracze_engine"] if g.nazwa == stara_nazwa), None)
            if gracz_obj:
                gracz_obj.nazwa = nowa_nazwa_bota

        # --- NOWY BLOK: Sprawdź, czy zostali jacyś ludzie ---
        pozostali_ludzie = any(s.get("typ") == "czlowiek" for s in partia.get("slots", []))

        if not pozostali_ludzie:
            print(f"[{id_gry}] Brak graczy ludzkich po zastąpieniu {stara_nazwa}. Usuwanie gry.")
            try:
                # Zamknij pozostałe połączenia (jeśli jakieś boty były połączone?)
                if id_gry in manager.active_connections:
                    connections_copy = manager.active_connections[id_gry][:]
                    for conn in connections_copy:
                        await conn.close(code=1000, reason="Gra zakończona - brak graczy.")
                    del manager.active_connections[id_gry] # Usuń wpis z managera
                
                # Usuń grę
                del gry[id_gry]
            except KeyError:
                print(f"[{id_gry}] Nie można było usunąć gry (może już usunięta).")
            return # Zakończ funkcję timera, nie rób broadcastu ani pętli botów
        # --- KONIEC NOWEGO BLOKU ---

        # Poinformuj wszystkich (jeśli gra nie została usunięta) i uruchom pętlę botów
        print(f"[{id_gry}] Zostali gracze ludzcy. Kontynuowanie gry.")
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        await uruchom_petle_botow(id_gry)
    else:
        print(f"[{id_gry}] Timer dla slotu {slot_id} anulowany (gracz wrócił).")

# === Pętla Botów ===
async def uruchom_petle_botow(id_gry: str):
    """Asynchroniczna pętla sprawdzająca, czy jest tura bota i wykonująca jego ruch."""
    while True:
        partia = gry.get(id_gry)

        # Sprawdzenia bezpieczeństwa
        if not partia or partia["status_partii"] != "W_TRAKCIE": break
        rozdanie = partia.get("aktualne_rozdanie")
        # POPRAWKA: Sprawdź też, czy gracze istnieją w rozdaniu
        if not rozdanie or not rozdanie.gracze or rozdanie.kolej_gracza_idx is None: break
        if not (0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze)): break
        gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        if not gracz_w_turze: break

        slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_w_turze.nazwa), None)

        # Jeśli to nie jest tura bota, przerwij pętlę
        if not slot_gracza or slot_gracza["typ"] == "czlowiek":
            break

        # --- TURA BOTA ---
        await asyncio.sleep(0.1) # Małe opóźnienie dla UI

        akcja_bota = None # POPRAWKA: Zainicjalizuj
        try:
            print(f"BOT MCTS ({gracz_w_turze.nazwa}): Myślenie...")
            akcja_bota = mcts_bot.znajdz_najlepszy_ruch(
                poczatkowy_stan_gry=rozdanie,
                nazwa_gracza_bota=gracz_w_turze.nazwa,
                limit_czasu_s=1.0
            )
            print(f"BOT MCTS ({gracz_w_turze.nazwa}): Wybrana akcja: {akcja_bota}")
        except Exception as e:
            print(f"!!! KRYTYCZNY BŁĄD BOTA MCTS dla {gracz_w_turze.nazwa}: {e}")
            traceback.print_exc()
            break

        if not akcja_bota or 'typ' not in akcja_bota:
            print(f"INFO: Bot {gracz_w_turze.nazwa} nie miał ruchu (MCTS zwrócił pustą akcję). Faza: {rozdanie.faza}")
            # Spróbujmy wymusić pas, jeśli to możliwe
            if rozdanie.faza not in [silnik_gry.FazaGry.ROZGRYWKA, silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]:
                mozliwe_akcje_bota = rozdanie.get_mozliwe_akcje(gracz_w_turze)
                akcja_pas_bota = next((a for a in mozliwe_akcje_bota if 'pas' in a.get('typ','')), None)
                if akcja_pas_bota:
                    print(f"INFO: Bot {gracz_w_turze.nazwa} wymusza PAS.")
                    akcja_bota = akcja_pas_bota
                else:
                    break # Naprawdę nie ma ruchu
            else:
                 break # Brak ruchu w rozgrywce - błąd lub koniec

        # Wykonaj akcję bota
        stan_zmieniony_przez_bota = False # POPRAWKA: Zainicjalizuj
        try:
            if akcja_bota['typ'] == 'zagraj_karte':
                # Upewnij się, że karta istnieje w ręce (MCTS może się mylić przy determinizacji)
                karta_do_zagrania = next((k for k in gracz_w_turze.reka if k == akcja_bota['karta_obj']), None)
                if karta_do_zagrania and rozdanie._waliduj_ruch(gracz_w_turze, karta_do_zagrania):
                    rozdanie.zagraj_karte(gracz_w_turze, karta_do_zagrania)
                    stan_zmieniony_przez_bota = True
                else:
                    print(f"OSTRZEŻENIE: Bot {gracz_w_turze.nazwa} próbował zagrać nielegalną kartę: {akcja_bota['karta_obj']}. Wybieram losową legalną.")
                    legalne_karty = [k for k in gracz_w_turze.reka if rozdanie._waliduj_ruch(gracz_w_turze, k)]
                    if legalne_karty:
                        losowa_karta = random.choice(legalne_karty)
                        rozdanie.zagraj_karte(gracz_w_turze, losowa_karta)
                        stan_zmieniony_przez_bota = True
                    else:
                        print(f"BŁĄD KRYTYCZNY: Bot {gracz_w_turze.nazwa} nie ma legalnych kart do zagrania.")
                        break # Przerwij pętlę
            else: # Akcja licytacyjna
                # Sprawdź, czy akcja jest legalna
                legalne_akcje = rozdanie.get_mozliwe_akcje(gracz_w_turze)
                # Porównanie słowników może być problematyczne, porównajmy typy i kluczowe wartości
                czy_legalna = any(
                    a['typ'] == akcja_bota['typ'] and
                    a.get('kontrakt') == akcja_bota.get('kontrakt') and
                    a.get('atut') == akcja_bota.get('atut')
                    for a in legalne_akcje
                )
                if czy_legalna:
                    rozdanie.wykonaj_akcje(gracz_w_turze, akcja_bota)
                    stan_zmieniony_przez_bota = True
                else:
                    print(f"OSTRZEŻENIE: Bot {gracz_w_turze.nazwa} próbował wykonać nielegalną akcję licytacyjną: {akcja_bota}. Wybieram losową legalną.")
                    if legalne_akcje:
                         losowa_akcja = random.choice(legalne_akcje)
                         # Upewnij się, że Enumy są przekazywane poprawnie
                         rozdanie.wykonaj_akcje(gracz_w_turze, losowa_akcja)
                         stan_zmieniony_przez_bota = True
                    else:
                        print(f"BŁĄD KRYTYCZNY: Bot {gracz_w_turze.nazwa} nie ma legalnych akcji licytacyjnych.")
                        break # Przerwij pętlę

        except Exception as e:
            print(f"BŁĄD podczas wykonywania akcji BOTA {gracz_w_turze.nazwa}: {e}. Akcja: {akcja_bota}")
            traceback.print_exc()
            break # Przerwij pętlę przy błędzie wykonania


        # Wyślij zaktualizowany stan PO ruchu bota (pobierz_stan_gry obliczy ocenę)
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))

        # Dodaj pauzę, aby gracze widzieli ruch bota
        await asyncio.sleep(1.0)
        # Pętla kontynuuje sprawdzanie następnego gracza

# === Główny Endpoint WebSocket ===
@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str,haslo: Optional[str] = Query(None)):
    """Obsługuje połączenie WebSocket dla gracza."""
    partia = gry.get(id_gry)

    # Sprawdzenia początkowe
    if not partia:
        await websocket.accept() # Zaakceptuj, żeby wysłać powód
        await websocket.close(code=1008, reason="Gra nie istnieje."); return

    # --- NOWA WALIDACJA HASŁA ---
    opcje = partia.get("opcje", {})
    haslo_lobby = opcje.get("haslo")

    # Jeśli lobby ma ustawione hasło
    if haslo_lobby:
        # A gracz nie podał hasła LUB podał błędne
        if haslo is None or haslo != haslo_lobby:
            await websocket.accept()
            await websocket.close(code=1008, reason="Nieprawidłowe hasło.")
            return
    await manager.connect(websocket, id_gry)
    if nazwa_gracza in partia.get("kicked_players", []):
        await websocket.close(code=1008, reason="Zostałeś wyrzucony z lobby.")
        return

    try:
        # Obsługa dołączania do lobby
        if partia["status_partii"] == "LOBBY":
            if not any(s['nazwa'] == nazwa_gracza for s in partia['slots']):
                 slot = next((s for s in partia["slots"] if s["typ"] == "pusty"), None)
                 if slot:
                     slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                     if not partia["host"]: partia["host"] = nazwa_gracza
                     # POPRAWKA: Wyślij stan PO dołączeniu
                     await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
                 else:
                     await websocket.close(code=1008, reason="Lobby jest pełne.")
                     manager.disconnect(websocket, id_gry)
                     return
        elif partia["status_partii"] == "W_TRAKCIE":
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
            
            if not slot_gracza:
                # Gracz nie należy do tej gry
                # await websocket.accept() # JUŻ NIEPOTRZEBNE - połączenie jest akceptowane przez manager.connect
                await websocket.close(code=1008, reason="Gra jest w toku, nie możesz dołączyć.")
                return # Zakończ obsługę

            # Sprawdź typ slotu gracza
            typ_slotu = slot_gracza.get("typ")

            if typ_slotu == "rozlaczony":
                # Gracz wraca do gry!
                print(f"[{id_gry}] Gracz {nazwa_gracza} dołączył ponownie.")
                slot_gracza["typ"] = "czlowiek"
                slot_gracza["disconnect_time"] = None
                
                # Anuluj timer
                task = slot_gracza.get("disconnect_task")
                if task:
                    task.cancel()
                    print(f"[{id_gry}] Anulowano timer dla slotu {slot_gracza['slot_id']}.")
                    slot_gracza["disconnect_task"] = None
                # Kontynuuj normalnie poniżej (wyślij stan itp.)

            elif typ_slotu == "czlowiek":
                # To MOŻE być druga karta LUB pierwsze połączenie do gry lokalnej
                czy_lokalna = partia.get("tryb_gry") == "lokalna"
                
                # Jeśli to NIE jest gra lokalna LUB gracz już jest aktywny (np. druga karta)
                # Musimy sprawdzić, czy gracz jest już na liście aktywnych połączeń
                gracz_juz_polaczony = False
                if id_gry in manager.active_connections:
                     # Sprawdźmy, czy jest już inne połączenie dla tego gracza
                     # (Potrzebujemy sposobu identyfikacji połączeń - na razie zakładamy, że tylko jedno na gracza)
                     # Proste sprawdzenie: czy jest więcej niż jedno połączenie w grze?
                     # Lepsze byłoby przechowywanie mapowania nazwa_gracza -> websocket
                     pass # Na razie pomijamy tę logikę odrzucania drugiej karty

                if not czy_lokalna and gracz_juz_polaczony: # Uproszczone: odrzuć tylko drugą kartę w grze online
                    # await websocket.accept() # JUŻ NIEPOTRZEBNE
                    await websocket.close(code=1008, reason="Jesteś już połączony z tą grą.")
                    return # Nie łącz
                else:
                     # To jest pierwsze połączenie do gry lokalnej LUB pierwsza karta gry online
                     print(f"[{id_gry}] Gracz {nazwa_gracza} połączył się (status W_TRAKCIE).")
                     # Po prostu kontynuuj normalnie poniżej

        # Wyślij stan początkowy, jeśli gracz dołączył w trakcie gry
        # (broadcast na początku obsługuje lobby)
        if partia["status_partii"] != "LOBBY":
             await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))

        # Uruchom pętlę botów (jeśli trzeba) - może być tura bota od razu po dołączeniu
        await uruchom_petle_botow(id_gry)

        # Główna pętla odbierania wiadomości od gracza
        while True:
            data = await websocket.receive_json()
            partia = gry.get(id_gry)
            if not partia: break # Gra została usunięta
        

            if data.get("typ_wiadomosci") == "czat":
                 # POPRAWKA: Upewnij się, że gracz jest w grze przed wysłaniem czatu
                 if any(s['nazwa'] == data.get("gracz") for s in partia['slots']):
                      await manager.broadcast(id_gry, data)
                 continue

            # Sprawdź, czy akcja pochodzi od gracza, którego jest tura (lub akcja systemowa)
            aktualne_rozdanie = partia.get("aktualne_rozdanie")
            gracz_w_turze_nazwa = None
            if aktualne_rozdanie and aktualne_rozdanie.kolej_gracza_idx is not None:
                gracz_w_turze_nazwa = aktualne_rozdanie.gracze[aktualne_rozdanie.kolej_gracza_idx].nazwa

            akcja_systemowa = data.get('akcja', {}).get('typ') in ['nastepne_rozdanie', 'finalizuj_lewe']
            akcja_lobby = 'akcja_lobby' in data
            czyj_ruch = data.get("gracz") == gracz_w_turze_nazwa

            if czyj_ruch or akcja_systemowa or akcja_lobby or partia["status_partii"] == "LOBBY":
                # 1. Przetwórz akcję gracza (aktualizuje stan gry)
                przetworz_akcje_gracza(data, partia)

                # 2. Pobierz NOWY stan gry (ta funkcja oblicza ocenę, jeśli trzeba)
                nowy_stan = pobierz_stan_gry(id_gry)

                # 3. Wyślij nowy stan (z oceną) do wszystkich graczy
                await manager.broadcast(id_gry, nowy_stan)

                # 4. Uruchom pętlę botów (jeśli jest tura bota)
                # Ta funkcja sama wyśle stan po ruchu bota
                await uruchom_petle_botow(id_gry)
            else:
                 print(f"Odrzucono akcję od {data.get('gracz')}. Tura: {gracz_w_turze_nazwa}")
                 # Opcjonalnie: wyślij wiadomość zwrotną do gracza, że to nie jego tura


    except WebSocketDisconnect: # Obsłuż rozłączenie jako pierwsze
        print(f"Gracz {nazwa_gracza} rozłączył się z gry {id_gry}.")
        manager.disconnect(websocket, id_gry) # Usuń z managera
        partia = gry.get(id_gry) # Pobierz partię ponownie (może już nie istnieć)

        stan_zmieniony = False # Flaga, czy trzeba wysłać broadcast
        lobby_usunięte = False # NOWA FLAGA

        if partia and partia["status_partii"] == "LOBBY":
             slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
             if slot_gracza:
                 slot_gracza["typ"], slot_gracza["nazwa"] = "pusty", None
                 if partia["host"] == nazwa_gracza:
                     # Znajdź nowego hosta (następnego człowieka)
                     nowy_host = next((s["nazwa"] for s in partia["slots"] if s["typ"] == "czlowiek"), None)
                     partia["host"] = nowy_host
                 stan_zmieniony = True
            
             # --- NOWA LOGIKA USUWANIA LOBBY ---
             if partia.get("tryb_gry") == "online":
                 # Sprawdź, czy wszyscy gracze są "pusty"
                 wszystkie_sloty_puste = all(s.get("typ") == "pusty" for s in partia.get("slots", []))
                 if wszystkie_sloty_puste:
                     print(f"Lobby {id_gry} jest puste. Usuwanie...")
                     try:
                         del gry[id_gry]
                         lobby_usunięte = True
                         stan_zmieniony = False # Nie ma do kogo wysyłać broadcastu
                     except KeyError:
                         print(f"Nie można było usunąć lobby {id_gry}, być może zostało już usunięte.")
        elif partia and partia["status_partii"] == "W_TRAKCIE":
            print(f"Gracz {nazwa_gracza} rozłączył się w trakcie gry {id_gry}.")
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
            
            # Uruchom timer tylko jeśli to był człowiek i nie ma już aktywnego timera
            if slot_gracza and slot_gracza.get('typ') == 'czlowiek':
                 slot_gracza['typ'] = 'rozlaczony'
                 slot_gracza['disconnect_time'] = time.time()
                 
                 # Uruchom zadanie zastąpienia botem w tle
                 task = asyncio.create_task(replacement_timer(id_gry, slot_gracza["slot_id"]))
                 slot_gracza['disconnect_task'] = task # Zapisz referencję do zadania
                 stan_zmieniony = True
            elif slot_gracza and slot_gracza.get('typ') == 'rozlaczony':
                # Gracz się rozłączył, ale już był oznaczony (np. druga karta)
                # Nie rób nic, timer już tyka
                pass

        # Wyślij broadcast tylko jeśli stan się zmienił i gra nadal istnieje
        if stan_zmieniony and not lobby_usunięte and partia:
             try:
                 await manager.broadcast(id_gry, pobierz_stan_gry(id_gry)) # Poinformuj innych
             except Exception as broadcast_error:
                 # Tutaj może nadal wystąpić błąd "Cannot call send", jeśli broadcast jest wolniejszy niż zamknięcie
                 print(f"INFO: Nie udało się wysłać broadcastu po rozłączeniu gracza {nazwa_gracza}: {broadcast_error}")
        # WAŻNE: Nie rób nic więcej z 'websocket' po disconnect

    except Exception as e: 
        # Ten blok łapie WSZYSTKIE inne błędy (RuntimeError, błędy logiki itp.)
        print(f"!!! KRYTYCZNY BŁĄD WEBSOCKET DLA GRY {id_gry} !!! Gracz: {nazwa_gracza}")
        print(f"Typ błędu: {type(e).__name__}")
        traceback.print_exc()
        
        try:
            # Spróbuj powiadomić pozostałych graczy
            if id_gry in manager.active_connections:
                 await manager.broadcast(id_gry, {"error": "Krytyczny błąd serwera. Gra może być niestabilna.", "details": str(e)})
        except Exception as broadcast_error:
            print(f"BŁĄD podczas broadcastu błędu krytycznego: {broadcast_error}")

        # Bezpiecznie zamknij połączenie, jeśli nadal jest otwarte
        # NIE wywołuj tutaj websocket.accept()!
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except RuntimeError as close_error:
            # (Ignoruj błąd, jeśli połączenie już się zamknęło, np. "Cannot call 'close' in state 'DISCONNECTED'")
            print(f"Info: Błąd podczas zamykania websocket po krytycznym błędzie: {close_error}")
            
        manager.disconnect(websocket, id_gry)