"""
Główny plik aplikacji FastAPI do obsługi gry w 66.
"""
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# --- 2. Zarządzanie Stanem Gry (przechowywanie w pamięci) ---
gry = {}

# --- 3. Modele Pydantic do Walidacji Danych ---
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

# --- 5. Serwowanie Plików Statycznych (HTML, CSS, JS) ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    """Serwuje stronę startową."""
    return FileResponse('static/start.html')

@app.get("/gra.html")
def read_game_page():
    """Serwuje stronę z interfejsem gry."""
    return FileResponse('static/index.html')

# --- 6. Główne Endpointy API Gry ---
@app.post("/gra/nowa")
def stworz_nowa_gre():
    """Tworzy nową partię gry i zwraca jej unikalne ID."""
    gracze = [
        silnik_gry.Gracz(nazwa="Jakub"), silnik_gry.Gracz(nazwa="Przeciwnik1"), 
        silnik_gry.Gracz(nazwa="Nasz"), silnik_gry.Gracz(nazwa="Przeciwnik2")
    ]
    druzyna_my = silnik_gry.Druzyna(nazwa="My")
    druzyna_my.dodaj_gracza(gracze[2]) # Nasz
    druzyna_my.dodaj_gracza(gracze[0]) # Jakub
    
    druzyna_oni = silnik_gry.Druzyna(nazwa="Oni")
    druzyna_oni.dodaj_gracza(gracze[1]) # Przeciwnik1
    druzyna_oni.dodaj_gracza(gracze[3]) # Przeciwnik2
    
    druzyna_my.przeciwnicy = druzyna_oni
    druzyna_oni.przeciwnicy = druzyna_my
    
    pierwsze_rozdanie = silnik_gry.Rozdanie(gracze=gracze, druzyny=[druzyna_my, druzyna_oni], rozdajacy_idx=0)
    pierwsze_rozdanie.rozpocznij_nowe_rozdanie()
    
    id_gry = str(uuid.uuid4())
    gry[id_gry] = {
        "gracze": gracze,
        "druzyny": [druzyna_my, druzyna_oni],
        "aktualne_rozdanie": pierwsze_rozdanie,
        "status_partii": "W_TRAKCIE",
        "pelna_historia": []
    }
    
    print(f"Utworzono nową partię o ID: {id_gry}")
    return {"id_gry": id_gry}

@app.get("/gra/{id_gry}")
def pobierz_stan_gry(id_gry: str):
    """Pobiera aktualny, pełny stan gry dla danego ID."""
    if id_gry not in gry:
        raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
    
    partia = gry[id_gry]
    rozdanie = partia["aktualne_rozdanie"]
    
    # Krok 1: Przygotowanie pełnej, połączonej historii
    wszystkie_logi = partia["pelna_historia"] + rozdanie.szczegolowa_historia
    
    # Krok 2: Przetworzenie historii na format JSON (NAPRAWA BŁĘDU PODWÓJNYCH LOGÓW)
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
        przetworzona_historia.append(nowy_log) # Log jest dodawany tylko RAZ

    # Krok 3: Ustalenie możliwych akcji dla gracza w turze
    gracz_w_turze = rozdanie.gracze[rozdanie.kolej_gracza_idx] if rozdanie.kolej_gracza_idx is not None else None
    mozliwe_akcje_json = []
    if gracz_w_turze:
        for akcja in rozdanie.get_mozliwe_akcje(gracz_w_turze):
            nowa_akcja = akcja.copy()
            if 'atut' in nowa_akcja and nowa_akcja['atut']: nowa_akcja['atut'] = nowa_akcja['atut'].name
            if 'kontrakt' in nowa_akcja and nowa_akcja['kontrakt']: nowa_akcja['kontrakt'] = nowa_akcja['kontrakt'].name
            mozliwe_akcje_json.append(nowa_akcja)
            
    # Krok 4: Ustalenie grywalnych kart
    grywalne_karty = []
    if gracz_w_turze and rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
        for karta in gracz_w_turze.reka:
            if rozdanie._waliduj_ruch(gracz_w_turze, karta):
                grywalne_karty.append(str(karta))

    # Krok 5: Złożenie finalnego obiektu stanu gry
    stan_gry = {
        "status_partii": partia["status_partii"],
        "punkty_meczu": {d.nazwa: d.punkty_meczu for d in partia["druzyny"]},
        "rozdanie": {
            "faza": rozdanie.faza.name,
            "kolej_gracza": gracz_w_turze.nazwa if gracz_w_turze else None,
            "kontrakt": {
                "typ": rozdanie.kontrakt.name if rozdanie.kontrakt else None,
                "atut": rozdanie.atut.name if rozdanie.atut else None,
                "grajacy": rozdanie.grajacy.nazwa if rozdanie.grajacy else None
            },
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
    """Przetwarza akcję wykonaną przez gracza."""
    if id_gry not in gry:
        raise HTTPException(status_code=404, detail="Gra o podanym ID nie istnieje")
        
    partia = gry[id_gry]
    rozdanie = partia["aktualne_rozdanie"]

    # Scenariusz 1: Gracz klika "Następne Rozdanie"
    if dane_akcji.akcja.get('typ') == 'nastepne_rozdanie':
        partia["pelna_historia"].extend(rozdanie.szczegolowa_historia)
        
        if sprawdz_koniec_partii(partia):
            return pobierz_stan_gry(id_gry)

        nowy_rozdajacy_idx = (rozdanie.rozdajacy_idx + 1) % 4
        for gracz in partia["gracze"]:
            gracz.reka.clear(); gracz.wygrane_karty.clear()

        nowe_rozdanie = silnik_gry.Rozdanie(
            gracze=partia["gracze"],
            druzyny=partia["druzyny"],
            rozdajacy_idx=nowy_rozdajacy_idx
        )
        nowe_rozdanie.rozpocznij_nowe_rozdanie()
        partia["aktualne_rozdanie"] = nowe_rozdanie
        return pobierz_stan_gry(id_gry)
    
    if partia["status_partii"] != "W_TRAKCIE":
        raise HTTPException(status_code=400, detail="Partia jest już zakończona")

    # Scenariusz 2: Akcja w trakcie gry (licytacja, zagranie karty)
    gracz_obj = next((g for g in rozdanie.gracze if g.nazwa == dane_akcji.gracz), None)
    if not gracz_obj:
        raise HTTPException(status_code=404, detail=f"Gracz '{dane_akcji.gracz}' nie istnieje")

    typ_akcji = dane_akcji.akcja.get('typ')
    if typ_akcji == 'zagraj_karte':
        karta_obj = karta_ze_stringa(dane_akcji.akcja.get('karta'))
        rozdanie.zagraj_karte(gracz_obj, karta_obj)
    else:
        # Przekształcenie stringów z JSON na obiekty Enum dla silnika gry
        if 'atut' in dane_akcji.akcja and dane_akcji.akcja['atut']:
            dane_akcji.akcja['atut'] = silnik_gry.Kolor[dane_akcji.akcja['atut']]
        if 'kontrakt' in dane_akcji.akcja and dane_akcji.akcja['kontrakt']:
            dane_akcji.akcja['kontrakt'] = silnik_gry.Kontrakt[dane_akcji.akcja['kontrakt']]
        
        rozdanie.wykonaj_akcje(gracz_obj, dane_akcji.akcja)

    return pobierz_stan_gry(id_gry)