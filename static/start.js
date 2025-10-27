// start.js

document.addEventListener('DOMContentLoaded', () => {

    // ==========================================================================
    // SEKCJA 1: POBIERANIE ELEMENTÓW DOM
    // ==========================================================================

    // --- Elementy DOM związane z Autentykacją ---
    const niezalogowanyKontener = document.getElementById('niezalogowany-kontener'); // Kontener dla opcji gościa i logowania
    const initialGuestOptions = document.getElementById('initial-guest-options'); // Przyciski "Zaloguj" i "Graj jako Gość"
    const guestNameSelection = document.getElementById('guest-name-selection');   // Kontener wyboru nazwy gościa
    const guestNameInput = document.getElementById('guest-name-input');         // Pole na nazwę gościa
    const confirmGuestBtn = document.getElementById('confirm-guest-btn');       // Przycisk potwierdzenia nazwy gościa
    const cancelGuestBtn = document.getElementById('cancel-guest-btn');         // Przycisk anulowania wyboru nazwy gościa
    const loginFormKontener = document.getElementById('login-form-kontener');   // Kontener formularza logowania/rejestracji
    const zalogowanyKontener = document.getElementById('zalogowany-kontener');    // Kontener wyświetlany po zalogowaniu
    const zalogowanyNazwaEl = document.getElementById('zalogowany-nazwa');      // Element wyświetlający nazwę zalogowanego gracza
    const authBladEl = document.getElementById('auth-blad');                  // Element na komunikaty o błędach autentykacji
    const showLoginBtn = document.getElementById('show-login-btn');           // Przycisk pokazujący formularz logowania
    const guestLoginBtn = document.getElementById('guest-login-btn');         // Przycisk "Graj jako Gość"
    const loginBtn = document.getElementById('login-btn');                    // Przycisk "Zaloguj"
    const registerBtn = document.getElementById('register-btn');              // Przycisk "Zarejestruj"
    const cancelLoginBtn = document.getElementById('cancel-login-btn');       // Przycisk anulowania logowania/rejestracji
    const logoutBtn = document.getElementById('logout-btn');                  // Przycisk "Wyloguj"
    const usernameInput = document.getElementById('auth-username');             // Pole na nazwę użytkownika
    const passwordInput = document.getElementById('auth-password');             // Pole na hasło

    // --- Elementy DOM związane z Dołączaniem / Tworzeniem Gry ---
    const rejoinKontener = document.getElementById('rejoin-kontener'); // Kontener przycisku "Wróć do gry"
    const rejoinBtn = document.getElementById('rejoin-btn');         // Przycisk "Wróć do gry"
    const trybyGryKontener = document.querySelector('.tryby-gry-kontener'); // Kontener przycisków "Stwórz" i "Przeglądaj"
    const openCreateLobbyBtn = document.getElementById('open-create-lobby-btn'); // Przycisk otwierający modal tworzenia lobby
    const createLobbyModal = document.getElementById('modal-stworz-lobby');    // Panel modala tworzenia lobby
    const modalBackdrop = document.getElementById('modal-backdrop');        // Tło modala
    const cancelCreateLobbyBtn = document.getElementById('cancel-create-lobby-btn'); // Przycisk Anuluj w modalu
    const createLobbyBtn = document.getElementById('create-lobby-btn');       // Przycisk Stwórz w modalu
    const trybLobbySelect = document.getElementById('tryb-lobby-select');     // Wybór typu lobby (Online/Lokalna)
    const hasloKontener = document.getElementById('haslo-kontener');        // Kontener pola hasła
    const rankingowaKontener = document.getElementById('rankingowa-kontener');  // Kontener checkboxa gry rankingowej
    const rankingowaCheckbox = document.getElementById('rankingowa-checkbox');  // Checkbox gry rankingowej
    // const dolaczBtn = document.getElementById('dolacz-btn'); // Usunięto - logika dołączania po kodzie nie istnieje w HTML
    // const kodGryInput = document.getElementById('kod-gry-input'); // Usunięto
    // const bladLobbyEl = document.getElementById('blad-lobby'); // Usunięto

    // ==========================================================================
    // SEKCJA 2: LOGIKA AUTENTYKACJI (Logowanie, Rejestracja, Gość, Wylogowanie)
    // ==========================================================================

    /**
     * Asynchronicznie sprawdza stan zalogowania użytkownika.
     * Odczytuje nazwę gracza z localStorage. Jeśli istnieje, pyta serwer
     * o aktywną grę do powrotu (`/check_active_game`).
     * Aktualizuje interfejs użytkownika (pokazuje/ukrywa odpowiednie kontenery).
     */
    async function sprawdzStanZalogowania() {
        const nazwaGracza = localStorage.getItem('nazwaGracza');
        let rejoinGameId = null; // Zresetuj ID gry do powrotu

        if (nazwaGracza) { // Użytkownik jest "zalogowany" (ma nazwę w localStorage)
            // Zapytaj serwer, czy ten gracz ma aktywną grę
            try {
                const response = await fetch(`/check_active_game/${encodeURIComponent(nazwaGracza)}`);
                if (response.ok) {
                    const data = await response.json();
                    rejoinGameId = data.active_game_id; // Pobierz ID gry z odpowiedzi
                    // Zapisz lub usuń ID gry do powrotu w localStorage
                    if (rejoinGameId) localStorage.setItem('rejoinGameId', rejoinGameId);
                    else localStorage.removeItem('rejoinGameId');
                } else {
                     console.error("Błąd serwera podczas sprawdzania aktywnej gry:", response.status);
                     localStorage.removeItem('rejoinGameId'); // Usuń ID w razie błędu
                }
            } catch (error) {
                console.error("Błąd sieci podczas sprawdzania aktywnej gry:", error);
                localStorage.removeItem('rejoinGameId'); // Usuń ID w razie błędu
            }

            // --- Aktualizuj UI dla zalogowanego użytkownika ---
            if (zalogowanyNazwaEl) zalogowanyNazwaEl.textContent = nazwaGracza;
            if (niezalogowanyKontener) niezalogowanyKontener.classList.add('hidden');
            if (loginFormKontener) loginFormKontener.classList.add('hidden');
            if (zalogowanyKontener) zalogowanyKontener.classList.remove('hidden');
            if (authBladEl) authBladEl.classList.add('hidden');

            // Pokaż/ukryj przycisk "Wróć do gry"
            if (rejoinGameId && rejoinKontener) rejoinKontener.classList.remove('hidden');
            else if (rejoinKontener) rejoinKontener.classList.add('hidden');

            // Zawsze pokazuj opcje tworzenia/przeglądania dla zalogowanego
            if (trybyGryKontener) trybyGryKontener.classList.remove('hidden');

        } else { // Użytkownik nie jest zalogowany
            // --- Aktualizuj UI dla niezalogowanego użytkownika ---
            if (niezalogowanyKontener) niezalogowanyKontener.classList.remove('hidden');
            if (initialGuestOptions) initialGuestOptions.classList.remove('hidden');
            if (guestNameSelection) guestNameSelection.classList.add('hidden');
            if (loginFormKontener) loginFormKontener.classList.add('hidden');
            if (zalogowanyKontener) zalogowanyKontener.classList.add('hidden');
            if (rejoinKontener) rejoinKontener.classList.add('hidden');
            // Zawsze pokazuj opcje tworzenia/przeglądania
            if (trybyGryKontener) trybyGryKontener.classList.remove('hidden');
        }
    }

    /**
     * Zapisuje dane zalogowanego użytkownika (nazwę, ID gry do powrotu, ustawienia)
     * w localStorage i odświeża interfejs.
     * @param {object} tokenData - Obiekt odpowiedzi z API logowania/rejestracji (zawiera username, active_game_id, settings).
     */
    function zapiszZalogowanie(tokenData) {
        // Zapisz nazwę gracza
        localStorage.setItem('nazwaGracza', tokenData.username);

        // Zapisz lub usuń ID gry do powrotu
        if (tokenData.active_game_id) localStorage.setItem('rejoinGameId', tokenData.active_game_id);
        else localStorage.removeItem('rejoinGameId');

        // Zapisz ustawienia UI, jeśli serwer je zwrócił
        if (tokenData.settings && typeof tokenData.settings === 'object') {
            for (const [key, value] of Object.entries(tokenData.settings)) {
                // Zapisz każde ustawienie jako osobny wpis w localStorage
                localStorage.setItem(key, value);
            }
            console.log("Wczytano ustawienia interfejsu z serwera:", tokenData.settings);
        } else {
            console.log("Brak ustawień na serwerze, używane będą lokalne (jeśli istnieją).");
        }

        // Odśwież interfejs, aby pokazać stan zalogowania
        sprawdzStanZalogowania();
    }

    /** Pokazuje sekcję wyboru nazwy gościa. */
    function pokazWyborNazwyGoscia() {
        if (initialGuestOptions) initialGuestOptions.classList.add('hidden');
        if (guestNameSelection) guestNameSelection.classList.remove('hidden');
        if (guestNameInput) {
            guestNameInput.value = '';
            guestNameInput.focus();
        }
    }

    /** Anuluje wybór nazwy gościa i wraca do początkowych opcji. */
    function anulujWyborNazwyGoscia() {
        if (guestNameSelection) guestNameSelection.classList.add('hidden');
        if (initialGuestOptions) initialGuestOptions.classList.remove('hidden');
    }

    /** Potwierdza nazwę gościa (lub generuje losową) i "loguje" gościa. */
    function potwierdzNazweGoscia() {
        let guestName = guestNameInput ? guestNameInput.value.trim() : '';
        // Jeśli nazwa pusta, wygeneruj losową
        if (!guestName) {
            guestName = `Gosc${Math.floor(Math.random() * 1000)}`;
        }
        // Zapisz dane gościa (jakby to był zalogowany użytkownik, ale bez ustawień/gry do powrotu)
        zapiszZalogowanie({ username: guestName, active_game_id: null, settings: null });
    }

    /** Pokazuje formularz logowania/rejestracji. */
    function pokazFormularzLogowania() {
        if (niezalogowanyKontener) niezalogowanyKontener.classList.add('hidden');
        if (loginFormKontener) loginFormKontener.classList.remove('hidden');
        if (authBladEl) authBladEl.classList.add('hidden'); // Ukryj stare błędy
        // Wyczyść pola formularza
        if (usernameInput) usernameInput.value = '';
        if (passwordInput) passwordInput.value = '';
    }

    /** Anuluje logowanie/rejestrację i wraca do stanu początkowego. */
    function anulujLogowanie() {
        // Sprawdź stan zalogowania (powinien pokazać opcje niezalogowanego)
        sprawdzStanZalogowania();
    }

    /**
     * Asynchronicznie wysyła żądanie do API logowania lub rejestracji.
     * Obsługuje odpowiedź serwera (sukces lub błąd).
     * @param {string} endpoint - Adres URL endpointu API ('/login' lub '/register').
     */
    async function obsluzAuthAPI(endpoint) {
        const username = usernameInput ? usernameInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value.trim() : '';
        // Prosta walidacja po stronie klienta
        if (!username || !password) {
            if (authBladEl) {
                authBladEl.textContent = "Nazwa użytkownika i hasło są wymagane.";
                authBladEl.classList.remove('hidden');
            }
            return;
        }
        // Zablokuj przyciski na czas żądania
        if (loginBtn) loginBtn.disabled = true;
        if (registerBtn) registerBtn.disabled = true;
        if (cancelLoginBtn) cancelLoginBtn.disabled = true;

        try {
            // Wyślij żądanie POST z danymi użytkownika
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, password: password })
            });
            const data = await response.json(); // Odczytaj odpowiedź JSON

            if (!response.ok) { // Jeśli serwer zwrócił błąd
                if (authBladEl) {
                    authBladEl.textContent = data.detail || "Wystąpił nieznany błąd.";
                    authBladEl.classList.remove('hidden');
                }
            } else { // Sukces (zalogowano lub zarejestrowano)
                if (authBladEl) authBladEl.classList.add('hidden'); // Ukryj ewentualne błędy
                zapiszZalogowanie(data); // Zapisz dane użytkownika i odśwież UI
            }
        } catch (error) { // Błąd sieciowy
            console.error("Błąd sieci podczas autentykacji:", error);
            if (authBladEl) {
                authBladEl.textContent = "Błąd sieci. Nie można połączyć się z serwerem.";
                authBladEl.classList.remove('hidden');
            }
        } finally {
            // Odblokuj przyciski po zakończeniu żądania
            if (loginBtn) loginBtn.disabled = false;
            if (registerBtn) registerBtn.disabled = false;
            if (cancelLoginBtn) cancelLoginBtn.disabled = false;
        }
    }

    /**
     * Funkcja pomocnicza do pobierania nazwy gracza z localStorage.
     * Wyświetla alert, jeśli nazwa nie jest ustawiona.
     * @returns {string|null} Nazwa gracza lub null, jeśli nie jest ustawiona.
     */
    function pobierzNazweGracza() {
        const nazwa = localStorage.getItem('nazwaGracza');
        if (!nazwa) {
            alert("Musisz się zalogować lub wybrać grę jako gość, aby kontynuować.");
            return null;
        }
        return nazwa;
    }

    // --- Przypisanie akcji do przycisków autentykacji ---
    if (showLoginBtn) showLoginBtn.onclick = pokazFormularzLogowania;
    if (guestLoginBtn) guestLoginBtn.onclick = pokazWyborNazwyGoscia;
    if (cancelGuestBtn) cancelGuestBtn.onclick = anulujWyborNazwyGoscia;
    if (confirmGuestBtn) confirmGuestBtn.onclick = potwierdzNazweGoscia;
    if (cancelLoginBtn) cancelLoginBtn.onclick = anulujLogowanie;
    if (loginBtn) loginBtn.onclick = () => obsluzAuthAPI('/login');
    if (registerBtn) registerBtn.onclick = () => obsluzAuthAPI('/register');
    if (logoutBtn) logoutBtn.onclick = () => {
        // Wyczyść dane sesji z localStorage
        localStorage.removeItem('nazwaGracza');
        localStorage.removeItem('lobbyHaslo'); // Na wszelki wypadek
        localStorage.removeItem('rejoinGameId');
        // Odśwież interfejs
        sprawdzStanZalogowania();
    };
    // Obsługa Enter w polach logowania/rejestracji
    if (usernameInput) usernameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') loginBtn?.click(); });
    if (passwordInput) passwordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') loginBtn?.click(); });
    // Obsługa Enter w polu nazwy gościa
    if (guestNameInput) guestNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmGuestBtn?.click(); });

    // ==========================================================================
    // SEKCJA 3: LOGIKA MODALA TWORZENIA LOBBY
    // ==========================================================================

    /** Ukrywa modal tworzenia lobby i jego tło. */
    function ukryjModalTworzenia() {
        if (createLobbyModal) createLobbyModal.classList.add('hidden');
        if (modalBackdrop) modalBackdrop.classList.add('hidden');
        // Resetuj stan przycisku tworzenia
        if (createLobbyBtn) {
             createLobbyBtn.disabled = false;
             createLobbyBtn.textContent = "Stwórz";
        }
    }

    // --- Dynamiczne pokazywanie/ukrywanie opcji w modalu ---
    if (trybLobbySelect && hasloKontener && rankingowaKontener && rankingowaCheckbox) {
        // Funkcja wywoływana przy zmianie typu lobby (Online/Lokalna)
        const aktualizujOpcjeModala = () => {
            const jestOnline = trybLobbySelect.value === 'online';
            // Pokaż/ukryj pole hasła (tylko dla Online)
            hasloKontener.classList.toggle('hidden', !jestOnline);
            // Pokaż/ukryj opcję gry rankingowej (tylko dla Online)
            rankingowaKontener.classList.toggle('hidden', !jestOnline);
            // Jeśli wybrano "Lokalnie", odznacz i zablokuj checkbox rankingowy
            if (!jestOnline) {
                rankingowaCheckbox.checked = false;
                // rankingowaCheckbox.disabled = true; // Opcjonalnie można zablokować
            } // else {
              // rankingowaCheckbox.disabled = false; // Odblokuj dla Online
            // }
        };
        // Przypisz funkcję do zdarzenia 'change' i wywołaj raz na starcie
        trybLobbySelect.onchange = aktualizujOpcjeModala;
        aktualizujOpcjeModala(); // Wywołaj raz, aby ustawić początkowy stan
    }

    // --- Przypisanie akcji do przycisków modala ---
    // Otwieranie modala
    if (openCreateLobbyBtn) {
        openCreateLobbyBtn.onclick = () => {
            if (!pobierzNazweGracza()) return; // Sprawdź, czy gracz jest zalogowany
            // Pokaż modal i tło
            if (createLobbyModal) createLobbyModal.classList.remove('hidden');
            if (modalBackdrop) modalBackdrop.classList.remove('hidden');
            // Zresetuj opcje do domyślnych (opcjonalnie)
            if(trybLobbySelect) trybLobbySelect.value = 'online';
            if(document.getElementById('tryb-gry-select')) document.getElementById('tryb-gry-select').value = '4p';
            if(rankingowaCheckbox) rankingowaCheckbox.checked = false;
            if(document.getElementById('haslo-lobby-input')) document.getElementById('haslo-lobby-input').value = '';
            // Uruchom aktualizację opcji na wypadek resetu
            if(trybLobbySelect?.onchange) trybLobbySelect.onchange();
        };
    }
    // Zamykanie modala (przycisk Anuluj i kliknięcie tła)
    if (cancelCreateLobbyBtn) cancelCreateLobbyBtn.onclick = ukryjModalTworzenia;
    if (modalBackdrop) {
         modalBackdrop.addEventListener('click', (e) => {
            // Zamknij tylko jeśli kliknięto tło (nie panel) i modal jest widoczny
            if (e.target === modalBackdrop && createLobbyModal && !createLobbyModal.classList.contains('hidden')) {
                ukryjModalTworzenia();
            }
         });
    }
    // Akcja przycisku "Stwórz"
    if (createLobbyBtn) {
        createLobbyBtn.onclick = async () => {
            const nazwa = pobierzNazweGracza();
            if (!nazwa) return; // Upewnij się, że jest nazwa gracza

            // Pobierz wartości z formularza modala
            const trybGrySelect = document.getElementById('tryb-gry-select');
            const trybLobbySelectModal = document.getElementById('tryb-lobby-select'); // Zmieniono nazwę zmiennej
            const hasloInputModal = document.getElementById('haslo-lobby-input'); // Zmieniono nazwę zmiennej
            const rankingowaCheckboxModal = document.getElementById('rankingowa-checkbox'); // Zmieniono nazwę zmiennej

            const trybGry = trybGrySelect ? trybGrySelect.value : '4p';
            const trybLobby = trybLobbySelectModal ? trybLobbySelectModal.value : 'online';
            let haslo = hasloInputModal ? hasloInputModal.value.trim() : '';
            const jestPubliczne = !haslo; // Publiczne, jeśli brak hasła
            // Gra rankingowa tylko jeśli Online ORAZ zaznaczony checkbox
            const czyRankingowa = (trybLobby === 'online' && rankingowaCheckboxModal && rankingowaCheckboxModal.checked);

            // Dla gier lokalnych hasło jest ignorowane
            if (trybLobby !== 'online') haslo = null;

            // Zablokuj przycisk i pokaż status tworzenia
            createLobbyBtn.disabled = true; createLobbyBtn.textContent = "Tworzenie...";
            // Usunięto log wysyłanych danych (już niepotrzebny)
            // console.log("Wysyłanie do /gra/stworz:", {...});

            try {
                // Wyślij żądanie POST do API serwera
                const response = await fetch('/gra/stworz', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nazwa_gracza: nazwa,
                        tryb_gry: trybGry,
                        tryb_lobby: trybLobby,
                        publiczna: jestPubliczne,
                        haslo: haslo ? haslo : null, // Wyślij null, jeśli brak hasła
                        czy_rankingowa: czyRankingowa
                    })
                });
                const data = await response.json(); // Odczytaj odpowiedź

                if (response.ok && data.id_gry) { // Sukces - serwer zwrócił ID gry
                    // Zapisz hasło w localStorage TYLKO dla prywatnych gier online
                    if (trybLobby === 'online' && haslo) localStorage.setItem('lobbyHaslo', haslo);
                    else localStorage.removeItem('lobbyHaslo'); // Wyczyść dla publicznych/lokalnych
                    // Przekieruj do strony gry z nowym ID
                    window.location.href = `/gra.html?id=${data.id_gry}`;
                } else { // Błąd tworzenia gry po stronie serwera
                    console.error("Nie udało się utworzyć gry:", data);
                    // Pokaż błąd użytkownikowi (jeśli istnieje odpowiedni element)
                    const bladEl = document.getElementById('blad-lobby'); // Użyj istniejącego elementu błędu
                    if (bladEl) {
                        bladEl.textContent = data.detail || "Błąd serwera podczas tworzenia gry.";
                        bladEl.classList.remove('hidden');
                    } else { // Awaryjnie pokaż alert
                        alert(data.detail || "Błąd serwera podczas tworzenia gry.");
                    }
                    ukryjModalTworzenia(); // Ukryj modal po błędzie
                }
            } catch (error) { // Błąd sieciowy
                console.error("Błąd sieci podczas tworzenia gry:", error);
                const bladEl = document.getElementById('blad-lobby');
                if (bladEl) {
                    bladEl.textContent = "Błąd sieci. Nie można połączyć się z serwerem.";
                    bladEl.classList.remove('hidden');
                } else {
                    alert("Błąd sieci. Nie można połączyć się z serwerem.");
                }
                ukryjModalTworzenia(); // Ukryj modal po błędzie
            }
            // Reset stanu przycisku (nie jest potrzebny, bo następuje przekierowanie lub błąd)
            // finally { createLobbyBtn.disabled = false; createLobbyBtn.textContent = "Stwórz"; }
        };
    }

    // ==========================================================================
    // SEKCJA 4: LOGIKA POWROTU DO GRY
    // ==========================================================================

    // Przypisanie akcji do przycisku "Wróć do gry"
    if (rejoinBtn) {
        rejoinBtn.onclick = () => {
            const gameId = localStorage.getItem('rejoinGameId'); // Pobierz zapisane ID gry
            if (gameId) {
                // Przekieruj do strony gry z tym ID
                window.location.href = `/gra.html?id=${gameId}`;
            } else {
                // To nie powinno się zdarzyć, jeśli przycisk jest widoczny
                alert("Nie znaleziono ID gry do powrotu. Odśwież stronę.");
                sprawdzStanZalogowania(); // Odśwież stan UI
            }
        };
    }

    // ==========================================================================
    // SEKCJA 5: INICJALIZACJA STRONY
    // ==========================================================================

    sprawdzStanZalogowania(); // Sprawdź stan logowania przy pierwszym załadowaniu strony

}); // Koniec DOMContentLoaded