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
import silnik_gry

app = FastAPI()
gry = {}

NAZWY_DRUZYN = [
    "Waleczne Asy", "Chytre Damy", "Królowie Kier", "Pikowi Mocarze",
    "TreflMasters", "Diamentowe Walety", "Dzwonkowe Bractwo", "Winni Zwycięzcy",
    "Mistrzowie Lewy", "Pogromcy Dziewiątek"
]

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
    while True:
        kod = ''.join(random.choices(string.ascii_uppercase + string.digits, k=dlugosc))
        if kod not in gry:
            return kod

def resetuj_gre_do_lobby(partia: dict):
    partia["status_partii"] = "LOBBY"
    partia["gracze_engine"] = []
    partia["druzyny_engine"] = []
    partia["aktualne_rozdanie"] = None
    partia["pelna_historia"] = []
    nazwy = partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
    partia["punkty_meczu"] = {nazwy["My"]: 0, nazwy["Oni"]: 0}
    partia["kicked_players"] = []
    partia["gracze_gotowi"] = []
    print(f"Partia {partia.get('id_gry', 'N/A')} wraca do lobby.")

def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    ranga_str, kolor_str = nazwa_karty.split()
    mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
    mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
    ranga = mapowanie_rang[ranga_str]
    kolor = mapowanie_kolorow[kolor_str]
    return silnik_gry.Karta(ranga=ranga, kolor=kolor)

def sprawdz_koniec_partii(partia: dict) -> bool:
    for druzyna in partia["druzyny_engine"]:
        if druzyna.punkty_meczu >= 66:
            partia["status_partii"] = "ZAKONCZONA"
            return True
    return False

def wybierz_akcje_dla_bota(bot: silnik_gry.Gracz, rozdanie: silnik_gry.Rozdanie) -> tuple[str, Any]:
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
def read_root():
    return FileResponse('static/start.html')

@app.get("/gra.html")
def read_game_page():
    return FileResponse('static/index.html')

@app.get("/zasady.html")
def read_rules_page():
    return FileResponse('static/zasady.html')

@app.post("/gra/nowa")
def stworz_nowa_gre():
    id_gry = generuj_krotki_id()
    nazwy = random.sample(NAZWY_DRUZYN, 2)
    nazwy_mapa = {"My": nazwy[0], "Oni": nazwy[1]}

    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "LOBBY", "host": None,
        "tryb_gry": "online",
        "nazwy_druzyn": nazwy_mapa,
        "slots": [
            {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 1, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
            {"slot_id": 2, "nazwa": None, "typ": "pusty", "druzyna": "My"},
            {"slot_id": 3, "nazwa": None, "typ": "pusty", "druzyna": "Oni"},
        ],
        "gracze_engine": [], "druzyny_engine": [], "aktualne_rozdanie": None,
        "pelna_historia": [],
        "punkty_meczu": {nazwy_mapa["My"]: 0, nazwy_mapa["Oni"]: 0},
        "kicked_players": [], "gracze_gotowi": []
    }
    return {"id_gry": id_gry}

@app.post("/gra/nowa/lokalna")
def stworz_gre_lokalna():
    id_gry = generuj_krotki_id()
    slots = [
        {"slot_id": 0, "nazwa": None, "typ": "pusty", "druzyna": "My"},
        {"slot_id": 1, "nazwa": "Bot_1", "typ": "bot", "druzyna": "Oni"},
        {"slot_id": 2, "nazwa": "Bot_2", "typ": "bot", "druzyna": "My"},
        {"slot_id": 3, "nazwa": "Bot_3", "typ": "bot", "druzyna": "Oni"},
    ]
    d_my, d_oni = silnik_gry.Druzyna("My"), silnik_gry.Druzyna("Oni")
    d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
    gracze_tmp = [None] * 4
    for slot in slots:
        if slot["typ"] == "bot":
            g = silnik_gry.Gracz(slot["nazwa"])
            gracze_tmp[slot["slot_id"]] = g
            (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)

    gry[id_gry] = {
        "id_gry": id_gry, "status_partii": "W_TRAKCIE", "host": "Gracz", "slots": slots,
        "tryb_gry": "lokalna",
        "nazwy_druzyn": {"My": "My", "Oni": "Oni"},
        "gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni],
        "aktualne_rozdanie": None, "pelna_historia": [],
        "punkty_meczu": {"My": 0, "Oni": 0}, "kicked_players": [],
        "gracze_gotowi": []
    }
    partia = gry[id_gry]
    rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], 0)
    partia["aktualne_rozdanie"] = rozdanie
    return {"id_gry": id_gry}

@app.get("/gra/sprawdz/{id_gry}")
def sprawdz_gre(id_gry: str):
    return {"exists": id_gry in gry}

def pobierz_stan_gry(id_gry: str) -> dict:
    partia = gry.get(id_gry)
    if not partia: return {"error": "Gra nie istnieje"}

    stan_podstawowy = {
        "status_partii": partia["status_partii"],
        "tryb_gry": partia.get("tryb_gry", "online"),
        "slots": partia["slots"],
        "host": partia["host"],
        "gracze_gotowi": partia.get("gracze_gotowi", []),
        "nazwy_druzyn": partia.get("nazwy_druzyn", {"My": "My", "Oni": "Oni"})
    }

    if partia['status_partii'] == 'LOBBY':
        stan_podstawowy["punkty_meczu"] = partia["punkty_meczu"]
        return stan_podstawowy
        
    # --- POCZĄTEK ZMIANY ---
    if partia['status_partii'] == 'ZAKONCZONA':
        if partia.get("druzyny_engine"):
            stan_podstawowy["punkty_meczu"] = {d.nazwa: d.punkty_meczu for d in partia["druzyny_engine"]}
        else:
            stan_podstawowy["punkty_meczu"] = partia["punkty_meczu"]
        return stan_podstawowy
    # --- KONIEC ZMIANY ---

    rozdanie = partia.get("aktualne_rozdanie")
    if not rozdanie:
        stan_podstawowy["punkty_meczu"] = partia["punkty_meczu"]
        return stan_podstawowy

    gracz_w_turze_obj = None
    if rozdanie.kolej_gracza_idx is not None:
        if len(rozdanie.gracze) > rozdanie.kolej_gracza_idx and rozdanie.gracze[rozdanie.kolej_gracza_idx]:
             gracz_w_turze_obj = rozdanie.gracze[rozdanie.kolej_gracza_idx]

    stan_podstawowy.update({
        "punkty_meczu": {d.nazwa: d.punkty_meczu for d in partia["druzyny_engine"]},
        "rozdanie": {
            "faza": rozdanie.faza,
            "kolej_gracza": gracz_w_turze_obj.nazwa if gracz_w_turze_obj else None,
            "rece_graczy": {g.nazwa: [str(k) for k in g.reka] for g in rozdanie.gracze if g},
            "karty_na_stole": [{"gracz": g.nazwa, "karta": str(k)} for g, k in rozdanie.aktualna_lewa],
            "grywalne_karty": [str(k) for k in gracz_w_turze_obj.reka if rozdanie._waliduj_ruch(gracz_w_turze_obj, k)] if gracz_w_turze_obj and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA else [],
            "mozliwe_akcje": rozdanie.get_mozliwe_akcje(gracz_w_turze_obj) if gracz_w_turze_obj else [],
            "punkty_w_rozdaniu": rozdanie.punkty_w_rozdaniu,
            "kontrakt": {"typ": rozdanie.kontrakt, "atut": rozdanie.atut},
            "aktualna_stawka": rozdanie.oblicz_aktualna_stawke(),
            "gracz_grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None,
            "historia_rozdania": rozdanie.szczegolowa_historia,
            "podsumowanie": rozdanie.podsumowanie,
            "lewa_do_zamkniecia": rozdanie.lewa_do_zamkniecia,
        }
    })
    return stan_podstawowy

@app.websocket("/ws/{id_gry}/{nazwa_gracza}")
async def websocket_endpoint(websocket: WebSocket, id_gry: str, nazwa_gracza: str):
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
        
        elif partia["status_partii"] == "W_TRAKCIE" and any(s['typ'] == 'pusty' for s in partia['slots']):
            slot = next((s for s in partia["slots"] if s["typ"] == "pusty"), None)
            if slot and not any(g for g in partia["gracze_engine"] if g and g.nazwa == nazwa_gracza):
                slot["typ"], slot["nazwa"] = "czlowiek", nazwa_gracza
                nowy_gracz = silnik_gry.Gracz(nazwa_gracza)
                partia["gracze_engine"][slot["slot_id"]] = nowy_gracz
                
                nazwa_druzyny_slota = partia["nazwy_druzyn"][slot["druzyna"]]
                druzyna_gracza = next(d for d in partia["druzyny_engine"] if d.nazwa == nazwa_druzyny_slota)
                druzyna_gracza.dodaj_gracza(nowy_gracz)
                
                rozdajacy_idx = partia["aktualne_rozdanie"].rozdajacy_idx if partia.get("aktualne_rozdanie") else 0
                nowe_rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], rozdajacy_idx)
                partia["aktualne_rozdanie"] = nowe_rozdanie
                nowe_rozdanie.rozpocznij_nowe_rozdanie()

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
            nazwy = partia["nazwy_druzyn"]
            d_my = silnik_gry.Druzyna(nazwy["My"])
            d_oni = silnik_gry.Druzyna(nazwy["Oni"])
            
            d_my.przeciwnicy, d_oni.przeciwnicy = d_oni, d_my
            gracze_tmp = [None] * 4
            for slot in partia["slots"]:
                g = silnik_gry.Gracz(slot["nazwa"])
                gracze_tmp[slot["slot_id"]] = g
                (d_my if slot["druzyna"] == "My" else d_oni).dodaj_gracza(g)
            
            partia.update({"gracze_engine": gracze_tmp, "druzyny_engine": [d_my, d_oni], "status_partii": "W_TRAKCIE"})
            rozdanie = silnik_gry.Rozdanie(gracze_tmp, [d_my, d_oni], 0)
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
                    nowe_rozdanie = silnik_gry.Rozdanie(partia["gracze_engine"], partia["druzyny_engine"], nowy_idx)
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
        elif typ_ruchu == 'licytacja':
            if 'atut' in akcja_bota and akcja_bota['atut']:
                akcja_bota['atut'] = silnik_gry.Kolor[akcja_bota['atut']]
            if 'kontrakt' in akcja_bota and akcja_bota['kontrakt']:
                akcja_bota['kontrakt'] = silnik_gry.Kontrakt[akcja_bota['kontrakt']]
            rozdanie.wykonaj_akcje(gracz_w_turze, akcja_bota)
        else:
            break
        
        await manager.broadcast(id_gry, pobierz_stan_gry(id_gry))