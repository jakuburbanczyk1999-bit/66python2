# plik: trening.py

import os
import silnik_gry
import numpy as np
from collections import OrderedDict
import gymnasium as gym
from gymnasium import spaces
import torch as th
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed

# === DEFINICJE I MAPOWANIA ===
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

class SrodowiskoGry66(gym.Env):
    def __init__(self):
        super(SrodowiskoGry66, self).__init__()
        # ZMIANA 1: Nowy, większy rozmiar wektora obserwacji
        self.observation_space = spaces.Box(low=-1.0, high=120.0, shape=(69,), dtype=np.float32)
        self.action_space = spaces.Discrete(LICZBA_AKCJI)
        self.gracze = [silnik_gry.Gracz(f"Agent-{i}") for i in range(LICZBA_GRACZY)]
        self.druzyna_A = silnik_gry.Druzyna("Drużyna A (0 i 2)")
        self.druzyna_B = silnik_gry.Druzyna("Drużyna B (1 i 3)")
        self.druzyna_A.dodaj_gracza(self.gracze[0]); self.druzyna_A.dodaj_gracza(self.gracze[2])
        self.druzyna_B.dodaj_gracza(self.gracze[1]); self.druzyna_B.dodaj_gracza(self.gracze[3])
        self.druzyna_A.przeciwnicy, self.druzyna_B.przeciwnicy = self.druzyna_B, self.druzyna_A
        self.rozdanie = None
        self.rozdajacy_idx = -1

    def _pobierz_stan(self, idx_gracza: int):
        gracz = self.gracze[idx_gracza]

        # 1. Wizja Taktyczna: Surowa lista kart w ręku
        reka_wektor = np.zeros(ROZMIAR_TALII)
        for karta in gracz.reka:
            reka_wektor[mapuj_karte_na_indeks(karta)] = 1.0
        
        # 2. Wizja Strategiczna: Wiedza ekspercka
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
        
        # 3. Kontekst Gry
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
        
        # ZMIANA 2: Łączymy wszystkie informacje w jeden, kompletny wektor stanu
        return np.concatenate([
            reka_wektor,        # 24
            inteligentne_cechy, # 13
            stol_wektor,        # 24
            kontekst_wektor     # 8
        ]).astype(np.float32) # Suma: 69

    # ... reszta klasy jest identyczna jak w wersji v7 ...
    def _pobierz_maske_akcji(self, idx_gracza: int) -> np.ndarray:
        maska = np.zeros(LICZBA_AKCJI, dtype=bool)
        gracz = self.gracze[idx_gracza]
        if self.rozdanie.faza == silnik_gry.FazaGry.FAZA_PYTANIA:
            maska[PYTANIE_ACTION_INDEX] = True
            return maska
        if self.rozdanie.faza == silnik_gry.FazaGry.ROZGRYWKA:
            offset = len(AKCJE_LICYTACJI)
            for i, karta in enumerate(WSZYSTKIE_KARTY):
                if karta in gracz.reka and self.rozdanie._waliduj_ruch(gracz, karta):
                    maska[offset + i] = True
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
    def step(self, akcja_idx: int):
        gracz_idx_przed_ruchem = self.rozdanie.kolej_gracza_idx
        self._wykonaj_akcje(gracz_idx_przed_ruchem, akcja_idx)
        self._obsluz_automatyczne_kroki()
        reward = 0; done = False
        if self.rozdanie.faza == silnik_gry.FazaGry.PODSUMOWANIE_ROZDANIA:
            punkty_za_rozdanie = self._oblicz_nagrode(gracz_idx_przed_ruchem)
            if punkty_za_rozdanie < 0: reward += punkty_za_rozdanie * 1.5
            else: reward += punkty_za_rozdanie
            if self.druzyna_A.punkty_meczu >= 66 or self.druzyna_B.punkty_meczu >= 66:
                done = True
                if self.gracze[gracz_idx_przed_ruchem].druzyna.punkty_meczu >= 66: reward += 50
                else: reward -= 50
            else:
                self._start_new_hand()
                self._obsluz_automatyczne_kroki()
        kolej_gracza = self.rozdanie.kolej_gracza_idx
        obs = self._pobierz_stan(kolej_gracza)
        info = {'action_mask': self.action_masks()}
        return obs, reward, done, False, info
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
    def _oblicz_nagrode(self, idx_gracza: int) -> int:
        podsumowanie = self.rozdanie.podsumowanie
        if not podsumowanie: return 0
        gracz = self.gracze[idx_gracza]
        punkty = podsumowanie.get("przyznane_punkty", 0)
        if podsumowanie.get("wygrana_druzyna") == gracz.druzyna.nazwa: return punkty
        else: return -punkty

def make_env(rank, seed=0):
    def _init():
        env = SrodowiskoGry66()
        env.reset(seed=seed + rank)
        return Monitor(env)
    set_random_seed(seed)
    return _init

if __name__ == "__main__":
    LOG_DIR, MODEL_DIR = "logs", "models"
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    num_cpu = os.cpu_count()
    env = SubprocVecEnv([make_env(i) for i in range(num_cpu)])
    
    policy_kwargs = dict(activation_fn=th.nn.ReLU, net_arch=dict(pi=[128, 128], vf=[128, 128]))

    print("Rozpoczynam trening Agenta v8 od zera (z pełną wizją).")
    model = MaskablePPO("MlpPolicy", env, policy_kwargs=policy_kwargs, verbose=1, tensorboard_log=LOG_DIR, device="cpu", ent_coef=0.01)

    TIMESTEPS = 1_000_000
    
    print(f"--- Rozpoczynam trening Agenta v8 na {num_cpu} rdzeniach ---")
    model.learn(total_timesteps=TIMESTEPS, progress_bar=True)
    
    model.save(f"{MODEL_DIR}/gra66_agent_v8_features")
    print(f"--- Trening zakończony. Model v8 zapisany jako {MODEL_DIR}/gra66_agent_v8_features.zip ---")