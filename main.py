import uuid
import random
import json
import asyncio
import string
import traceback
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import silnik_gry

# --- Modele danych Pydantic ---
class LocalGameRequest(BaseModel):
    """Model danych dla żądania utworzenia gry lokalnej."""
    nazwa_gracza: str

# --- Inicjalizacja FastAPI ---
app = FastAPI()

# --- Globalny słownik przechowujący stan wszystkich gier ---
# Kluczem jest ID gry, wartością jest słownik reprezentujący stan partii.
gry = {}

# --- Przykładowe nazwy drużyn ---
NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]

# === Zarządzanie Połączeniami WebSocket ===
class ConnectionManager:
    """Zarządza aktywnymi połączeniami WebSocket dla każdej gry."""
    def __init__(self):
        # Słownik przechowujący listę WebSocketów dla każdego ID gry
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        """Dodaje nowe połączenie WebSocket do gry."""
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        """Usuwa połączenie WebSocket z gry."""
        if game_id in self.active_connections:
            self.active_connections[game_id].remove(websocket)
            # Można dodać logikę usuwania gry, jeśli lista jest pusta

    async def broadcast(self, game_id: str, message: dict):
        """Wysyła wiadomość (stan gry) do wszystkich podłączonych graczy w danej grze."""
        if game_id in self.active_connections:
            # Serializator JSON radzący sobie z obiektami Enum, Karta, Gracz, Druzyna z silnika gry
            def safe_serializer(o):
                if isinstance(o, (silnik_gry.Kolor, silnik_gry.Kontrakt, silnik_gry.FazaGry, silnik_gry.Ranga)):
                    return o.name # Zwraca nazwę elementu Enum jako string
                if isinstance(o, silnik_gry.Karta):
                    return str(o) # Zwraca reprezentację stringową karty
                if isinstance(o, (silnik_gry.Gracz, silnik_gry.Druzyna)):
                    return o.nazwa # Zwraca nazwę gracza/drużyny
                # Zwraca informację o typie dla obiektów, których nie potrafi serializować
                return f"<Nieserializowalny obiekt: {type(o).__name__}>"

            try:
                message_json = json.dumps(message, default=safe_serializer)
                # Wyślij wiadomość do każdego połączenia w grze
                for connection in self.active_connections[game_id]:
                    await connection.send_text(message_json)
            except Exception as e:
                print(f"BŁĄD podczas serializacji lub broadcastu dla gry {game_id}: {e}")
                traceback.print_exc()

# Instancja managera połączeń
manager = ConnectionManager()

# === Funkcje Pomocnicze ===

def generuj_krotki_id(dlugosc=6) -> str:
    """Generuje unikalny, krótki identyfikator dla gry."""
    while True:
        kod = ''.join(random.choices(string.ascii_uppercase + string.digits, k=dlugosc))
        if kod not in gry: # Sprawdza unikalność
            return kod

def resetuj_gre_do_lobby(partia: dict):
    """Resetuje stan gry do początkowego stanu lobby."""
    partia["status_partii"] = "LOBBY"
    partia["gracze_engine"] = []
    partia["druzyny_engine"] = []
    partia["aktualne_rozdanie"] = None
    partia["pelna_historia"] = [] # Historia wszystkich rozdań (jeśli potrzebna)
    # Resetowanie punktów meczu w zależności od trybu
    if partia.get("max_graczy", 4) == 4:
        nazwy = partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
        partia["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
    else:
        partia["punkty_meczu"] = {slot['nazwa']: 0 for slot in partia['slots'] if slot['typ'] != 'pusty'}
    partia["kicked_players"] = [] # Lista wyrzuconych graczy
    partia["gracze_gotowi"] = [] # Lista graczy gotowych na następne rozdanie/grę
    partia["numer_rozdania"] = 1 # Reset numeru rozdania
    partia["historia_partii"] = [] # Reset historii partii
    print(f"Partia {partia.get('id_gry', 'N/A')} wraca do lobby.")

def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    """Konwertuje string (np. "As Czerwien") na obiekt Karta z silnika gry."""
    try:
        ranga_str, kolor_str = nazwa_karty.split()
        mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
        mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
        ranga = mapowanie_rang[ranga_str]
        kolor = mapowanie_kolorow[kolor_str]
        return silnik_gry.Karta(ranga=ranga, kolor=kolor)
    except (ValueError, KeyError) as e:
        print(f"BŁĄD: Nie można przekonwertować stringa '{nazwa_karty}' na kartę: {e}")
        # Można zwrócić None lub rzucić wyjątek
        raise ValueError(f"Nieprawidłowa nazwa karty: {nazwa_karty}") from e

def sprawdz_koniec_partii(partia: dict) -> bool:
    """Sprawdza, czy partia osiągnęła warunek końca (66 punktów), obsługując remisy w grze 3-osobowej."""
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
            return False # Nikt nie wygrał

        if len(gracze_powyzej_progu) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True # Jeden wyraźny zwycięzca

        # Obsługa remisu: jeśli kilku graczy ma >= 66, wygrywa ten z najwyższym wynikiem
        najwyzszy_wynik = max(g.punkty_meczu for g in gracze_powyzej_progu)
        gracze_z_najwyzszym_wynikiem = [g for g in gracze_powyzej_progu if g.punkty_meczu == najwyzszy_wynik]

        if len(gracze_z_najwyzszym_wynikiem) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True # Jeden gracz ma wyraźnie więcej punktów
        else:
            return False # Prawdziwy remis, gra toczy się dalej

    return False

# === Logika Bota (Tryb Testowy - wymuszone akcje) ===
def wybierz_akcje_dla_bota(bot: silnik_gry.Gracz, rozdanie: Any) -> tuple[str, Any]:
    """Wybiera akcję dla bota. Aktualnie w trybie testowym wymusza konkretne akcje."""

    # Logika rozgrywki (wybiera losową grywalną kartę)
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        if grywalne_karty:
            return 'karta', random.choice(grywalne_karty)
    # Logika licytacji (wymuszone akcje)
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        if not mozliwe_akcje:
            return 'brak', None

        # --- Testowe wymuszenia akcji ---
        if rozdanie.faza == silnik_gry.FazaGry.LICYTACJA:
            akcja_pas = next((a for a in mozliwe_akcje if a['typ'] == 'pas'), None)
            if akcja_pas: print(f"BOT TEST: {bot.nazwa} wymuszony 'pas'"); return 'licytacja', akcja_pas
        if rozdanie.faza == silnik_gry.FazaGry.LUFA:
            akcja_pas_lufa = next((a for a in mozliwe_akcje if a['typ'] == 'pas_lufa'), None)
            if akcja_pas_lufa: print(f"BOT TEST: {bot.nazwa} wymuszony 'pas_lufa'"); return 'licytacja', akcja_pas_lufa
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_DECYZJI_PO_PASACH:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'graj_normalnie'), None)
            if akcja_normalna: print(f"BOT TEST: {bot.nazwa} wymuszony 'graj_normalnie'"); return 'licytacja', akcja_normalna
        if rozdanie.faza == silnik_gry.FazaGry.FAZA_PYTANIA_START:
            akcja_pytanie = next((a for a in mozliwe_akcje if a['typ'] == 'pytanie'), None)
            if akcja_pytanie: print(f"BOT TEST: {bot.nazwa} wymuszony 'pytanie'"); return 'licytacja', akcja_pytanie
        if rozdanie.faza == silnik_gry.FazaGry.DEKLARACJA_1:
            akcja_normalna = next((a for a in mozliwe_akcje if a['typ'] == 'deklaracja' and a['kontrakt'] == silnik_gry.Kontrakt.NORMALNA), None)
            if akcja_normalna:
                print(f"BOT TEST: {bot.nazwa} wymuszony 'NORMALNA'")
                # Ustawiamy atut jako string, bo taka forma może przyjść z get_mozliwe_akcje
                akcja_normalna['atut'] = silnik_gry.Kolor.CZERWIEN.name
                return 'licytacja', akcja_normalna

        # Fallback: Jeśli żadna reguła testowa nie pasuje, wybierz losowo
        print(f"BOT TEST: {bot.nazwa} brak reguły, wybór losowy z: {mozliwe_akcje}")
        wybrana_akcja = random.choice(mozliwe_akcje)
        # Zwracamy akcję w formie, która może zawierać stringi zamiast Enumów
        # Konwersja z powrotem na Enumy odbędzie się w `uruchom_petle_botow`
        if 'atut' in wybrana_akcja and isinstance(wybrana_akcja['atut'], silnik_gry.Kolor):
            wybrana_akcja['atut'] = wybrana_akcja['atut'].name
        if 'kontrakt' in wybrana_akcja and isinstance(wybrana_akcja['kontrakt'], silnik_gry.Kontrakt):
            wybrana_akcja['kontrakt'] = wybrana_akcja['kontrakt'].name
        return 'licytacja', wybrana_akcja

    return 'brak', None # Jeśli bot nie ma żadnego ruchu

# === Konfiguracja Statycznych Plików ===
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

@app.get("/zasady.html")
def read_rules_page():
    """Zwraca stronę z zasadami gry."""
    return FileResponse('static/zasady.html')

# --- Tworzenie Nowych Gier ---

@app.post("/gra/nowa")
def stworz_nowa_gre():
    """Tworzy nową grę online dla 4 graczy."""
    id_gry = generuj_krotki_id()
    nazwy = random.sample(NAZWY_DRUZYN, 2)
    nazwy_mapa = {"My": nazwy[0], "Oni": nazwy[1]}
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "LOBBY", "host": None,
        "tryb_gry": "online", "max_graczy": 4, "nazwy_druzyn": nazwy_mapa,
        "slots": [ # Lista slotów dla graczy
            {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 1, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
            {"slot_id": 2, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 3, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
        ],
        "gracze_engine": [], "druzyny_engine": [], "aktualne_rozdanie": None,
        "numer_rozdania": 1, "historia_partii": [],
        "pelna_historia": [], "punkty_meczu": {nazwy_mapa["My"]: 0, nazwy_mapa["Oni"]: 0},
        "kicked_players": [], "gracze_gotowi": []
    }
    return {"id_gry": id_gry}

@app.post("/gra/nowa/trzyosoby")
def stworz_gre_trzyosobowa():
    """Tworzy nową grę online dla 3 graczy."""
    id_gry = generuj_krotki_id()
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "LOBBY", "host": None,
        "tryb_gry": "online", "max_graczy": 3,
        "slots": [ # Sloty bez przypisania do drużyn
            {"slot_id": 0, "nazwa": None, "typ": "pusty"},
            {"slot_id": 1, "nazwa": None, "typ": "pusty"},
            {"slot_id": 2, "nazwa": None, "typ": "pusty"},
        ],
        "gracze_engine": [], "aktualne_rozdanie": None,
        "numer_rozdania": 1, "historia_partii": [],
        "pelna_historia": [], "punkty_meczu": {}, # Punkty przypisane do graczy po starcie
        "kicked_players": [], "gracze_gotowi": []
    }
    return {"id_gry": id_gry}

@app.post("/gra/nowa/lokalna")
def stworz_gre_lokalna(request: LocalGameRequest):
    """Tworzy nową grę lokalną (1 człowiek + 3 boty) dla 4 graczy."""
    id_gry = generuj_krotki_id()
    nazwa_gracza = request.nazwa_gracza
    # Definicja slotów dla gry lokalnej
    slots = [
        {"slot_id": 0, "nazwa": nazwa_gracza, "typ": "czlowiek", "druzyna": "My"},
        {"slot_id": 1, "nazwa": "Bot_1", "typ": "bot", "druzyna": "Oni"},
        {"slot_id": 2, "nazwa": "Bot_2", "typ": "bot", "druzyna": "My"},
        {"slot_id": 3, "nazwa": "Bot_3", "typ": "bot", "druzyna": "Oni"},
    ]
    # Inicjalizacja obiektów silnika gry
    d_my, d_oni = silnik_gry.Druzyna("My"), silnik_gry.Druzyna("Oni")
    d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
    gracze_tmp = [None] * 4
    for slot in slots:
        g = silnik_gry.Gracz(slot["nazwa"])
        gracze_tmp[slot["slot_id"]] = g
        (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)

    # Utworzenie wpisu gry od razu w stanie "W_TRAKCIE"
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "W_TRAKCIE", "host": nazwa_gracza, "slots": slots,
        "tryb_gry": "lokalna", "max_graczy": 4, "nazwy_druzyn": {"My": "My", "Oni": "Oni"},
        "gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni],
        "numer_rozdania": 1, "historia_partii": [],
        "aktualne_rozdanie": None, "pelna_historia": [],
        "punkty_meczu": {"My": 0, "Oni": 0}, "kicked_players": [], "gracze_gotowi": []
    }
    partia = gry[id_gry]
    # Utworzenie i rozpoczęcie pierwszego rozdania
    rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], 0) # Bot_3 rozdaje jako ostatni (indeks 3), więc Bot_1 zaczyna (indeks 0) - poprawiono na 0
    rozdanie.rozpocznij_nowe_rozdanie()
    partia["aktualne_rozdanie"] = rozdanie
    return {"id_gry": id_gry}

@app.post("/gra/nowa/lokalna/trzyosoby")
def stworz_gre_lokalna_trzyosobowa(request: LocalGameRequest):
    """Tworzy nową grę lokalną (1 człowiek + 2 boty) dla 3 graczy."""
    id_gry = generuj_krotki_id()
    nazwa_gracza = request.nazwa_gracza
    slots = [
        {"slot_id": 0, "nazwa": nazwa_gracza, "typ": "czlowiek"},
        {"slot_id": 1, "nazwa": "Bot_1", "typ": "bot"},
        {"slot_id": 2, "nazwa": "Bot_2", "typ": "bot"},
    ]
    gracze_tmp = [None] * 3
    for slot in slots:
        g = silnik_gry.Gracz(slot["nazwa"])
        g.punkty_meczu = 0 # Inicjalizacja punktów dla graczy 3-osobowych
        gracze_tmp[slot["slot_id"]] = g

    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "W_TRAKCIE", "host": nazwa_gracza, "slots": slots,
        "tryb_gry": "lokalna", "max_graczy": 3,
        "gracze_engine": gracze_tmp, "aktualne_rozdanie": None,
        "numer_rozdania": 1, "historia_partii": [],
        "pelna_historia": [], "punkty_meczu": {g.nazwa: 0 for g in gracze_tmp},
        "kicked_players": [], "gracze_gotowi": []
    }
    partia = gry[id_gry]
    rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], 0) # Bot_2 rozdaje (indeks 2), Gracz zaczyna (indeks 0) - poprawiono na 0
    rozdanie.rozpocznij_nowe_rozdanie()
    partia["aktualne_rozdanie"] = rozdanie
    return {"id_gry": id_gry}

# --- Sprawdzanie Gry ---
@app.get("/gra/sprawdz/{id_gry}")
def sprawdz_gre(id_gry: str):
    """Sprawdza, czy gra o danym ID istnieje."""
    return {"exists": id_gry in gry}

# === Pobieranie Stanu Gry ===
def pobierz_stan_gry(id_gry: str):
    """Pobiera i formatuje aktualny stan gry dla klienta."""
    partia = gry.get(id_gry)
    if not partia: return {"error": "Gra nie istnieje"}

    # --- Stan podstawowy, niezależny od fazy gry ---
    stan_podstawowy = {
        "status_partii": partia["status_partii"], # LOBBY, W_TRAKCIE, ZAKONCZONA
        "tryb_gry": partia.get("tryb_gry", "online"), # online / lokalna
        "max_graczy": partia.get("max_graczy", 4), # 3 lub 4
        "slots": partia["slots"], # Lista slotów (nazwa, typ, druzyna?)
        "host": partia["host"], # Nick hosta gry
        "gracze_gotowi": partia.get("gracze_gotowi", []), # Gracze gotowi na nast. rozdanie
        "nazwy_druzyn": partia.get("nazwy_druzyn", {}), # Mapa nazw drużyn My/Oni
        "historia_partii": partia.get("historia_partii", []), # Lista podsumowań rozdań
    }

    # --- Obsługa stanu LOBBY ---
    if partia['status_partii'] == 'LOBBY':
        # W lobby punkty meczu są jeszcze puste lub resetowane
        stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {})
        return stan_podstawowy

    # --- Obsługa stanu ZAKONCZONA ---
    if partia['status_partii'] == 'ZAKONCZONA':
        # Po zakończeniu pobieramy finalne punkty z obiektów silnika (jeśli istnieją) lub z partii
        if partia.get("max_graczy", 4) == 4:
            stan_podstawowy["punkty_meczu"] = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])} if partia.get("druzyny_engine") else partia.get("punkty_meczu", {})
        else:
            stan_podstawowy["punkty_meczu"] = {g.nazwa: g.punkty_meczu for g in partia.get("gracze_engine", [])} if partia.get("gracze_engine") else partia.get("punkty_meczu", {})
        return stan_podstawowy

    # --- Obsługa stanu W_TRAKCIE ---
    rozdanie = partia.get("aktualne_rozdanie")
    if not rozdanie: # Zabezpieczenie, jeśli rozdanie nie istnieje
        stan_podstawowy["punkty_meczu"] = partia.get("punkty_meczu", {}) # Wyślij przynajmniej punkty
        return stan_podstawowy

    # Pobierz aktualne punkty meczu z obiektów silnika gry
    if partia.get("max_graczy", 4) == 4:
        punkty_meczu = {d.nazwa: d.punkty_meczu for d in partia.get("druzyny_engine", [])}
        punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu
    else: # 3 graczy
        punkty_meczu = {g.nazwa: g.punkty_meczu for g in rozdanie.gracze if g}
        punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu

    # Znajdź gracza, którego jest tura
    gracz_w_turze_obj = None
    if rozdanie.kolej_gracza_idx is not None and rozdanie.gracze and 0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze):
         gracz_w_turze_obj = rozdanie.gracze[rozdanie.kolej_gracza_idx]

    # Zaktualizuj stan podstawowy o dane specyficzne dla rozdania
    stan_podstawowy.update({
        "punkty_meczu": punkty_meczu, # Aktualne punkty w meczu
        "rozdanie": { # Słownik zawierający szczegóły bieżącego rozdania
            "faza": rozdanie.faza, # Aktualna faza gry (np. LICYTACJA, ROZGRYWKA)
            "kolej_gracza": gracz_w_turze_obj.nazwa if gracz_w_turze_obj else None, # Nick gracza w turze
            "rece_graczy": {g.nazwa: [str(k) for k in g.reka] for g in rozdanie.gracze if g}, # Ręce graczy (stringi kart)
            "karty_na_stole": [{"gracz": g.nazwa, "karta": str(k)} for g, k in rozdanie.aktualna_lewa], # Karty w bieżącej lewie
            "grywalne_karty": [str(k) for k in gracz_w_turze_obj.reka if rozdanie._waliduj_ruch(gracz_w_turze_obj, k)] if gracz_w_turze_obj and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA else [], # Grywalne karty dla gracza w turze
            "mozliwe_akcje": rozdanie.get_mozliwe_akcje(gracz_w_turze_obj) if gracz_w_turze_obj else [], # Dostępne akcje licytacyjne
            "punkty_w_rozdaniu": punkty_w_rozdaniu, # Punkty zdobyte w bieżącym rozdaniu
            "kontrakt": {"typ": rozdanie.kontrakt, "atut": rozdanie.atut}, # Aktualny kontrakt
            "aktualna_stawka": rozdanie.oblicz_aktualna_stawke() if hasattr(rozdanie, 'oblicz_aktualna_stawke') else 0, # Aktualna wartość punktowa rozdania
            "gracz_grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None, # Nick rozgrywającego
            "historia_rozdania": rozdanie.szczegolowa_historia, # Szczegółowe logi z rozdania
            "podsumowanie": rozdanie.podsumowanie, # Podsumowanie zakończonego rozdania
            "lewa_do_zamkniecia": rozdanie.lewa_do_zamkniecia, # Flaga sygnalizująca frontendowi pauzę na koniec lewy
        }
    })
    return stan_podstawowy

# === Główny Endpoint WebSocket ===

@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str):
    """Obsługuje połączenie WebSocket dla gracza."""
    # Połącz gracza
    await manager.connect(websocket, id_gry)
    partia = gry.get(id_gry)

    # Sprawdzenia początkowe
    if not partia:
        await websocket.close(code=1008, reason="Gra nie istnieje."); return
    if nazwa_gracza in partia.get("kicked_players", []):
        await websocket.close(code=1008, reason="Zostałeś wyrzucony z lobby.")
        return

    try:
        # Logika dołączania do lobby (jeśli gra jest w lobby)
        if partia["status_partii"] == "LOBBY":
            # Sprawdź, czy gracz już jest w slocie
            if not any(s['nazwa'] == nazwa_gracza for s in partia['slots']):
                # Znajdź pierwszy wolny slot
                slot = next((s for s in partia["slots"] if s["typ"] == "pusty"), None)
                if slot:
                    slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                    # Pierwszy gracz zostaje hostem
                    if not partia["host"]: partia["host"] = nazwa_gracza
                else:
                    await websocket.close(code=1008, reason="Lobby jest pełne.")
                    manager.disconnect(websocket, id_gry)
                    return

        # Wyślij aktualny stan gry do nowo podłączonego gracza (lub wszystkich po zmianie w lobby)
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        # Uruchom pętlę botów (jeśli są i jest ich tura)
        await uruchom_petle_botow(id_gry)

        # Główna pętla odbierania wiadomości od klienta
        while True:
            data = await websocket.receive_json() # Oczekuj na wiadomość (akcję) od gracza
            partia = gry.get(id_gry) # Pobierz aktualny stan partii (mógł się zmienić)
            if not partia: break # Jeśli gra zniknęła, zakończ pętlę

            # Obsługa wiadomości czatu
            if data.get("typ_wiadomosci") == "czat":
                 await manager.broadcast(id_gry, data) # Po prostu roześlij wiadomość czatu
                 continue # Czekaj na następną wiadomość

            # Przetwarzanie akcji gry/lobby
            przetworz_akcje_gracza(data, partia)

            # Po przetworzeniu akcji, wyślij nowy stan gry do wszystkich
            await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
            # Uruchom pętlę botów ponownie (może być ich tura po ruchu gracza)
            await uruchom_petle_botow(id_gry)

    except WebSocketDisconnect:
        # Obsługa rozłączenia gracza
        manager.disconnect(websocket, id_gry)
        partia = gry.get(id_gry) # Sprawdź stan partii po rozłączeniu
        if partia and partia["status_partii"] == "LOBBY":
            # Jeśli gracz opuścił lobby, zwolnij jego slot
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
            if slot_gracza:
                slot_gracza["typ"], slot_gracza["nazwa"] = "pusty", None
                # Jeśli host wyszedł, wybierz nowego hosta
                if partia["host"] == nazwa_gracza:
                    nowy_host = next((s["nazwa"] for s in partia["slots"] if s["typ"] == "czlowiek"), None)
                    partia["host"] = nowy_host
                # Poinformuj pozostałych o zmianie w lobby
                await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        elif partia and partia["status_partii"] == "W_TRAKCIE":
            # TODO: Obsługa wyjścia gracza w trakcie gry (np. zastąpienie botem, przerwanie gry)
            print(f"Gracz {nazwa_gracza} rozłączył się w trakcie gry {id_gry}.")
            # Na razie gra może kontynuować, jeśli są boty, lub się zawiesić

    except Exception as e:
        # Logowanie krytycznych błędów
        print(f"!!! KRYTYCZNY BŁĄD W WEBSOCKET DLA GRY {id_gry} !!!")
        traceback.print_exc()
        # Poinformuj graczy o błędzie
        try:
            await manager.broadcast(id_gry, {"error": "Krytyczny błąd serwera. Gra została zatrzymana.", "details": str(e)})
        except Exception as broadcast_error:
            print(f"BŁĄD podczas broadcastu błędu krytycznego: {broadcast_error}")
        # Można dodać logikę zamykania gry

# === Przetwarzanie Akcji Gracza ===

def przetworz_akcje_gracza(data: dict, partia: dict):
    """Przetwarza akcję otrzymaną od gracza (z lobby lub z gry)."""
    gracz_akcji_nazwa = data.get("gracz")

    # --- Logika dla stanu LOBBY ---
    if partia["status_partii"] == "LOBBY":
        akcja = data.get("akcja_lobby")
        if akcja == "dolacz_do_slota":
            # Logika zmiany slotu przez gracza
            slot_id = data.get("slot_id")
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_akcji_nazwa), None)
            slot_docelowy = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
            if slot_gracza and slot_docelowy and slot_docelowy["typ"] == "pusty":
                # Przenieś gracza do nowego slotu, stary zrób pusty
                slot_docelowy.update({"nazwa": slot_gracza["nazwa"], "typ": slot_gracza["typ"]})
                slot_gracza.update({"nazwa": None, "typ": "pusty"})
        elif akcja == "zmien_slot" and partia["host"] == gracz_akcji_nazwa:
            # Logika zmiany typu slotu przez hosta (wyrzucenie / dodanie bota)
            slot_id = data.get("slot_id")
            nowy_typ = data.get("nowy_typ")
            slot = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
            # Host nie może zmienić swojego slotu
            if slot and slot["nazwa"] != partia["host"]:
                if nowy_typ == "pusty":
                    # Jeśli wyrzucamy człowieka, dodaj go do listy wyrzuconych
                    if slot["typ"] == "czlowiek" and slot["nazwa"]:
                        partia.setdefault("kicked_players", []).append(slot["nazwa"])
                    slot.update({"nazwa": None, "typ": "pusty"})
                elif nowy_typ == "bot":
                    slot.update({"nazwa": f"Bot_{slot_id}", "typ": "bot"})
        elif akcja == "start_gry" and partia["host"] == gracz_akcji_nazwa and all(s["typ"] != "pusty" for s in partia["slots"]):
            # Logika rozpoczęcia gry przez hosta
            liczba_graczy = len(partia["slots"])
            gracze_tmp = [None] * liczba_graczy # Tymczasowa lista obiektów Graczy
            # Stwórz obiekty Graczy z silnika gry
            for slot in partia["slots"]:
                g = silnik_gry.Gracz(slot["nazwa"])
                gracze_tmp[slot["slot_id"]] = g

            partia.update({"gracze_engine": gracze_tmp, "status_partii": "W_TRAKCIE"})
            rozdanie = None
            if liczba_graczy == 3:
                # Inicjalizacja punktów dla gry 3-osobowej
                for gracz in gracze_tmp: gracz.punkty_meczu = 0
                partia["punkty_meczu"] = {g.nazwa: 0 for g in gracze_tmp}
                rozdanie = silnik_gry.RozdanieTrzyOsoby(gracze_tmp, 0) # Pierwszy gracz zaczyna licytację
            else: # 4 graczy
                # Inicjalizacja drużyn
                nazwy = partia["nazwy_druzyn"]
                d_my, d_oni = silnik_gry.Druzyna(nazwy["My"]), silnik_gry.Druzyna(nazwy["Oni"])
                d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                # Dodaj graczy do drużyn
                for slot in partia["slots"]:
                    gracz_obj = next(g for g in gracze_tmp if g.nazwa == slot["nazwa"])
                    (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(gracz_obj)
                partia.update({"druzyny_engine": [d_my, d_oni]})
                rozdanie = silnik_gry.Rozdanie(gracze_tmp, [d_my, d_oni], 0) # Pierwszy gracz zaczyna licytację
            # Rozpocznij pierwsze rozdanie
            if rozdanie:
                rozdanie.rozpocznij_nowe_rozdanie()
                partia["aktualne_rozdanie"] = rozdanie

    # --- Logika dla stanu W_TRAKCIE ---
    elif partia["status_partii"] == "W_TRAKCIE":
        akcja = data.get('akcja')
        rozdanie = partia.get("aktualne_rozdanie")
        if not akcja or not rozdanie:
            print(f"BŁĄD: Brak akcji lub rozdania dla {gracz_akcji_nazwa}. Akcja: {akcja}")
            return
        typ_akcji = akcja.get('typ')
        gracz_obj = next((g for g in rozdanie.gracze if g and g.nazwa == gracz_akcji_nazwa), None)
        if not gracz_obj:
            print(f"BŁĄD: Nie znaleziono obiektu gracza dla {gracz_akcji_nazwa}.")
            return

        # --- Obsługa akcji "nastepne_rozdanie" ---
        if typ_akcji == 'nastepne_rozdanie':
            if gracz_akcji_nazwa not in partia.get("gracze_gotowi", []):
                partia.setdefault("gracze_gotowi", []).append(gracz_akcji_nazwa)

            liczba_ludzi = sum(1 for s in partia["slots"] if s["typ"] == "czlowiek")

            wszyscy_ludzie_gotowi = False
            if "gracze_gotowi" in partia and len(partia["gracze_gotowi"]) >= liczba_ludzi:
                 gotowi_ludzie = [nazwa for nazwa in partia["gracze_gotowi"] if any(s["nazwa"] == nazwa and s["typ"] == "czlowiek" for s in partia["slots"])]
                 if len(gotowi_ludzie) >= liczba_ludzi:
                     wszyscy_ludzie_gotowi = True

            if wszyscy_ludzie_gotowi:
                partia["gracze_gotowi"] = [] # Resetuj listę gotowych

                # Zapis historii partii
                if rozdanie.podsumowanie:
                    pod = rozdanie.podsumowanie
                    nr = partia.get("numer_rozdania", 1)
                    gral = rozdanie.grajacy.nazwa if rozdanie.grajacy else "Brak"
                    # Bezpieczne pobieranie nazw Enum
                    kontrakt_nazwa = pod.get("kontrakt", "Brak")
                    atut_nazwa = pod.get("atut", "")
                    if atut_nazwa and atut_nazwa != "Brak": kontrakt_nazwa = f"{kontrakt_nazwa} ({atut_nazwa[0]})"
                    wygrani = pod.get("wygrana_druzyna", ", ".join(pod.get("wygrani_gracze", [])))
                    punkty = pod.get("przyznane_punkty", 0)
                    wpis = (f"Rozdanie {nr} | Grał: {gral} | "
                            f"Kontrakt: {kontrakt_nazwa} | "
                            f"Wygrani: {wygrani} | Zdobycz: {punkty} pkt")
                    partia["historia_partii"].append(wpis)
                    partia["numer_rozdania"] = nr + 1

                # Sprawdź koniec partii
                if not sprawdz_koniec_partii(partia):
                    # Przygotuj nowe rozdanie
                    for gracz in partia["gracze_engine"]:
                        gracz.reka.clear(); gracz.wygrane_karty.clear()
                    nowy_idx = (rozdanie.rozdajacy_idx + 1) % len(partia["gracze_engine"])
                    if partia.get("max_graczy", 4) == 4:
                        nowe_rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], nowy_idx)
                    else:
                        nowe_rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], nowy_idx)
                    nowe_rozdanie.rozpocznij_nowe_rozdanie()
                    partia["aktualne_rozdanie"] = nowe_rozdanie

        # --- Obsługa akcji "finalizuj_lewe" ---
        elif typ_akcji == 'finalizuj_lewe':
            rozdanie.finalizuj_lewe()

        # --- Obsługa akcji "zagraj_karte" ---
        elif typ_akcji == 'zagraj_karte':
            karta_str = akcja.get('karta')
            if not karta_str:
                print(f"BŁĄD: Brak 'karta' w akcji 'zagraj_karte' od {gracz_akcji_nazwa}.")
                return
            try:
                karta_obj = karta_ze_stringa(karta_str)
                rozdanie.zagraj_karte(gracz_obj, karta_obj)
            except Exception as e:
                 print(f"BŁĄD przy zagraniu karty '{karta_str}' przez {gracz_akcji_nazwa}: {e}")
                 traceback.print_exc()

        # --- Obsługa akcji licytacyjnych ---
        else:

            akcja_do_wykonania = akcja.copy()
            try:
                # Konwertuj 'atut' (string z frontend) na Enum
                atut_val = akcja_do_wykonania.get('atut')
                if atut_val and isinstance(atut_val, str):
                    akcja_do_wykonania['atut'] = silnik_gry.Kolor[atut_val]
                elif atut_val is not None and not isinstance(atut_val, silnik_gry.Kolor):
                     print(f"BŁĄD: Nieprawidłowy typ atutu '{atut_val}' ({type(atut_val)}) w akcji od {gracz_akcji_nazwa}.")
                     return

                # Konwertuj 'kontrakt' (string z frontend) na Enum
                kontrakt_val = akcja_do_wykonania.get('kontrakt')
                if kontrakt_val and isinstance(kontrakt_val, str):
                    akcja_do_wykonania['kontrakt'] = silnik_gry.Kontrakt[kontrakt_val]
                elif kontrakt_val is not None and not isinstance(kontrakt_val, silnik_gry.Kontrakt):
                     print(f"BŁĄD: Nieprawidłowy typ kontraktu '{kontrakt_val}' ({type(kontrakt_val)}) w akcji od {gracz_akcji_nazwa}.")
                     return
                rozdanie.wykonaj_akcje(gracz_obj, akcja_do_wykonania)

            except KeyError as e:
                print(f"BŁĄD KONWERSJI ENUM dla {gracz_akcji_nazwa}: Nie można znaleźć klucza '{e}' w Enum. Oryginalna akcja: {akcja}")
                traceback.print_exc()
            except Exception as e:
                print(f"!!! KRYTYCZNY BŁĄD podczas wykonywania akcji licytacyjnej dla {gracz_akcji_nazwa}: {e}")
                print(f"Oryginalna akcja: {akcja}")
                traceback.print_exc()

    # --- Logika dla stanu ZAKONCZONA ---
    elif partia["status_partii"] == "ZAKONCZONA":
        akcja = data.get('akcja')
        # Tylko host może wrócić do lobby
        if akcja and akcja.get('typ') == 'powrot_do_lobby' and partia["host"] == gracz_akcji_nazwa:
            resetuj_gre_do_lobby(partia)

# === Pętla Ruchów Botów ===
async def uruchom_petle_botow(id_gry: str):
    """Asynchroniczna pętla sprawdzająca, czy jest tura bota i wykonująca jego ruch."""
    while True: # Pętla wykonuje ruchy botów jeden po drugim, aż do tury człowieka
        partia = gry.get(id_gry)
        if not partia or partia["status_partii"] != "W_TRAKCIE": break # Zakończ, jeśli gra nie istnieje lub nie jest w trakcie
        rozdanie = partia.get("aktualne_rozdanie")
        if not rozdanie or not rozdanie.gracze or rozdanie.kolej_gracza_idx is None: break
        if not (0 <= rozdanie.kolej_gracza_idx < len(rozdanie.gracze)): break
        gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        if not gracz_w_turze: break

        slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_w_turze.nazwa), None)
        # Jeśli nie ma slotu lub to człowiek, przerwij pętlę i czekaj na ruch człowieka
        if not slot_gracza or slot_gracza["typ"] == "czlowiek":
            break

        # Tura bota - poczekaj chwilę
        await asyncio.sleep(1.5)

        # Wybierz akcję bota
        typ_ruchu, akcja_bota = wybierz_akcje_dla_bota(gracz_w_turze, rozdanie)

        # Wykonaj akcję bota w silniku gry
        if typ_ruchu == 'karta':
            rozdanie.zagraj_karte(gracz_w_turze, akcja_bota)
        elif typ_ruchu == 'licytacja':
            akcja_do_wykonania = akcja_bota.copy()
            try:
                # Konwertuj stringi (z logiki testowej) na Enumy
                atut_val = akcja_do_wykonania.get('atut')
                if atut_val and isinstance(atut_val, str):
                    akcja_do_wykonania['atut'] = silnik_gry.Kolor[atut_val]
                kontrakt_val = akcja_do_wykonania.get('kontrakt')
                if kontrakt_val and isinstance(kontrakt_val, str):
                    akcja_do_wykonania['kontrakt'] = silnik_gry.Kontrakt[kontrakt_val]

                # Wykonaj akcję
                rozdanie.wykonaj_akcje(gracz_w_turze, akcja_do_wykonania)
            except KeyError as e:
                print(f"BŁĄD KONWERSJI ENUM BOTA dla {gracz_w_turze.nazwa}: Nie można znaleźć klucza '{e}'. Akcja: {akcja_bota}")
                continue # Pomiń błędną akcję, spróbuj następny ruch (jeśli pętla pozwoli)
            except Exception as e:
                print(f"BŁĄD podczas wykonywania akcji BOTA {gracz_w_turze.nazwa}: {e}. Akcja: {akcja_bota}")
                traceback.print_exc()
                continue # Pomiń błędną akcję
        else: # typ_ruchu == 'brak'
            print(f"INFO: Bot {gracz_w_turze.nazwa} nie miał ruchu do wykonania.")
            break # Przerwij, jeśli bot nie może nic zrobić

        # Po ruchu bota, wyślij zaktualizowany stan do wszystkich graczy
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        # Pętla while True sama się powtórzy, sprawdzając czyj jest teraz ruch