// ZAKTUALIZOWANY PLIK: script.js

/* ==========================================================================
   SEKCJA 1: DEKLARACJE GLOBALNE I POBIERANIE ELEMENTÓW DOM
   ========================================================================== */

let idGry = null;
let nazwaGracza = null;
let socket = null;
let mojSlotId = null;
let ostatniaDlugoscHistorii = 0;
let nazwyDruzyn = { My: "My", Oni: "Oni" };
let ostatniStanGry = {}; // Do śledzenia zmian dla dźwięków i animacji

const ekranLobbyEl = document.getElementById('ekran-lobby');
const ekranGryEl = document.querySelector('.ekran-gry');
const modalOverlayEl = document.getElementById('modal-overlay');
const czatWiadomosciEl = document.getElementById('czat-wiadomosci');
const czatInputEl = document.getElementById('czat-input');
const czatWyslijBtn = document.getElementById('czat-wyslij-btn');
const animationOverlayEl = document.getElementById('animation-overlay');

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

window.onload = () => {
    const params = new URLSearchParams(window.location.search);
    idGry = params.get('id');
    nazwaGracza = sessionStorage.getItem('nazwaGracza') || `Gracz${Math.floor(Math.random() * 1000)}`;
    sessionStorage.setItem('nazwaGracza', nazwaGracza);

    if (idGry) {
        inicjalizujWebSocket();
    } else {
        window.location.href = "/";
    }
};

function inicjalizujWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${idGry}/${nazwaGracza}`;
    socket = new WebSocket(wsUrl);

    socket.onmessage = function(event) {
        const stan = JSON.parse(event.data);
        if (stan.typ_wiadomosci === 'czat') {
            dodajWiadomoscDoCzatu(stan.gracz, stan.tresc);
            return;
        }
        
        if (stan.nazwy_druzyn) {
            nazwyDruzyn = stan.nazwy_druzyn;
        }

        synchronizujDaneGracza(stan);

        if (stan.status_partii === "LOBBY") {
            ekranGryEl.classList.add('hidden');
            ekranLobbyEl.classList.remove('hidden');
            modalOverlayEl.classList.add('hidden');
            renderujLobby(stan);
        } else {
            ekranLobbyEl.classList.add('hidden');
            ekranGryEl.classList.remove('hidden');
            uruchomEfektyWizualne(stan, ostatniStanGry); // Uruchamiamy animacje przed renderowaniem
            aktualizujWidokGry(stan);
        }
        
        ostatniStanGry = JSON.parse(JSON.stringify(stan));
    };

    socket.onclose = (event) => {
        console.log("Połączenie WebSocket zamknięte.", event.reason);
        if (event.reason) { alert(event.reason); window.location.href = "/"; }
    };
    socket.onerror = (error) => console.error("Błąd WebSocket:", error);
}

function synchronizujDaneGracza(stan) {
    if (!stan.slots) return;
    const mojObecnySlot = stan.slots.find(s => s.nazwa === nazwaGracza);
    if (mojObecnySlot) { mojSlotId = mojObecnySlot.slot_id; }
}

function wyslijAkcjeLobby(typAkcji, dane = {}) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja_lobby: typAkcji, ...dane }));
    }
}

function wyslijAkcjeGry(akcja) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja: akcja }));
    }
}

/* ==========================================================================
   SEKCJA 4: RENDEROWANIE WIDOKU LOBBY
   ========================================================================== */

function renderujLobby(stan) {
    // ... (bez zmian)
    const lobbyIdGryEl = document.getElementById('lobby-id-gry');
    const druzynaMyEl = document.getElementById('druzyna-my');
    const druzynaOniEl = document.getElementById('druzyna-oni');
    const lobbyAkcjeEl = document.getElementById('lobby-akcje');

    lobbyIdGryEl.textContent = idGry;
    druzynaMyEl.innerHTML = `<h2>Drużyna "${nazwyDruzyn.My}"</h2>`;
    druzynaOniEl.innerHTML = `<h2>Drużyna "${nazwyDruzyn.Oni}"</h2>`;
    lobbyAkcjeEl.innerHTML = '';

    const jestesHostem = stan.host === nazwaGracza;
    stan.slots.forEach(slot => {
        const slotDiv = document.createElement('div');
        slotDiv.className = 'slot-gracza';
        const czyHost = stan.host === slot.nazwa;
        const ikonaHosta = czyHost ? '<span class="crown-icon">👑</span> ' : '';

        if (slot.typ === "pusty") {
            const btn = document.createElement('button');
            btn.textContent = '🪑 Dołącz tutaj';
            btn.onclick = () => wyslijAkcjeLobby('dolacz_do_slota', { slot_id: slot.slot_id });
            slotDiv.appendChild(btn);
            if (jestesHostem) {
                const botBtn = document.createElement('button');
                botBtn.textContent = '🤖 Dodaj Bota';
                botBtn.onclick = (e) => { e.stopPropagation(); wyslijAkcjeLobby('zmien_slot', { slot_id: slot.slot_id, nowy_typ: 'bot' }); };
                slotDiv.appendChild(botBtn);
            }
        } else if (slot.nazwa === nazwaGracza) {
            slotDiv.innerHTML = `${ikonaHosta}<strong>👤 ${slot.nazwa} (Ty)</strong>`;
        } else {
            const ikonaTypu = slot.typ === 'bot' ? '🤖' : '👤';
            slotDiv.innerHTML = `${ikonaHosta}${ikonaTypu} ${slot.nazwa}`;
            if (jestesHostem) {
                const btn = document.createElement('button');
                btn.textContent = 'Wyrzuć';
                btn.onclick = () => wyslijAkcjeLobby('zmien_slot', { slot_id: slot.slot_id, nowy_typ: 'pusty' });
                slotDiv.appendChild(btn);
            }
        }
        (slot.druzyna === 'My' ? druzynaMyEl : druzynaOniEl).appendChild(slotDiv);
    });

    if (jestesHostem) {
        const startBtn = document.createElement('button');
        startBtn.textContent = 'Rozpocznij Grę';
        startBtn.onclick = () => wyslijAkcjeLobby('start_gry');
        const moznaStartowac = stan.slots.every(s => s.typ !== 'pusty');
        startBtn.disabled = !moznaStartowac;
        if (!moznaStartowac) { startBtn.title = 'Wszystkie miejsca muszą być zajęte, aby rozpocząć.'; }
        lobbyAkcjeEl.appendChild(startBtn);
    }
}


/* ==========================================================================
   SEKCJA 5: RENDEROWANIE GŁÓWNEGO WIDOKU GRY
   ========================================================================== */
function aktualizujWidokGry(stanGry) {
    if (stanGry.status_partii === 'ZAKONCZONA') {
        pokazPodsumowanieMeczu(stanGry);
        return;
    }
    if (!stanGry?.rozdanie || !stanGry?.slots) return;

    const rozdanie = stanGry.rozdanie;
    const slotGracza = stanGry.slots.find(s => s.nazwa === nazwaGracza);
    if (!slotGracza) return;
    
    // Ustalanie pozycji graczy
    const partner = stanGry.slots.find(s => s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza);
    const przeciwnicy = stanGry.slots.filter(s => s.druzyna !== slotGracza.druzyna);
    const pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
    const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]));

    // Aktualizacja informacji o graczach
    document.querySelectorAll('.gracz-boczny, #gracz-gora, #gracz-dol').forEach(el => el.classList.remove('aktywny-gracz'));
    for (const [pos, slot] of Object.entries(pozycje)) {
        const kontenerGraczaEl = document.getElementById(`gracz-${pos}`);
        if (kontenerGraczaEl && slot) {
            const czyGrajacy = rozdanie.gracz_grajacy === slot.nazwa;
            const ikonaGrajacego = czyGrajacy ? '<span class="crown-icon">👑</span> ' : '';
            kontenerGraczaEl.querySelector('.info-gracza').innerHTML = `${ikonaGrajacego}${slot.nazwa}`;
            if (rozdanie.kolej_gracza === slot.nazwa) {
                kontenerGraczaEl.classList.add('aktywny-gracz');
            }
        }
    }

    // Aktualizacja paneli informacyjnych
    // ... (reszta kodu bez zmian)
    const nazwaTeam1 = nazwyDruzyn.My;
    const nazwaTeam2 = nazwyDruzyn.Oni;
    const punktyMeczu1 = stanGry.punkty_meczu[nazwaTeam1] || 0;
    const punktyMeczu2 = stanGry.punkty_meczu[nazwaTeam2] || 0;
    const punktyRozdania1 = rozdanie.punkty_w_rozdaniu[nazwaTeam1] || 0;
    const punktyRozdania2 = rozdanie.punkty_w_rozdaniu[nazwaTeam2] || 0;
    const mojaDruzyna = slotGracza.druzyna === 'My' ? nazwaTeam1 : nazwaTeam2;
    const ichDruzyna = slotGracza.druzyna === 'My' ? nazwaTeam2 : nazwaTeam1;
    const mojePunktyMeczu = slotGracza.druzyna === 'My' ? punktyMeczu1 : punktyMeczu2;
    const ichPunktyMeczu = slotGracza.druzyna === 'My' ? punktyMeczu2 : punktyMeczu1;
    const mojePunktyRozdania = slotGracza.druzyna === 'My' ? punktyRozdania1 : punktyRozdania2;
    const ichPunktyRozdania = slotGracza.druzyna === 'My' ? punktyRozdania2 : punktyRozdania1;
    document.getElementById('info-lewy-rog').innerHTML = `<div class="info-box">Wynik: <strong>${mojaDruzyna} ${mojePunktyMeczu} - ${ichPunktyMeczu} ${ichDruzyna}</strong></div>`;
    document.getElementById('info-srodek').innerHTML = `<div class="info-box">Punkty: ${mojaDruzyna} ${mojePunktyRozdania} - ${ichPunktyRozdania} ${ichDruzyna}</div>`;
    document.getElementById('info-prawy-rog').innerHTML = `<div class="info-box">Kontrakt: ${formatujKontrakt(rozdanie.kontrakt)}</div>`;
    const infoStawkaEl = document.getElementById('info-stawka');
    if (rozdanie.aktualna_stawka > 0) {
        infoStawkaEl.innerHTML = `Stawka: <strong>${rozdanie.aktualna_stawka} pkt</strong>`;
        infoStawkaEl.classList.remove('hidden');
    } else {
        infoStawkaEl.classList.add('hidden');
    }


    // Renderowanie ręki głównego gracza z logiką animacji
    const rekaGlownaEl = document.querySelector('#gracz-dol .reka-glowna');
    rekaGlownaEl.innerHTML = '';
    const rekaTwojegoGracza = rozdanie.rece_graczy[nazwaGracza] || [];
    rekaTwojegoGracza.forEach(nazwaKarty => {
        const img = document.createElement('img');
        img.className = 'karta';
        img.src = `/static/karty/${nazwaKarty.replace(' ', '')}.png`;
        if (rozdanie.grywalne_karty.includes(nazwaKarty)) {
            img.classList.add('grywalna');
            img.onclick = (e) => {
                const celEl = document.getElementById('slot-karty-dol');
                animujZagranieKarty(e.target, celEl); // Uruchom animację
                wyslijAkcjeGry({ typ: 'zagraj_karte', karta: nazwaKarty });
            };
        }
        rekaGlownaEl.appendChild(img);
    });

    // Renderowanie rąk pozostałych graczy
    for (const [pos, slot] of Object.entries(pozycje)) {
        if (pos === 'dol' || !slot) continue;
        const rekaEl = document.querySelector(`#gracz-${pos} .reka-${pos === 'gora' ? 'gorna' : 'boczna'}`);
        if (!rekaEl) continue;
        rekaEl.innerHTML = '';
        const iloscKart = (rozdanie.rece_graczy[slot.nazwa] || []).length;
        for (let i = 0; i < iloscKart; i++) {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = '/static/karty/Rewers.png';
            rekaEl.appendChild(img);
        }
    }
    
    // ZMIANA: Renderowanie kart na stole w stałych slotach
    document.querySelectorAll('.slot-karty').forEach(slot => slot.innerHTML = '');
    rozdanie.karty_na_stole.forEach(item => {
        const pozycjaGracza = pozycjeWgNazwy[item.gracz];
        if (pozycjaGracza) {
            const slotEl = document.getElementById(`slot-karty-${pozycjaGracza}`);
            if (slotEl) {
                slotEl.innerHTML = `<img class="karta" src="/static/karty/${item.karta.replace(' ', '')}.png">`;
            }
        }
    });

    // Reszta funkcji bez zmian
    if (rozdanie.kolej_gracza === nazwaGracza && rozdanie.faza !== 'ROZGRYWKA' && rozdanie.mozliwe_akcje.length > 0) {
        renderujPrzyciskiLicytacji(rozdanie.mozliwe_akcje);
    } else {
        document.getElementById('kontener-akcji').innerHTML = '';
    }
    const historiaListaEl = document.getElementById('historia-lista');
    historiaListaEl.innerHTML = '';
    (rozdanie.historia_rozdania || []).forEach(log => {
        const p = document.createElement('p');
        p.innerHTML = formatujWpisHistorii(log);
        historiaListaEl.appendChild(p);
    });
    historiaListaEl.scrollTop = historiaListaEl.scrollHeight;
    if (rozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && rozdanie.podsumowanie) {
        pokazPodsumowanieRozdania(stanGry);
    } else if (stanGry.status_partii === "W_TRAKCIE") {
        modalOverlayEl.classList.add('hidden');
    }
    if (rozdanie.lewa_do_zamkniecia) {
        setTimeout(() => wyslijAkcjeGry({ typ: 'finalizuj_lewe' }), 2000);
    }
    pokazDymekPoOstatniejAkcji(stanGry, pozycje);
}

/* ==========================================================================
   SEKCJA 6: LOGIKA EFEKTÓW (DŹWIĘKI I ANIMACJE)
   ========================================================================== */

function uruchomEfektyWizualne(nowyStan, staryStan) {
    if (!staryStan?.rozdanie || !nowyStan?.rozdanie) return;

    const noweKartyNaStole = nowyStan.rozdanie.karty_na_stole;
    const stareKartyNaStole = staryStan.rozdanie.karty_na_stole;

    // Animacja zagrania karty przez przeciwnika
    if (noweKartyNaStole.length > stareKartyNaStole.length) {
        const nowaKartaZagranie = noweKartyNaStole.find(nk => !stareKartyNaStole.some(sk => sk.karta === nk.karta && sk.gracz === nk.gracz));
        if (nowaKartaZagranie && nowaKartaZagranie.gracz !== nazwaGracza) {
            const slotGracza = nowyStan.slots.find(s => s.nazwa === nazwaGracza);
            const partner = nowyStan.slots.find(s => s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza);
            const przeciwnicy = nowyStan.slots.filter(s => s.druzyna !== slotGracza.druzyna);
            const pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
            const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]));

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

    // Dźwięki
    uruchomEfektyDzwiekowe(nowyStan, staryStan);
}

function animujZagranieKarty(startEl, celEl, nazwaKarty = null) {
    const startRect = startEl.getBoundingClientRect();
    const celRect = celEl.getBoundingClientRect();
    
    const animowanaKarta = document.createElement('img');
    animowanaKarta.className = 'animowana-karta';
    
    // Jeśli nazwaKarty jest podana (dla przeciwników), użyj jej. W przeciwnym razie (dla gracza) użyj źródła klikniętego elementu.
    animowanaKarta.src = nazwaKarty ? `/static/karty/${nazwaKarty.replace(' ', '')}.png` : startEl.src;

    // Pozycja startowa
    animowanaKarta.style.left = `${startRect.left}px`;
    animowanaKarta.style.top = `${startRect.top}px`;
    
    animationOverlayEl.appendChild(animowanaKarta);
    
    // Ukryj oryginalną kartę w ręce, jeśli to animacja gracza
    if (startEl.tagName === 'IMG') {
        startEl.style.visibility = 'hidden';
    }

    // Wymuś reflow, aby przeglądarka zastosowała style początkowe przed animacją
    void animowanaKarta.offsetWidth;

    // Ustaw pozycję końcową, aby uruchomić transition z CSS
    const deltaX = celRect.left - startRect.left;
    const deltaY = celRect.top - startRect.top;
    animowanaKarta.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

    // Usuń animowany element po zakończeniu animacji
    setTimeout(() => {
        animowanaKarta.remove();
        // Jeśli karta była ukryta, przywróć jej widoczność (stan i tak ją usunie)
        if (startEl.style.visibility === 'hidden') {
            startEl.style.visibility = 'visible';
        }
    }, 400); // Czas musi być zgodny z transition w CSS
}

function uruchomEfektyDzwiekowe(nowyStan, staryStan) {
    if (!staryStan || !staryStan.rozdanie || !nowyStan.rozdanie) {
        return; 
    }
    const noweRozdanie = nowyStan.rozdanie;
    const stareRozdanie = staryStan.rozdanie;

    // 1. ZAGRANIE KARTY: Tylko gdy przybywa karta, ale lewa się jeszcze NIE kończy
    if (noweRozdanie.karty_na_stole.length > stareRozdanie.karty_na_stole.length && !noweRozdanie.lewa_do_zamkniecia) {
        odtworzDzwiek('zagranieKarty');
    }

    // 2. WYGRANA LEWA: Gdy flaga `lewa_do_zamkniecia` się pojawia
    if (noweRozdanie.lewa_do_zamkniecia && !stareRozdanie.lewa_do_zamkniecia) {
         odtworzDzwiek('wygranaLewa');
    }
    
    // 3. AKCJA LICYTACYJNA
    if (noweRozdanie.historia_rozdania.length > stareRozdanie.historia_rozdania.length) {
        // --- POCZĄTEK ZMIAN ---
        // Bierzemy tylko nowe logi, które pojawiły się w tej aktualizacji
        const noweLogi = noweRozdanie.historia_rozdania.slice(stareRozdanie.historia_rozdania.length);
        // Sprawdzamy, czy WŚRÓD nowych logów jest akcja licytacyjna
        const logAkcji = noweLogi.find(log => log.typ === 'akcja_licytacyjna');
        
        if (logAkcji) {
            const akcja = logAkcji.akcja;
            if (akcja.typ === 'pas' || akcja.typ === 'pas_lufa') {
                odtworzDzwiek('pas');
            } 
            else if (['deklaracja', 'przebicie', 'lufa', 'kontra', 'zmiana_kontraktu'].includes(akcja.typ)) {
                odtworzDzwiek('licytacja');
            }
        }
        // --- KONIEC ZMIAN ---
    }

    // 4. KONIEC ROZDANIA
    if (noweRozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && stareRozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
        odtworzDzwiek('koniecRozdania');
    }
}


/* ==========================================================================
   SEKCJA 7: FUNKCJE POMOCNICZE I OBSŁUGA ZDARZEŃ
   ========================================================================== */
function formatujKontrakt(kontrakt) {
    // ... (bez zmian)
    if (!kontrakt || !kontrakt.typ) return 'Brak';
    const info = mapowanieKolorow[kontrakt.atut];
    if (kontrakt.typ === 'NORMALNA' && info) {
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span>`;
    }
    if (kontrakt.typ === 'BEZ_PYTANIA' && info) {
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span><span class="znak-zapytania-przekreslony">?</span>`;
    }
    return `<strong>${kontrakt.typ}</strong>`;
}

function pokazPodsumowanieRozdania(stanGry) {
    // ... (bez zmian)
    const podsumowanie = stanGry.rozdanie.podsumowanie;
    const modalPanelEl = document.getElementById('podsumowanie-rozdania');
    const podsumowanieTrescEl = document.getElementById('podsumowanie-tresc');
    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove());
    let bonusInfo = '';
    if (podsumowanie.bonus_z_trzech_kart) {
        bonusInfo += `<p style="color: yellow; font-weight: bold;">Bonus za grę z 3 kart (x2)!</p>`;
    }
    if (podsumowanie.mnoznik_lufy > 1) {
        bonusInfo += `<p style="color: orange; font-weight: bold;">Bonus za lufy (x${podsumowanie.mnoznik_lufy})!</p>`;
    }
    podsumowanieTrescEl.innerHTML = `<p>Rozdanie wygrane przez: <strong>${podsumowanie.wygrana_druzyna}</strong></p>
                                    <p>Zdobyte punkty: <strong>${podsumowanie.przyznane_punkty}</strong></p>
                                    ${bonusInfo}`;
    document.getElementById('podsumowanie-tytul').textContent = 'Koniec Rozdania!';
    const nastepneRozdanieBtn = document.createElement('button');
    modalPanelEl.appendChild(nastepneRozdanieBtn);
    const czyJestesGotowy = stanGry.gracze_gotowi && stanGry.gracze_gotowi.includes(nazwaGracza);
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
    modalOverlayEl.classList.remove('hidden');
}

function pokazPodsumowanieMeczu(stanGry) {
    // ... (bez zmian)
    const tytulEl = document.getElementById('podsumowanie-tytul');
    const trescEl = document.getElementById('podsumowanie-tresc');
    const modalPanelEl = document.getElementById('podsumowanie-rozdania');
    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove());
    const nazwaTeam1 = nazwyDruzyn.My;
    const nazwaTeam2 = nazwyDruzyn.Oni;
    const punkty1 = stanGry.punkty_meczu[nazwaTeam1] || 0;
    const punkty2 = stanGry.punkty_meczu[nazwaTeam2] || 0;
    const zwyciezca = punkty1 >= 66 ? nazwaTeam1 : nazwaTeam2;
    tytulEl.textContent = 'Koniec Meczu!';
    trescEl.innerHTML = `<h2>Wygrała drużyna "${zwyciezca}"!</h2>
                         <p>Wynik końcowy: ${nazwaTeam1} ${punkty1} - ${punkty2} ${nazwaTeam2}</p>`;
    const wyjdzBtn = document.createElement('button');
    wyjdzBtn.textContent = 'Wyjdź do menu';
    wyjdzBtn.onclick = () => { window.location.href = '/'; };
    modalPanelEl.appendChild(wyjdzBtn);
    if (stanGry.tryb_gry === 'online') {
        const lobbyBtn = document.createElement('button');
        if (stanGry.host === nazwaGracza) {
            lobbyBtn.textContent = 'Powrót do lobby';
            lobbyBtn.onclick = () => { wyslijAkcjeGry({ typ: 'powrot_do_lobby' }); };
        } else {
            lobbyBtn.textContent = 'Oczekiwanie na hosta...';
            lobbyBtn.disabled = true;
        }
        modalPanelEl.appendChild(lobbyBtn);
    }
    modalOverlayEl.classList.remove('hidden');
}

function formatujWpisHistorii(log) {
    // ... (bez zmian)
    const gracz = `<strong>${log.gracz}</strong>`;
    switch (log.typ) {
        case 'akcja_licytacyjna': {
            const akcja = log.akcja;
            if (akcja.typ === 'pas' || akcja.typ === 'pas_lufa') return `${gracz} pasuje.`;
            if (akcja.typ === 'deklaracja') {
                const kontraktObj = { typ: akcja.kontrakt, atut: akcja.atut };
                return `${gracz} licytuje: ${formatujKontrakt(kontraktObj)}`;
            }
            if (akcja.typ === 'zmiana_kontraktu') {
                return `${gracz} zmienia kontrakt na: <strong>${akcja.kontrakt}</strong>.`;
            }
            return `${gracz} wykonuje akcję: ${akcja.typ}.`;
        }
        case 'zagranie_karty':
            return `${gracz} zagrał ${log.karta}.`;
        case 'koniec_lewy':
            return `Lewę wygrywa <strong>${log.zwyciezca}</strong> (zdobywając ${log.punkty} pkt).`;
        case 'meldunek':
            return `${gracz} melduje parę za ${log.punkty} pkt.`;
        case 'bonus':
            return `Bonus za grę <strong>${gracz}</strong> z 3 kart.`;
        default:
            const tresc = JSON.stringify(log);
            return `[${log.typ}] ${tresc.substring(0, 50)}`;
    }
}

function pokazDymekPoOstatniejAkcji(stanGry, pozycje) {
    // ... (bez zmian)
    const historia = stanGry.rozdanie.historia_rozdania || [];
    const nowaDlugosc = historia.length;
    if (nowaDlugosc === ostatniaDlugoscHistorii) {
        return;
    }
    const noweLogi = historia.slice(ostatniaDlugoscHistorii);
    let logDoWyswietlenia = null;
    for (let i = noweLogi.length - 1; i >= 0; i--) {
        const log = noweLogi[i];
        if (log.typ === 'akcja_licytacyjna' || log.typ === 'meldunek') {
            logDoWyswietlenia = log;
            break;
        }
    }
    if (!logDoWyswietlenia) {
        ostatniaDlugoscHistorii = nowaDlugosc;
        return;
    }
    const pozycjaGracza = Object.keys(pozycje).find(p => pozycje[p] && pozycje[p].nazwa === logDoWyswietlenia.gracz);
    if (!pozycjaGracza) {
        ostatniaDlugoscHistorii = nowaDlugosc;
        return;
    }
    let tekstDymka = '';
    if (logDoWyswietlenia.typ === 'akcja_licytacyjna') {
        const akcja = logDoWyswietlenia.akcja;
        switch (akcja.typ) {
            case 'deklaracja':
                tekstDymka = formatujKontrakt({ typ: akcja.kontrakt, atut: akcja.atut });
                break;
            case 'zmiana_kontraktu':
                tekstDymka = `Zmieniam na: <strong>${akcja.kontrakt}</strong>`;
                break;
            case 'przebicie':
                tekstDymka = `Przebijam: ${akcja.kontrakt}!`;
                break;
            case 'pas':
            case 'pas_lufa':
                tekstDymka = 'Pas';
                break;
            case 'do_konca':
                tekstDymka = 'Do końca!';
                break;
            default:
                tekstDymka = akcja.typ.charAt(0).toUpperCase() + akcja.typ.slice(1);
                break;
        }
    } else if (logDoWyswietlenia.typ === 'meldunek') {
        tekstDymka = `Para (${logDoWyswietlenia.punkty} pkt)!`;
    }
    if (tekstDymka) {
        pokazDymekAkcji(pozycjaGracza, tekstDymka);
    }
    ostatniaDlugoscHistorii = nowaDlugosc;
}

function pokazDymekAkcji(pozycja, tekst) {
    // ... (bez zmian)
    const kontenerGracza = document.getElementById(`gracz-${pozycja}`);
    if (!kontenerGracza) return;
    const staryDymek = kontenerGracza.querySelector('.dymek-akcji');
    if (staryDymek) staryDymek.remove();
    const dymek = document.createElement('div');
    dymek.className = 'dymek-akcji';
    dymek.innerHTML = tekst;
    kontenerGracza.appendChild(dymek);
    setTimeout(() => dymek.remove(), 4000);
}

function renderujPrzyciskiLicytacji(akcje) {
    // ... (bez zmian)
    const kontener = document.getElementById('kontener-akcji');
    kontener.innerHTML = '';
    const grupy = akcje.reduce((acc, akcja) => {
        const klucz = akcja.kontrakt || akcja.typ;
        if (!acc[klucz]) acc[klucz] = [];
        acc[klucz].push(akcja);
        return acc;
    }, {});
    for (const [nazwaGrupy, akcjeWGrupie] of Object.entries(grupy)) {
        const btn = document.createElement('button');
        btn.textContent = nazwaGrupy;
        if (akcjeWGrupie.length === 1 && !akcjeWGrupie[0].atut) {
            btn.onclick = () => wyslijAkcjeGry(akcjeWGrupie[0]);
        } else {
            btn.onclick = () => {
                kontener.innerHTML = '';
                akcjeWGrupie.forEach(akcjaKoloru => {
                    const kolorBtn = document.createElement('button');
                    const info = mapowanieKolorow[akcjaKoloru.atut];
                    kolorBtn.innerHTML = `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span> ${akcjaKoloru.atut}`;
                    kolorBtn.onclick = () => wyslijAkcjeGry(akcjaKoloru);
                    kontener.appendChild(kolorBtn);
                });
            };
        }
        kontener.appendChild(btn);
    }
}

/* ==========================================================================
   SEKCJA 8: OBSŁUGA CZATU
   ========================================================================== */
function wyslijWiadomoscCzat() {
    // ... (bez zmian)
    const wiadomosc = czatInputEl.value.trim();
    if (wiadomosc && socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            gracz: nazwaGracza,
            typ_wiadomosci: 'czat',
            tresc: wiadomosc
        }));
        czatInputEl.value = '';
    }
}

function dodajWiadomoscDoCzatu(gracz, tresc) {
    // ... (bez zmian)
    const p = document.createElement('p');
    p.innerHTML = `<strong>${gracz}:</strong> ${tresc.replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
    czatWiadomosciEl.appendChild(p);
    czatWiadomosciEl.scrollTop = czatWiadomosciEl.scrollHeight;
    if (gracz !== nazwaGracza) {
        odtworzDzwiek('wiadomoscCzat');
    }
}

czatWyslijBtn.onclick = wyslijWiadomoscCzat;
czatInputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') wyslijWiadomoscCzat();
});