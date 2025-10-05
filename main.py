import random
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
from pydantic import BaseModel
from typing import Any

import silnik_gry

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gry = {}
HUMAN_PLAYER_NAME = "Jakub"

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    ranga_str, kolor_str = nazwa_karty.split()
    mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
    mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
    ranga = mapowanie_rang[ranga_str]
    kolor = mapowanie_kolorow[kolor_str]
    return silnik_gry.Karta(ranga=ranga, kolor=kolor)



@app.post("/gra/nowa")
def stworz_nowa_gre():
    gracze = [silnik_gry.Gracz(nazwa="Jakub"), silnik_gry.Gracz(nazwa="Przeciwnik1"), 
              silnik_gry.Gracz(nazwa="Nasz"), silnik_gry.Gracz(nazwa="Przeciwnik2")]
    druzyna_my = silnik_gry.Druzyna(nazwa="My"); druzyna_my.dodaj_gracza(gracze[2]); druzyna_my.dodaj_gracza(gracze[0]) # Nasz, Jakub
    druzyna_oni = silnik_gry.Druzyna(nazwa="Oni"); druzyna_oni.dodaj_gracza(gracze[1]); druzyna_oni.dodaj_gracza(gracze[3])
    druzyna_my.przeciwnicy = druzyna_oni; druzyna_oni.przeciwnicy = druzyna_my
    pierwsze_rozdanie = silnik_gry.Rozdanie(gracze=gracze, druzyny=[druzyna_my, druzyna_oni], rozdajacy_idx=0)
    pierwsze_rozdanie.rozpocznij_nowe_rozdanie()
    id_gry = str(uuid.uuid4()); gry[id_gry] = { "gracze": gracze, "druzyny": [druzyna_my, druzyna_oni], "rozdajacy_idx": 0, "aktualne_rozdanie": pierwsze_rozdanie, "status_partii": "W_TRAKCIE", "historia_rozdan": [] }
    
    print(f"Utworzono nową partię o ID: {id_gry}")
    return {"id_gry": id_gry}

@app.get("/gra/{id_gry}")
def pobierz_stan_gry(id_gry: str):
    if id_gry not in gry: raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    partia = gry[id_gry]; rozdanie = partia["aktualne_rozdanie"]
    mozliwe_akcje_oryginal = []
    kolej_gracza_idx = rozdanie.kolej_gracza_idx; gracz_w_turze = rozdanie.gracze[kolej_gracza_idx] if kolej_gracza_idx is not None else None
    if gracz_w_turze: mozliwe_akcje_oryginal = rozdanie.get_mozliwe_akcje(gracz_w_turze)
    mozliwe_akcje_json = []
    for akcja in mozliwe_akcje_oryginal:
        nowa_akcja = akcja.copy()
        if 'atut' in nowa_akcja and nowa_akcja['atut'] is not None: nowa_akcja['atut'] = nowa_akcja['atut'].name
        if 'kontrakt' in nowa_akcja and nowa_akcja['kontrakt'] is not None: nowa_akcja['kontrakt'] = nowa_akcja['kontrakt'].name
        mozliwe_akcje_json.append(nowa_akcja)
    grywalne_karty = []
    if gracz_w_turze and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        for karta in gracz_w_turze.reka:
            if rozdanie._waliduj_ruch(gracz_w_turze, karta): grywalne_karty.append(str(karta))
    stan_gry = {
        "status_partii": partia["status_partii"], "punkty_meczu": { d.nazwa: d.punkty_meczu for d in partia["druzyny"] },
        "rozdanie": {
            "faza": rozdanie.faza.name, "kolej_gracza": gracz_w_turze.nazwa if gracz_w_turze else None,
            "stawka": { "mnoznik_lufy": rozdanie.mnoznik_lufy },
            "kontrakt": { "typ": rozdanie.kontrakt.name if rozdanie.kontrakt else None, "atut": rozdanie.atut.name if rozdanie.atut else None, "grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None },
            "rece_graczy": { gracz.nazwa: [str(karta) for karta in gracz.reka] for gracz in rozdanie.gracze },
            "mozliwe_akcje": mozliwe_akcje_json, "punkty_w_rozdaniu": rozdanie.punkty_w_rozdaniu,
            "karty_na_stole": [ {"gracz": gracz.nazwa, "karta": str(karta)} for gracz, karta in rozdanie.aktualna_lewa ],
            "grywalne_karty": grywalne_karty,
            "historia_rozdania": rozdanie.szczegolowa_historia 
        }, 
        "historia_rozdan": partia["historia_rozdan"] 
    }
    return stan_gry

# --- PRZYWRÓCONA DEFINICJA KLASY AKCJA ---
class Akcja(BaseModel):
    gracz: str
    akcja: dict[str, Any]

@app.post("/gra/{id_gry}/akcja")
def wykonaj_akcje(id_gry: str, dane_akcji: Akcja):
    if id_gry not in gry: raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    partia = gry[id_gry]; rozdanie = partia["aktualne_rozdanie"]
    if partia["status_partii"] != "W_TRAKCIE": raise HTTPException(status_code=400, detail="Partia jest już zakończona")
    gracz_obj = next((g for g in rozdanie.gracze if g.nazwa == dane_akcji.gracz), None)
    if not gracz_obj: raise HTTPException(status_code=404, detail=f"Gracz o nazwie '{dane_akcji.gracz}' nie istnieje")

    typ_akcji = dane_akcji.akcja.get('typ')
    if typ_akcji == 'zagraj_karte':
        karta_obj = karta_ze_stringa(dane_akcji.akcja.get('karta'))
        if not rozdanie._waliduj_ruch(gracz_obj, karta_obj): raise HTTPException(status_code=400, detail="Niedozwolony ruch!")
        rozdanie.zagraj_karte(gracz_obj, karta_obj)
    else:
        if 'atut' in dane_akcji.akcja and dane_akcji.akcja['atut'] is not None: dane_akcji.akcja['atut'] = silnik_gry.Kolor[dane_akcji.akcja['atut']]
        if 'kontrakt' in dane_akcji.akcja and dane_akcji.akcja['kontrakt'] is not None: dane_akcji.akcja['kontrakt'] = silnik_gry.Kontrakt[dane_akcji.akcja['kontrakt']]
        rozdanie.wykonaj_akcje(gracz_obj, dane_akcji.akcja)

    

    return pobierz_stan_gry(id_gry)