# 📋 Changelog - Miedziowe Karty

Wszystkie istotne zmiany w projekcie są dokumentowane w tym pliku.

---

## 🔧 [1.1.2] - 2024-12-07

### Nowe funkcje
- **Strona profilu** - placeholder dla przyszłych statystyk gracza (ELO, wygrane, historia)
- **Filtrowanie lobby** - możliwość filtrowania po typie gry i statusie (można dołączyć / w trakcie)

### Zmiany UI
- Klikalny avatar w sidebar prowadzi do profilu
- Dropdowny do filtrowania na liście lobby
- Przycisk "Wyczyść filtry" gdy brak wyników

### Naprawione błędy
- **Status offline przy odświeżeniu** - usunięto `beforeunload` event który wysyłał offline przy F5
- **Logi INFO** - wyłączono spam logów HTTP w konsoli backend
- **Przycisk "Następna runda"** - naprawiono blokadę gdy boty czekały na gracza
- **Nieskończona lufa 3p** - dodano warunek `do_konca` w lufie wstępnej trybu 3-osobowego
- **Powrót do lobby** - naprawiono podwójne uruchamianie timera powrotu

---

## 🔧 [1.1.1] - 2024-12-06

### Zmiany UI
- **Sekcja gier na Landing** - grid 2x2 z 4 grami:
  - Gra w 66 (Dostępne) - zaktualizowano opis "3-4 graczy"
  - Tysiąc (Wkrótce)
  - Pan (Wkrótce) - nowy placeholder
  - Remik (Wkrótce) - nowy placeholder

### Optymalizacje
- **Szybsze boty** - zmniejszono opóźnienia:
  - Pierwsza akcja: 0.8s → 0.2s
  - Kolejne akcje: 0.8s → 0.6s
  - Głosowanie: 2-5s → 0.5-1.5s

### Naprawione błędy
- **availableGames** - przywrócono wartość 1 (tylko 66 aktywne)
- **Modal końca meczu** - naprawiono błąd 404 po ostatnim rozdaniu
- **Statystyki gier** - naprawiono naliczanie rozegranych gier
- **System końca meczu** - przepisana logika:
  - 10s na kliknięcie "Powrót do lobby"
  - Boty mają 20% szans na pozostanie
  - Po timeout backend finalizuje lobby

---

<details>
<summary><h2>🎉 [1.1.0] - 2024-12-06 - Tryb 3-osobowy</h2></summary>

### Nowe funkcje
- **Tryb 3-osobowy w grze 66** - pełne wsparcie dla gry FFA (każdy na każdego)
- **System timeout/forfeit** - gracze mają 60s na powrót po rozłączeniu
- **Timer rozłączenia** - wizualny countdown do walkoweru
- **Podgląd wyniku w lobby** - aktualny wynik meczu w podglądzie

### Zmiany UI/UX
- **Przeprojektowany interfejs** - nowy dark theme
- **Modułowa architektura CSS** - reorganizacja stylów
- **Responsywny design** - lepsze dostosowanie do ekranów
- **Dynamiczne pozycjonowanie graczy** - poprawne dla 2p/3p/4p

### Naprawione błędy
- Modal podsumowania - naprawiono z-index
- Dymki akcji w 3p - poprawione pozycjonowanie
- Nieskończona lufa - walidacja wielokrotnego dawania
- Synchronizacja stanu po rozłączeniu
- Timeout gracza - logika wykrywania powrotu

### Zmiany techniczne
- Rozdzielenie logiki silnika gry dla 3p i 4p
- Ulepszone zarządzanie stanem WebSocket
- Lepsza obsługa błędów real-time
- Optymalizacja re-renderów React

</details>

---

<details>
<summary><h2>🎉 [1.0.0] - 2024-12-01 - Pierwsze wydanie</h2></summary>

### Funkcje
- Gra w 66 (tryb 4-osobowy, 2 vs 2)
- Gra w Tysiąc (2-4 graczy)
- System lobby z czatem
- Matchmaking z botami AI
- System rankingowy
- Autonomiczne boty z osobowościami (MCTS)

### Stack technologiczny
- Backend: Python FastAPI + Redis
- Frontend: React + Zustand + Tailwind CSS
- Real-time: WebSocket
- AI: MCTS z modyfikatorami osobowości

</details>
