# Changelog - Miedziowe Karty

## [1.1.0] - 2024-12-06

### 🎮 Nowe funkcje
- **Tryb 3-osobowy w grze 66** - pełne wsparcie dla gry FFA (każdy na każdego)
- **System timeout/forfeit** - gracze mają 60 sekund na powrót po rozłączeniu, po przekroczeniu czasu następuje walkower
- **Timer rozłączenia** - wizualny countdown pokazujący czas do walkoweru
- **Podgląd wyniku w lobby** - wyświetlanie aktualnego wyniku meczu w podglądzie lobby

### 🎨 Zmiany UI/UX
- **Przeprojektowany interfejs** - nowy dark theme z profesjonalnym wyglądem
- **Modułowa architektura CSS** - reorganizacja stylów (base, components, layout, pages)
- **Responsywny design** - lepsze dostosowanie do różnych rozmiarów ekranu
- **Dynamiczne pozycjonowanie graczy** - poprawne rozmieszczenie dla 2p/3p/4p

### 🐛 Naprawione błędy
- **Modal podsumowania** - naprawiono z-index (modal był zasłonięty przez karty)
- **Dymki akcji w 3p** - poprawione pozycjonowanie dla prawego gracza
- **Nieskończona lufa** - dodana walidacja zapobiegająca wielokrotnemu dawaniu lufy
- **Synchronizacja stanu** - naprawiona synchronizacja wyniku meczu po rozłączeniu
- **Timeout gracza** - naprawiona logika wykrywania powrotu gracza

### 🔧 Zmiany techniczne
- Rozdzielenie logiki silnika gry dla 3p i 4p
- Ulepszone zarządzanie stanem WebSocket
- Lepsza obsługa błędów w komunikacji real-time
- Optymalizacja re-renderów komponentów React

### 📁 Struktura plików
```
frontend/src/
├── styles/
│   ├── base/           # Reset, zmienne, typography
│   ├── components/     # Karty, przyciski, modele
│   ├── layout/         # Header, grid, spacing
│   └── pages/          # Strony specyficzne
└── components/
    ├── Game/           # Komponenty gry
    ├── Lobby/          # Komponenty lobby
    └── shared/         # Współdzielone
```

---

## [1.0.0] - 2024-12-01

### 🎮 Funkcje
- Gra w 66 (tryb 4-osobowy, 2 vs 2)
- Gra w Tysiąc (2-4 graczy)
- System lobby z czatem
- Matchmaking z botami AI
- System rankingowy
- Autonomiczne boty z różnymi osobowościami (MCTS + personality-based rewards)

### 🔧 Stack technologiczny
- Backend: Python FastAPI + Redis
- Frontend: React + Zustand + Tailwind CSS
- Real-time: WebSocket
- AI: MCTS z modyfikatorami osobowości
