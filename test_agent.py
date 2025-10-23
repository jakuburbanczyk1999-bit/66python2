# plik: test_agent_v8.py

import os
import random
import silnik_gry
import numpy as np
from collections import OrderedDict, defaultdict

# === KROK 1: IMPORT NARZĘDZI I MODELU ===
import gymnasium as gym
from gymnasium import spaces
from sb3_contrib import MaskablePPO

# === KROK 2: DEFINICJE I MAPOWANIA (identyczne jak w treningu v8) ===
KOLORY = OrderedDict([(kolor, i) for i, kolor in enumerate(silnik_gry.Kolor)])
RANGI = OrderedDict([(ranga, i) for i, ranga in enumerate(silnik_gry.Ranga)])
KONTRATY = OrderedDict([(kontrakt, i) for i, kontrakt in enumerate(silnik_gry.Kontrakt)])
ROZMIAR_TALII = len(KOLORY) * len(RANGI)
LICZBA_GRACZY = 4
WSZYSTKIE_KARTY = [silnik_gry.Karta(r, k) for k in KOLORY for r in RANGI]

def mapuj_karte_na_indeks(karta: silnik_gry.Karta) -> int:
    return KOLORY[karta.kolor] * len(RANGI) + RANGI[karta.ranga]

AKCJE_LICYTACJI = [
    {'typ': 'pas'}, {'typ': 'lufa'}, {'typ': 'kontra'}, {'typ': 'pas_lufa'}, {'typ': 'pytanie'},
    {'typ': 'zmiana_kontraktu', 'kontrakt': silnik_gry.Kontrakt.LEPSZA},
    {'typ': 'zmiana_kontraktu', 'kontrakt': silnik_gry.Kontrakt.GORSZA},
    {'typ': 'zmiana_kontraktu', 'kontrakt': silnik_gry.Kontrakt.BEZ_PYTANIA},
    {'typ': 'przebicie', 'kontrakt': silnik_gry.Kontrakt.LEPSZA},
    {'typ': 'przebicie', 'kontrakt': silnik_gry.Kontrakt.GORSZA},
]
for kontrakt in silnik_gry.Kontrakt:
    if kontrakt in [silnik_gry.Kontrakt.LEPSZA, silnik_gry.Kontrakt.GORSZA]:
        AKCJE_LICYTACJI.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': None})
    else:
        for kolor in silnik_gry.Kolor:
            AKCJE_LICYTACJI.append({'typ': 'deklaracja', 'kontrakt': kontrakt, 'atut': kolor})

MAPOWANIE_AKCJI = AKCJE_LICYTACJI + [{'typ': 'zagraj_karte', 'karta': karta} for karta in WSZYSTKIE_KARTY]
LICZBA_AKCJI = len(MAPOWANIE_AKCJI)
PYTANIE_ACTION_INDEX = MAPOWANIE_AKCJI.index({'typ': 'pytanie'})

# === KROK 3: KLASA ŚRODOWISKA Z PEŁNĄ WIZJĄ ===
class SrodowiskoGry66(gym.Env):
    def __init__(self):
        super(SrodowiskoGry66, self).__init__()
        # ZMIANA 1: Nowy, poprawny rozmiar wektora obserwacji (69)
        self.observation_space = spaces.Box(low=-1.0, high=120.0, shape=(69,), dtype=np.float32)
        self.action_space = spaces.Discrete(LICZBA_AKCJI)
        self.gracze = [silnik_gry.Gracz(f"Agent-{i}") for i in range(LICZBA_GRACZY)]
        self.druzyna_A = silnik_gry.Druzyna("Drużyna AI")
        self.druzyna_B = silnik_gry.Druzyna("Drużyna Losowa")
        self.druzyna_A.dodaj_gracza(self.gracze[0]); self.druzyna_A.dodaj_gracza(self.gracze[2])
        self.druzyna_B.dodaj_gracza(self.gracze[1]); self.druzyna_B.dodaj_gracza(self.gracze[3])
        self.druzyna_A.przeciwnicy, self.druzyna_B.przeciwnicy = self.druzyna_B, self.druzyna_A
        self.rozdanie = None
        self.rozdajacy_idx = -1
        self.wygrane_partie_AI = 0
        self.statystyki = {
            'normalna_ai_zagrania': 0, 'normalna_ai_wygrane': 0,
            'normalna_losowy_zagrania': 0, 'normalna_losowy_wygrane': 0,
        }

    # ZMIANA 2: Nowa, w pełni inteligentna funkcja _pobierz_stan
    def _pobierz_stan(self, idx_gracza: int):
        gracz = self.gracze[idx_gracza]
        reka_wektor = np.zeros(ROZMIAR_TALII)
        for karta in gracz.reka:
            reka_wektor[mapuj_karte_na_indeks(karta)] = 1.0
        punkty_w_kolorach = np.zeros(len(KOLORY)); liczba_kart_w_kolorach = np.zeros(len(KOLORY))
        czy_ma_meldunek = np.zeros(len(KOLORY)); ma_krola = np.zeros(len(KOLORY), dtype=bool)
        ma_dame = np.zeros(len(KOLORY), dtype=bool)
        for karta in gracz.reka:
            kolor_idx = KOLORY[karta.kolor]
            punkty_w_kolorach[kolor_idx] += karta.wartosc
            liczba_kart_w_kolorach[kolor_idx] += 1
            if karta.ranga == silnik_gry.Ranga.KROL: ma_krola[kolor_idx] = True
            elif karta.ranga == silnik_gry.Ranga.DAMA: ma_dame[kolor_idx] = True
        czy_ma_meldunek = np.logical_and(ma_krola, ma_dame).astype(np.float32)
        calkowite_punkty_reki = np.sum(punkty_w_kolorach)
        inteligentne_cechy = np.concatenate([punkty_w_kolorach, liczba_kart_w_kolorach, czy_ma_meldunek, [calkowite_punkty_reki]])
        stol_wektor = np.zeros(ROZMIAR_TALII)
        for _, karta in self.rozdanie.aktualna_lewa: stol_wektor[mapuj_karte_na_indeks(karta)] = 1.0
        kontrakt_typ = -1 if self.rozdanie.kontrakt is None else KONTRATY[self.rozdanie.kontrakt]
        atut_kolor = -1 if self.rozdanie.atut is None else KOLORY[self.rozdanie.atut]
        kolej_gracza_idx_stan = -1 if self.rozdanie.kolej_gracza_idx is None else self.rozdanie.kolej_gracza_idx
        kontekst_wektor = np.array([
            (self.druzyna_A.punkty_meczu if idx_gracza % 2 == 0 else self.druzyna_B.punkty_meczu) / 66.0,
            (self.druzyna_B.punkty_meczu if idx_gracza % 2 == 0 else self.druzyna_A.punkty_meczu) / 66.0,
            kontrakt_typ, atut_kolor, self.rozdanie.mnoznik_lufy,
            kolej_gracza_idx_stan, self.rozdajacy_idx,
            1.0 if self.rozdanie.grajacy and self.rozdanie.grajacy.druzyna == gracz.druzyna else 0.0,
        ])
        return np.concatenate([reka_wektor, inteligentne_cechy, stol_wektor, kontekst_wektor]).astype(np.float32)

    # ... reszta klasy jest identyczna jak w teście v7 ...
    def step(self, akcja_idx: int):
        self._wykonaj_akcje(self.rozdanie.kolej_gracza_idx, akcja_idx)
        self._obsluz_automatyczne_kroki()
        done = False
        if self.rozdanie.faza == silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA:
            self._zaktualizuj_statystyki_rozdania()
            if self.druzyna_A.punkty_meczu >= 66 or self.druzyna_B.punkty_meczu >= 66:
                done = True
                if self.druzyna_A.punkty_meczu >= 66: self.wygrane_partie_AI += 1
            else:
                self._start_new_hand()
                self._obsluz_automatyczne_kroki()
        kolej_gracza = self.rozdanie.kolej_gracza_idx if not done else 0
        obs = self._pobierz_stan(kolej_gracza)
        info = {'action_mask': self.action_masks()}
        return obs, 0, done, False, info
    def _zaktualizuj_statystyki_rozdania(self):
        podsumowanie = self.rozdanie.podsumowanie
        if not podsumowanie or not self.rozdanie.grajacy: return
        gracz_rozgrywajacy = self.rozdanie.grajacy
        wygrana_druzyna_nazwa = podsumowanie.get("wygrana_druzyna")
        if gracz_rozgrywajacy.druzyna == self.druzyna_A:
            self.statystyki['normalna_ai_zagrania'] += 1
            if wygrana_druzyna_nazwa == self.druzyna_A.nazwa: self.statystyki['normalna_ai_wygrane'] += 1
        else:
            self.statystyki['normalna_losowy_zagrania'] += 1
            if wygrana_druzyna_nazwa == self.druzyna_B.nazwa: self.statystyki['normalna_losowy_wygrane'] += 1
    def _pobierz_maske_akcji(self, idx_gracza: int) -> np.ndarray:
        maska = np.zeros(LICZBA_AKCJI, dtype=bool)
        gracz = self.gracze[idx_gracza]
        if self.rozdanie.faza == silnik_gry.FazaGry.FAZA_PYTANIA:
            maska[PYTANIE_ACTION_INDEX] = True
            return maska
        if self.rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
            offset = len(AKCJE_LICYTACJI)
            for i, karta in enumerate(WSZYSTKIE_KARTY):
                if karta in gracz.reka and self.rozdanie._waliduj_ruch(gracz, karta): maska[offset + i] = True
        else:
            mozliwe_akcje = self.rozdanie.get_mozliwe_akcje(gracz)
            for i, akcja_master in enumerate(AKCJE_LICYTACJI):
                if akcja_master in mozliwe_akcje:
                    kontrakt_w_akcji = akcja_master.get('kontrakt')
                    typ_akcji = akcja_master.get('typ')
                    if typ_akcji in ['lufa', 'kontra', 'pytanie']: continue
                    if kontrakt_w_akcji is None or kontrakt_w_akcji == silnik_gry.Kontrakt.NORMALNA:
                        maska[i] = True
        if not np.any(maska): maska[0] = True
        return maska
    def _start_new_hand(self):
        self.rozdajacy_idx = (self.rozdajacy_idx + 1) % LICZBA_GRACZY
        for gracz in self.gracze:
            gracz.reka.clear(); gracz.wygrane_karty.clear()
        self.rozdanie = silnik_gry.Rozdanie(self.gracze, [self.druzyna_A, self.druzyna_B], self.rozdajacy_idx)
        self.rozdanie.rozpocznij_nowe_rozdanie()
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.druzyna_A.punkty_meczu = 0
        self.druzyna_B.punkty_meczu = 0
        self._start_new_hand()
        self._obsluz_automatyczne_kroki()
        obs = self._pobierz_stan(self.rozdanie.kolej_gracza_idx)
        info = {'action_mask': self.action_masks()}
        return obs, info
    def action_masks(self) -> np.ndarray:
        if self.rozdanie.kolej_gracza_idx is None: return np.ones(LICZBA_AKCJI, dtype=bool)
        return self._pobierz_maske_akcji(self.rozdanie.kolej_gracza_idx)
    def _wykonaj_akcje(self, gracz_idx, akcja_idx):
        gracz = self.gracze[gracz_idx]
        akcja = MAPOWANIE_AKCJI[akcja_idx]
        if akcja['typ'] == 'zagraj_karte': self.rozdanie.zagraj_karte(gracz, akcja['karta'])
        else: self.rozdanie.wykonaj_akcje(gracz, akcja)
    def _obsluz_automatyczne_kroki(self):
         while self.rozdanie.kolej_gracza_idx is None and self.rozdanie.faza != silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA:
            if self.rozdanie.lewa_do_zamkniecia: self.rozdanie.finalizuj_lewe()
            else: break

# === KROK 4: SKRYPT TESTUJĄCY ===
if __name__ == "__main__":
    # ZMIANA 3: Upewnij się, że nazwa modelu jest poprawna dla Agenta v8
    MODEL_PATH = "models/gra66_agent_v8_features.zip"
    LICZBA_Gier_TESTOWYCH = 250

    if not os.path.exists(MODEL_PATH):
        print(f"Błąd: Nie znaleziono modelu w {MODEL_PATH}")
    else:
        print(f"Ładowanie modelu z {MODEL_PATH}...")
        model = MaskablePPO.load(MODEL_PATH)
        print("Model załadowany. Rozpoczynam symulację w środowisku 'Tylko Normalna'...")

        env = SrodowiskoGry66()

        for i in range(LICZBA_Gier_TESTOWYCH):
            obs, info = env.reset()
            done = False
            while not done:
                kolej_gracza = env.rozdanie.kolej_gracza_idx
                action_mask = info['action_mask']
                if kolej_gracza == 0:
                    action, _ = model.predict(obs, action_masks=action_mask, deterministic=True)
                else:
                    legalne_akcje = np.where(action_mask)[0]
                    action = random.choice(legalne_akcje)
                obs, _, done, _, info = env.step(action)
            print(f"\rPostęp symulacji: {i + 1}/{LICZBA_Gier_TESTOWYCH}", end="")

        print("\n\n--- Symulacja 'Tylko Normalna' zakończona. Wyniki: ---")
        win_rate_partii = (env.wygrane_partie_AI / LICZBA_Gier_TESTOWYCH) * 100
        print(f"\n Ogólny wskaźnik wygranych partii przez AI: {win_rate_partii:.2f}%")

        stats = env.statystyki
        print("\n--- Analiza Skuteczności Licytacji (Kontrakt 'NORMALNA') ---")
        zagrania_ai = stats['normalna_ai_zagrania']; wygrane_ai = stats['normalna_ai_wygrane']
        win_rate_ai = (wygrane_ai / zagrania_ai) * 100 if zagrania_ai > 0 else 0
        print(f"Drużyna AI wybrała atut: {zagrania_ai} razy")
        print(f"Skuteczność, gdy AI wybiera atut: {win_rate_ai:.2f}%")
        print("-" * 20)
        zagrania_losowe = stats['normalna_losowy_zagrania']; wygrane_losowe = stats['normalna_losowy_wygrane']
        win_rate_losowe = (wygrane_losowe / zagrania_losowe) * 100 if zagrania_losowe > 0 else 0
        print(f"Drużyna Losowa wybrała atut: {zagrania_losowe} razy")
        print(f"Skuteczność, gdy Losowy Bot wybiera atut: {win_rate_losowe:.2f}%")