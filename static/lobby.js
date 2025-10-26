document.addEventListener('DOMContentLoaded', () => {

    const listaLobbyKontener = document.getElementById('lista-lobby-kontener');
    const ladowanieInfo = document.getElementById('ladowanie-lobby-info');
    const odswiezBtn = document.getElementById('odswiez-btn');

    // Elementy modala hasła
    const modalHaslo = document.getElementById('modal-haslo');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const anulujHasloBtn = document.getElementById('anuluj-haslo-btn');
    const zatwierdzHasloBtn = document.getElementById('zatwierdz-haslo-btn');
    const hasloInput = document.getElementById('haslo-input');
    const bladHaslaEl = document.getElementById('blad-hasla');

    let lobbyDoDolaczeniaId = null;

    // Funkcja pobierająca i renderująca listę lobby
    async function pobierzLobby() {
        ladowanieInfo.textContent = 'Ładowanie listy lobby...';
        ladowanieInfo.classList.remove('hidden');
        listaLobbyKontener.innerHTML = '';
        listaLobbyKontener.appendChild(ladowanieInfo);

        try {
            const response = await fetch('/gra/lista_lobby');
            if (!response.ok) {
                throw new Error('Błąd serwera przy pobieraniu lobby');
            }

            const data = await response.json();

            ladowanieInfo.classList.add('hidden');
            listaLobbyKontener.innerHTML = '';

            if (data.lobby_list && data.lobby_list.length > 0) {
                data.lobby_list.forEach(lobby => {
                    const wpis = document.createElement('div');
                    wpis.className = 'wpis-lobby';

                    const trybGryText = lobby.tryb_gry === '4p' ? '4-osobowy (2v2)' : '3-osobowy (FFA)';
                    const graczeText = `${lobby.aktualni_gracze} / ${lobby.max_gracze}`;
                    const hasloText = lobby.ma_haslo ? 'Tak 🔒' : 'Nie';

                    let statusText = '';
                    let przyciskText = 'Dołącz';
                    let czyMoznaDolaczyc = true;

                    const mojGracz = localStorage.getItem('nazwaGracza'); // Changed
                    const jestemWGrze = lobby.gracze.includes(mojGracz);

                    if (lobby.status === 'W_TRAKCIE') {
                        if (jestemWGrze) {
                            statusText = '<strong style="color: #ffc107;">Rozłączono</strong>';
                            przyciskText = 'Dołącz Ponownie';
                            czyMoznaDolaczyc = true;
                        } else {
                            statusText = '<strong style="color: #ffc107;">W Trakcie</strong>';
                            przyciskText = 'Obserwuj';
                            czyMoznaDolaczyc = false;
                        }
                    } else if (lobby.aktualni_gracze >= lobby.max_gracze) {
                        statusText = '<strong style="color: #dc3545;">Pełne</strong>';
                        przyciskText = 'Pełne';
                        czyMoznaDolaczyc = false;
                    } else {
                        statusText = '<strong style="color: #28a745;">Otwarte</strong>';
                        przyciskText = 'Dołącz';
                        czyMoznaDolaczyc = true;
                    }

                    const dolaczBtn = document.createElement('button');
                    dolaczBtn.textContent = przyciskText;
                    dolaczBtn.disabled = !czyMoznaDolaczyc;
                    if (czyMoznaDolaczyc) {
                        dolaczBtn.onclick = () => {
                            obsluzDolaczenie(lobby.id_gry, lobby.ma_haslo);
                        };
                    }

                    wpis.innerHTML = `
                        <div>${lobby.host}</div>
                        <div>${trybGryText}</div>
                        <div>${graczeText}</div>
                        <div>${hasloText}</div>
                        <div>${statusText}</div> `;
                    wpis.appendChild(dolaczBtn);

                    listaLobbyKontener.appendChild(wpis);
                });
            } else {
                ladowanieInfo.textContent = 'Nie znaleziono żadnych publicznych lobby.';
                ladowanieInfo.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Błąd pobierania lobby:', error);
            ladowanieInfo.textContent = 'Nie można załadować lobby. Spróbuj ponownie.';
            ladowanieInfo.classList.remove('hidden');
        }
    }

    // Obsługa kliknięcia "Dołącz"
    function obsluzDolaczenie(idGry, maHaslo) {
        const nazwaGracza = localStorage.getItem('nazwaGracza'); // Changed
        if (!nazwaGracza) {
            alert("Nie ustawiono nazwy gracza. Wróć do menu głównego.");
            window.location.href = '/';
            return;
        }

        if (maHaslo) {
            lobbyDoDolaczeniaId = idGry;
            hasloInput.value = '';
            bladHaslaEl.classList.add('hidden');
            modalHaslo.classList.remove('hidden');
            modalBackdrop.classList.remove('hidden');
        } else {
            localStorage.removeItem('lobbyHaslo'); // Changed
            przejdzDoGry(idGry);
        }
    }

    // Funkcja przekierowująca do gry
    function przejdzDoGry(idGry) {
        window.location.href = `/gra.html?id=${idGry}`;
    }

    // Logika modala hasła
    function ukryjModalHasla() {
        modalHaslo.classList.add('hidden');
        modalBackdrop.classList.add('hidden');
        lobbyDoDolaczeniaId = null;
    }

    anulujHasloBtn.onclick = ukryjModalHasla;
    if (modalBackdrop) { // Added check
        modalBackdrop.onclick = (e) => {
             // Close only password modal if clicked on backdrop
            if (e.target === modalBackdrop && !modalHaslo.classList.contains('hidden')) {
                ukryjModalHasla();
            }
        };
    }

    zatwierdzHasloBtn.onclick = async () => {
        const idGry = lobbyDoDolaczeniaId;
        const haslo = hasloInput.value;
        if (!idGry) return;

        localStorage.setItem('lobbyHaslo', haslo); // Changed
        przejdzDoGry(idGry);
        ukryjModalHasla();
    };

    // Nasłuchiwacz przycisku odświeżania
    odswiezBtn.onclick = pobierzLobby;

    // Pobierz lobby przy pierwszym ładowaniu strony
    pobierzLobby();
});