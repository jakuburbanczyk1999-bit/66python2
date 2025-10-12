const nazwaGraczaInput = document.getElementById('nazwa-gracza-input');

// Po załadowaniu strony, wczytaj zapisaną nazwę (jeśli istnieje)
window.onload = () => {
    const zapisanaNazwa = sessionStorage.getItem('nazwaGracza');
    if (zapisanaNazwa) {
        nazwaGraczaInput.value = zapisanaNazwa;
    }
};

// Funkcja pomocnicza do zapisywania nazwy
function zapiszNazweGracza() {
    let nazwa = nazwaGraczaInput.value.trim();
    if (!nazwa) {
        // Jeśli gracz nic nie wpisze, nadaj mu losową nazwę
        nazwa = `Gracz${Math.floor(Math.random() * 1000)}`;
    }
    sessionStorage.setItem('nazwaGracza', nazwa);
}

// --- Przycisk "Graj Online" ---
document.getElementById('start-online-btn').onclick = async () => {
    zapiszNazweGracza(); // Zapisz nazwę przed akcją
    const response = await fetch('/gra/nowa', { method: 'POST' });
    const data = await response.json();
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    }
};

// --- Przycisk "Graj Lokalnie" ---
document.getElementById('start-local-btn').onclick = async () => {
    zapiszNazweGracza(); // Zapisz nazwę przed akcją
    const response = await fetch('/gra/nowa/lokalna', { method: 'POST' });
    const data = await response.json();
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    }
};

// --- Logika dołączania do gry ---
const dolaczBtn = document.getElementById('dolacz-btn');
const kodGryInput = document.getElementById('kod-gry-input');
const bladLobbyEl = document.getElementById('blad-lobby');

const dolaczDoGry = async () => {
    zapiszNazweGracza(); // Zapisz nazwę przed akcją
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