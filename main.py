"""
Główny plik aplikacji FastAPI do obsługi gry w 66.
"""
import uuid
import random
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import silnik_gry

# --- 1. Inicjalizacja Aplikacji i Middleware ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. Zarządzanie Stanem Gry i Definicje ---
gry = {}
HUMAN_PLAYER_NAME = "Jakub"

# --- 3. Modele Pydantic ---
class Akcja(BaseModel):
    gracz: str
    akcja: dict[str, Any]

# --- 4. Funkcje Pomocnicze ---
def karta_ze_stringa(nazwa_karty: str) -> silnik_gry.Karta:
    """Konwertuje nazwę karty (string) na obiekt klasy Karta."""
    ranga_str, kolor_str = nazwa_karty.split()
    mapowanie_rang = {r.name.capitalize(): r for r in silnik_gry.Ranga}
    mapowanie_kolorow = {k.name.capitalize(): k for k in silnik_gry.Kolor}
    ranga = mapowanie_rang[ranga_str]
    kolor = mapowanie_kolorow[kolor_str]
    return silnik_gry.Karta(ranga=ranga, kolor=kolor)

def sprawdz_koniec_partii(partia):
    """Sprawdza, czy któraś z drużyn osiągnęła 66 punktów i aktualizuje status partii."""
    for druzyna in partia["druzyny"]:
        if druzyna.punkty_meczu >= 66:
            partia["status_partii"] = "ZAKONCZONA"
            return True
    return False

# --- 5. Logika Bota (AI) ---
def wybierz_akcje_dla_bota(bot: silnik_gry.Gracz, rozdanie: silnik_gry.Rozdanie) -> tuple[str, Any]:
    """
    Wybiera akcję dla bota. W przyszłości tutaj podepniemy modele ML.
    Zwraca typ akcji ('karta' lub 'licytacja') oraz samą akcję.
    """
    # === AKTUALNA LOGIKA: "GŁUPI BOT" ===
    if rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        grywalne_karty = [k for k in bot.reka if rozdanie._waliduj_ruch(bot, k)]
        if grywalne_karty:
            return 'karta', random.choice(grywalne_karty)
    else:
        mozliwe_akcje = rozdanie.get_mozliwe_akcje(bot)
        if mozliwe_akcje:
            return 'licytacja', random.choice(mozliwe_akcje)
    return 'brak', None

def uruchom_petle_ai(partia: dict, rozdanie: silnik_gry.Rozdanie):
    """Wykonuje ruchy botów, aż dojdzie do tury człowieka lub końca rozdania."""
    while (
        rozdanie.kolej_gracza_idx is not None and
        rozdanie.gracze[rozdanie.kolej_gracza_idx].nazwa != HUMAN_PLAYER_NAME and
        rozdanie.faza not in [silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA] and
        partia["status_partii"] == "W_TRAKCIE"
    ):
        bot = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        typ_ruchu, akcja = wybierz_akcje_dla_bota(bot, rozdanie)

        if typ_ruchu == 'karta':
            rozdanie.zagraj_karte(bot, akcja)
        elif typ_ruchu == 'licytacja':
            rozdanie.wykonaj_akcje(bot, akcja)
        else:
            # Przerwij pętlę, jeśli bot nie ma żadnego ruchu (bezpiecznik)
            break
        time.sleep(1.5)
    

# --- 6. Serwowanie Plików Statycznych ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    """Serwuje stronę startową."""
    return FileResponse('static/start.html')

@app.get("/gra.html")
def read_game_page():
    """Serwuje stronę z interfejsem gry."""
    return FileResponse('static/index.html')

# --- 7. Główne Endpointy API Gry ---
@app.post("/gra/nowa")
def stworz_nowa_gre():
    """Tworzy nową partię gry i zwraca jej unikalne ID."""
    gracze = [
        silnik_gry.Gracz(nazwa="Jakub"), silnik_gry.Gracz(nazwa="Przeciwnik1"), 
        silnik_gry.Gracz(nazwa="Nasz"), silnik_gry.Gracz(nazwa="Przeciwnik2")
    ]
    druzyna_my = silnik_gry.Druzyna(nazwa="My")
    druzyna_my.dodaj_gracza(gracze[0]) # Jakub
    druzyna_my.dodaj_gracza(gracze[2]) # Nasz
    
    druzyna_oni = silnik_gry.Druzyna(nazwa="Oni")
    druzyna_oni.dodaj_gracza(gracze[1]) # Przeciwnik1
    druzyna_oni.dodaj_gracza(gracze[3]) # Przeciwnik2
    
    druzyna_my.przeciwnicy = druzyna_oni
    druzyna_oni.przeciwnicy = druzyna_my
    
    id_gry = str(uuid.uuid4())
    gry[id_gry] = {
        "gracze": gracze,
        "druzyny": [druzyna_my, druzyna_oni],
        "aktualne_rozdanie": None, # Zostanie utworzone za chwilę
        "status_partii": "W_TRAKCIE",
        "pelna_historia": []
    }
    
    pierwsze_rozdanie = silnik_gry.Rozdanie(gracze=gracze, druzyny=[druzyna_my, druzyna_oni], rozdajacy_idx=0)
    pierwsze_rozdanie.rozpocznij_nowe_rozdanie()
    gry[id_gry]["aktualne_rozdanie"] = pierwsze_rozdanie
    
    # Uruchom pętlę AI od razu po stworzeniu gry, jeśli pierwszy ruch nie należy do człowieka
    uruchom_petle_ai(gry[id_gry], pierwsze_rozdanie)

    print(f"Utworzono nową partię o ID: {id_gry}")
    return {"id_gry": id_gry}

@app.get("/gra/{id_gry}")
def pobierz_stan_gry(id_gry: str):
    """Pobiera aktualny, pełny stan gry dla danego ID."""
    if id_gry not in gry:
        raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    
    partia = gry[id_gry]
    rozdanie = partia["aktualne_rozdanie"]
    
    wszystkie_logi = partia["pelna_historia"] + rozdanie.szczegolowa_historia
    
    przetworzona_historia = []
    for log in wszystkie_logi:
        nowy_log = log.copy()
        if log['typ'] == 'akcja_licytacyjna' and 'akcja' in log:
            nowa_akcja_logu = log['akcja'].copy()
            if 'atut' in nowa_akcja_logu and isinstance(nowa_akcja_logu['atut'], silnik_gry.Kolor):
                nowa_akcja_logu['atut'] = nowa_akcja_logu['atut'].name
            if 'kontrakt' in nowa_akcja_logu and isinstance(nowa_akcja_logu['kontrakt'], silnik_gry.Kontrakt):
                nowa_akcja_logu['kontrakt'] = nowa_akcja_logu['kontrakt'].name
            nowy_log['akcja'] = nowa_akcja_logu
        przetworzona_historia.append(nowy_log)

    gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx] if rozdanie.kolej_gracza_idx is not None else None
    
    mozliwe_akcje_json = []
    if gracz_w_turze:
        for akcja in rozdanie.get_mozliwe_akcje(gracz_w_turze):
            nowa_akcja = akcja.copy()
            if 'atut' in nowa_akcja and nowa_akcja['atut']: nowa_akcja['atut'] = nowa_akcja['atut'].name
            if 'kontrakt' in nowa_akcja and nowa_akcja['kontrakt']: nowa_akcja['kontrakt'] = nowa_akcja['kontrakt'].name
            mozliwe_akcje_json.append(nowa_akcja)
            
    grywalne_karty = []
    if gracz_w_turze and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        for karta in gracz_w_turze.reka:
            if rozdanie._waliduj_ruch(gracz_w_turze, karta):
                grywalne_karty.append(str(karta))

    stan_gry = {
        "status_partii": partia["status_partii"],
        "punkty_meczu": {d.nazwa: d.punkty_meczu for d in partia["druzyny"]},
        "rozdanie": {
            "faza": rozdanie.faza.name,
            "kolej_gracza": gracz_w_turze.nazwa if gracz_w_turze else None,
            "stawka": { "mnoznik_lufy": rozdanie.mnoznik_lufy },
            "kontrakt": { "typ": rozdanie.kontrakt.name if rozdanie.kontrakt else None, "atut": rozdanie.atut.name if rozdanie.atut else None, "grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None },
            "rece_graczy": {gracz.nazwa: [str(karta) for karta in gracz.reka] for gracz in rozdanie.gracze},
            "mozliwe_akcje": mozliwe_akcje_json,
            "punkty_w_rozdaniu": rozdanie.punkty_w_rozdaniu,
            "karty_na_stole": [{"gracz": gracz.nazwa, "karta": str(karta)} for gracz, karta in rozdanie.aktualna_lewa],
            "grywalne_karty": grywalne_karty,
            "historia_rozdania": przetworzona_historia,
            "podsumowanie": rozdanie.podsumowanie
        }
    }
    return stan_gry

@app.post("/gra/{id_gry}/akcja")
def wykonaj_akcje(id_gry: str, dane_akcji: Akcja):
    """Przetwarza JEDNĄ akcję wykonaną przez gracza (tylko człowieka)."""
    partia = gry.get(id_gry)
    if not partia: raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    
    rozdanie = partia["aktualne_rozdanie"]
    
    # Przenosimy logikę "następnego rozdania" tutaj, bo to akcja gracza
    if dane_akcji.akcja.get('typ') == 'nastepne_rozdanie':
        partia["pelna_historia"].extend(rozdanie.szczegolowa_historia)
        if sprawdz_koniec_partii(partia):
            return pobierz_stan_gry(id_gry)
        
        nowy_rozdajacy_idx = (rozdanie.rozdajacy_idx + 1) % len(partia["gracze"])
        for gracz in partia["gracze"]:
            gracz.reka.clear(); gracz.wygrane_karty.clear()
        
        nowe_rozdanie = silnik_gry.Rozdanie(gracze=partia["gracze"], druzyny=partia["druzyny"], rozdajacy_idx=nowy_rozdajacy_idx)
        nowe_rozdanie.rozpocznij_nowe_rozdanie()
        partia["aktualne_rozdanie"] = nowe_rozdanie
        return pobierz_stan_gry(id_gry)

    if partia["status_partii"] != "W_TRAKCIE":
        raise HTTPException(status_code=400, detail="Partia jest już zakończona")
        
    gracz_obj = next((g for g in rozdanie.gracze if g.nazwa == dane_akcji.gracz), None)
    if not gracz_obj: raise HTTPException(status_code=404, detail=f"Gracz '{dane_akcji.gracz}' nie istnieje")

    typ_akcji = dane_akcji.akcja.get('typ')
    if typ_akcji == 'zagraj_karte':
        karta_obj = karta_ze_stringa(dane_akcji.akcja.get('karta'))
        rozdanie.zagraj_karte(gracz_obj, karta_obj)
    else:
        # Konwersja na Enumy
        if 'atut' in dane_akcji.akcja and dane_akcji.akcja['atut']:
            dane_akcji.akcja['atut'] = silnik_gry.Kolor[dane_akcji.akcja['atut']]
        if 'kontrakt' in dane_akcji.akcja and dane_akcji.akcja['kontrakt']:
            dane_akcji.akcja['kontrakt'] = silnik_gry.Kontrakt[dane_akcji.akcja['kontrakt']]
        rozdanie.wykonaj_akcje(gracz_obj, dane_akcji.akcja)

    return pobierz_stan_gry(id_gry)

@app.post("/gra/{id_gry}/ruch_bota")
def wykonaj_ruch_bota(id_gry: str):
    """Endpoint wyzwalany przez klienta, aby wykonać JEDEN ruch bota."""
    partia = gry.get(id_gry)
    if not partia: raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    
    rozdanie = partia["aktualne_rozdanie"]
    
    if (rozdanie.kolej_gracza_idx is not None and
        rozdanie.gracze[rozdanie.kolej_gracza_idx].nazwa != HUMAN_PLAYER_NAME and
        rozdanie.faza not in [silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA]):
        
        bot = rozdanie.gracze[rozdanie.kolej_gracza_idx]
        typ_ruchu, akcja = wybierz_akcje_dla_bota(bot, rozdanie)

        if typ_ruchu == 'karta':
            rozdanie.zagraj_karte(bot, akcja)
        elif typ_ruchu == 'licytacja':
            rozdanie.wykonaj_akcje(bot, akcja)

    return pobierz_stan_gry(id_gry)