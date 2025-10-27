// lobby.js

document.addEventListener('DOMContentLoaded', () => {

    // ==========================================================================
    // SEKCJA 1: POBIERANIE ELEMENTÓW DOM
    // ==========================================================================

    const listaLobbyKontener = document.getElementById('lista-lobby-kontener'); // Kontener na listę wpisów lobby
    const ladowanieInfo = document.getElementById('ladowanie-lobby-info');       // Element pokazujący status ładowania
    const odswiezBtn = document.getElementById('odswiez-btn');                 // Przycisk odświeżania listy

    // Elementy modala do wpisywania hasła
    const modalHaslo = document.getElementById('modal-haslo');           // Panel modala
    const modalBackdrop = document.getElementById('modal-backdrop');       // Tło modala
    const anulujHasloBtn = document.getElementById('anuluj-haslo-btn');    // Przycisk Anuluj w modalu
    const zatwierdzHasloBtn = document.getElementById('zatwierdz-haslo-btn'); // Przycisk Dołącz w modalu
    const hasloInput = document.getElementById('haslo-input');           // Pole do wpisania hasła
    const bladHaslaEl = document.getElementById('blad-hasla');           // Element na komunikaty o błędach hasła

    // Zmienna przechowująca ID lobby, do którego użytkownik próbuje dołączyć (jeśli wymaga hasła)
    let lobbyDoDolaczeniaId = null;

    // ==========================================================================
    // SEKCJA 2: GŁÓWNA FUNKCJA - POBIERANIE I RENDEROWANIE LISTY LOBBY
    // ==========================================================================

    /**
     * Asynchronicznie pobiera listę dostępnych lobby z serwera (endpoint /gra/lista_lobby)
     * i renderuje ją w kontenerze #lista-lobby-kontener.
     */
    async function pobierzLobby() {
        // Pokaż komunikat ładowania i wyczyść poprzednią listę
        ladowanieInfo.textContent = 'Ładowanie listy lobby...';
        ladowanieInfo.classList.remove('hidden');
        listaLobbyKontener.innerHTML = ''; // Wyczyść stare wpisy
        listaLobbyKontener.appendChild(ladowanieInfo); // Dodaj ponownie komunikat ładowania

        try {
            // Wykonaj żądanie do API serwera
            const response = await fetch('/gra/lista_lobby');
            if (!response.ok) {
                // Rzuć błąd, jeśli odpowiedź serwera nie jest OK (np. 404, 500)
                throw new Error(`Błąd serwera (${response.status}) przy pobieraniu lobby`);
            }

            // Sparsuj odpowiedź JSON
            const data = await response.json();

            // Ukryj komunikat ładowania i wyczyść kontener (ponownie, dla pewności)
            ladowanieInfo.classList.add('hidden');
            listaLobbyKontener.innerHTML = '';
            // Usunięto log odebranych danych (już niepotrzebny)
            // console.log("Odebrano z /gra/lista_lobby:", data.lobby_list);

            // Sprawdź, czy lista lobby nie jest pusta
            if (data.lobby_list && data.lobby_list.length > 0) {
                // Przetwórz i wyrenderuj każdy wpis lobby
                data.lobby_list.forEach(lobby => {
                    const wpis = document.createElement('div'); // Stwórz div dla wiersza
                    wpis.className = 'wpis-lobby'; // Dodaj klasę CSS

                    // --- Formatowanie danych lobby ---
                    const trybGryText = lobby.tryb_gry === '4p' ? '4-osobowy (2v2)' : '3-osobowy (FFA)';
                    const graczeText = `${lobby.aktualni_gracze} / ${lobby.max_gracze}`;
                    const hasloText = lobby.ma_haslo ? 'Tak 🔒' : 'Nie';
                    const rankingText = lobby.rankingowa ? 'Tak 🏆' : 'Nie';
                    // Wyświetl średnie Elo tylko dla gier rankingowych
                    const eloText = lobby.rankingowa
                        ? (lobby.srednie_elo ? Math.round(lobby.srednie_elo) : 'Brak') // Pokaż Elo lub 'Brak'
                        : '-'; // Pokaż '-' dla gier nierankingowych

                    // --- Ustalanie statusu i przycisku akcji ---
                    let statusText = '';
                    let przyciskText = 'Dołącz';
                    let czyMoznaDolaczyc = true;

                    // Pobierz nazwę aktualnego gracza z localStorage
                    const mojGracz = localStorage.getItem('nazwaGracza');
                    // Sprawdź, czy aktualny gracz jest już w tym lobby/grze
                    const jestemWGrze = lobby.gracze.includes(mojGracz);

                    if (lobby.status === 'W_TRAKCIE') { // Gra jest w toku
                        if (jestemWGrze) { // Jeśli gracz był w tej grze i się rozłączył
                            statusText = '<strong style="color: #ffc107;">Rozłączono</strong>';
                            przyciskText = 'Dołącz Ponownie';
                            czyMoznaDolaczyc = true; // Może wrócić
                        } else { // Jeśli gracz nie był w tej grze
                            statusText = '<strong style="color: #ffc107;">W Trakcie</strong>';
                            przyciskText = 'Obserwuj'; // TODO: Implementacja obserwowania?
                            czyMoznaDolaczyc = false; // Nie można dołączyć do trwającej gry
                        }
                    } else if (lobby.aktualni_gracze >= lobby.max_gracze) { // Lobby jest pełne
                        statusText = '<strong style="color: #dc3545;">Pełne</strong>';
                        przyciskText = 'Pełne';
                        czyMoznaDolaczyc = false; // Nie można dołączyć
                    } else { // Lobby jest otwarte
                        statusText = '<strong style="color: #28a745;">Otwarte</strong>';
                        przyciskText = 'Dołącz';
                        czyMoznaDolaczyc = true; // Można dołączyć
                    }

                    // --- Tworzenie przycisku Dołącz/Obserwuj/Pełne ---
                    const dolaczBtn = document.createElement('button');
                    dolaczBtn.textContent = przyciskText;
                    dolaczBtn.disabled = !czyMoznaDolaczyc; // Wyłącz przycisk, jeśli nie można dołączyć
                    if (czyMoznaDolaczyc) {
                        // Przypisz akcję do przycisku
                        dolaczBtn.onclick = () => {
                            obsluzDolaczenie(lobby.id_gry, lobby.ma_haslo);
                        };
                    }

                    // --- Wypełnienie wiersza danymi ---
                    wpis.innerHTML = `
                        <div>${lobby.host}</div>
                        <div>${trybGryText}</div>
                        <div>${graczeText}</div>
                        <div>${hasloText}</div>
                        <div>${rankingText}</div>
                        <div>${eloText}</div>
                        <div>${statusText}</div>
                        <div></div> `;
                    // Dodaj przycisk do ostatniej komórki wiersza
                    wpis.lastElementChild.appendChild(dolaczBtn);

                    // Dodaj gotowy wiersz do kontenera listy
                    listaLobbyKontener.appendChild(wpis);
                });
            } else {
                // Jeśli lista lobby jest pusta, pokaż odpowiedni komunikat
                ladowanieInfo.textContent = 'Nie znaleziono żadnych publicznych lobby.';
                ladowanieInfo.classList.remove('hidden');
                listaLobbyKontener.appendChild(ladowanieInfo); // Dodaj komunikat do pustego kontenera
            }
        } catch (error) {
            // Obsługa błędów sieciowych lub błędów serwera
            console.error('Błąd pobierania lobby:', error);
            ladowanieInfo.textContent = 'Nie można załadować lobby. Spróbuj ponownie.';
            ladowanieInfo.classList.remove('hidden');
            listaLobbyKontener.appendChild(ladowanieInfo); // Pokaż błąd w kontenerze
        }
    }

    // ==========================================================================
    // SEKCJA 3: OBSŁUGA DOŁĄCZANIA DO LOBBY
    // ==========================================================================

    /**
     * Obsługuje kliknięcie przycisku "Dołącz" / "Dołącz Ponownie".
     * Sprawdza, czy lobby wymaga hasła i odpowiednio reaguje.
     * @param {string} idGry - ID gry, do której użytkownik chce dołączyć.
     * @param {boolean} maHaslo - Czy lobby jest chronione hasłem.
     */
    function obsluzDolaczenie(idGry, maHaslo) {
        // Sprawdź, czy nazwa gracza jest ustawiona
        const nazwaGracza = localStorage.getItem('nazwaGracza');
        if (!nazwaGracza) {
            alert("Nie ustawiono nazwy gracza. Wróć do menu głównego.");
            window.location.href = '/'; // Przekieruj do menu
            return;
        }

        if (maHaslo) { // Jeśli lobby wymaga hasła
            // Zapisz ID gry i pokaż modal do wpisania hasła
            lobbyDoDolaczeniaId = idGry;
            hasloInput.value = ''; // Wyczyść pole hasła
            bladHaslaEl.classList.add('hidden'); // Ukryj ewentualne błędy
            modalHaslo.classList.remove('hidden'); // Pokaż modal
            modalBackdrop.classList.remove('hidden'); // Pokaż tło
        } else { // Jeśli lobby jest publiczne
            // Wyczyść ewentualne zapisane hasło i przejdź do gry
            localStorage.removeItem('lobbyHaslo');
            przejdzDoGry(idGry);
        }
    }

    /**
     * Przekierowuje użytkownika do strony gry z podanym ID.
     * @param {string} idGry - ID gry.
     */
    function przejdzDoGry(idGry) {
        window.location.href = `/gra.html?id=${idGry}`;
    }

    // ==========================================================================
    // SEKCJA 4: OBSŁUGA MODALA HASŁA
    // ==========================================================================

    /** Ukrywa modal wpisywania hasła i resetuje stan. */
    function ukryjModalHasla() {
        modalHaslo.classList.add('hidden');
        modalBackdrop.classList.add('hidden');
        lobbyDoDolaczeniaId = null; // Zresetuj ID lobby
    }

    // Przypisanie akcji do przycisku Anuluj
    if (anulujHasloBtn) anulujHasloBtn.onclick = ukryjModalHasla;

    // Przypisanie akcji do tła modala (zamykanie po kliknięciu poza panelem)
    if (modalBackdrop) {
        modalBackdrop.onclick = (e) => {
            // Zamknij modal hasła tylko jeśli jest widoczny i kliknięto tło
            if (e.target === modalBackdrop && !modalHaslo.classList.contains('hidden')) {
                ukryjModalHasla();
            }
        };
    }

    // Przypisanie akcji do przycisku Zatwierdź/Dołącz w modalu hasła
    if (zatwierdzHasloBtn) {
        zatwierdzHasloBtn.onclick = async () => {
            const idGry = lobbyDoDolaczeniaId;
            const haslo = hasloInput.value;
            if (!idGry) return; // Zabezpieczenie

            // Zapisz wpisane hasło w localStorage (WebSocket użyje go do połączenia)
            localStorage.setItem('lobbyHaslo', haslo);
            // Przejdź do gry (WebSocket sprawdzi hasło przy połączeniu)
            przejdzDoGry(idGry);
            // Ukryj modal
            ukryjModalHasla();
            // TODO: Rozważyć sprawdzenie hasła przez API HTTP *przed* przejściem do gry,
            // aby dać natychmiastową informację zwrotną o błędnym haśle.
        };
    }
    // Obsługa Enter w polu hasła
     if (hasloInput) {
         hasloInput.addEventListener('keydown', (e) => {
             if (e.key === 'Enter' && !modalHaslo.classList.contains('hidden')) {
                 zatwierdzHasloBtn.click(); // Symuluj kliknięcie przycisku Dołącz
             }
         });
     }

    // ==========================================================================
    // SEKCJA 5: INICJALIZACJA I OBSŁUGA ODŚWIEŻANIA
    // ==========================================================================

    // Przypisanie akcji do przycisku Odśwież
    if (odswiezBtn) odswiezBtn.onclick = pobierzLobby;

    // Pobierz listę lobby przy pierwszym załadowaniu strony
    pobierzLobby();

}); // Koniec DOMContentLoaded