function zapiszNazweGracza() {
    let nazwa = nazwaGraczaInput.value.trim();
    if (!nazwa) {
        nazwa = `Gracz${Math.floor(Math.random() * 1000)}`;
        nazwaGraczaInput.value = nazwa; // KROK 2: Zaktualizuj pole, aby użytkownik widział nazwę
    }
    sessionStorage.setItem('nazwaGracza', nazwa);
}

const nazwaGraczaInput = document.getElementById('nazwa-gracza-input');
nazwaGraczaInput.onchange = zapiszNazweGracza;

window.onload = () => {
    const zapisanaNazwa = sessionStorage.getItem('nazwaGracza');
    if (zapisanaNazwa) {
        nazwaGraczaInput.value = zapisanaNazwa;
    }
};


// --- Logika przycisków ---

const openCreateLobbyBtn = document.getElementById('open-create-lobby-btn');
const createLobbyModal = document.getElementById('modal-stworz-lobby');
const modalBackdrop = document.getElementById('modal-backdrop');
const cancelCreateLobbyBtn = document.getElementById('cancel-create-lobby-btn');
const createLobbyBtn = document.getElementById('create-lobby-btn');
const trybLobbySelect = document.getElementById('tryb-lobby-select');
    const hasloKontener = document.getElementById('haslo-kontener');

    trybLobbySelect.onchange = () => {
        const jestOnline = trybLobbySelect.value === 'online';
        hasloKontener.classList.toggle('hidden', !jestOnline);
    };
    trybLobbySelect.onchange();


// Otwieranie modala
openCreateLobbyBtn.onclick = () => {
    createLobbyModal.classList.remove('hidden');
    modalBackdrop.classList.remove('hidden');
};

// Funkcja do zamykania modala
function ukryjModalTworzenia() {
    createLobbyModal.classList.add('hidden');
    modalBackdrop.classList.add('hidden');
}

// Zamykanie modala
cancelCreateLobbyBtn.onclick = ukryjModalTworzenia;
modalBackdrop.onclick = ukryjModalTworzenia;

// Akcja tworzenia gry
createLobbyBtn.onclick = async () => {
    zapiszNazweGracza();
    const nazwa = sessionStorage.getItem('nazwaGracza');
    const trybGry = document.getElementById('tryb-gry-select').value;
    const trybLobby = document.getElementById('tryb-lobby-select').value;
    let haslo = document.getElementById('haslo-lobby-input').value.trim();
    const jestPubliczne = !haslo;
        
        // Wyczyść hasło, jeśli gra nie jest online
        if (trybLobby !== 'online') {
            haslo = null;
        }

    // Wyczyść hasło, jeśli gra nie jest online lub jest publiczna
    if (trybLobby !== 'online') {
        haslo = null;
    }
    
    // Zablokuj przycisk na czas tworzenia
    createLobbyBtn.disabled = true;
    createLobbyBtn.textContent = "Tworzenie...";
    
    try {
        const response = await fetch('/gra/stworz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
            nazwa_gracza: nazwa,
            tryb_gry: trybGry,
            tryb_lobby: trybLobby,
            publiczna: jestPubliczne, 
            haslo: haslo ? haslo : null 
        })
        });
        
        const data = await response.json();
        if (data.id_gry) {
            
            if (trybLobby === 'online' && haslo) {
                sessionStorage.setItem('lobbyHaslo', haslo);
            } else {
                sessionStorage.removeItem('lobbyHaslo'); // Upewnij się, że jest czyste
            }

            // Przekieruj do gry
            window.location.href = `/gra.html?id=${data.id_gry}`;
        } else {
            console.error("Nie udało się utworzyć gry", data);
            bladLobbyEl.textContent = "Błąd serwera podczas tworzenia lobby.";
            bladLobbyEl.classList.remove('hidden');
            ukryjModalTworzenia();
        }
    } catch (error) {
        console.error("Błąd sieci:", error);
        bladLobbyEl.textContent = "Błąd sieci. Nie można połączyć się z serwerem.";
        bladLobbyEl.classList.remove('hidden');
        ukryjModalTworzenia();
    } finally {
        // Odblokuj przycisk
        createLobbyBtn.disabled = false;
        createLobbyBtn.textContent = "Stwórz";
    }
};


// --- Logika dołączania do gry ---
const dolaczBtn = document.getElementById('dolacz-btn');
const kodGryInput = document.getElementById('kod-gry-input');
const bladLobbyEl = document.getElementById('blad-lobby');

const dolaczDoGry = async () => {
    zapiszNazweGracza();
    const kodGry = kodGryInput.value.trim().toUpperCase();
    if (!kodGry) {
        bladLobbyEl.textContent = "Wpisz kod gry.";
        bladLobbyEl.classList.remove('hidden');
        return;
    }

    const response = await fetch(`/gra/sprawdz/${kodGry}`);
    const data = await response.json();

    if (data.exists) {
        window.location.href = `/gra.html?id=${kodGry}`;
    } else {
        bladLobbyEl.textContent = "Lobby nie istnieje. Sprawdź kod.";
        bladLobbyEl.classList.remove('hidden');
    }
};

dolaczBtn.onclick = dolaczDoGry;
kodGryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        dolaczDoGry();
    }
});