/* ==========================================================================
   SEKCJA 1: DEKLARACJE GLOBALNE I POBIERANIE ELEMENTÓW DOM
   ========================================================================== */

// --- Zmienne globalne stanu gry ---
let idGry = null;
let nazwaGracza = null;
let socket = null;
let mojSlotId = null;
let nazwyDruzyn = { My: "My", Oni: "Oni" };
let ostatniStanGry = {};

// --- Elementy DOM ---
let ekranLobbyEl;
let ekranGryEl;
let modalOverlayEl;
let czatWiadomosciEl;
let czatInputEl;
let czatWyslijBtn;
let animationOverlayEl;
let settingsBtn;
let settingsModalEl;
let settingsCloseBtn;
let podsumowanieRozdaniaEl;
let settingUkryjCzat;
let settingUkryjHistorie;
let settingUkryjHistoriePartii;
let partiaHistoriaListaEl;
let infoSrodekTrescEl;

// --- Konfiguracja ---
const mapowanieKolorow = {
    'CZERWIEN': { symbol: '♥', klasa: 'kolor-czerwien' },
    'DZWONEK':  { symbol: '♦', klasa: 'kolor-dzwonek' },
    'ZOLADZ':   { symbol: '♣', klasa: 'kolor-zoladz' },
    'WINO':     { symbol: '♠', klasa: 'kolor-wino' }
};

/* ==========================================================================
   SEKCJA 2: ZARZĄDZANIE DŹWIĘKAMI
   ========================================================================== */
const dzwieki = {
    zagranieKarty: new Audio('/static/dzwieki/zagranie-karty.mp3'),
    wygranaLewa: new Audio('/static/dzwieki/wygrana-lewa.mp3'),
    licytacja: new Audio('/static/dzwieki/licytacja.mp3'),
    pas: new Audio('/static/dzwieki/pas.mp3'),
    koniecRozdania: new Audio('/static/dzwieki/koniec-rozdania.mp3'),
    wiadomoscCzat: new Audio('/static/dzwieki/wiadomosc-czat.mp3'),
};

function odtworzDzwiek(nazwaDzwieku) {
    const dzwiek = dzwieki[nazwaDzwieku];
    if (dzwiek) {
        dzwiek.currentTime = 0;
        dzwiek.play().catch(error => console.log(`Nie można odtworzyć dźwięku "${nazwaDzwieku}": ${error}`));
    }
}

/* ==========================================================================
   SEKCJA 3: GŁÓWNA LOGIKA APLIKACJI (INICJALIZACJA I WEBSOCKET)
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    inicjalizujElementyDOM();
    const params = new URLSearchParams(window.location.search);
    idGry = params.get('id');
    nazwaGracza = localStorage.getItem('nazwaGracza') || `Gosc${Math.floor(Math.random() * 1000)}`; // Changed
    localStorage.setItem('nazwaGracza', nazwaGracza); // Changed
    inicjalizujUstawieniaUI();

    if (idGry) {
        inicjalizujWebSocket();
    } else {
        if (window.location.pathname.includes('gra.html')) {
             window.location.href = "/";
        }
    }
});

function inicjalizujElementyDOM() {
    ekranLobbyEl = document.getElementById('ekran-lobby');
    ekranGryEl = document.querySelector('.ekran-gry');
    modalOverlayEl = document.getElementById('modal-overlay');
    czatWiadomosciEl = document.getElementById('czat-wiadomosci');
    czatInputEl = document.getElementById('czat-input');
    czatWyslijBtn = document.getElementById('czat-wyslij-btn');
    animationOverlayEl = document.getElementById('animation-overlay');
    settingsBtn = document.getElementById('settings-btn');
    settingsModalEl = document.getElementById('modal-ustawienia');
    settingsCloseBtn = document.getElementById('settings-close-btn');
    podsumowanieRozdaniaEl = document.getElementById('podsumowanie-rozdania');
    settingUkryjCzat = document.getElementById('setting-ukryj-czat');
    settingUkryjHistorie = document.getElementById('setting-ukryj-historie');
    settingUkryjHistoriePartii = document.getElementById('setting-ukryj-historie-partii');
    partiaHistoriaListaEl = document.getElementById('partia-historia-lista');
    settingUkryjPasekEwaluacji = document.getElementById('setting-ukryj-pasek-ewaluacji');
    infoSrodekTrescEl = document.getElementById('info-srodek-tresc');

    if (czatWyslijBtn) czatWyslijBtn.onclick = wyslijWiadomoscCzat;
    if (czatInputEl) czatInputEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') wyslijWiadomoscCzat(); });
    if (settingsBtn) settingsBtn.addEventListener('click', () => pokazModal(settingsModalEl));
    if (settingsCloseBtn) settingsCloseBtn.addEventListener('click', () => ukryjModal());
    if (modalOverlayEl) modalOverlayEl.addEventListener('click', (e) => { if (e.target === modalOverlayEl && settingsModalEl && !settingsModalEl.classList.contains('hidden')) ukryjModal(); });
    if (settingUkryjCzat) settingUkryjCzat.addEventListener('change', (e) => {
    const jestZaznaczone = e.target.checked;
    if (ekranGryEl) ekranGryEl.classList.toggle('czat-ukryty', jestZaznaczone);
        aktualizujUkrycieLewejKolumny();
        localStorage.setItem('czatUkryty', jestZaznaczone);
        zapiszUstawieniaNaSerwerze(); // <-- DODAJ WYWOŁANIE
    });
    if (settingUkryjHistorie) settingUkryjHistorie.addEventListener('change', (e) => {
        const jestZaznaczone = e.target.checked;
        if (ekranGryEl) ekranGryEl.classList.toggle('historia-ukryta', jestZaznaczone);
        localStorage.setItem('historiaUkryta', jestZaznaczone);
        zapiszUstawieniaNaSerwerze(); // <-- DODAJ WYWOŁANIE
    });
    if (settingUkryjHistoriePartii) settingUkryjHistoriePartii.addEventListener('change', (e) => {
        const jestZaznaczone = e.target.checked;
        if (ekranGryEl) ekranGryEl.classList.toggle('partia-historia-ukryta', jestZaznaczone);
        aktualizujUkrycieLewejKolumny();
        localStorage.setItem('partiaHistoriaUkryta', jestZaznaczone);
        zapiszUstawieniaNaSerwerze(); // <-- DODAJ WYWOŁANIE
    });
    if (settingUkryjPasekEwaluacji) settingUkryjPasekEwaluacji.addEventListener('change', (e) => {
        const jestZaznaczone = e.target.checked;
        if (ekranGryEl) ekranGryEl.classList.toggle('pasek-ewaluacji-ukryty', jestZaznaczone);
        localStorage.setItem('pasekEwaluacjiUkryty', jestZaznaczone);
        zapiszUstawieniaNaSerwerze(); // <-- DODAJ WYWOŁANIE
    });
}

function aktualizujUkrycieLewejKolumny() {
    if (!ekranGryEl) return;
    const czatUkryty = ekranGryEl.classList.contains('czat-ukryty');
    const partiaHistoriaUkryta = ekranGryEl.classList.contains('partia-historia-ukryta');
    ekranGryEl.classList.toggle('lewa-kolumna-ukryta', czatUkryty && partiaHistoriaUkryta);
}

function inicjalizujUstawieniaUI() {
    if (ekranGryEl && settingUkryjCzat) {
        const czatUkryty = localStorage.getItem('czatUkryty') === 'true'; // Changed
        if (czatUkryty) ekranGryEl.classList.add('czat-ukryty');
        settingUkryjCzat.checked = czatUkryty;
    }
    if (ekranGryEl && settingUkryjHistorie) {
        const historiaUkryta = localStorage.getItem('historiaUkryta') === 'true'; // Changed
        if (historiaUkryta) ekranGryEl.classList.add('historia-ukryta');
        settingUkryjHistorie.checked = historiaUkryta;
    }
    if (ekranGryEl && settingUkryjHistoriePartii) {
        const partiaHistoriaUkryta = localStorage.getItem('partiaHistoriaUkryta') === 'true'; // Changed
        if (partiaHistoriaUkryta) ekranGryEl.classList.add('partia-historia-ukryta');
        settingUkryjHistoriePartii.checked = partiaHistoriaUkryta;
    }
    if (ekranGryEl && settingUkryjPasekEwaluacji) {
        const pasekUkryty = localStorage.getItem('pasekEwaluacjiUkryty') === 'true';
        if (pasekUkryty) ekranGryEl.classList.add('pasek-ewaluacji-ukryty');
        settingUkryjPasekEwaluacji.checked = pasekUkryty;
    }
    aktualizujUkrycieLewejKolumny();
}

function inicjalizujWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const haslo = localStorage.getItem('lobbyHaslo') || ''; // Changed
    const wsUrl = `${protocol}//${window.location.host}/ws/${idGry}/${nazwaGracza}?haslo=${encodeURIComponent(haslo)}`;
    socket = new WebSocket(wsUrl);

    socket.onmessage = function(event) {
        try { // Added try-catch for safety
            const stan = JSON.parse(event.data);

            if (stan.typ_wiadomosci === 'czat') {
                dodajWiadomoscDoCzatu(stan.gracz, stan.tresc);
                return;
            }
            if (stan.nazwy_druzyn) nazwyDruzyn = stan.nazwy_druzyn;

            synchronizujDaneGracza(stan);

            if (stan.status_partii !== "LOBBY") {
                uruchomEfektyWizualne(stan, ostatniStanGry);
            }

            if (stan.status_partii === "LOBBY") {
                if (ekranGryEl) ekranGryEl.classList.add('hidden');
                if (ekranLobbyEl) ekranLobbyEl.classList.remove('hidden');
                if (modalOverlayEl) modalOverlayEl.classList.add('hidden');
                renderujLobby(stan);
            } else {
                if (ekranLobbyEl) ekranLobbyEl.classList.add('hidden');
                if (ekranGryEl) ekranGryEl.classList.remove('hidden');
                aktualizujWidokGry(stan);
            }
            ostatniStanGry = JSON.parse(JSON.stringify(stan));
        } catch (error) {
            console.error("Błąd przetwarzania wiadomości WebSocket:", error, event.data);
        }
    };

    socket.onclose = (event) => {
        console.log("Połączenie WebSocket zamknięte.", event.reason);
        if (event.reason) {
            if (event.reason === "Nieprawidłowe hasło.") {
                alert("Nieprawidłowe hasło.");
                window.location.href = "/lobby.html";
            } else {
                alert(event.reason);
                window.location.href = "/";
            }
        }
        // Optionally add a reconnect mechanism here if needed
    };

    socket.onerror = (error) => console.error("Błąd WebSocket:", error);
}

function synchronizujDaneGracza(stan) {
    if (!stan.slots) return;
    const mojObecnySlot = stan.slots.find(s => s.nazwa === nazwaGracza);
    if (mojObecnySlot) mojSlotId = mojObecnySlot.slot_id;
    else mojSlotId = null; // Handle case where player might be kicked
}

function wyslijAkcjeLobby(typAkcji, dane = {}) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja_lobby: typAkcji, ...dane }));
    } else console.error("WebSocket nie jest otwarty do wysłania akcji lobby.");
}

function wyslijAkcjeGry(akcja) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja: akcja }));
    } else console.error("WebSocket nie jest otwarty do wysłania akcji gry.");
}

async function zapiszUstawieniaNaSerwerze() {
    const aktualnyGracz = localStorage.getItem('nazwaGracza');
    // Nie zapisuj ustawień dla gości
    if (!aktualnyGracz || aktualnyGracz.toLowerCase().startsWith('gosc')) {
         console.log("Ustawienia nie są zapisywane dla gości.");
         return;
    }

    // Zbierz aktualne wartości z localStorage
    const settingsToSend = {
        czatUkryty: localStorage.getItem('czatUkryty') === 'true',
        historiaUkryta: localStorage.getItem('historiaUkryta') === 'true',
        partiaHistoriaUkryta: localStorage.getItem('partiaHistoriaUkryta') === 'true',
        pasekEwaluacjiUkryty: localStorage.getItem('pasekEwaluacjiUkryty') === 'true'
    };

    console.log("Wysyłanie ustawień na serwer:", settingsToSend);

    try {
        const response = await fetch(`/save_settings/${encodeURIComponent(aktualnyGracz)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsToSend)
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error("Błąd zapisywania ustawień na serwerze:", errorData.detail);
        } else {
            console.log("Ustawienia zapisane na serwerze.");
        }
    } catch (error) {
        console.error("Błąd sieci podczas zapisywania ustawień:", error);
    }
}




/* ==========================================================================
   SEKCJA 4: RENDEROWANIE WIDOKU LOBBY
   ========================================================================== */

function renderujLobby(stan) {
    const lobbyIdGryEl = document.getElementById('lobby-id-gry');
    const lobbyAkcjeEl = document.getElementById('lobby-akcje');

    if (!lobbyIdGryEl || !lobbyAkcjeEl) return;

    lobbyIdGryEl.textContent = idGry; // Wyświetl kod gry
    lobbyAkcjeEl.innerHTML = ''; // Wyczyść stare przyciski akcji

    const jestesHostem = stan.host === nazwaGracza;

    // Renderowanie slotów graczy w zależności od trybu gry
    if (stan.max_graczy === 3) { // Tryb 3-osobowy
        if (ekranLobbyEl) ekranLobbyEl.classList.add('lobby-3p');
        const druzynaMyEl = document.getElementById('druzyna-my');
        if (druzynaMyEl) druzynaMyEl.innerHTML = `<h2>Gracze (1 vs 2)</h2>`;
        const druzynaOniEl = document.getElementById('druzyna-oni');
        if (druzynaOniEl) druzynaOniEl.innerHTML = ''; // Wyczyść drugi panel

        stan.slots.forEach(slot => {
            const slotDiv = stworzSlotLobby(slot, stan);
            if (druzynaMyEl) druzynaMyEl.appendChild(slotDiv);
        });
    } else { // Tryb 4-osobowy
        if (ekranLobbyEl) ekranLobbyEl.classList.remove('lobby-3p');
        const druzynaMyEl = document.getElementById('druzyna-my');
        const druzynaOniEl = document.getElementById('druzyna-oni');
        // Wyświetl nazwy drużyn
        if (druzynaMyEl) druzynaMyEl.innerHTML = `<h2>Drużyna "${nazwyDruzyn.My}"</h2>`;
        if (druzynaOniEl) druzynaOniEl.innerHTML = `<h2>Drużyna "${nazwyDruzyn.Oni}"</h2>`;

        stan.slots.forEach(slot => {
            const slotDiv = stworzSlotLobby(slot, stan);
            // Dodaj slot do odpowiedniego panelu drużyny
            if (slot.druzyna === 'My' && druzynaMyEl) {
                druzynaMyEl.appendChild(slotDiv);
            } else if (druzynaOniEl) {
                druzynaOniEl.appendChild(slotDiv);
            }
        });
    }

    // Dodaj przycisk "Start Gry" dla hosta, jeśli wszystkie sloty są zajęte
    if (jestesHostem) {
        const startBtn = document.createElement('button');
        startBtn.textContent = 'Rozpocznij Grę';
        startBtn.onclick = () => wyslijAkcjeLobby('start_gry');
        const moznaStartowac = stan.slots.every(s => s.typ !== 'pusty');
        startBtn.disabled = !moznaStartowac; // Wyłącz, jeśli są puste sloty
        if (!moznaStartowac) { startBtn.title = 'Wszystkie miejsca muszą być zajęte, aby rozpocząć.'; }
        lobbyAkcjeEl.appendChild(startBtn);
    }
}

/**
 * Tworzy element HTML reprezentujący pojedynczy slot gracza w lobby.
 */
function stworzSlotLobby(slot, stan) {
    const slotDiv = document.createElement('div');
    slotDiv.className = 'slot-gracza';
    const jestesHostem = stan.host === nazwaGracza;
    const czyHost = stan.host === slot.nazwa;
    const ikonaHosta = czyHost ? '<span class="crown-icon">👑</span> ' : '';

    if (slot.typ === "pusty") { // Pusty slot
        const btn = document.createElement('button');
        btn.textContent = '🪑 Dołącz tutaj';
        btn.onclick = () => wyslijAkcjeLobby('dolacz_do_slota', { slot_id: slot.slot_id });
        slotDiv.appendChild(btn);
        // Host może dodać bota
        if (jestesHostem) {
            const botBtn = document.createElement('button');
            botBtn.textContent = '🤖 Dodaj Bota';
            botBtn.onclick = (e) => { e.stopPropagation(); wyslijAkcjeLobby('zmien_slot', { slot_id: slot.slot_id, nowy_typ: 'bot' }); };
            slotDiv.appendChild(botBtn);
        }
    } else if (slot.nazwa === nazwaGracza) { // Slot aktualnego gracza
        slotDiv.innerHTML = `${ikonaHosta}<strong>👤 ${slot.nazwa} (Ty)</strong>`;
    } else { // Slot innego gracza lub bota
        const ikonaTypu = slot.typ === 'bot' ? '🤖' : (slot.typ === 'rozlaczony' ? '🔌' : '👤'); // Added icon for disconnected
        const statusText = slot.typ === 'rozlaczony' ? ' (Rozłączony)' : ''; // Added status text
        slotDiv.innerHTML = `${ikonaHosta}${ikonaTypu} ${slot.nazwa}${statusText}`; // Display status
        // Host może wyrzucić gracza/bota
        if (jestesHostem) {
            const btn = document.createElement('button');
            btn.textContent = 'Wyrzuć';
            btn.onclick = () => wyslijAkcjeLobby('zmien_slot', { slot_id: slot.slot_id, nowy_typ: 'pusty' });
            slotDiv.appendChild(btn);
        }
    }
    return slotDiv;
}


/* ==========================================================================
   SEKCJA 5: RENDEROWANIE GŁÓWNEGO WIDOKU GRY
   ========================================================================== */
/**
 * Główna funkcja aktualizująca cały interfejs gry na podstawie danych ze stanu gry.
 */
function aktualizujWidokGry(stanGry) {
    // Jeśli gra się zakończyła, pokaż podsumowanie meczu i zakończ
    if (stanGry.status_partii === 'ZAKONCZONA') {
        pokazPodsumowanieMeczu(stanGry);
        return;
    }
    // Podstawowe zabezpieczenia przed brakiem danych
    if (!stanGry?.rozdanie || !stanGry?.slots) return;

    // Ustaw klasę CSS w zależności od trybu gry
    if (ekranGryEl) {
        ekranGryEl.classList.toggle('tryb-3-osoby', stanGry.max_graczy === 3);
    }

    const rozdanie = stanGry.rozdanie;
    const slotGracza = stanGry.slots.find(s => s.nazwa === nazwaGracza);
    if (!slotGracza) return; // Gracz nie jest już w grze?
    const pasekKontenerEl = document.getElementById('pasek-ewaluacji-kontener');
    const pasekWartoscEl = document.getElementById('pasek-ewaluacji-wartosc');
    const ocenaSilnika = stanGry.rozdanie?.aktualna_ocena; // ? dla bezpieczeństwa
    const fazaGry = stanGry.rozdanie?.faza;
    const czyLewaDoZamkniecia = stanGry.rozdanie?.lewa_do_zamkniecia;

    if (pasekKontenerEl && pasekWartoscEl) {
        const czyFazaRozgrywki = (rozdanie.faza === 'ROZGRYWKA');
        const czyPokazacPasek = (ocenaSilnika !== null && ocenaSilnika !== undefined);
        console.log("DEBUG Paska:", { faza: rozdanie.faza, ocena: ocenaSilnika, czyPokazac: czyPokazacPasek }); // Dodaj logowanie
        if (ekranGryEl) ekranGryEl.classList.toggle('brak-oceny', !czyPokazacPasek);
        if (czyPokazacPasek) {
            let procentWygranej = (ocenaSilnika + 1.0) / 2.0 * 100.0;
            procentWygranej = Math.max(0, Math.min(100, procentWygranej));

            console.log("DEBUG Paska - Aktualizacja:", { ocena: ocenaSilnika, procent: procentWygranej }); // Dodaj logowanie obliczeń

            // Ustaw szerokość
            pasekWartoscEl.style.width = `${procentWygranej}%`;
        } else {
             pasekWartoscEl.style.width = '50%';
        }
    }

    // --- Ustal pozycje graczy na ekranie (dol, gora, lewy, prawy) ---
    let pozycje = {};
    if (stanGry.max_graczy === 3) {
        const inniGracze = stanGry.slots.filter(s => s && s.nazwa !== nazwaGracza); // Added check for s
        pozycje = { dol: slotGracza, lewy: inniGracze[0], prawy: inniGracze[1] };
    } else {
        const partner = stanGry.slots.find(s => s && s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza); // Added check for s
        const przeciwnicy = stanGry.slots.filter(s => s && s.druzyna !== slotGracza.druzyna); // Added check for s
        pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
    }
    const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]).filter(([nazwa, _]) => nazwa)); // Filter out undefined names

    // --- Aktualizacja informacji o graczach (nazwy, podświetlenie tury) ---
    document.querySelectorAll('.gracz-boczny, #gracz-gora, #gracz-dol').forEach(el => {
        if(el) el.classList.remove('aktywny-gracz');
    });
    for (const [pos, slot] of Object.entries(pozycje)) {
        const kontenerGraczaEl = document.getElementById(`gracz-${pos}`);
        if (kontenerGraczaEl && slot) {
            const czyGrajacy = rozdanie.gracz_grajacy === slot.nazwa;
            const ikonaGrajacego = czyGrajacy ? '<span class="crown-icon">👑</span> ' : '';
            const statusText = slot.typ === 'rozlaczony' ? ' <span style="color:red;">(🔌)</span>' : ''; // Indicate disconnected in-game
            const infoGraczaEl = kontenerGraczaEl.querySelector('.info-gracza');
            if (infoGraczaEl) infoGraczaEl.innerHTML = `${ikonaGrajacego}${slot.nazwa}${statusText}`; // Show status
            if (rozdanie.kolej_gracza === slot.nazwa) {
                kontenerGraczaEl.classList.add('aktywny-gracz');
            }
        }
    }

    // --- Aktualizacja górnych paneli informacyjnych ---
    const kontraktTyp = rozdanie.kontrakt?.typ;
    const infoLewyRogEl = document.getElementById('info-lewy-rog');
    const kontenerPrawy = document.getElementById('kontener-info-prawy-rog');


    if (stanGry.max_graczy === 3) {
        const wynikHtml = Object.entries(stanGry.punkty_meczu || {}) // Added default {}
            .map(([nazwa, pkt]) => `<strong>${nazwa}:</strong> ${pkt}`)
            .join(' / ');
        if (infoLewyRogEl) infoLewyRogEl.innerHTML = `<div class="info-box">Wynik: ${wynikHtml}</div>`;

        let srodekHtml = '';
        const rekaGracza = rozdanie.rece_graczy ? rozdanie.rece_graczy[nazwaGracza] : null; // Check rece_graczy
        const iloscLew = rekaGracza?.length || 0; // Check rekaGracza

        if (kontraktTyp === 'LEPSZA' || kontraktTyp === 'GORSZA') {
            srodekHtml = `Pozostało lew: <strong>${iloscLew}</strong>`;
        } else if (kontraktTyp === 'BEZ_PYTANIA' && rozdanie.gracz_grajacy) {
            const pktGrajacego = (rozdanie.punkty_w_rozdaniu && rozdanie.punkty_w_rozdaniu[rozdanie.gracz_grajacy]) || 0; // Check punkty_w_rozdaniu
            srodekHtml = `Punkty 👑 ${rozdanie.gracz_grajacy}: <strong>${pktGrajacego}</strong>`;
        } else {
             let punktyHtml = Object.entries(rozdanie.punkty_w_rozdaniu || {}) // Added default {}
                .map(([nazwa, pkt]) => {
                    const ikona = (nazwa === rozdanie.gracz_grajacy) ? '👑 ' : '';
                    return `${ikona}${nazwa.substring(0, 8)}: ${pkt}`;
                })
                .join(' / ');
            srodekHtml = `Punkty: ${punktyHtml}`;
        }
        if (infoSrodekTrescEl) infoSrodekTrescEl.innerHTML = `<div class="info-box">${srodekHtml}</div>`;

    } else {
        const nazwaTeam1 = nazwyDruzyn.My;
        const nazwaTeam2 = nazwyDruzyn.Oni;
        const mojePunktyMeczu = (stanGry.punkty_meczu && stanGry.punkty_meczu[slotGracza.druzyna === 'My' ? nazwaTeam1 : nazwaTeam2]) || 0; // Check punkty_meczu
        const ichPunktyMeczu = (stanGry.punkty_meczu && stanGry.punkty_meczu[slotGracza.druzyna === 'My' ? nazwaTeam2 : nazwaTeam1]) || 0; // Check punkty_meczu
        if (infoLewyRogEl) infoLewyRogEl.innerHTML = `<div class="info-box">Wynik: <strong>My ${mojePunktyMeczu} - ${ichPunktyMeczu} Oni</strong></div>`;

        let srodekHtml = '';
        const rekaGracza = rozdanie.rece_graczy ? rozdanie.rece_graczy[nazwaGracza] : null; // Check rece_graczy
        const iloscLew = rekaGracza?.length || 0; // Check rekaGracza

        if (kontraktTyp === 'LEPSZA' || kontraktTyp === 'GORSZA') {
            srodekHtml = `Pozostało lew: <strong>${iloscLew}</strong>`;
        } else if (kontraktTyp === 'BEZ_PYTANIA' && rozdanie.gracz_grajacy) {
            const grajacySlot = stanGry.slots.find(s => s && s.nazwa === rozdanie.gracz_grajacy); // Check s
            const druzynaGrajacego = grajacySlot?.druzyna;
            const nazwaDruzynyGrajacego = druzynaGrajacego ? nazwyDruzyn[druzynaGrajacego] : 'Błąd';
            const pktGrajacego = (rozdanie.punkty_w_rozdaniu && rozdanie.punkty_w_rozdaniu[nazwaDruzynyGrajacego]) || 0; // Check punkty_w_rozdaniu
            srodekHtml = `Punkty 👑 ${rozdanie.gracz_grajacy}: <strong>${pktGrajacego}</strong>`;
        } else {
            const mojePunktyRozdania = (rozdanie.punkty_w_rozdaniu && rozdanie.punkty_w_rozdaniu[slotGracza.druzyna === 'My' ? nazwaTeam1 : nazwaTeam2]) || 0; // Check punkty_w_rozdaniu
            const ichPunktyRozdania = (rozdanie.punkty_w_rozdaniu && rozdanie.punkty_w_rozdaniu[slotGracza.druzyna === 'My' ? nazwaTeam2 : nazwaTeam1]) || 0; // Check punkty_w_rozdaniu
            srodekHtml = `Punkty: My ${mojePunktyRozdania} - ${ichPunktyRozdania} Oni`;
        }
        if (infoSrodekTrescEl) infoSrodekTrescEl.innerHTML = `<div class="info-box">${srodekHtml}</div>`;
    }

    if (kontenerPrawy) {
        const infoPrawyIstniejacy = kontenerPrawy.querySelector('#info-prawy-rog');
        const infoStawkaIstniejaca = kontenerPrawy.querySelector('#info-stawka');
        if(infoPrawyIstniejacy) infoPrawyIstniejacy.innerHTML = `<div class="info-box">Kontrakt: ${formatujKontrakt(rozdanie.kontrakt)}</div>`;

        const aktualnaStawka = stanGry.rozdanie.aktualna_stawka || 0;
        if(infoStawkaIstniejaca){
             if (aktualnaStawka > 0) {
                infoStawkaIstniejaca.innerHTML = `Stawka: <strong>${aktualnaStawka}</strong> pkt`;
                infoStawkaIstniejaca.classList.remove('hidden');
            } else {
                infoStawkaIstniejaca.classList.add('hidden');
            }
        }
    }

    // --- Renderowanie kart na ręce gracza ---
    const rekaGlownaEl = document.querySelector('#gracz-dol .reka-glowna');
    if (rekaGlownaEl) {
        rekaGlownaEl.innerHTML = '';
        const rekaTwojegoGracza = (rozdanie.rece_graczy && rozdanie.rece_graczy[nazwaGracza]) || []; // Check rece_graczy
        const grywalneKarty = rozdanie.grywalne_karty || []; // Default to empty array

        rekaTwojegoGracza.forEach(nazwaKarty => {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = `/static/karty/${nazwaKarty.replace(' ', '')}.png`;
            if (grywalneKarty.includes(nazwaKarty)) { // Use checked grywalneKarty
                img.classList.add('grywalna');
                img.onclick = (e) => {
                    const celEl = document.getElementById('slot-karty-dol');
                    if (celEl) animujZagranieKarty(e.target, celEl);
                    wyslijAkcjeGry({ typ: 'zagraj_karte', karta: nazwaKarty });
                };
            }
            rekaGlownaEl.appendChild(img);
        });
    }

    // --- Renderowanie rewersów kart dla pozostałych graczy ---
    for (const [pos, slot] of Object.entries(pozycje)) {
        if (pos === 'dol' || !slot) continue;
        const rekaEl = document.querySelector(`#gracz-${pos} .reka-${pos === 'gora' ? 'gorna' : 'boczna'}`);
        if (!rekaEl) continue;
        rekaEl.innerHTML = '';
        const iloscKart = (rozdanie.rece_graczy && rozdanie.rece_graczy[slot.nazwa])?.length || 0; // Check rece_graczy
        for (let i = 0; i < iloscKart; i++) {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = '/static/karty/Rewers.png';
            rekaEl.appendChild(img);
        }
    }

    // --- Renderowanie kart zagranych na stół ---
    document.querySelectorAll('.slot-karty').forEach(slot => {
         if(slot) slot.innerHTML = '';
    });
    (rozdanie.karty_na_stole || []).forEach(item => { // Added default []
        const pozycjaGracza = pozycjeWgNazwy[item.gracz];
        if (pozycjaGracza) {
            const slotEl = document.getElementById(`slot-karty-${pozycjaGracza}`);
            if (slotEl) {
                slotEl.innerHTML = `<img class="karta" src="/static/karty/${item.karta.replace(' ', '')}.png">`;
            }
        }
    });

    // --- Renderowanie przycisków akcji (licytacja) ---
    const kontenerAkcjiEl = document.getElementById('kontener-akcji');
    if (kontenerAkcjiEl) {
        const mozliweAkcje = rozdanie.mozliwe_akcje || []; // Default to empty array
        if (rozdanie.kolej_gracza === nazwaGracza && rozdanie.faza !== 'ROZGRYWKA' && mozliweAkcje.length > 0) {
            renderujPrzyciskiLicytacji(mozliweAkcje); // Use checked mozliweAkcje
        } else {
            kontenerAkcjiEl.innerHTML = '';
        }
    }

    // --- Renderowanie historii rozdania (prawa kolumna) ---
    const historiaListaEl = document.getElementById('historia-lista');
    if (historiaListaEl) {
        historiaListaEl.innerHTML = '';
        (rozdanie.historia_rozdania || []).forEach(log => { // Added default []
            const p = document.createElement('p');
            p.innerHTML = formatujWpisHistorii(log);
            historiaListaEl.appendChild(p);
        });
        historiaListaEl.scrollTop = historiaListaEl.scrollHeight;
    }

    // --- Pokaż podsumowanie rozdania, jeśli jest dostępne ---
    if (rozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && rozdanie.podsumowanie) {
        pokazPodsumowanieRozdania(stanGry);
    }
    else if (podsumowanieRozdaniaEl && !podsumowanieRozdaniaEl.classList.contains('hidden')) {
         podsumowanieRozdaniaEl.classList.add('hidden');
         if (modalOverlayEl && !modalOverlayEl.querySelector('.panel:not(.hidden)')) {
             modalOverlayEl.classList.add('hidden');
         }
         console.log("DEBUG: Ukryto modal podsumowania rozdania, bo faza gry to:", rozdanie.faza);
    }

    // --- Jeśli lewa ma być zamknięta, wyślij akcję finalizacji po chwili ---
    if (rozdanie.lewa_do_zamkniecia) {
        setTimeout(() => wyslijAkcjeGry({ typ: 'finalizuj_lewe' }), 2000);
    }

    // --- Renderowanie historii partii (lewa górna kolumna) ---
    if (partiaHistoriaListaEl) {
        partiaHistoriaListaEl.innerHTML = '';
        (stanGry.historia_partii || []).forEach(wpis => { // Added default []
            const p = document.createElement('p');
            p.textContent = wpis;
            partiaHistoriaListaEl.appendChild(p);
        });
        if (stanGry.historia_partii && stanGry.historia_partii.length > 0) {
             partiaHistoriaListaEl.scrollTop = partiaHistoriaListaEl.scrollHeight;
        }
    }

    pokazDymekPoOstatniejAkcji(stanGry, pozycje);
}

/* ==========================================================================
   SEKCJA 6: LOGIKA EFEKTÓW (DŹWIĘKI I ANIMACJE)
   ========================================================================== */
function uruchomEfektyWizualne(nowyStan, staryStan) {
    if (!staryStan?.rozdanie || !nowyStan?.rozdanie) {
        console.log("Brak danych do porównania efektów", {nowyStan, staryStan});
        return;
    }

    const noweRozdanie = nowyStan.rozdanie;
    const stareRozdanie = staryStan.rozdanie;
    const noweKartyNaStole = noweRozdanie.karty_na_stole || [];
    const stareKartyNaStole = stareRozdanie.karty_na_stole || [];

    if (noweKartyNaStole.length > stareKartyNaStole.length) {
        const nowaKartaZagranie = noweKartyNaStole.find(nk =>
            !stareKartyNaStole.some(sk => sk.karta === nk.karta && sk.gracz === nk.gracz)
        );

        if (nowaKartaZagranie && nowaKartaZagranie.gracz !== nazwaGracza) {
             let pozycje = {};
             const slotGracza = nowyStan.slots.find(s => s && s.nazwa === nazwaGracza); // Check s
            if (!slotGracza) return;

            if (nowyStan.max_graczy === 3) {
                const inniGracze = nowyStan.slots.filter(s => s && s.nazwa !== nazwaGracza); // Check s
                pozycje = { dol: slotGracza, lewy: inniGracze[0], prawy: inniGracze[1] };
            } else {
                const partner = nowyStan.slots.find(s => s && s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza); // Check s
                const przeciwnicy = nowyStan.slots.filter(s => s && s.druzyna !== slotGracza.druzyna); // Check s
                pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
            }
            const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]).filter(([nazwa, _]) => nazwa)); // Filter undefined names

            const pozycjaGracza = pozycjeWgNazwy[nowaKartaZagranie.gracz];
            if (pozycjaGracza) {
                const startEl = document.querySelector(`#gracz-${pozycjaGracza} .info-gracza`);
                const celEl = document.getElementById(`slot-karty-${pozycjaGracza}`);
                if (startEl && celEl) {
                    animujZagranieKarty(startEl, celEl, nowaKartaZagranie.karta);
                }
            }
        }
    }
    uruchomEfektyDzwiekowe(nowyStan, staryStan);
}

function animujZagranieKarty(startEl, celEl, nazwaKarty = null) {
    const startRect = startEl.getBoundingClientRect();
    const celRect = celEl.getBoundingClientRect();

    const animowanaKarta = document.createElement('img');
    animowanaKarta.className = 'animowana-karta';
    animowanaKarta.src = nazwaKarty ? `/static/karty/${nazwaKarty.replace(' ', '')}.png` : (startEl.src || '/static/karty/Rewers.png'); // Added fallback src
    animowanaKarta.style.left = `${startRect.left}px`;
    animowanaKarta.style.top = `${startRect.top}px`;
    animowanaKarta.style.width = startEl.tagName === 'IMG' ? `${startRect.width}px` : '70px'; // Set width based on source
    animowanaKarta.style.height = 'auto'; // Maintain aspect ratio

    if (animationOverlayEl) animationOverlayEl.appendChild(animowanaKarta);

    if (startEl.tagName === 'IMG') {
        startEl.style.visibility = 'hidden';
    }

    void animowanaKarta.offsetWidth;

    const deltaX = celRect.left + (celRect.width / 2) - (startRect.left + (startRect.width / 2)); // Center animation
    const deltaY = celRect.top + (celRect.height / 2) - (startRect.top + (startRect.height / 2)); // Center animation
    animowanaKarta.style.transform = `translate(${deltaX}px, ${deltaY}px) scale(1)`; // Ensure scale is 1 initially maybe?

    setTimeout(() => {
        animowanaKarta.remove();
        if (startEl.style.visibility === 'hidden') {
            startEl.style.visibility = 'visible';
        }
    }, 400);
}

function uruchomEfektyDzwiekowe(nowyStan, staryStan) {
    if (!staryStan?.rozdanie || !nowyStan?.rozdanie) return;

    const noweRozdanie = nowyStan.rozdanie;
    const stareRozdanie = staryStan.rozdanie;

    const noweKartyStol = noweRozdanie.karty_na_stole || [];
    const stareKartyStol = stareRozdanie.karty_na_stole || [];
    if (noweKartyStol.length > stareKartyStol.length && !noweRozdanie.lewa_do_zamkniecia) {
        odtworzDzwiek('zagranieKarty');
    }
    if (noweRozdanie.lewa_do_zamkniecia && !stareRozdanie.lewa_do_zamkniecia) {
         odtworzDzwiek('wygranaLewa');
    }
    const nowaHistoria = noweRozdanie.historia_rozdania || [];
    const staraHistoria = stareRozdanie.historia_rozdania || [];
    if (nowaHistoria.length > staraHistoria.length) {
        const noweLogi = nowaHistoria.slice(staraHistoria.length);
        const logAkcji = noweLogi.find(log => log.typ === 'akcja_licytacyjna');
        if (logAkcji && logAkcji.akcja) {
            const akcja = logAkcji.akcja;
            const typAkcji = akcja.typ?.name || akcja.typ; // Handle enum or string
            if (typAkcji === 'pas' || typAkcji === 'pas_lufa') {
                odtworzDzwiek('pas');
            } else if (['deklaracja', 'przebicie', 'lufa', 'kontra', 'zmiana_kontraktu', 'pytanie', 'nie_pytam', 'graj_normalnie', 'do_konca'].includes(typAkcji)) { // Added do_konca
                odtworzDzwiek('licytacja');
            }
        }
    }
    if (noweRozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && stareRozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
        odtworzDzwiek('koniecRozdania');
    }
}


/* ==========================================================================
   SEKCJA 7: FUNKCJE POMOCNICZE I OBSŁUGA ZDARZEŃ
   ========================================================================== */
function pokazModal(modalElement) {
    if (!modalOverlayEl || !modalElement) return;
    modalOverlayEl.querySelectorAll('.panel').forEach(panel => panel.classList.add('hidden'));
    modalElement.classList.remove('hidden');
    modalOverlayEl.classList.remove('hidden');
}

function ukryjModal() {
    if (!modalOverlayEl) return;
    modalOverlayEl.classList.add('hidden');
    modalOverlayEl.querySelectorAll('.panel').forEach(panel => panel.classList.add('hidden'));
}

function formatujKontrakt(kontrakt) {
    if (!kontrakt || !kontrakt.typ) return 'Brak';
    const kontraktTyp = kontrakt.typ.name || kontrakt.typ;
    const atut = kontrakt.atut?.name || kontrakt.atut;
    const info = atut ? mapowanieKolorow[atut] : null; // Check if atut exists

    if (kontraktTyp === 'NORMALNA' && info) {
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span>`;
    }
    if (kontraktTyp === 'BEZ_PYTANIA' && info) {
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span><span class="znak-zapytania-przekreslony">?</span>`;
    }
    // Handle cases like LEPSZA, GORSZA, or if info is null
    const readableName = kontraktTyp.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()); // Format name
    return `<strong>${readableName}</strong>`;
}

function pokazPodsumowanieRozdania(stanGry) {
    const podsumowanie = stanGry.rozdanie?.podsumowanie;
    const modalPanelEl = podsumowanieRozdaniaEl;
    if (!modalPanelEl || !podsumowanie) return;
    const podsumowanieTrescEl = document.getElementById('podsumowanie-tresc');
    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove());

    let bonusInfo = '';
    if (podsumowanie.bonus_z_trzech_kart) {
        bonusInfo += `<p style="color: yellow; font-weight: bold;">Bonus za grę z ${stanGry.max_graczy === 3 ? '4' : '3'} kart (x2)!</p>`;
    }
    if (podsumowanie.mnoznik_lufy > 1) {
        bonusInfo += `<p style="color: orange; font-weight: bold;">Bonus za lufy (x${podsumowanie.mnoznik_lufy})!</p>`;
    }

    let wygraniHtml = '';
    if (stanGry.max_graczy === 3) {
        wygraniHtml = `Rozdanie wygrane przez: <strong>${(podsumowanie.wygrani_gracze || []).join(', ')}</strong>`;
    } else {
        wygraniHtml = `Rozdanie wygrane przez: <strong>${podsumowanie.wygrana_druzyna || 'Brak'}</strong>`;
    }

    if (podsumowanieTrescEl) {
        podsumowanieTrescEl.innerHTML = `<p>${wygraniHtml}</p>
                                        <p>Zdobyte punkty: <strong>${podsumowanie.przyznane_punkty || 0}</strong></p>
                                        ${bonusInfo}
                                        <p style="font-size: 0.9em; color: #ccc;">(${podsumowanie.powod || 'Koniec rozdania'})</p>`; // Added reason
    }
    const tytulEl = document.getElementById('podsumowanie-tytul');
    if (tytulEl) tytulEl.textContent = 'Koniec Rozdania!';

    const nastepneRozdanieBtn = document.createElement('button');
    modalPanelEl.appendChild(nastepneRozdanieBtn);
    const graczeGotowi = stanGry.gracze_gotowi || []; // Default to empty array
    const czyJestesGotowy = graczeGotowi.includes(nazwaGracza);
    if (czyJestesGotowy) {
        nastepneRozdanieBtn.textContent = 'Oczekiwanie na pozostałych...';
        nastepneRozdanieBtn.disabled = true;
    } else {
        nastepneRozdanieBtn.textContent = 'Dalej';
        nastepneRozdanieBtn.disabled = false;
        nastepneRozdanieBtn.onclick = () => {
            wyslijAkcjeGry({ typ: 'nastepne_rozdanie' });
            nastepneRozdanieBtn.textContent = 'Oczekiwanie na pozostałych...';
            nastepneRozdanieBtn.disabled = true;
        };
    }
    pokazModal(podsumowanieRozdaniaEl);
}

function pokazPodsumowanieMeczu(stanGry) {
    const tytulEl = document.getElementById('podsumowanie-tytul');
    const trescEl = document.getElementById('podsumowanie-tresc');
    const modalPanelEl = podsumowanieRozdaniaEl;
    if (!modalPanelEl || !tytulEl || !trescEl) return;

    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove());

    let zwyciezca = 'Brak';
    let wynikHtml = 'Brak danych';
    if(stanGry.max_graczy === 3) {
        const wyniki = Object.entries(stanGry.punkty_meczu || {});
        if (wyniki.length > 0) {
            const posortowani = wyniki.sort((a, b) => b[1] - a[1]);
            zwyciezca = posortowani[0][0];
            wynikHtml = wyniki.map(([nazwa, pkt]) => `${nazwa}: ${pkt}`).join(', ');
        }
    } else {
        const nazwaTeam1 = nazwyDruzyn.My;
        const nazwaTeam2 = nazwyDruzyn.Oni;
        const punkty1 = stanGry.punkty_meczu ? stanGry.punkty_meczu[nazwaTeam1] || 0 : 0;
        const punkty2 = stanGry.punkty_meczu ? stanGry.punkty_meczu[nazwaTeam2] || 0 : 0;
        zwyciezca = punkty1 >= 66 ? nazwaTeam1 : (punkty2 >= 66 ? nazwaTeam2 : 'Remis/Błąd'); // Handle draw/error
        wynikHtml = `${nazwaTeam1} ${punkty1} - ${punkty2} ${nazwaTeam2}`;
    }

    tytulEl.textContent = 'Koniec Meczu!';
    trescEl.innerHTML = `<h2>Wygrał ${stanGry.max_graczy === 3 ? 'gracz' : 'drużyna'} "${zwyciezca}"!</h2>
                         <p>Wynik końcowy: ${wynikHtml}</p>`;

    const wyjdzBtn = document.createElement('button');
    wyjdzBtn.textContent = 'Wyjdź do menu';
    wyjdzBtn.onclick = () => {
        localStorage.removeItem('lobbyHaslo'); // Changed
        localStorage.removeItem('rejoinGameId'); // Remove rejoin ID on exit
        window.location.href = '/';
    };
    modalPanelEl.appendChild(wyjdzBtn);

    if (stanGry.tryb_gry === 'online' && stanGry.host === nazwaGracza) { // Show only for host in online game
        const lobbyBtn = document.createElement('button');
        lobbyBtn.textContent = 'Powrót do lobby';
        lobbyBtn.onclick = () => { wyslijAkcjeGry({ typ: 'powrot_do_lobby' }); };
        modalPanelEl.appendChild(lobbyBtn);
    } else if (stanGry.tryb_gry === 'online') { // Show waiting text for non-hosts
        const waitingText = document.createElement('p');
        waitingText.textContent = 'Oczekiwanie na hosta...';
        waitingText.style.marginTop = '10px';
        modalPanelEl.appendChild(waitingText);
    }
    pokazModal(podsumowanieRozdaniaEl);
}


function formatujWpisHistorii(log) {
    const gracz = `<strong>${log.gracz || 'System'}</strong>`;
    switch (log.typ) {
        case 'akcja_licytacyjna': {
            const akcja = log.akcja;
            if (!akcja) return `${gracz} wykonał nieznaną akcję.`;
            const typAkcji = akcja.typ?.name || akcja.typ;
            const kontraktAkcji = akcja.kontrakt?.name || akcja.kontrakt;
            const atutAkcji = akcja.atut?.name || akcja.atut;

            if (typAkcji === 'pas' || typAkcji === 'pas_lufa') return `${gracz} pasuje.`;
            if (typAkcji === 'pytanie') return `${gracz} pyta.`;
            if (typAkcji === 'nie_pytam') return `${gracz} gra <strong>Bez Pytania</strong>.`;
            if (typAkcji === 'graj_normalnie') return `${gracz} gra normalnie.`;
            if (typAkcji === 'deklaracja') {
                const kontraktObj = { typ: kontraktAkcji, atut: atutAkcji };
                return `${gracz} licytuje: ${formatujKontrakt(kontraktObj)}`;
            }
            if (typAkcji === 'zmiana_kontraktu') {
                return `${gracz} zmienia kontrakt na: <strong>${kontraktAkcji}</strong>.`;
            }
             if (typAkcji === 'przebicie') {
                return `${gracz} przebija na: <strong>${kontraktAkcji}</strong>.`;
            }
             if (typAkcji === 'lufa' || typAkcji === 'kontra' || typAkcji === 'do_konca') {
                 let txt = typAkcji.charAt(0).toUpperCase() + typAkcji.slice(1).replace('_', ' '); // Format name
                 if(typAkcji === 'lufa' && kontraktAkcji) { // Removed atut check, might not be available
                     const kontraktStr = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji }); // Still try to format
                     txt = `Lufa (na ${kontraktStr})`;
                 }
                return `${gracz} mówi: <strong>${txt}</strong>.`;
            }
            return `${gracz} wykonuje akcję: ${typAkcji}.`;
        }
        case 'zagranie_karty':
            return `${gracz} zagrał ${log.karta || 'kartę'}.`; // Simplified
        case 'koniec_lewy':
            return `Lewę ${log.numer_lewy ? `nr ${log.numer_lewy} ` : ''}wygrywa <strong>${log.zwyciezca || '?'}</strong> (+${log.punkty || 0} pkt).`; // Added trick number if available
        case 'meldunek':
            return `${gracz} melduje ${log.punkty === 40 ? 'dużą ' : ''}parę (+${log.punkty || 0} pkt).`; // Better text
        case 'bonus':
            const liczbaGraczy = ostatniStanGry.max_graczy || 4;
            const opisBonusu = log.opis ? `(${log.opis})` : `z ${liczbaGraczy === 3 ? '4' : '3'} kart`;
            return `Bonus za grę <strong>${gracz}</strong> ${opisBonusu}.`;
        case 'nowe_rozdanie': // Added log type
             return `--- Rozdanie ${log.numer_rozdania || '?'} (Rozdający: ${log.rozdajacy || '?'}) ---`;
        case 'koniec_rozdania': // Added log type
             return `--- Koniec Rozdania ---`;
        default:
            try {
                // Try to format common simple logs
                let details = Object.entries(log).filter(([key, _]) => key !== 'typ').map(([key, val]) => `${key}: ${val}`).join(', ');
                return `[${log.typ || 'Log'}] ${details}`;
            } catch { return `[Nieznany log]`; }
    }
}

function pokazDymekPoOstatniejAkcji(stanGry, pozycje) {
    if (!stanGry?.rozdanie || !ostatniStanGry?.rozdanie) return;

    const nowaHistoria = stanGry.rozdanie.historia_rozdania || [];
    const staraHistoria = ostatniStanGry.rozdanie.historia_rozdania || [];
    const nowaDlugosc = nowaHistoria.length;
    const staraDlugosc = staraHistoria.length;

    if (nowaDlugosc <= staraDlugosc) return;

    const noweLogi = nowaHistoria.slice(staraDlugosc);
    let logDoWyswietlenia = null;
    for (let i = noweLogi.length - 1; i >= 0; i--) {
        const log = noweLogi[i];
        if (log.typ === 'akcja_licytacyjna' || log.typ === 'meldunek') {
            logDoWyswietlenia = log; break;
        }
    }

    if (!logDoWyswietlenia || !logDoWyswietlenia.gracz) return; // Added check for gracz

    const pozycjaGracza = Object.keys(pozycje).find(p => pozycje[p] && pozycje[p].nazwa === logDoWyswietlenia.gracz);
    if (!pozycjaGracza) return;

    let tekstDymka = '';
    if (logDoWyswietlenia.typ === 'akcja_licytacyjna') {
        const akcja = logDoWyswietlenia.akcja;
        if (!akcja) return;
        const typAkcji = akcja.typ?.name || akcja.typ;
        const kontraktAkcji = akcja.kontrakt?.name || akcja.kontrakt;
        const atutAkcji = akcja.atut?.name || akcja.atut;

        switch (typAkcji) {
            case 'deklaracja': tekstDymka = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji }); break;
            case 'zmiana_kontraktu': tekstDymka = `Zmieniam na: ${formatujKontrakt({ typ: kontraktAkcji })}`; break; // Use formatter
            case 'przebicie': tekstDymka = `Przebijam: ${formatujKontrakt({ typ: kontraktAkcji })}!`; break; // Use formatter
            case 'pas': case 'pas_lufa': tekstDymka = 'Pas'; break;
            case 'pytanie': tekstDymka = 'Pytam?'; break;
            case 'nie_pytam': tekstDymka = 'Bez Pytania!'; break;
            case 'graj_normalnie': tekstDymka = 'Gramy!'; break;
            case 'do_konca': tekstDymka = 'Do końca!'; break;
            default:
                 tekstDymka = typAkcji.charAt(0).toUpperCase() + typAkcji.slice(1).replace('_', ' ');
                 if (typAkcji === 'lufa' && kontraktAkcji) {
                     const kontraktStr = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji });
                     tekstDymka = `Lufa (${kontraktStr})`; // Simplified text
                 }
                break;
        }
    } else if (logDoWyswietlenia.typ === 'meldunek') {
        tekstDymka = `${logDoWyswietlenia.punkty === 40 ? 'Duża ' : ''}Para! (+${logDoWyswietlenia.punkty || 0})`; // Better text
    }

    if (tekstDymka) pokazDymekAkcji(pozycjaGracza, tekstDymka);
}


function pokazDymekAkcji(pozycja, tekst) {
    const kontenerGracza = document.getElementById(`gracz-${pozycja}`);
    if (!kontenerGracza) return;

    const staryDymek = kontenerGracza.querySelector('.dymek-akcji');
    if (staryDymek) staryDymek.remove();

    const dymek = document.createElement('div');
    dymek.className = 'dymek-akcji';
    dymek.innerHTML = tekst;
    kontenerGracza.appendChild(dymek);

    setTimeout(() => {
        if (dymek.parentNode) dymek.remove();
    }, 4000);
}

function renderujPrzyciskiLicytacji(akcje) {
    const kontener = document.getElementById('kontener-akcji');
    if (!kontener) return;
    kontener.innerHTML = '';

    const grupy = akcje.reduce((acc, akcja) => {
        const typAkcji = akcja.typ?.name || akcja.typ;
        const kontraktAkcji = akcja.kontrakt?.name || akcja.kontrakt;
        let klucz = typAkcji === 'deklaracja' || typAkcji === 'przebicie' ? kontraktAkcji : typAkcji;
        if (!acc[klucz]) acc[klucz] = [];
        acc[klucz].push(akcja);
        return acc;
    }, {});

    for (const [nazwaGrupy, akcjeWGrupie] of Object.entries(grupy)) {
        const btn = document.createElement('button');
        const pierwszaAkcja = akcjeWGrupie[0];
        const typAkcjiGrupy = pierwszaAkcja.typ?.name || pierwszaAkcja.typ; // Type of the group's first action

        if (typAkcjiGrupy === 'lufa') {
            const kontekst = pierwszaAkcja;
             let btnHTML = "Lufa"; // Default
            if (kontekst.kontrakt) { // Check if contract context is provided
                 const kontraktStr = formatujKontrakt({ typ: kontekst.kontrakt, atut: kontekst.atut });
                 btnHTML = `Lufa (${kontraktStr})`;
            }
             btn.innerHTML = btnHTML;
            btn.onclick = () => wyslijAkcjeGry(pierwszaAkcja);
        }
        else if (akcjeWGrupie.length === 1 && !pierwszaAkcja.atut && typAkcjiGrupy !== 'deklaracja') { // Single action buttons without suits (pas, LEPSZA, pytanie, etc.) AND NOT a declaration
            let btnText = nazwaGrupy.replace('_', ' ');
            btnText = btnText.charAt(0).toUpperCase() + btnText.slice(1).toLowerCase();
            if(nazwaGrupy === 'pas_lufa') btnText = 'Pas Lufa';
            if(nazwaGrupy === 'do_konca') btnText = 'Do Końca'; // Better formatting
            if(nazwaGrupy === 'graj_normalnie') btnText = 'Graj Normalnie'; // Better formatting
            if(nazwaGrupy === 'nie_pytam') btnText = 'Bez Pytania'; // Better formatting

             btn.textContent = btnText;
            btn.onclick = () => wyslijAkcjeGry(pierwszaAkcja);
        } else { // Buttons grouping suits (NORMALNA, BEZ_PYTANIA declarations) OR single declarations (LEPSZA, GORSZA)
            // Use formatujKontrakt to display the button text (handles LEPSZA, GORSZA nicely)
            btn.innerHTML = formatujKontrakt({ typ: nazwaGrupy }); // Display contract name correctly

            if (akcjeWGrupie.length === 1 && !pierwszaAkcja.atut) {
                // If it's a single declaration without a suit (LEPSZA, GORSZA), assign action directly
                btn.onclick = () => wyslijAkcjeGry(pierwszaAkcja);
            } else {
                // Otherwise (NORMALNA, BEZ_PYTANIA with suits), show suit buttons on click
                btn.onclick = () => {
                    kontener.innerHTML = '';
                    akcjeWGrupie.forEach(akcjaKoloru => {
                        const kolorBtn = document.createElement('button');
                        const atutKoloru = akcjaKoloru.atut?.name || akcjaKoloru.atut;
                        if (atutKoloru) {
                            const info = mapowanieKolorow[atutKoloru];
                            if (info) kolorBtn.innerHTML = `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span> ${atutKoloru}`;
                            else kolorBtn.textContent = atutKoloru;
                        } else kolorBtn.textContent = nazwaGrupy; // Fallback
                        kolorBtn.onclick = () => wyslijAkcjeGry(akcjaKoloru);
                        kontener.appendChild(kolorBtn);
                    });
                     // Add a back button
                     const backBtn = document.createElement('button');
                     backBtn.textContent = '<< Wstecz';
                     backBtn.style.backgroundColor = '#6c757d';
                     backBtn.onclick = () => renderujPrzyciskiLicytacji(akcje); // Re-render initial buttons
                     kontener.appendChild(backBtn);
                };
            }
        }
        kontener.appendChild(btn);
    }
}

/* ==========================================================================
   SEKCJA 8: OBSŁUGA CZATU
   ========================================================================== */
function wyslijWiadomoscCzat() {
    if (!czatInputEl) return;
    const wiadomosc = czatInputEl.value.trim();
    if (wiadomosc && socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            gracz: nazwaGracza, typ_wiadomosci: 'czat', tresc: wiadomosc
        }));
        czatInputEl.value = '';
    }
}

function dodajWiadomoscDoCzatu(gracz, tresc) {
    if (!czatWiadomosciEl) return;
    const p = document.createElement('p');
    // Sanitize HTML content before inserting
    const sanitizedContent = tresc.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    p.innerHTML = `<strong>${gracz}:</strong> ${sanitizedContent}`;
    czatWiadomosciEl.appendChild(p);
    czatWiadomosciEl.scrollTop = czatWiadomosciEl.scrollHeight;
    if (gracz !== nazwaGracza) {
        odtworzDzwiek('wiadomoscCzat');
    }
}
