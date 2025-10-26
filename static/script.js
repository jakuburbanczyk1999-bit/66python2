/* ==========================================================================
   SEKCJA 1: DEKLARACJE GLOBALNE I POBIERANIE ELEMENTÓW DOM
   ========================================================================== */

// --- Zmienne globalne stanu gry ---
let idGry = null;
let nazwaGracza = null;
let socket = null;
let mojSlotId = null;
let nazwyDruzyn = { My: "My", Oni: "Oni" };
let ostatniStanGry = {}; // Przechowuje poprzedni stan gry do porównań (np. dla efektów)

// --- Elementy DOM (przypisywane w inicjalizujElementyDOM) ---
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

// --- Konfiguracja ---
const mapowanieKolorow = { // Mapowanie nazw kolorów na symbole i klasy CSS
    'CZERWIEN': { symbol: '♥', klasa: 'kolor-czerwien' },
    'DZWONEK':  { symbol: '♦', klasa: 'kolor-dzwonek' },
    'ZOLADZ':   { symbol: '♣', klasa: 'kolor-zoladz' },
    'WINO':     { symbol: '♠', klasa: 'kolor-wino' }
};

/* ==========================================================================
   SEKCJA 2: ZARZĄDZANIE DŹWIĘKAMI
   ========================================================================== */
const dzwieki = { // Obiekty Audio dla różnych zdarzeń w grze
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
        dzwiek.currentTime = 0; // Resetuj dźwięk, aby można go było odtworzyć ponownie szybko
        dzwiek.play().catch(error => console.log(`Nie można odtworzyć dźwięku "${nazwaDzwieku}": ${error}`));
    }
}

/* ==========================================================================
   SEKCJA 3: GŁÓWNA LOGIKA APLIKACJI (INICJALIZACJA I WEBSOCKET)
   ========================================================================== */

// Uruchamia inicjalizację po załadowaniu struktury HTML
document.addEventListener('DOMContentLoaded', () => {
    inicjalizujElementyDOM(); // Pobierz referencje do elementów HTML i ustaw nasłuchiwacze
    const params = new URLSearchParams(window.location.search);
    idGry = params.get('id');
    nazwaGracza = sessionStorage.getItem('nazwaGracza') || `Gracz${Math.floor(Math.random() * 1000)}`;
    sessionStorage.setItem('nazwaGracza', nazwaGracza); // Zapisz nazwę (lub wygenerowaną)
    inicjalizujUstawieniaUI(); // Wczytaj zapisane ustawienia interfejsu (np. ukryte panele)

    if (idGry) {
        inicjalizujWebSocket(); // Jeśli mamy ID gry, połącz się z serwerem
    } else {
        // Jeśli jesteśmy na gra.html bez ID, wróć do strony startowej
        if (window.location.pathname.includes('gra.html')) {
             window.location.href = "/";
        }
    }
});

/**
 * Pobiera referencje do wszystkich potrzebnych elementów DOM
 * i ustawia globalne nasłuchiwacze zdarzeń (np. dla przycisków ustawień, czatu).
 */
function inicjalizujElementyDOM() {
    // Przypisanie elementów
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

    // Przypisanie event listenerów
    // Sprawdzamy, czy elementy istnieją, zanim dodamy listenery
    if (czatWyslijBtn) {
        czatWyslijBtn.onclick = wyslijWiadomoscCzat;
    }
    if (czatInputEl) {
        czatInputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') wyslijWiadomoscCzat();
        });
    }

    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            pokazModal(settingsModalEl);
        });
    }

    if (settingsCloseBtn) {
        settingsCloseBtn.addEventListener('click', () => {
            ukryjModal();
        });
    }

    if (modalOverlayEl) {
        modalOverlayEl.addEventListener('click', (e) => {
            // Zamykanie modala ustawień po kliknięciu w tło
            if (e.target === modalOverlayEl) {
                if (settingsModalEl && !settingsModalEl.classList.contains('hidden')) {
                    ukryjModal();
                }
            }
        });
    }

    // Listenery dla checkboxów w ustawieniach
    if (settingUkryjCzat) {
        settingUkryjCzat.addEventListener('change', (e) => {
            const jestZaznaczone = e.target.checked;
            if (ekranGryEl) {
                ekranGryEl.classList.toggle('czat-ukryty', jestZaznaczone);
                aktualizujUkrycieLewejKolumny(); // Sprawdź, czy ukryć całą lewą kolumnę
            }
            localStorage.setItem('czatUkryty', jestZaznaczone); // Zapisz wybór
        });
    }

    if (settingUkryjHistorie) {
        settingUkryjHistorie.addEventListener('change', (e) => {
            const jestZaznaczone = e.target.checked;
            if (ekranGryEl) ekranGryEl.classList.toggle('historia-ukryta', jestZaznaczone);
            localStorage.setItem('historiaUkryta', jestZaznaczone); // Zapisz wybór
        });
    }
    if (settingUkryjHistoriePartii) {
        settingUkryjHistoriePartii.addEventListener('change', (e) => {
            const jestZaznaczone = e.target.checked;
            if (ekranGryEl) {
                ekranGryEl.classList.toggle('partia-historia-ukryta', jestZaznaczone);
                aktualizujUkrycieLewejKolumny(); // Sprawdź, czy ukryć całą lewą kolumnę
            }
            localStorage.setItem('partiaHistoriaUkryta', jestZaznaczone); // Zapisz wybór
        });
    }
}

/**
 * Sprawdza, czy oba lewe panele (historia partii i czat) są ukryte
 * i dodaje/usuwa klasę 'lewa-kolumna-ukryta' do głównego kontenera gry,
 * co pozwala CSS ukryć całą lewą kolumnę siatki.
 */
function aktualizujUkrycieLewejKolumny() {
    if (!ekranGryEl) return;
    const czatUkryty = ekranGryEl.classList.contains('czat-ukryty');
    const partiaHistoriaUkryta = ekranGryEl.classList.contains('partia-historia-ukryta');

    // Klasa 'lewa-kolumna-ukryta' jest zdefiniowana w CSS
    ekranGryEl.classList.toggle('lewa-kolumna-ukryta', czatUkryty && partiaHistoriaUkryta);
}

/**
 * Wczytuje zapisane w localStorage ustawienia interfejsu użytkownika
 * (np. które panele były ukryte) i stosuje je do widoku.
 */
function inicjalizujUstawieniaUI() {
    // Wczytaj stan ukrycia czatu
    if (ekranGryEl && settingUkryjCzat) {
        const czatUkryty = localStorage.getItem('czatUkryty') === 'true';
        if (czatUkryty) {
            ekranGryEl.classList.add('czat-ukryty');
        }
        settingUkryjCzat.checked = czatUkryty;
    }

    // Wczytaj stan ukrycia historii rozdania (prawa kolumna)
    if (ekranGryEl && settingUkryjHistorie) {
        const historiaUkryta = localStorage.getItem('historiaUkryta') === 'true';
        if (historiaUkryta) {
            ekranGryEl.classList.add('historia-ukryta');
        }
        settingUkryjHistorie.checked = historiaUkryta;
    }

    // Wczytaj stan ukrycia historii partii (lewa górna)
    if (ekranGryEl && settingUkryjHistoriePartii) {
        const partiaHistoriaUkryta = localStorage.getItem('partiaHistoriaUkryta') === 'true';
        if (partiaHistoriaUkryta) {
            ekranGryEl.classList.add('partia-historia-ukryta');
        }
        settingUkryjHistoriePartii.checked = partiaHistoriaUkryta;
    }
    // Zaktualizuj stan ukrycia całej lewej kolumny przy ładowaniu
    aktualizujUkrycieLewejKolumny();
}


/**
 * Nawiązuje połączenie WebSocket z serwerem gry
 * i ustawia obsługę przychodzących wiadomości.
 */
function inicjalizujWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const haslo = sessionStorage.getItem('lobbyHaslo') || '';
    const wsUrl = `${protocol}//${window.location.host}/ws/${idGry}/${nazwaGracza}?haslo=${encodeURIComponent(haslo)}`;
    socket = new WebSocket(wsUrl);

    // Główna funkcja obsługująca wiadomości od serwera
    socket.onmessage = function(event) {
        const stan = JSON.parse(event.data); // Parsuj JSON otrzymany od serwera

        // Obsługa wiadomości czatu
        if (stan.typ_wiadomosci === 'czat') {
            dodajWiadomoscDoCzatu(stan.gracz, stan.tresc);
            return; // Zakończ obsługę tej wiadomości
        }

        // Aktualizacja nazw drużyn, jeśli serwer je przysłał
        if (stan.nazwy_druzyn) {
            nazwyDruzyn = stan.nazwy_druzyn;
        }

        // Zsynchronizuj ID slotu gracza
        synchronizujDaneGracza(stan);

        // Uruchom efekty wizualne i dźwiękowe porównując NOWY stan ze STARYM
        if (stan.status_partii !== "LOBBY") {
            // Przekazujemy kopie obiektów stanu, aby uniknąć problemów z referencjami
            uruchomEfektyWizualne(stan, ostatniStanGry);
        }

        // Przełącz widok między lobby a grą i zaktualizuj odpowiedni widok
        if (stan.status_partii === "LOBBY") {
            if (ekranGryEl) ekranGryEl.classList.add('hidden');
            if (ekranLobbyEl) ekranLobbyEl.classList.remove('hidden');
            if (modalOverlayEl) modalOverlayEl.classList.add('hidden'); // Ukryj modale
            renderujLobby(stan);
        } else { // Status W_TRAKCIE lub ZAKONCZONA
            if (ekranLobbyEl) ekranLobbyEl.classList.add('hidden');
            if (ekranGryEl) ekranGryEl.classList.remove('hidden');
            aktualizujWidokGry(stan); // Ta funkcja pokaże też podsumowanie meczu i dymki
        }

        // Zapisz obecny stan jako "ostatni" na potrzeby następnej aktualizacji
        // Ważne: Tworzymy głęboką kopię, aby uniknąć modyfikacji poprzedniego stanu przez referencję
        ostatniStanGry = JSON.parse(JSON.stringify(stan));
    };

    // Obsługa zamknięcia połączenia
    socket.onclose = (event) => {
        console.log("Połączenie WebSocket zamknięte.", event.reason);
        // Jeśli jest powód zamknięcia (np. błąd serwera), pokaż go i wróć do menu
        if (event.reason) {
            // Sprawdź, czy powodem jest błędne hasło
            if (event.reason === "Nieprawidłowe hasło.") {
                alert("Nieprawidłowe hasło."); // Poinformuj użytkownika
                window.location.href = "/lobby.html"; // Wróć do listy lobby
            } else {
                // Dla innych błędów (np. "Gra nie istnieje", "Lobby jest pełne")
                alert(event.reason);
                window.location.href = "/"; // Wróć do menu głównego
            }
        }
    };

    // Obsługa błędów połączenia
    socket.onerror = (error) => console.error("Błąd WebSocket:", error);
}

/**
 * Aktualizuje globalną zmienną `mojSlotId` na podstawie danych ze stanu gry.
 */
function synchronizujDaneGracza(stan) {
    if (!stan.slots) return;
    const mojObecnySlot = stan.slots.find(s => s.nazwa === nazwaGracza);
    if (mojObecnySlot) { mojSlotId = mojObecnySlot.slot_id; }
}

/**
 * Wysyła akcję gracza dotyczącą lobby (np. dołączenie do slotu, start gry).
 */
function wyslijAkcjeLobby(typAkcji, dane = {}) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja_lobby: typAkcji, ...dane }));
    }
}

/**
 * Wysyła akcję gracza podczas gry (np. zagranie karty, licytacja, przejście do następnego rozdania).
 */
function wyslijAkcjeGry(akcja) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ gracz: nazwaGracza, akcja: akcja }));
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
        const ikonaTypu = slot.typ === 'bot' ? '🤖' : '👤';
        slotDiv.innerHTML = `${ikonaHosta}${ikonaTypu} ${slot.nazwa}`;
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
        // UPROSZCZONY WARUNEK: Pokaż pasek ZAWSZE, gdy ocenaSilnika ma wartość.
        const czyPokazacPasek = (ocenaSilnika !== null && ocenaSilnika !== undefined);

        if (ekranGryEl) {
             ekranGryEl.classList.toggle('brak-oceny', !czyPokazacPasek);
        }

        if (czyPokazacPasek) {
            // Przekształć ocenę [-1.0, 1.0] na procent [0, 100]
            const procentWygranej = Math.max(0, Math.min(100, (ocenaSilnika + 1.0) / 2.0 * 100.0)); // Dodano Math.max/min dla pewności
            pasekWartoscEl.style.width = `${procentWygranej}%`;
        } else {
            // Jeśli nie ma oceny LUB jest 0 (co może się zdarzyć), ustaw na 50%
             pasekWartoscEl.style.width = '50%';
        }
    }

    // --- Ustal pozycje graczy na ekranie (dol, gora, lewy, prawy) ---
    let pozycje = {}; // Obiekt mapujący pozycję na slot gracza
    if (stanGry.max_graczy === 3) {
        const inniGracze = stanGry.slots.filter(s => s.nazwa !== nazwaGracza);
        // W trybie 3-osobowym nie ma gracza "gora"
        pozycje = { dol: slotGracza, lewy: inniGracze[0], prawy: inniGracze[1] };
    } else { // 4 graczy
        const partner = stanGry.slots.find(s => s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza);
        const przeciwnicy = stanGry.slots.filter(s => s.druzyna !== slotGracza.druzyna);
        pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
    }
    // Odwrócona mapa: nazwa gracza -> pozycja na ekranie (przydatne do umieszczania kart na stole)
    const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]));

    // --- Aktualizacja informacji o graczach (nazwy, podświetlenie tury) ---
    document.querySelectorAll('.gracz-boczny, #gracz-gora, #gracz-dol').forEach(el => {
        if(el) el.classList.remove('aktywny-gracz');
    });
    for (const [pos, slot] of Object.entries(pozycje)) {
        const kontenerGraczaEl = document.getElementById(`gracz-${pos}`);
        if (kontenerGraczaEl && slot) {
            const czyGrajacy = rozdanie.gracz_grajacy === slot.nazwa; // Czy ten gracz jest rozgrywającym w tym rozdaniu?
            const ikonaGrajacego = czyGrajacy ? '<span class="crown-icon">👑</span> ' : '';
            const infoGraczaEl = kontenerGraczaEl.querySelector('.info-gracza');
            if (infoGraczaEl) infoGraczaEl.innerHTML = `${ikonaGrajacego}${slot.nazwa}`;
            // Podświetl gracza, którego jest aktualnie tura
            if (rozdanie.kolej_gracza === slot.nazwa) {
                kontenerGraczaEl.classList.add('aktywny-gracz');
            }
        }
    }

    // --- Aktualizacja górnych paneli informacyjnych ---
    const kontraktTyp = rozdanie.kontrakt?.typ; // Jaki jest aktualny kontrakt?
    const infoSrodekEl = document.getElementById('info-srodek');
    const infoLewyRogEl = document.getElementById('info-lewy-rog');
    const infoPrawyRogEl = document.getElementById('info-prawy-rog');
    const infoStawkaEl = document.getElementById('info-stawka');

    if (stanGry.max_graczy === 3) { // Tryb 3-osobowy
        // Wyświetl wynik meczu dla każdego gracza
        const wynikHtml = Object.entries(stanGry.punkty_meczu)
            .map(([nazwa, pkt]) => `<strong>${nazwa}:</strong> ${pkt}`)
            .join(' / ');
        if (infoLewyRogEl) infoLewyRogEl.innerHTML = `<div class="info-box">Wynik: ${wynikHtml}</div>`;

        // Wyświetl punkty w rozdaniu lub pozostałe lewy
        let srodekHtml = '';
        if (kontraktTyp === 'LEPSZA' || kontraktTyp === 'GORSZA') { // Gry solo
            const iloscLew = rozdanie.rece_graczy[nazwaGracza]?.length || 0;
            srodekHtml = `Pozostało lew: <strong>${iloscLew}</strong>`;
        } else if (kontraktTyp === 'BEZ_PYTANIA' && rozdanie.gracz_grajacy) { // Gra solo "Bez Pytania"
            const pktGrajacego = rozdanie.punkty_w_rozdaniu[rozdanie.gracz_grajacy] || 0;
            srodekHtml = `Punkty 👑 ${rozdanie.gracz_grajacy}: <strong>${pktGrajacego}</strong>`;
        } else { // Normalna gra lub faza licytacji
            let punktyHtml = Object.entries(rozdanie.punkty_w_rozdaniu)
                .map(([nazwa, pkt]) => {
                    const ikona = (nazwa === rozdanie.gracz_grajacy) ? '👑 ' : '';
                    return `${ikona}${nazwa.substring(0, 8)}: ${pkt}`; // Skróć nicki, jeśli są długie
                })
                .join(' / ');
            srodekHtml = `Punkty: ${punktyHtml}`;
        }
        if (infoSrodekEl) infoSrodekEl.innerHTML = `<div class="info-box">${srodekHtml}</div>`;

    } else { // Tryb 4-osobowy
        // Wyświetl wynik meczu dla drużyn
        const nazwaTeam1 = nazwyDruzyn.My;
        const nazwaTeam2 = nazwyDruzyn.Oni;
        const mojePunktyMeczu = stanGry.punkty_meczu[slotGracza.druzyna === 'My' ? nazwaTeam1 : nazwaTeam2] || 0;
        const ichPunktyMeczu = stanGry.punkty_meczu[slotGracza.druzyna === 'My' ? nazwaTeam2 : nazwaTeam1] || 0;
        if (infoLewyRogEl) infoLewyRogEl.innerHTML = `<div class="info-box">Wynik: <strong>My ${mojePunktyMeczu} - ${ichPunktyMeczu} Oni</strong></div>`;

        // Wyświetl punkty w rozdaniu lub pozostałe lewy
        let srodekHtml = '';
        if (kontraktTyp === 'LEPSZA' || kontraktTyp === 'GORSZA') { // Gry solo
            const iloscLew = rozdanie.rece_graczy[nazwaGracza]?.length || 0;
            srodekHtml = `Pozostało lew: <strong>${iloscLew}</strong>`;
        } else if (kontraktTyp === 'BEZ_PYTANIA' && rozdanie.gracz_grajacy) { // Gra solo "Bez Pytania"
            const grajacySlot = stanGry.slots.find(s => s.nazwa === rozdanie.gracz_grajacy);
            const druzynaGrajacego = grajacySlot?.druzyna; // Dodano ?. dla bezpieczeństwa
            const nazwaDruzynyGrajacego = nazwyDruzyn[druzynaGrajacego] || 'Błąd';
            const pktGrajacego = rozdanie.punkty_w_rozdaniu[nazwaDruzynyGrajacego] || 0;
            srodekHtml = `Punkty 👑 ${rozdanie.gracz_grajacy}: <strong>${pktGrajacego}</strong>`;
        } else { // Normalna gra lub faza licytacji
            const mojePunktyRozdania = rozdanie.punkty_w_rozdaniu[slotGracza.druzyna === 'My' ? nazwaTeam1 : nazwaTeam2] || 0;
            const ichPunktyRozdania = rozdanie.punkty_w_rozdaniu[slotGracza.druzyna === 'My' ? nazwaTeam2 : nazwaTeam1] || 0;
            srodekHtml = `Punkty: My ${mojePunktyRozdania} - ${ichPunktyRozdania} Oni`;
        }
        if (infoSrodekEl) infoSrodekEl.innerHTML = `<div class="info-box">${srodekHtml}</div>`;
    }

    // Wyświetl aktualny kontrakt i stawkę rozdania
    const kontenerPrawy = document.getElementById('kontener-info-prawy-rog'); // Znajdź główny kontener
    if (kontenerPrawy) {
        // Wyczyść tylko elementy info, zachowaj przycisk ustawień
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
        rekaGlownaEl.innerHTML = ''; // Wyczyść stare karty
        const rekaTwojegoGracza = rozdanie.rece_graczy[nazwaGracza] || [];
        rekaTwojegoGracza.forEach(nazwaKarty => {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = `/static/karty/${nazwaKarty.replace(' ', '')}.png`; // Ścieżka do obrazka karty
            // Jeśli karta jest grywalna, dodaj klasę i obsługę kliknięcia
            if (rozdanie.grywalne_karty.includes(nazwaKarty)) {
                img.classList.add('grywalna');
                img.onclick = (e) => {
                    const celEl = document.getElementById('slot-karty-dol');
                    if (celEl) animujZagranieKarty(e.target, celEl); // Uruchom animację
                    wyslijAkcjeGry({ typ: 'zagraj_karte', karta: nazwaKarty }); // Wyślij akcję do serwera
                };
            }
            rekaGlownaEl.appendChild(img);
        });
    }

    // --- Renderowanie rewersów kart dla pozostałych graczy ---
    for (const [pos, slot] of Object.entries(pozycje)) {
        if (pos === 'dol' || !slot) continue; // Pomiń gracza dolnego i puste sloty
        const rekaEl = document.querySelector(`#gracz-${pos} .reka-${pos === 'gora' ? 'gorna' : 'boczna'}`);
        if (!rekaEl) continue;
        rekaEl.innerHTML = ''; // Wyczyść stare rewersy
        const iloscKart = (rozdanie.rece_graczy[slot.nazwa] || []).length;
        // Dodaj odpowiednią liczbę rewersów
        for (let i = 0; i < iloscKart; i++) {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = '/static/karty/Rewers.png';
            rekaEl.appendChild(img);
        }
    }

    // --- Renderowanie kart zagranych na stół ---
    document.querySelectorAll('.slot-karty').forEach(slot => {
         if(slot) slot.innerHTML = ''; // Wyczyść stół
    });
    rozdanie.karty_na_stole.forEach(item => {
        const pozycjaGracza = pozycjeWgNazwy[item.gracz]; // Znajdź pozycję gracza, który zagrał kartę
        if (pozycjaGracza) {
            const slotEl = document.getElementById(`slot-karty-${pozycjaGracza}`);
            // Wyświetl kartę w odpowiednim slocie na stole
            if (slotEl) {
                slotEl.innerHTML = `<img class="karta" src="/static/karty/${item.karta.replace(' ', '')}.png">`;
            }
        }
    });

    // --- Renderowanie przycisków akcji (licytacja) ---
    const kontenerAkcjiEl = document.getElementById('kontener-akcji');
    if (kontenerAkcjiEl) {
        // Pokaż przyciski tylko, gdy jest tura gracza, nie jest to faza rozgrywki i są dostępne akcje
        if (rozdanie.kolej_gracza === nazwaGracza && rozdanie.faza !== 'ROZGRYWKA' && rozdanie.mozliwe_akcje.length > 0) {
            renderujPrzyciskiLicytacji(rozdanie.mozliwe_akcje);
        } else {
            kontenerAkcjiEl.innerHTML = ''; // Ukryj przyciski
        }
    }

    // --- Renderowanie historii rozdania (prawa kolumna) ---
    const historiaListaEl = document.getElementById('historia-lista');
    if (historiaListaEl) {
        historiaListaEl.innerHTML = ''; // Wyczyść starą historię
        (rozdanie.historia_rozdania || []).forEach(log => {
            const p = document.createElement('p');
            p.innerHTML = formatujWpisHistorii(log); // Formatuj wpis na czytelny tekst
            historiaListaEl.appendChild(p);
        });
        historiaListaEl.scrollTop = historiaListaEl.scrollHeight; // Przewiń na dół
    }

    // --- Pokaż podsumowanie rozdania, jeśli jest dostępne ---
    if (rozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && rozdanie.podsumowanie) {
        pokazPodsumowanieRozdania(stanGry);
    }
    else if (podsumowanieRozdaniaEl && !podsumowanieRozdaniaEl.classList.contains('hidden')) {
         // Ukryj tylko modal podsumowania, niekoniecznie cały overlay (np. jeśli ustawienia są otwarte)
         podsumowanieRozdaniaEl.classList.add('hidden');
         // Jeśli w overlay'u nie ma już żadnych widocznych paneli, ukryj go
         if (modalOverlayEl && !modalOverlayEl.querySelector('.panel:not(.hidden)')) {
             modalOverlayEl.classList.add('hidden');
         }
         console.log("DEBUG: Ukryto modal podsumowania rozdania, bo faza gry to:", rozdanie.faza); // Log
    }

    // --- Jeśli lewa ma być zamknięta, wyślij akcję finalizacji po chwili ---
    if (rozdanie.lewa_do_zamkniecia) {
        setTimeout(() => wyslijAkcjeGry({ typ: 'finalizuj_lewe' }), 2000); // Czekaj 2 sekundy
    }

    // --- Renderowanie historii partii (lewa górna kolumna) ---
    if (partiaHistoriaListaEl) {
        partiaHistoriaListaEl.innerHTML = ''; // Wyczyść starą historię partii
        (stanGry.historia_partii || []).forEach(wpis => {
            const p = document.createElement('p');
            p.textContent = wpis; // Wyświetl sformatowany wpis z backendu
            partiaHistoriaListaEl.appendChild(p);
        });
        // Przewiń na dół, jeśli jest nowa zawartość
        if (stanGry.historia_partii && stanGry.historia_partii.length > 0) {
             partiaHistoriaListaEl.scrollTop = partiaHistoriaListaEl.scrollHeight;
        }
    }

    // Pokaż dymek z ostatnią akcją licytacyjną lub meldunkiem
    // Musi być wywołane PO zrenderowaniu graczy
    pokazDymekPoOstatniejAkcji(stanGry, pozycje);
}

/* ==========================================================================
   SEKCJA 6: LOGIKA EFEKTÓW (DŹWIĘKI I ANIMACJE)
   ========================================================================== */
/**
 * Uruchamia efekty wizualne (animacje) i dźwiękowe na podstawie różnic
 * między nowym a starym stanem gry.
 */
function uruchomEfektyWizualne(nowyStan, staryStan) {
    // Podstawowe zabezpieczenie, jeśli któryś stan lub rozdanie nie istnieje
    if (!staryStan?.rozdanie || !nowyStan?.rozdanie) {
        console.log("Brak danych do porównania efektów", {nowyStan, staryStan});
        return;
    }

    const noweRozdanie = nowyStan.rozdanie;
    const stareRozdanie = staryStan.rozdanie;
    const noweKartyNaStole = noweRozdanie.karty_na_stole || [];
    const stareKartyNaStole = stareRozdanie.karty_na_stole || [];

    // --- Animacja zagrania karty przez innego gracza ---
    if (noweKartyNaStole.length > stareKartyNaStole.length) {
        // Znajdź nowo zagraną kartę porównując obie listy
        const nowaKartaZagranie = noweKartyNaStole.find(nk =>
            !stareKartyNaStole.some(sk => sk.karta === nk.karta && sk.gracz === nk.gracz)
        );

        // Jeśli znaleziono nową kartę i nie została zagrana przez nas
        if (nowaKartaZagranie && nowaKartaZagranie.gracz !== nazwaGracza) {
             let pozycje = {}; // Ustal pozycje graczy na ekranie
             const slotGracza = nowyStan.slots.find(s => s.nazwa === nazwaGracza);
            if (!slotGracza) return; // Zabezpieczenie

            if (nowyStan.max_graczy === 3) {
                const inniGracze = nowyStan.slots.filter(s => s.nazwa !== nazwaGracza);
                pozycje = { dol: slotGracza, lewy: inniGracze[0], prawy: inniGracze[1] };
            } else {
                const partner = nowyStan.slots.find(s => s.druzyna === slotGracza.druzyna && s.nazwa !== nazwaGracza);
                const przeciwnicy = nowyStan.slots.filter(s => s.druzyna !== slotGracza.druzyna);
                pozycje = { dol: slotGracza, gora: partner, lewy: przeciwnicy[0], prawy: przeciwnicy[1] };
            }
            // Odwrócona mapa: nazwa -> pozycja
            const pozycjeWgNazwy = Object.fromEntries(Object.entries(pozycje).map(([pos, slot]) => [slot?.nazwa, pos]));

            const pozycjaGracza = pozycjeWgNazwy[nowaKartaZagranie.gracz]; // Znajdź pozycję gracza, który zagrał
            if (pozycjaGracza) {
                // Element startowy animacji (nick gracza)
                const startEl = document.querySelector(`#gracz-${pozycjaGracza} .info-gracza`);
                // Element docelowy (slot karty na stole)
                const celEl = document.getElementById(`slot-karty-${pozycjaGracza}`);
                if (startEl && celEl) {
                    // Uruchom animację
                    animujZagranieKarty(startEl, celEl, nowaKartaZagranie.karta);
                }
            }
        }
    }
    // Uruchom efekty dźwiękowe
    uruchomEfektyDzwiekowe(nowyStan, staryStan);
}

/**
 * Tworzy i animuje element karty lecącej od gracza na stół.
 */
function animujZagranieKarty(startEl, celEl, nazwaKarty = null) {
    const startRect = startEl.getBoundingClientRect(); // Pozycja startowa
    const celRect = celEl.getBoundingClientRect();   // Pozycja docelowa

    const animowanaKarta = document.createElement('img');
    animowanaKarta.className = 'animowana-karta';
    // Użyj obrazka karty, jeśli podano, inaczej użyj obrazka elementu startowego (dla gracza dolnego)
    animowanaKarta.src = nazwaKarty ? `/static/karty/${nazwaKarty.replace(' ', '')}.png` : startEl.src;
    animowanaKarta.style.left = `${startRect.left}px`;
    animowanaKarta.style.top = `${startRect.top}px`;

    // Dodaj kartę do warstwy animacji
    if (animationOverlayEl) animationOverlayEl.appendChild(animowanaKarta);

    // Jeśli animacja startuje z karty gracza (IMG), ukryj ją na czas animacji
    if (startEl.tagName === 'IMG') {
        startEl.style.visibility = 'hidden';
    }

    // Wymuszenie reflow - potrzebne, aby animacja zadziałała od razu
    void animowanaKarta.offsetWidth;

    // Oblicz przesunięcie
    const deltaX = celRect.left - startRect.left;
    const deltaY = celRect.top - startRect.top;
    // Zastosuj transformację, która uruchomi animację zdefiniowaną w CSS
    animowanaKarta.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

    // Usuń animowaną kartę i pokaż z powrotem oryginalną kartę gracza po zakończeniu animacji
    setTimeout(() => {
        animowanaKarta.remove();
        if (startEl.style.visibility === 'hidden') {
            startEl.style.visibility = 'visible'; // Pokaż z powrotem kartę gracza
        }
    }, 400); // Czas animacji zdefiniowany w CSS
}

/**
 * Odtwarza odpowiednie dźwięki na podstawie zmian w stanie gry.
 */
function uruchomEfektyDzwiekowe(nowyStan, staryStan) {
     // Podstawowe zabezpieczenie, jeśli któryś stan lub rozdanie nie istnieje
    if (!staryStan?.rozdanie || !nowyStan?.rozdanie) return;

    const noweRozdanie = nowyStan.rozdanie;
    const stareRozdanie = staryStan.rozdanie;

    // Dźwięk zagrania karty
    const noweKartyStol = noweRozdanie.karty_na_stole || [];
    const stareKartyStol = stareRozdanie.karty_na_stole || [];
    if (noweKartyStol.length > stareKartyStol.length && !noweRozdanie.lewa_do_zamkniecia) {
        odtworzDzwiek('zagranieKarty');
    }
    // Dźwięk wygrania lewy
    if (noweRozdanie.lewa_do_zamkniecia && !stareRozdanie.lewa_do_zamkniecia) {
         odtworzDzwiek('wygranaLewa');
    }
    // Dźwięki licytacji (pas vs inne akcje)
    const nowaHistoria = noweRozdanie.historia_rozdania || [];
    const staraHistoria = stareRozdanie.historia_rozdania || [];
    if (nowaHistoria.length > staraHistoria.length) {
        const noweLogi = nowaHistoria.slice(staraHistoria.length);
        const logAkcji = noweLogi.find(log => log.typ === 'akcja_licytacyjna');
        if (logAkcji && logAkcji.akcja) { // Dodano sprawdzenie logAkcji.akcja
            const akcja = logAkcji.akcja;
            if (akcja.typ === 'pas' || akcja.typ === 'pas_lufa') {
                odtworzDzwiek('pas');
            } else if (['deklaracja', 'przebicie', 'lufa', 'kontra', 'zmiana_kontraktu', 'pytanie', 'nie_pytam', 'graj_normalnie'].includes(akcja.typ)) {
                odtworzDzwiek('licytacja');
            }
        }
    }
    // Dźwięk końca rozdania
    if (noweRozdanie.faza === 'PODSUMOWANIE_ROZDANIA' && stareRozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
        odtworzDzwiek('koniecRozdania');
    }
}


/* ==========================================================================
   SEKCJA 7: FUNKCJE POMOCNICZE I OBSŁUGA ZDARZEŃ
   ========================================================================== */
/**
 * Pokazuje wybrany panel modalny (np. podsumowanie, ustawienia).
 */
function pokazModal(modalElement) {
    if (!modalOverlayEl || !modalElement) return; // Zabezpieczenie
    // Ukryj wszystkie inne panele wewnątrz overlay'a
    modalOverlayEl.querySelectorAll('.panel').forEach(panel => {
        panel.classList.add('hidden');
    });
    // Pokaż overlay i wybrany panel
    modalElement.classList.remove('hidden');
    modalOverlayEl.classList.remove('hidden');
}

/**
 * Ukrywa overlay modalny i wszystkie panele wewnątrz.
 */
function ukryjModal() {
    if (!modalOverlayEl) return; // Zabezpieczenie
    modalOverlayEl.classList.add('hidden');
    // Ukryj wszystkie panele na wszelki wypadek
    modalOverlayEl.querySelectorAll('.panel').forEach(panel => {
        panel.classList.add('hidden');
    });
}

/**
 * Formatuje obiekt kontraktu na czytelny ciąg znaków HTML.
 */
function formatujKontrakt(kontrakt) {
    if (!kontrakt || !kontrakt.typ) return 'Brak'; // Jeśli brak kontraktu
    const kontraktTyp = kontrakt.typ.name || kontrakt.typ; // Obsługa enum lub string z backendu
    const atut = kontrakt.atut?.name || kontrakt.atut; // Obsługa enum lub string
    const info = mapowanieKolorow[atut]; // Znajdź symbol i klasę dla koloru atutowego

    if (kontraktTyp === 'NORMALNA' && info) { // Normalna gra z atutem
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span>`;
    }
    if (kontraktTyp === 'BEZ_PYTANIA' && info) { // Gra "Bez Pytania" z atutem
        return `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span><span class="znak-zapytania-przekreslony">?</span>`;
    }
    // Inne kontrakty (Lepsza, Gorsza) lub błąd
    return `<strong>${kontraktTyp}</strong>`;
}

/**
 * Wyświetla modal z podsumowaniem zakończonego rozdania.
 */
function pokazPodsumowanieRozdania(stanGry) {
    const podsumowanie = stanGry.rozdanie?.podsumowanie; // Dodano ?.
    const modalPanelEl = podsumowanieRozdaniaEl;
    if (!modalPanelEl || !podsumowanie) return; // Zabezpieczenie
    const podsumowanieTrescEl = document.getElementById('podsumowanie-tresc');
    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove()); // Usuń stare przyciski

    // Dodaj informacje o bonusach, jeśli wystąpiły
    let bonusInfo = '';
    if (podsumowanie.bonus_z_trzech_kart) {
        bonusInfo += `<p style="color: yellow; font-weight: bold;">Bonus za grę z ${stanGry.max_graczy === 3 ? '4' : '3'} kart (x2)!</p>`;
    }
    if (podsumowanie.mnoznik_lufy > 1) {
        bonusInfo += `<p style="color: orange; font-weight: bold;">Bonus za lufy (x${podsumowanie.mnoznik_lufy})!</p>`;
    }

    // Wyświetl informację o zwycięzcach rozdania
    let wygraniHtml = '';
    if (stanGry.max_graczy === 3) {
        wygraniHtml = `Rozdanie wygrane przez: <strong>${(podsumowanie.wygrani_gracze || []).join(', ')}</strong>`;
    } else {
        wygraniHtml = `Rozdanie wygrane przez: <strong>${podsumowanie.wygrana_druzyna || 'Brak'}</strong>`;
    }

    // Wypełnij treść modala
    if (podsumowanieTrescEl) {
        podsumowanieTrescEl.innerHTML = `<p>${wygraniHtml}</p>
                                        <p>Zdobyte punkty: <strong>${podsumowanie.przyznane_punkty || 0}</strong></p>
                                        ${bonusInfo}`;
    }
    const tytulEl = document.getElementById('podsumowanie-tytul');
    if (tytulEl) tytulEl.textContent = 'Koniec Rozdania!';

    // Dodaj przycisk "Dalej" / "Oczekiwanie..."
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
            // Zmień tekst i wyłącz przycisk po kliknięciu
            nastepneRozdanieBtn.textContent = 'Oczekiwanie na pozostałych...';
            nastepneRozdanieBtn.disabled = true;
        };
    }
    // Pokaż modal
    pokazModal(podsumowanieRozdaniaEl);
}

/**
 * Wyświetla modal z podsumowaniem zakończonego meczu.
 */
function pokazPodsumowanieMeczu(stanGry) {
    const tytulEl = document.getElementById('podsumowanie-tytul');
    const trescEl = document.getElementById('podsumowanie-tresc');
    const modalPanelEl = podsumowanieRozdaniaEl; // Używamy tego samego modala co dla rozdania
    if (!modalPanelEl || !tytulEl || !trescEl) return;

    modalPanelEl.querySelectorAll('button').forEach(btn => btn.remove()); // Usuń stare przyciski

    // Znajdź zwycięzcę i sformatuj wynik
    let zwyciezca = 'Brak';
    let wynikHtml = 'Brak danych';
    if(stanGry.max_graczy === 3) { // Tryb 3-osobowy
        const wyniki = Object.entries(stanGry.punkty_meczu || {});
        if (wyniki.length > 0) {
            const posortowani = wyniki.sort((a, b) => b[1] - a[1]);
            zwyciezca = posortowani[0][0];
            wynikHtml = wyniki.map(([nazwa, pkt]) => `${nazwa}: ${pkt}`).join(', ');
        }
    } else { // Tryb 4-osobowy
        const nazwaTeam1 = nazwyDruzyn.My;
        const nazwaTeam2 = nazwyDruzyn.Oni;
        const punkty1 = stanGry.punkty_meczu ? stanGry.punkty_meczu[nazwaTeam1] || 0 : 0;
        const punkty2 = stanGry.punkty_meczu ? stanGry.punkty_meczu[nazwaTeam2] || 0 : 0;
        zwyciezca = punkty1 >= 66 ? nazwaTeam1 : (punkty2 >= 66 ? nazwaTeam2 : 'Błąd');
        wynikHtml = `${nazwaTeam1} ${punkty1} - ${punkty2} ${nazwaTeam2}`;
    }

    // Wypełnij treść modala
    tytulEl.textContent = 'Koniec Meczu!';
    trescEl.innerHTML = `<h2>Wygrał gracz "${zwyciezca}"!</h2>
                         <p>Wynik końcowy: ${wynikHtml}</p>`;

    // Dodaj przycisk "Wyjdź do menu"
    const wyjdzBtn = document.createElement('button');
    wyjdzBtn.textContent = 'Wyjdź do menu';
    wyjdzBtn.onclick = () => { 
    sessionStorage.removeItem('lobbyHaslo'); // Wyczyść hasło przy wyjściu
    window.location.href = '/'; 
    };
    modalPanelEl.appendChild(wyjdzBtn);

    // W grze online dodaj przycisk "Powrót do lobby" dla hosta
    if (stanGry.tryb_gry === 'online') {
        const lobbyBtn = document.createElement('button');
        if (stanGry.host === nazwaGracza) { // Tylko host może wrócić do lobby
            lobbyBtn.textContent = 'Powrót do lobby';
            lobbyBtn.onclick = () => { wyslijAkcjeGry({ typ: 'powrot_do_lobby' }); };
        } else {
            lobbyBtn.textContent = 'Oczekiwanie na hosta...';
            lobbyBtn.disabled = true;
        }
        modalPanelEl.appendChild(lobbyBtn);
    }
    // Pokaż modal
    pokazModal(podsumowanieRozdaniaEl);
}

/**
 * Formatuje wpis z historii rozdania na czytelny ciąg znaków HTML.
 */
function formatujWpisHistorii(log) {
    const gracz = `<strong>${log.gracz || 'System'}</strong>`; // Pogrub nick gracza
    switch (log.typ) {
        case 'akcja_licytacyjna': {
            const akcja = log.akcja;
            if (!akcja) return `${gracz} wykonał nieznaną akcję.`; // Zabezpieczenie
            const typAkcji = akcja.typ?.name || akcja.typ; // Obsługa enum lub string
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
                 let txt = typAkcji.charAt(0).toUpperCase() + typAkcji.slice(1);
                 // Sprawdźmy, czy jest kontekst lufy
                 if(typAkcji === 'lufa' && kontraktAkcji && atutAkcji) {
                     const kontraktStr = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji });
                     txt = `Lufa (na ${kontraktStr})`;
                 }
                return `${gracz} mówi: <strong>${txt}</strong>.`;
            }
            // Domyślny format dla innych akcji licytacyjnych
            return `${gracz} wykonuje akcję: ${typAkcji}.`;
        }
        case 'zagranie_karty':
            return `${gracz} zagrał ${log.karta || 'nieznaną kartę'}.`;
        case 'koniec_lewy':
            return `Lewę wygrywa <strong>${log.zwyciezca || '?'}</strong> (zdobywając ${log.punkty || 0} pkt).`;
        case 'meldunek':
            return `${gracz} melduje parę za ${log.punkty || 0} pkt.`;
        case 'bonus':
            // Użyj globalnego 'ostatniStanGry' do określenia liczby graczy
            const liczbaGraczy = ostatniStanGry.max_graczy || 4;
            const opisBonusu = log.opis ? `(${log.opis})` : `z ${liczbaGraczy === 3 ? '4' : '3'} kart`;
            return `Bonus za grę <strong>${gracz}</strong> ${opisBonusu}.`;
        default: // Nieznany typ logu
            try {
                const tresc = JSON.stringify(log);
                return `[${log.typ || 'Nieznany typ'}] ${tresc.substring(0, 50)}`;
            } catch {
                return `[Nieznany log]`;
            }
    }
}

/**
 * Pokazuje dymek z ostatnią akcją licytacyjną lub meldunkiem nad odpowiednim graczem.
 * Porównuje historię z poprzednim stanem gry, aby znaleźć nowe wpisy.
 */
function pokazDymekPoOstatniejAkcji(stanGry, pozycje) {
     // Podstawowe zabezpieczenie
    if (!stanGry?.rozdanie || !ostatniStanGry?.rozdanie) return;

    // Porównaj historię obecną z zapisaną historią z poprzedniego stanu
    const nowaHistoria = stanGry.rozdanie.historia_rozdania || [];
    const staraHistoria = ostatniStanGry.rozdanie.historia_rozdania || [];
    const nowaDlugosc = nowaHistoria.length;
    const staraDlugosc = staraHistoria.length;

    // Jeśli nie ma nowych wpisów, nic nie rób
    if (nowaDlugosc <= staraDlugosc) {
        return;
    }

    // Znajdź ostatni wpis o akcji licytacyjnej lub meldunku wśród NOWYCH wpisów
    const noweLogi = nowaHistoria.slice(staraDlugosc);
    let logDoWyswietlenia = null;
    for (let i = noweLogi.length - 1; i >= 0; i--) {
        const log = noweLogi[i];
        if (log.typ === 'akcja_licytacyjna' || log.typ === 'meldunek') {
            logDoWyswietlenia = log;
            break;
        }
    }

    // Jeśli nie znaleziono odpowiedniego logu, nic nie rób
    if (!logDoWyswietlenia) {
        return;
    }

    // Znajdź pozycję gracza, który wykonał akcję
    const pozycjaGracza = Object.keys(pozycje).find(p => pozycje[p] && pozycje[p].nazwa === logDoWyswietlenia.gracz);
    if (!pozycjaGracza) {
        return;
    }

    // Sformatuj tekst dymka na podstawie typu akcji
    let tekstDymka = '';
    if (logDoWyswietlenia.typ === 'akcja_licytacyjna') {
        const akcja = logDoWyswietlenia.akcja;
        if (!akcja) return; // Zabezpieczenie
        const typAkcji = akcja.typ?.name || akcja.typ;
        const kontraktAkcji = akcja.kontrakt?.name || akcja.kontrakt;
        const atutAkcji = akcja.atut?.name || akcja.atut;

        switch (typAkcji) {
            case 'deklaracja':
                tekstDymka = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji });
                break;
            case 'zmiana_kontraktu':
                tekstDymka = `Zmieniam na: <strong>${kontraktAkcji}</strong>`;
                break;
            case 'przebicie':
                tekstDymka = `Przebijam: ${kontraktAkcji}!`;
                break;
            case 'pas': case 'pas_lufa': tekstDymka = 'Pas'; break;
            case 'pytanie': tekstDymka = 'Pytam?'; break;
            case 'nie_pytam': tekstDymka = 'Bez Pytania!'; break;
            case 'graj_normalnie': tekstDymka = 'Gramy!'; break;
            case 'do_konca': tekstDymka = 'Do końca!'; break;
            default: // Dla 'lufa', 'kontra' itp.
                 tekstDymka = typAkcji.charAt(0).toUpperCase() + typAkcji.slice(1);
                 if (typAkcji === 'lufa' && kontraktAkcji && atutAkcji) {
                     const kontraktStr = formatujKontrakt({ typ: kontraktAkcji, atut: atutAkcji });
                     tekstDymka = `Lufa (na ${kontraktStr})`;
                 }
                break;
        }
    } else if (logDoWyswietlenia.typ === 'meldunek') {
        tekstDymka = `Para (${logDoWyswietlenia.punkty || 0} pkt)!`;
    }

    // Jeśli tekst został sformatowany, pokaż dymek
    if (tekstDymka) {
        pokazDymekAkcji(pozycjaGracza, tekstDymka);
    }
}


/**
 * Tworzy i wyświetla element dymka nad kontenerem gracza na określony czas.
 */
function pokazDymekAkcji(pozycja, tekst) {
    const kontenerGracza = document.getElementById(`gracz-${pozycja}`);
    if (!kontenerGracza) return; // Zabezpieczenie

    // Usuń poprzedni dymek, jeśli istnieje
    const staryDymek = kontenerGracza.querySelector('.dymek-akcji');
    if (staryDymek) staryDymek.remove();

    // Stwórz nowy dymek
    const dymek = document.createElement('div');
    dymek.className = 'dymek-akcji';
    dymek.innerHTML = tekst; // Użyj HTML (np. dla formatowania kontraktu)
    kontenerGracza.appendChild(dymek);

    // Usuń dymek po 4 sekundach
    setTimeout(() => {
        // Sprawdź, czy dymek nadal istnieje (na wypadek szybkiego odświeżenia)
        if (dymek.parentNode) {
            dymek.remove();
        }
    }, 4000);
}

/**
 * Renderuje przyciski dostępne dla gracza w fazie licytacji.
 * Grupuje przyciski według typu kontraktu (np. NORMALNA) i koloru.
 */
function renderujPrzyciskiLicytacji(akcje) {
    const kontener = document.getElementById('kontener-akcji');
    if (!kontener) return;
    kontener.innerHTML = ''; // Wyczyść stare przyciski

    // Pogrupuj akcje (np. wszystkie deklaracje 'NORMALNA' razem)
    const grupy = akcje.reduce((acc, akcja) => {
        let klucz;
        // Używaj .name jeśli to enum, inaczej użyj stringa
        const typAkcji = akcja.typ?.name || akcja.typ;
        const kontraktAkcji = akcja.kontrakt?.name || akcja.kontrakt;

        if (typAkcji === 'przebicie') klucz = kontraktAkcji;
        else if (typAkcji === 'deklaracja') klucz = kontraktAkcji;
        else klucz = typAkcji; // pas, lufa, pytanie, etc.

        if (!acc[klucz]) acc[klucz] = [];
        acc[klucz].push(akcja); // Przechowuj oryginalny obiekt akcji
        return acc;
    }, {});

    // Stwórz przyciski dla każdej grupy
    for (const [nazwaGrupy, akcjeWGrupie] of Object.entries(grupy)) {
        const btn = document.createElement('button');
        const pierwszaAkcja = akcjeWGrupie[0]; // Weź pierwszą akcję jako reprezentanta grupy

        if (nazwaGrupy === 'lufa') { // Specjalne formatowanie dla przycisku "Lufa"
            const kontekst = pierwszaAkcja;
            // Sprawdź, czy serwer podał kontekst (kontrakt i atut)
            if (kontekst.kontrakt && kontekst.atut) {
                const kontraktStr = formatujKontrakt({ typ: kontekst.kontrakt, atut: kontekst.atut });
                btn.innerHTML = `Lufa (na ${kontraktStr})`;
            } else { // Domyślne "Lufa"
                btn.textContent = "Lufa";
            }
            btn.onclick = () => wyslijAkcjeGry(pierwszaAkcja);
        }
        // Przyciski pojedyncze bez atutu (pas, LEPSZA, GORSZA, pytanie, etc.)
        else if (akcjeWGrupie.length === 1 && !pierwszaAkcja.atut) {
            // Zamień nazwę grupy (np. 'LEPSZA', 'GORSZA', 'pas_lufa') na bardziej czytelną
             let btnText = nazwaGrupy.replace('_', ' ');
             // Użyj wielkiej litery na początku dla czytelności
             btnText = btnText.charAt(0).toUpperCase() + btnText.slice(1).toLowerCase();
             // Specjalny przypadek dla Pas Lufa
             if(nazwaGrupy === 'pas_lufa') btnText = 'Pas Lufa';

             btn.textContent = btnText;
            btn.onclick = () => wyslijAkcjeGry(pierwszaAkcja);
        } else { // Przyciski grupujące kolory (NORMALNA, BEZ_PYTANIA)
            btn.textContent = nazwaGrupy; // Wyświetl nazwę kontraktu
            btn.onclick = () => { // Po kliknięciu pokaż przyciski kolorów
                kontener.innerHTML = ''; // Wyczyść przyciski grup
                akcjeWGrupie.forEach(akcjaKoloru => { // Dla każdej akcji z kolorem w tej grupie
                    const kolorBtn = document.createElement('button');
                    const atutKoloru = akcjaKoloru.atut?.name || akcjaKoloru.atut; // Pobierz nazwę atutu

                    if (atutKoloru) {
                        const info = mapowanieKolorow[atutKoloru];
                        if (info) { // Wyświetl symbol i nazwę koloru
                            kolorBtn.innerHTML = `<span class="symbol-koloru ${info.klasa}">${info.symbol}</span> ${atutKoloru}`;
                        } else { // Fallback
                            kolorBtn.textContent = atutKoloru;
                        }
                    } else { // Fallback, jeśli brak atutu
                        kolorBtn.textContent = nazwaGrupy;
                    }
                    kolorBtn.onclick = () => wyslijAkcjeGry(akcjaKoloru); // Wyślij akcję z wybranym kolorem
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
/**
 * Wysyła wiadomość wpisaną w polu czatu do serwera.
 */
function wyslijWiadomoscCzat() {
    if (!czatInputEl) return;
    const wiadomosc = czatInputEl.value.trim(); // Pobierz i oczyść wiadomość
    if (wiadomosc && socket?.readyState === WebSocket.OPEN) {
        // Wyślij wiadomość jako obiekt JSON
        socket.send(JSON.stringify({
            gracz: nazwaGracza,
            typ_wiadomosci: 'czat',
            tresc: wiadomosc
        }));
        czatInputEl.value = ''; // Wyczyść pole input
    }
}

/**
 * Dodaje nową wiadomość do okna czatu.
 */
function dodajWiadomoscDoCzatu(gracz, tresc) {
    if (!czatWiadomosciEl) return;
    const p = document.createElement('p');
    // Użyj innerHTML, aby pogrubić nick, ale zabezpiecz treść przed HTML injection
    p.innerHTML = `<strong>${gracz}:</strong> ${tresc.replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
    czatWiadomosciEl.appendChild(p);
    // Automatycznie przewiń na dół
    czatWiadomosciEl.scrollTop = czatWiadomosciEl.scrollHeight;
    // Odtwórz dźwięk powiadomienia, jeśli wiadomość nie jest od nas
    if (gracz !== nazwaGracza) {
        odtworzDzwiek('wiadomoscCzat');
    }
}