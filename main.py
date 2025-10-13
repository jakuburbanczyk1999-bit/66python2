# ZAKTUALIZOWANY PLIK: main.py

# ZAKTUALIZOWANY PLIK: main.py

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
from pydantic import BaseModel # Dodajemy import
import silnik_gry

# --- NOWY MODEL DANYCH ---
class LocalGameRequest(BaseModel):
    nazwa_gracza: str

app = FastAPI()
gry = {}

NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]

class ConnectionManager:
    # ... (bez zmian)
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)
    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            self.active_connections[game_id].remove(websocket)
    async def broadcast(self, game_id: str, message: dict):
        if game_id in self.active_connections:
            def safe_serializer(o):
                if isinstance(o, (silnik_gry.Kolor, silnik_gry.Kontrakt, silnik_gry.FazaGry, silnik_gry.Ranga)):
                    return o.name
                if isinstance(o, silnik_gry.Karta):
                    return str(o)
                if isinstance(o, (silnik_gry.Gracz, silnik_gry.Druzyna)):
                    return o.nazwa
                return f"<Nieserializowalny obiekt: {type(o).__name__}>"
            message_json = json.dumps(message, default=safe_serializer)
            for connection in self.active_connections[game_id]:
                await connection.send_text(message_json)

manager = ConnectionManager()

def generuj_krotki_id(dlugosc=6) -> str:
    # ... (bez zmian)
    while True:
        kod = ''.join(random.choices(string.ascii_uppercase + string.digits, k=dlugosc))
        if kod not in gry:
            return kod

def resetuj_gre_do_lobby(partia: dict):
    # ... (bez zmian)
    partia["status_partii"] = "LOBBY"
    partia["gracze_engine"] = []
    partia["druzyny_engine"] = []
    partia["aktualne_rozdanie"] = None
    partia["pelna_historia"] = []
    if partia.get("max_graczy", 4) == 4:
        nazwy = partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
        partia["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
    else:
        partia["punkty_meczu"] = {slot['nazwa']: 0 for slot in partia['slots'] if slot['typ'] != 'pusty'}
    partia["kicked_players"] = []
    partia["gracze_gotowi"] = []
    print(f"Partia {partia.get('id_gry', 'N/A')} wraca do lobby.")

def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    # ... (bez zmian)
    ranga_str, kolor_str = nazwa_karty.split()
    mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
    mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
    ranga = mapowanie_rang[ranga_str]
    kolor = mapowanie_kolorow[kolor_str]
    return silnik_gry.Karta(ranga=ranga, kolor=kolor)

def sprawdz_koniec_partii(partia: dict) -> bool:
    """Sprawdza, czy partia dobiegła końca, obsługując remisy."""
    if partia.get("max_graczy", 4) == 4:
        for druzyna in partia["druzyny_engine"]:
            if druzyna.punkty_meczu >= 66:
                partia["status_partii"] = "ZAKONCZONA"
                return True
    else: # Logika dla 3 graczy
        gracze_powyzej_progu = [g for g in partia["gracze_engine"] if g.punkty_meczu >= 66]

        if not gracze_powyzej_progu:
            return False # Nikt nie wygrał

        if len(gracze_powyzej_progu) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True # Mamy jednego, wyraźnego zwycięzcę

        # Jeśli jest więcej niż 1 gracz powyżej progu, sprawdzamy remis
        najwyzszy_wynik = max(g.punkty_meczu for g in gracze_powyzej_progu)
        gracze_z_najwyzszym_wynikiem = [g for g in gracze_powyzej_progu if g.punkty_meczu == najwyzszy_wynik]

        if len(gracze_z_najwyzszym_wynikiem) == 1:
            partia["status_partii"] = "ZAKONCZONA"
            return True # Jeden gracz ma wyraźnie więcej punktów od pozostałych remisujących
        else:
            return False # Mamy prawdziwy remis, gra toczy się dalej

    return False

def wybierz_akcje_dla_bota(bot: silnik_gry.Gracz, rozdanie: Any) -> tuple[str, Any]:
    # ... (bez zmian)
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        if grywalne_karty:
            return 'karta', random.choice(grywalne_karty)
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        if mozliwe_akcje:
            wybrana_akcja = random.choice(mozliwe_akcje)
            if 'atut' in wybrana_akcja and wybrana_akcja['atut']:
                wybrana_akcja['atut'] = wybrana_akcja['atut'].name
            if 'kontrakt' in wybrana_akcja and wybrana_akcja['kontrakt']:
                wybrana_akcja['kontrakt'] = wybrana_akcja['kontrakt'].name
            return 'licytacja', wybrana_akcja
    return 'brak', None

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root(): return FileResponse('static/start.html')

@app.get("/gra.html")
def read_game_page(): return FileResponse('static/index.html')

@app.get("/zasady.html")
def read_rules_page(): return FileResponse('static/zasady.html')

@app.post("/gra/nowa")
def stworz_nowa_gre():
    # ... (bez zmian)
    id_gry = generuj_krotki_id()
    nazwy = random.sample(NAZWY_DRUZYN, 2)
    nazwy_mapa = {"My": nazwy[0], "Oni": nazwy[1]}
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "LOBBY", "host": None,
        "tryb_gry": "online", "max_graczy": 4, "nazwy_druzyn": nazwy_mapa,
        "slots": [
            {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 1, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
            {"slot_id": 2, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 3, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
        ],
        "gracze_engine": [], "druzyny_engine": [], "aktualne_rozdanie": None,
        "pelna_historia": [], "punkty_meczu": {nazwy_mapa["My"]: 0, nazwy_mapa["Oni"]: 0},
        "kicked_players": [], "gracze_gotowi": []
    }
    return {"id_gry": id_gry}

@app.post("/gra/nowa/trzyosoby")
def stworz_gre_trzyosobowa():
    # ... (bez zmian)
    id_gry = generuj_krotki_id()
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "LOBBY", "host": None,
        "tryb_gry": "online", "max_graczy": 3,
        "slots": [
            {"slot_id": 0, "nazwa": None, "typ": "pusty"},
            {"slot_id": 1, "nazwa": None, "typ": "pusty"},
            {"slot_id": 2, "nazwa": None, "typ": "pusty"},
        ],
        "gracze_engine": [], "aktualne_rozdanie": None,
        "pelna_historia": [], "punkty_meczu": {},
        "kicked_players": [], "gracze_gotowi": []
    }
    return {"id_gry": id_gry}

# --- ZAKTUALIZOWANY ENDPOINT ---
@app.post("/gra/nowa/lokalna")
def stworz_gre_lokalna(request: LocalGameRequest):
    id_gry = generuj_krotki_id()
    nazwa_gracza = request.nazwa_gracza
    slots = [
        {"slot_id": 0, "nazwa": nazwa_gracza, "typ": "czlowiek", "druzyna": "My"},
        {"slot_id": 1, "nazwa": "Bot_1", "typ": "bot", "druzyna": "Oni"},
        {"slot_id": 2, "nazwa": "Bot_2", "typ": "bot", "druzyna": "My"},
        {"slot_id": 3, "nazwa": "Bot_3", "typ": "bot", "druzyna": "Oni"},
    ]
    d_my, d_oni = silnik_gry.Druzyna("My"), silnik_gry.Druzyna("Oni")
    d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
    gracze_tmp = [None] * 4
    for slot in slots:
        g = silnik_gry.Gracz(slot["nazwa"])
        gracze_tmp[slot["slot_id"]] = g
        (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)
    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "W_TRAKCIE", "host": nazwa_gracza, "slots": slots,
        "tryb_gry": "lokalna", "max_graczy": 4, "nazwy_druzyn": {"My": "My", "Oni": "Oni"},
        "gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni],
        "aktualne_rozdanie": None, "pelna_historia": [],
        "punkty_meczu": {"My": 0, "Oni": 0}, "kicked_players": [], "gracze_gotowi": []
    }
    partia = gry[id_gry]
    rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], 0)
    rozdanie.rozpocznij_nowe_rozdanie()
    partia["aktualne_rozdanie"] = rozdanie
    return {"id_gry": id_gry}

# --- ZAKTUALIZOWANY ENDPOINT ---
@app.post("/gra/nowa/lokalna/trzyosoby")
def stworz_gre_lokalna_trzyosobowa(request: LocalGameRequest):
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
        g.punkty_meczu = 0
        gracze_tmp[slot["slot_id"]] = g

    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "W_TRAKCIE", "host": nazwa_gracza, "slots": slots,
        "tryb_gry": "lokalna", "max_graczy": 3,
        "gracze_engine": gracze_tmp, "aktualne_rozdanie": None,
        "pelna_historia": [], "punkty_meczu": {g.nazwa: 0 for g in gracze_tmp},
        "kicked_players": [], "gracze_gotowi": []
    }
    partia = gry[id_gry]
    rozdanie = silnik_gry.RozdanieTrzyOsoby(partia["gracze_engine"], 0)
    rozdanie.rozpocznij_nowe_rozdanie()
    partia["aktualne_rozdanie"] = rozdanie
    return {"id_gry": id_gry}

@app.get("/gra/sprawdz/{id_gry}")
def sprawdz_gre(id_gry: str): return {"exists": id_gry in gry}

def pobierz_stan_gry(id_gry: str):
    # ... (bez zmian)
    partia = gry.get(id_gry)
    if not partia: return {"error": "Gra nie istnieje"}
    stan_podstawowy = {
        "status_partii": partia["status_partii"], "tryb_gry": partia.get("tryb_gry", "online"),
        "max_graczy": partia.get("max_graczy", 4), "slots": partia["slots"], "host": partia["host"],
        "gracze_gotowi": partia.get("gracze_gotowi", []), "nazwy_druzyn": partia.get("nazwy_druzyn", {})
    }
    if partia['status_partii'] == 'LOBBY':
        stan_podstawowy["punkty_meczu"] = partia["punkty_meczu"]
        return stan_podstawowy
    if partia['status_partii'] == 'ZAKONCZONA':
        if partia.get("max_graczy", 4) == 4:
            stan_podstawowy["punkty_meczu"] = {d.nazwa: d.punkty_meczu for d in partia["druzyny_engine"]} if partia.get("druzyny_engine") else partia["punkty_meczu"]
        else:
            stan_podstawowy["punkty_meczu"] = {g.nazwa: g.punkty_meczu for g in partia["gracze_engine"]} if partia.get("gracze_engine") else partia["punkty_meczu"]
        return stan_podstawowy
    rozdanie = partia.get("aktualne_rozdanie")
    if not rozdanie:
        stan_podstawowy["punkty_meczu"] = partia["punkty_meczu"]
        return stan_podstawowy
    if partia.get("max_graczy", 4) == 4:
        punkty_meczu = {d.nazwa: d.punkty_meczu for d in partia["druzyny_engine"]}
        punkty_w_rozdaniu = rozdanie.punkty_w_rozdaniu
    else:
        punkty_meczu = {g.nazwa: g.punkty_meczu for g in rozdanie.gracze if g}
        punkty_w_rozdaniu = { rozdanie.grajacy.nazwa: rozdanie.punkty_w_rozdaniu[rozdanie.grajacy.nazwa], "Obrona": sum(rozdanie.punkty_w_rozdaniu[o.nazwa] for o in rozdanie.obroncy)} if rozdanie.grajacy else {}
    gracz_w_turze_obj = rozdanie.gracze[rozdanie.kolej_gracza_idx] if rozdanie.kolej_gracza_idx is not None and rozdanie.gracze[rozdanie.kolej_gracza_idx] else None
    stan_podstawowy.update({
        "punkty_meczu": punkty_meczu,
        "rozdanie": {
            "faza": rozdanie.faza, "kolej_gracza": gracz_w_turze_obj.nazwa if gracz_w_turze_obj else None,
            "rece_graczy": {g.nazwa: [str(k) for k in g.reka] for g in rozdanie.gracze if g},
            "karty_na_stole": [{"gracz": g.nazwa, "karta": str(k)} for g, k in rozdanie.aktualna_lewa],
            "grywalne_karty": [str(k) for k in gracz_w_turze_obj.reka if rozdanie._waliduj_ruch(gracz_w_turze_obj, k)] if gracz_w_turze_obj and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA else [],
            "mozliwe_akcje": rozdanie.get_mozliwe_akcje(gracz_w_turze_obj) if gracz_w_turze_obj else [],
            "punkty_w_rozdaniu": punkty_w_rozdaniu,
            "kontrakt": {"typ": rozdanie.kontrakt, "atut": rozdanie.atut},
            "aktualna_stawka": rozdanie.oblicz_aktualna_stawke() if hasattr(rozdanie, 'oblicz_aktualna_stawke') else 0,
            "gracz_grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None,
            "historia_rozdania": rozdanie.szczegolowa_historia,
            "podsumowanie": rozdanie.podsumowanie, "lewa_do_zamkniecia": rozdanie.lewa_do_zamkniecia,
        }
    })
    return stan_podstawowy

@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str):
    # ... (bez zmian)
    await manager.connect(websocket, id_gry)
    partia = gry.get(id_gry)
    if not partia:
        await websocket.close(code=1008, reason="Gra nie istnieje."); return
    if nazwa_gracza in partia.get("kicked_players", []):
        await websocket.close(code=1008, reason="Zostałeś wyrzucony z lobby.")
        return
    try:
        if partia["status_partii"] == "LOBBY":
            if not any(s['nazwa'] == nazwa_gracza for s in partia['slots']):
                slot = next((s for s in partia["slots"] if s["typ"] == "pusty"), None)
                if slot:
                    slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                    if not partia["host"]: partia["host"] = nazwa_gracza
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
        await uruchom_petle_botow(id_gry)
        while True:
            data = await websocket.receive_json()
            partia = gry.get(id_gry)
            if data.get("typ_wiadomosci") == "czat":
                 await manager.broadcast(id_gry, data)
                 continue
            przetworz_akcje_gracza(data, partia)
            await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
            await uruchom_petle_botow(id_gry)
    except WebSocketDisconnect:
        manager.disconnect(websocket, id_gry)
        if partia and partia["status_partii"] == "LOBBY":
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == nazwa_gracza), None)
            if slot_gracza:
                slot_gracza["typ"], slot_gracza["nazwa"] = "pusty", None
                if partia["host"] == nazwa_gracza:
                    nowy_host = next((s["nazwa"] for s in partia["slots"] if s["typ"] == "czlowiek"), None)
                    partia["host"] = nowy_host
                await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))
    except Exception as e:
        print(f"!!! KRYTYCZNY BŁĄD W WEBSOCKET DLA GRY {id_gry} !!!")
        traceback.print_exc()
        await manager.broadcast(id_gry, {"error": "Krytyczny błąd serwera. Gra została zatrzymana.", "details": str(e)})

def przetworz_akcje_gracza(data: dict, partia: dict):
    # ... (bez zmian)
    gracz_akcji_nazwa = data.get("gracz")
    if partia["status_partii"] == "LOBBY":
        akcja = data.get("akcja_lobby")
        if akcja == "dolacz_do_slota":
            slot_id = data.get("slot_id")
            slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_akcji_nazwa), None)
            slot_docelowy = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
            if slot_gracza and slot_docelowy and slot_docelowy["typ"] == "pusty":
                slot_docelowy.update({"nazwa": slot_gracza["nazwa"], "typ": slot_gracza["typ"]})
                slot_gracza.update({"nazwa": None, "typ": "pusty"})
        elif akcja == "zmien_slot" and partia["host"] == gracz_akcji_nazwa:
            slot_id = data.get("slot_id")
            nowy_typ = data.get("nowy_typ")
            slot = next((s for s in partia["slots"] if s["slot_id"] == slot_id), None)
            if slot and slot["nazwa"] != partia["host"]:
                if nowy_typ == "pusty":
                    if slot["typ"] == "czlowiek" and slot["nazwa"]:
                        partia["kicked_players"].append(slot["nazwa"])
                    slot.update({"nazwa": None, "typ": "pusty"})
                elif nowy_typ == "bot":
                    slot.update({"nazwa": f"Bot_{slot_id}", "typ": "bot"})
        elif akcja == "start_gry" and partia["host"] == gracz_akcji_nazwa and all(s["typ"] != "pusty" for s in partia["slots"]):
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
            else:
                nazwy = partia["nazwy_druzyn"]
                d_my, d_oni = silnik_gry.Druzyna(nazwy["My"]), silnik_gry.Druzyna(nazwy["Oni"])
                d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
                for slot in partia["slots"]:
                    gracz_obj = next(g for g in gracze_tmp if g.nazwa == slot["nazwa"])
                    (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(gracz_obj)
                partia.update({"druzyny_engine": [d_my, d_oni]})
                rozdanie = silnik_gry.Rozdanie(gracze_tmp, [d_my, d_oni], 0)
            if rozdanie:
                rozdanie.rozpocznij_nowe_rozdanie()
                partia["aktualne_rozdanie"] = rozdanie
    elif partia["status_partii"] == "W_TRAKCIE":
        akcja = data.get('akcja')
        rozdanie = partia.get("aktualne_rozdanie")
        if not akcja or not rozdanie: return
        typ_akcji = akcja.get('typ')
        if typ_akcji == 'nastepne_rozdanie':
            if gracz_akcji_nazwa not in partia["gracze_gotowi"]:
                partia["gracze_gotowi"].append(gracz_akcji_nazwa)
            liczba_ludzi = sum(1 for s in partia["slots"] if s["typ"] == "czlowiek")
            if len(partia["gracze_gotowi"]) >= liczba_ludzi:
                partia["gracze_gotowi"] = []
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
            return
        gracz_obj = next((g for g in rozdanie.gracze if g and g.nazwa == gracz_akcji_nazwa), None)
        if not gracz_obj: return
        if typ_akcji == 'finalizuj_lewe':
            rozdanie.finalizuj_lewe()
        elif typ_akcji == 'zagraj_karte':
            rozdanie.zagraj_karte(gracz_obj, karta_ze_stringa(akcja['karta']))
        else:
            if 'atut' in akcja and akcja['atut']: akcja['atut'] = silnik_gry.Kolor[akcja['atut']]
            if 'kontrakt' in akcja and akcja['kontrakt']: akcja['kontrakt'] = silnik_gry.Kontrakt[akcja['kontrakt']]
            rozdanie.wykonaj_akcje(gracz_obj, akcja)
    elif partia["status_partii"] == "ZAKONCZONA":
        akcja = data.get('akcja')
        if akcja and akcja.get('typ') == 'powrot_do_lobby' and partia["host"] == gracz_akcji_nazwa:
            resetuj_gre_do_lobby(partia)

async def uruchom_petle_botow(id_gry: str):
    # ... (bez zmian)
    while True:
        partia = gry.get(id_gry)
        if not partia or partia["status_partii"] != "W_TRAKCIE": break
        rozdanie = partia.get("aktualne_rozdanie")
        if not rozdanie or rozdanie.kolej_gracza_idx is None: break
        if len(rozdanie.gracze) <= rozdanie.kolej_gracza_idx or not rozdanie.gracze[rozdanie.kolej_gracza_idx]:
            break
        gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        slot_gracza = next((s for s in partia["slots"] if s["nazwa"] == gracz_w_turze.nazwa), None)
        if not slot_gracza or slot_gracza["typ"] == "czlowiek":
            break
        await asyncio.sleep(1.5)
        typ_ruchu, akcja_bota = wybierz_akcje_dla_bota(gracz_w_turze, rozdanie)
        if typ_ruchu == 'karta':
            rozdanie.zagraj_karte(gracz_w_turze, akcja_bota)
            rozdanie.zagraj_karte(gracz_w_turze, akcja_bota)
        elif typ_ruchu == 'licytacja':
            if 'atut' in akcja_bota and akcja_bota['atut']:
                akcja_bota['atut'] = silnik_gry.Kolor[akcja_bota['atut']]
            if 'kontrakt' in akcja_bota and akcja_bota['kontrakt']:
                akcja_bota['kontrakt'] = silnik_gry.Kontrakt[akcja_bota['kontrakt']]
            rozdanie.wykonaj_akcje(gracz_w_turze, akcja_bota)
        else:
            break
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))