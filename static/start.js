document.addEventListener('DOMContentLoaded', () => {

    // === LOGIKA AUTENTYKACJI ===

    // --- Elementy DOM (Auth) ---
    const niezalogowanyKontener = document.getElementById('niezalogowany-kontener');
    const initialGuestOptions = document.getElementById('initial-guest-options');
    const guestNameSelection = document.getElementById('guest-name-selection');
    const guestNameInput = document.getElementById('guest-name-input');
    const confirmGuestBtn = document.getElementById('confirm-guest-btn');
    const cancelGuestBtn = document.getElementById('cancel-guest-btn');
    const loginFormKontener = document.getElementById('login-form-kontener');
    const zalogowanyKontener = document.getElementById('zalogowany-kontener');
    const zalogowanyNazwaEl = document.getElementById('zalogowany-nazwa');
    const authBladEl = document.getElementById('auth-blad');
    const showLoginBtn = document.getElementById('show-login-btn');
    const guestLoginBtn = document.getElementById('guest-login-btn');
    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');
    const cancelLoginBtn = document.getElementById('cancel-login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const usernameInput = document.getElementById('auth-username');
    const passwordInput = document.getElementById('auth-password');
    // NOWE referencje dla Rejoin
    const rejoinKontener = document.getElementById('rejoin-kontener');
    const rejoinBtn = document.getElementById('rejoin-btn');
    const trybyGryKontener = document.querySelector('.tryby-gry-kontener');

    // --- Funkcje (Auth) ---
    async function sprawdzStanZalogowania() { // ZMIENIONO na async
        const nazwaGracza = localStorage.getItem('nazwaGracza'); // Changed
        let rejoinGameId = null; // Zresetuj przed sprawdzeniem

        if (nazwaGracza) {
            // Użytkownik JEST zalogowany w localStorage - zapytaj serwer o aktywną grę
            try {
                const response = await fetch(`/check_active_game/${encodeURIComponent(nazwaGracza)}`);
                if (response.ok) {
                    const data = await response.json();
                    rejoinGameId = data.active_game_id; // Pobierz ID z serwera
                    // Zaktualizuj localStorage
                    if (rejoinGameId) {
                        localStorage.setItem('rejoinGameId', rejoinGameId); // Changed
                    } else {
                        localStorage.removeItem('rejoinGameId'); // Changed
                    }
                } else {
                     console.error("Błąd podczas sprawdzania aktywnej gry:", response.status);
                     localStorage.removeItem('rejoinGameId'); // Changed
                }
            } catch (error) {
                console.error("Błąd sieci podczas sprawdzania aktywnej gry:", error);
                localStorage.removeItem('rejoinGameId'); // Changed
            }

            // Aktualizuj UI na podstawie nazwy I wyniku sprawdzenia gry
            zalogowanyNazwaEl.textContent = nazwaGracza;
            niezalogowanyKontener.classList.add('hidden');
            loginFormKontener.classList.add('hidden');
            zalogowanyKontener.classList.remove('hidden');
            authBladEl.classList.add('hidden');

            // Pokaż/ukryj przycisk powrotu
            if (rejoinGameId && rejoinKontener) {
                rejoinKontener.classList.remove('hidden');
            } else if (rejoinKontener) {
                rejoinKontener.classList.add('hidden');
            }
            // Zawsze pokazuj "Stwórz/Przeglądaj" dla zalogowanego
            if (trybyGryKontener) trybyGryKontener.classList.remove('hidden');

        } else {
            // Użytkownik NIE JEST zalogowany
            niezalogowanyKontener.classList.remove('hidden');
            initialGuestOptions.classList.remove('hidden');
            guestNameSelection.classList.add('hidden');
            loginFormKontener.classList.add('hidden');
            zalogowanyKontener.classList.add('hidden');
            if (rejoinKontener) rejoinKontener.classList.add('hidden');
            if (trybyGryKontener) trybyGryKontener.classList.remove('hidden');
        }
    }

    function zapiszZalogowanie(tokenData) {
        localStorage.setItem('nazwaGracza', tokenData.username);

        if (tokenData.active_game_id) {
            localStorage.setItem('rejoinGameId', tokenData.active_game_id);
        } else {
            localStorage.removeItem('rejoinGameId');
        }

        if (tokenData.settings && typeof tokenData.settings === 'object') {
            // Zapisz każde ustawienie osobno w localStorage
            for (const [key, value] of Object.entries(tokenData.settings)) {
                localStorage.setItem(key, value); // Klucze powinny pasować do tych w UserSettings
            }
            console.log("Wczytano ustawienia z serwera:", tokenData.settings);
        } else {
            console.log("Brak ustawień na serwerze, używane będą lokalne (jeśli istnieją).");
        }

        sprawdzStanZalogowania();
    }
    function pokazWyborNazwyGoscia() {
        initialGuestOptions.classList.add('hidden');
        guestNameSelection.classList.remove('hidden');
        guestNameInput.value = '';
        guestNameInput.focus();
    }

    function anulujWyborNazwyGoscia() {
        guestNameSelection.classList.add('hidden');
        initialGuestOptions.classList.remove('hidden');
    }

    function potwierdzNazweGoscia() {
        let guestName = guestNameInput.value.trim();
        if (!guestName) {
            guestName = `Gosc${Math.floor(Math.random() * 1000)}`;
        }
        // Użyj obiektu tokenData dla spójności
        zapiszZalogowanie({ username: guestName, active_game_id: null });
    }

    function pokazFormularzLogowania() {
        niezalogowanyKontener.classList.add('hidden');
        loginFormKontener.classList.remove('hidden');
        authBladEl.classList.add('hidden');
        usernameInput.value = '';
        passwordInput.value = '';
    }

    function anulujLogowanie() {
        sprawdzStanZalogowania();
    }

    async function obsluzAuthAPI(endpoint) {
        const username = usernameInput.value.trim();
        const password = passwordInput.value.trim();
        if (!username || !password) {
            authBladEl.textContent = "Nazwa i hasło są wymagane.";
            authBladEl.classList.remove('hidden'); return;
        }
        loginBtn.disabled = true; registerBtn.disabled = true; cancelLoginBtn.disabled = true;
        try {
            const response = await fetch(endpoint, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, password: password })
            });
            const data = await response.json();
            if (!response.ok) {
                authBladEl.textContent = data.detail || "Wystąpił nieznany błąd.";
                authBladEl.classList.remove('hidden');
            } else {
                authBladEl.classList.add('hidden');
                zapiszZalogowanie(data); // ZMIENIONO: Przekaż cały obiekt data
            }
        } catch (error) {
            console.error("Błąd sieci:", error);
            authBladEl.textContent = "Błąd sieci. Nie można połączyć się z serwerem.";
            authBladEl.classList.remove('hidden');
        } finally {
            loginBtn.disabled = false; registerBtn.disabled = false; cancelLoginBtn.disabled = false;
        }
    }

    // --- Przypisanie akcji (Auth) ---
    if (showLoginBtn) showLoginBtn.onclick = pokazFormularzLogowania;
    if (guestLoginBtn) guestLoginBtn.onclick = pokazWyborNazwyGoscia;
    if (cancelGuestBtn) cancelGuestBtn.onclick = anulujWyborNazwyGoscia;
    if (confirmGuestBtn) confirmGuestBtn.onclick = potwierdzNazweGoscia;
    if (cancelLoginBtn) cancelLoginBtn.onclick = anulujLogowanie;
    if (loginBtn) loginBtn.onclick = () => obsluzAuthAPI('/login');
    if (registerBtn) registerBtn.onclick = () => obsluzAuthAPI('/register');
    if (logoutBtn) logoutBtn.onclick = () => {
        localStorage.removeItem('nazwaGracza'); // Changed
        localStorage.removeItem('lobbyHaslo'); // Changed
        localStorage.removeItem('rejoinGameId'); // Changed
        sprawdzStanZalogowania();
    };

    // --- Funkcja pomocnicza (Auth) ---
    function pobierzNazweGracza() {
        const nazwa = localStorage.getItem('nazwaGracza'); // Changed
        if (!nazwa) {
            alert("Musisz się zalogować lub wybrać grę jako gość, aby kontynuować.");
            return null;
        }
        return nazwa;
    }

    // === LOGIKA MODALA TWORZENIA LOBBY ===

    // --- Elementy DOM (Modal) ---
    const openCreateLobbyBtn = document.getElementById('open-create-lobby-btn');
    const createLobbyModal = document.getElementById('modal-stworz-lobby');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const cancelCreateLobbyBtn = document.getElementById('cancel-create-lobby-btn');
    const createLobbyBtn = document.getElementById('create-lobby-btn');
    const trybLobbySelect = document.getElementById('tryb-lobby-select');
    const hasloKontener = document.getElementById('haslo-kontener');

    // --- Funkcje (Modal) ---
    function ukryjModalTworzenia() {
        createLobbyModal.classList.add('hidden');
        modalBackdrop.classList.add('hidden');
    }

    // --- Przypisanie akcji (Modal) ---
    if (trybLobbySelect && hasloKontener) {
        trybLobbySelect.onchange = () => {
            const jestOnline = trybLobbySelect.value === 'online';
            hasloKontener.classList.toggle('hidden', !jestOnline);
        };
        trybLobbySelect.onchange();
    }

    if (openCreateLobbyBtn) {
        openCreateLobbyBtn.onclick = () => {
            if (!pobierzNazweGracza()) return;
            createLobbyModal.classList.remove('hidden');
            modalBackdrop.classList.remove('hidden');
        };
    }

    if (cancelCreateLobbyBtn) cancelCreateLobbyBtn.onclick = ukryjModalTworzenia;
    if (modalBackdrop) {
         modalBackdrop.addEventListener('click', (e) => {
            if (e.target === modalBackdrop && !createLobbyModal.classList.contains('hidden')) {
                ukryjModalTworzenia();
            }
         });
    }


    if (createLobbyBtn) {
        createLobbyBtn.onclick = async () => {
            const nazwa = pobierzNazweGracza();
            if (!nazwa) return;

            const trybGry = document.getElementById('tryb-gry-select').value;
            const trybLobby = document.getElementById('tryb-lobby-select').value;
            let haslo = document.getElementById('haslo-lobby-input').value.trim();
            const jestPubliczne = !haslo;

            if (trybLobby !== 'online') haslo = null;

            createLobbyBtn.disabled = true; createLobbyBtn.textContent = "Tworzenie...";
            try {
                const response = await fetch('/gra/stworz', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nazwa_gracza: nazwa, tryb_gry: trybGry, tryb_lobby: trybLobby,
                        publiczna: jestPubliczne, haslo: haslo ? haslo : null
                    })
                });
                const data = await response.json();
                if (data.id_gry) {
                    if (trybLobby === 'online' && haslo) localStorage.setItem('lobbyHaslo', haslo); // Changed
                    else localStorage.removeItem('lobbyHaslo'); // Changed
                    window.location.href = `/gra.html?id=${data.id_gry}`;
                } else {
                    console.error("Nie udało się utworzyć gry", data);
                    const bladEl = document.getElementById('blad-lobby');
                    if (bladEl) {
                        bladEl.textContent = data.detail || "Błąd serwera.";
                        bladEl.classList.remove('hidden');
                    } else alert(data.detail || "Błąd serwera.");
                    ukryjModalTworzenia();
                }
            } catch (error) {
                console.error("Błąd sieci:", error);
                const bladEl = document.getElementById('blad-lobby');
                if (bladEl) {
                    bladEl.textContent = "Błąd sieci.";
                    bladEl.classList.remove('hidden');
                } else alert("Błąd sieci.");
                ukryjModalTworzenia();
            } finally {
                createLobbyBtn.disabled = false; createLobbyBtn.textContent = "Stwórz";
            }
        };
    }

    // === LOGIKA DOŁĄCZANIA PO KODZIE ===

    // --- Elementy DOM (Dołącz) ---
    const dolaczBtn = document.getElementById('dolacz-btn');
    const kodGryInput = document.getElementById('kod-gry-input');
    const bladLobbyEl = document.getElementById('blad-lobby');

    // --- Funkcje (Dołącz) ---
    const dolaczDoGry = async () => {
        const nazwa = pobierzNazweGracza();
        if (!nazwa) return;
        const kodGry = kodGryInput.value.trim().toUpperCase();
        if (!kodGry) {
            bladLobbyEl.textContent = "Wpisz kod gry.";
            bladLobbyEl.classList.remove('hidden'); return;
        }

        try {
            dolaczBtn.disabled = true;
            const response = await fetch(`/gra/sprawdz/${kodGry}`);
            const data = await response.json();

            if (data.exists) {
                window.location.href = `/gra.html?id=${kodGry}`;
            } else {
                bladLobbyEl.textContent = "Lobby nie istnieje. Sprawdź kod.";
                bladLobbyEl.classList.remove('hidden');
                dolaczBtn.disabled = false;
            }
        } catch(error) {
             console.error("Błąd sprawdzania gry:", error);
             bladLobbyEl.textContent = "Błąd sieci podczas sprawdzania lobby.";
             bladLobbyEl.classList.remove('hidden');
             dolaczBtn.disabled = false;
        }
    };

    // --- Przypisanie akcji (Dołącz) ---
    if (dolaczBtn) dolaczBtn.onclick = dolaczDoGry;
    if (kodGryInput) {
        kodGryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') dolaczDoGry();
        });
    }

    // === LOGIKA POWROTU DO GRY ===
    if (rejoinBtn) {
        rejoinBtn.onclick = () => {
            const gameId = localStorage.getItem('rejoinGameId'); // Changed
            if (gameId) {
                window.location.href = `/gra.html?id=${gameId}`;
            } else {
                alert("Nie znaleziono ID gry do powrotu.");
                sprawdzStanZalogowania();
            }
        };
    }

    // === INICJALIZACJA ===
    sprawdzStanZalogowania(); // Sprawdź stan logowania przy pierwszym ładowaniu

}); // Koniec DOMContentLoaded