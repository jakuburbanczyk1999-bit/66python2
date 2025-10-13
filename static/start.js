// ZAKTUALIZOWANY PLIK: start.js
const nazwaGraczaInput = document.getElementById('nazwa-gracza-input');

window.onload = () => {
    const zapisanaNazwa = sessionStorage.getItem('nazwaGracza');
    if (zapisanaNazwa) {
        nazwaGraczaInput.value = zapisanaNazwa;
    }
};

function zapiszNazweGracza() {
    let nazwa = nazwaGraczaInput.value.trim();
    if (!nazwa) {
        nazwa = `Gracz${Math.floor(Math.random() * 1000)}`;
    }
    sessionStorage.setItem('nazwaGracza', nazwa);
}

// --- Logika przycisków ---

// 4-osobowa online
document.getElementById('start-online-btn').onclick = async () => {
    zapiszNazweGracza();
    const response = await fetch('/gra/nowa', { method: 'POST' });
    const data = await response.json();
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    }
};

// 4-osobowa lokalna
document.getElementById('start-local-btn').onclick = async () => {
    zapiszNazweGracza();
    const nazwa = sessionStorage.getItem('nazwaGracza');
    const response = await fetch('/gra/nowa/lokalna', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nazwa_gracza: nazwa })
    });
    const data = await response.json();
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    }
};

// 3-osobowa online
document.getElementById('start-online-3p-btn').onclick = async () => {
    zapiszNazweGracza();
    const response = await fetch('/gra/nowa/trzyosoby', { method: 'POST' });
    const data = await response.json();
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    }
};

// 3-osobowa lokalna
document.getElementById('start-local-3p-btn').onclick = async () => {
    zapiszNazweGracza();
    const nazwa = sessionStorage.getItem('nazwaGracza');
    const response = await fetch('/gra/nowa/lokalna/trzyosoby', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nazwa_gracza: nazwa })
    });
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