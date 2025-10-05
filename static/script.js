// === DEKLARACJE STAŁYCH DLA NOWEGO UKŁADU ===
// Kontenery informacyjne
const infoLewyRogEl = document.getElementById('info-lewy-rog');
const infoSrodekEl = document.getElementById('info-srodek');
const infoPrawyRogEl = document.getElementById('info-prawy-rog');

// Kontenery graczy
const rekaGlownaEl = document.querySelector('#gracz-dol .reka-glowna');
const rekaGoraEl = document.querySelector('#gracz-gora .reka-gorna');
const rekaLewyEl = document.querySelector('#gracz-lewy .reka-boczna');
const rekaPrawyEl = document.querySelector('#gracz-prawy .reka-boczna');

// Inne elementy
const stolGryEl = document.getElementById('stol-gry');
const kontenerAkcjiEl = document.getElementById('kontener-akcji');
const historiaListaEl = document.getElementById('historia-lista');
const modalOverlayEl = document.getElementById('modal-overlay');
const podsumowanieTrescEl = document.getElementById('podsumowanie-tresc');
const nastepneRozdanieBtn = document.getElementById('nastepne-rozdanie-btn');

// Zmienne globalne
let idGry = null;
let autoCloseTimer = null;

// === FUNKCJE POMOCNICZE I OBSŁUGA ZDARZEŃ ===
const mapowanieKontenerowGraczy = {
    'Jakub': document.getElementById('gracz-dol'),
    'Nasz': document.getElementById('gracz-gora'),
    'Przeciwnik1': document.getElementById('gracz-lewy'),
    'Przeciwnik2': document.getElementById('gracz-prawy')
};

function sprawdzTureBota(stanGry) {
    const kolejGracza = stanGry.rozdanie.kolej_gracza;
    const fazaGry = stanGry.rozdanie.faza;

    // Sprawdź, czy gra jest w toku i czy kolej na bota
    if (kolejGracza && kolejGracza !== 'Jakub' && fazaGry !== 'PODSUMOWANIE_ROZDANIA') {
        // Poczekaj 1.5 sekundy przed ruchem bota
        setTimeout(async () => {
            const response = await fetch(`/gra/${idGry}/ruch_bota`, { method: 'POST' });
            const nowyStanGry = await response.json();
            aktualizujWidok(nowyStanGry);
        }, 1500);
    }
}
function pokazDymekAkcji(gracz, tekst) {
    const kontenerGracza = mapowanieKontenerowGraczy[gracz];
    if (!kontenerGracza) return;

    // Usuń stary dymek, jeśli jeszcze istnieje
    const staryDymek = kontenerGracza.querySelector('.dymek-akcji');
    if (staryDymek) {
        staryDymek.remove();
    }

    // Stwórz nowy dymek
    const dymek = document.createElement('div');
    dymek.className = 'dymek-akcji';
    dymek.textContent = tekst;

    kontenerGracza.style.position = 'relative'; // Ważne dla pozycjonowania dymku
    kontenerGracza.appendChild(dymek);

    // Dymek zniknie sam dzięki animacji CSS, ale usuwamy go z DOM po 4 sekundach
    setTimeout(() => {
        dymek.remove();
    }, 2000);
}

function przejdzDoNastepnegoRozdania() {
    if (autoCloseTimer) clearTimeout(autoCloseTimer);
    modalOverlayEl.classList.add('hidden');
    
    if (nastepneRozdanieBtn.textContent === "Powrót do menu") {
        window.location.href = "/";
    } else {
        wyslijAkcje("Jakub", { typ: 'nastepne_rozdanie' });
    }
}

function pokazPodsumowanie(podsumowanie, punktyMeczu, statusPartii) {
    if (!podsumowanie || Object.keys(podsumowanie).length === 0) {
        modalOverlayEl.classList.add('hidden');
        return;
    }
    if (autoCloseTimer) clearTimeout(autoCloseTimer);
    let tresc = `
        <p>Rozdanie wygrywa drużyna: <strong>${podsumowanie.wygrana_druzyna}</strong></p>
        <p>Zdobyte punkty: <strong>${podsumowanie.przyznane_punkty}</strong></p>
        <hr>
        <p>Kontrakt: ${podsumowanie.kontrakt} (${podsumowanie.atut})</p>
        <p>Wynik w kartach: My ${podsumowanie.wynik_w_kartach.My} - ${podsumowanie.wynik_w_kartach.Oni} Oni</p>
        <hr>
        <h3>Wynik partii:</h3>
        <p><strong>My: ${punktyMeczu.My}</strong></p>
        <p><strong>Oni: ${punktyMeczu.Oni}</strong></p>`;
    podsumowanieTrescEl.innerHTML = tresc;
    modalOverlayEl.classList.remove('hidden');

    if (statusPartii !== 'ZAKONCZONA') {
        autoCloseTimer = setTimeout(przejdzDoNastepnegoRozdania, 3000);
    }
}

function formatujAkcjeLicytacyjna(log) {
    const gracz = `<strong>${log.gracz}</strong>`;
    const akcja = log.akcja;
    switch(akcja.typ) {
        case 'deklaracja':
            let deklaracja = `${gracz} deklaruje: ${akcja.kontrakt}`;
            if (akcja.atut) deklaracja += ` (${akcja.atut})`;
            return deklaracja;
        case 'lufa': return `${gracz}: Lufa!`;
        case 'kontra': return `${gracz}: Kontra!`;
        case 'pas_lufa': return `${gracz}: Pas`;
        case 'do_konca': return `${gracz}: Do końca!`;
        default:
            let tekst = `${gracz}: ${akcja.typ}`;
            if (akcja.kontrakt) tekst += ` - ${akcja.kontrakt}`;
            return tekst;
    }
}

function aktualizujHistorie(historia) {
    historiaListaEl.innerHTML = '';
    if (!historia) return;
    historia.forEach(log => {
        const p = document.createElement('p');
        let tresc = '';
        switch (log.typ) {
            case 'zagranie_karty': tresc = `<strong>${log.gracz}</strong> zagrywa: ${log.karta}`; break;
            case 'akcja_licytacyjna': tresc = formatujAkcjeLicytacyjna(log); break;
            case 'koniec_lewy': tresc = `Lewę bierze <strong>${log.zwyciezca}</strong> (+${log.punkty} pkt).`; break;
            case 'meldunek': tresc = `<strong>${log.gracz}</strong> melduje za ${log.punkty} pkt!`; break;
            case 'koniec_rozdania': tresc = `<hr><strong>Koniec rozdania!</strong> Wygrywa: <strong>${log.wygrana_druzyna}</strong> (+${log.punkty_meczu} pkt).<br>Powód: ${log.powod}`; break;
            default: tresc = JSON.stringify(log);
        }
        p.innerHTML = tresc;
        historiaListaEl.appendChild(p);
    });
    historiaListaEl.scrollTop = historiaListaEl.scrollHeight;
}

// === GŁÓWNA FUNKCJA RENDERUJĄCA WIDOK ===
function aktualizujWidok(stanGry) {
    console.log(stanGry);
    if (!stanGry || stanGry.error) return;
    const rozdanie = stanGry.rozdanie;
    if (!rozdanie) return;

    // 1. Aktualizacja paneli informacyjnych
    infoLewyRogEl.innerHTML = `<div class="info-box">Wynik: <strong>My ${stanGry.punkty_meczu.My} - ${stanGry.punkty_meczu.Oni} Oni</strong><br>Stawka: <strong>x${rozdanie.stawka?.mnoznik_lufy || 1}</strong></div>`;
    if (rozdanie.kontrakt.typ === 'NORMALNA' || rozdanie.kontrakt.typ === 'BEZ_PYTANIA') {
        infoSrodekEl.innerHTML = `<div class="info-box">Punkty: My ${rozdanie.punkty_w_rozdaniu.My} - ${rozdanie.punkty_w_rozdaniu.Oni} Oni</div>`;
    } else { infoSrodekEl.innerHTML = ''; }
    if (rozdanie.kontrakt.typ) {
        infoPrawyRogEl.innerHTML = `<div class="info-box">Kontrakt: <strong>${rozdanie.kontrakt.typ}</strong><br>Atut: <strong>${rozdanie.kontrakt.atut || 'Brak'}</strong></div>`;
    } else { infoPrawyRogEl.innerHTML = ''; }

    // 2. Aktualizacja historii
    aktualizujHistorie(rozdanie.historia_rozdania);
    const ostatniLog = rozdanie.historia_rozdania[rozdanie.historia_rozdania.length - 1];
    if (ostatniLog) {
        let tekstDymku = '';
        if (ostatniLog.typ === 'akcja_licytacyjna') {
            const akcja = ostatniLog.akcja;
            tekstDymku = akcja.kontrakt || akcja.typ; // np. "NORMALNA" albo "Lufa"
        } 

        if (tekstDymku) {
            // Wyświetl dymek tylko jeśli poprzednia akcja nie była nasza
            // (aby uniknąć dublowania akcji, którą właśnie wykonaliśmy)
            const poprzedniGracz = ostatniLog.gracz;
            if (poprzedniGracz !== 'Jakub' || rozdanie.kolej_gracza === 'Jakub') {
                 pokazDymekAkcji(poprzedniGracz, tekstDymku);
            }
        }
    }

    // 3. Renderowanie rąk graczy i podświetlanie aktywnego gracza
    const kolejGracza = rozdanie.kolej_gracza;
    const mapowanieGraczy = {
        'Jakub': { kontener: document.getElementById('gracz-dol'), reka: rekaGlownaEl },
        'Nasz': { kontener: document.getElementById('gracz-gora'), reka: rekaGoraEl },
        'Przeciwnik1': { kontener: document.getElementById('gracz-lewy'), reka: rekaLewyEl },
        'Przeciwnik2': { kontener: document.getElementById('gracz-prawy'), reka: rekaPrawyEl }
    };

    Object.keys(mapowanieGraczy).forEach(nazwa => {
        const el = mapowanieGraczy[nazwa];
        const kontenerGracza = el.kontener;
        const kontenerReki = el.reka;

        kontenerGracza.classList.remove('aktywny-gracz');
        if (nazwa === kolejGracza) {
            kontenerGracza.classList.add('aktywny-gracz');
        }

        kontenerReki.innerHTML = ''; 
        const reka = rozdanie.rece_graczy[nazwa] || [];
        reka.forEach(nazwaKarty => {
            const img = document.createElement('img');
            img.className = 'karta';
            
            // --- POPRAWKA WIDOCZNOŚCI KART ---
            if (nazwa === 'Jakub') {
                // Jeśli to gracz ludzki, pokaż normalną kartę
                img.src = `/static/karty/${nazwaKarty.replace(' ', '')}.png`;
                
                // Spraw, aby tylko karty gracza ludzkiego były klikalne
                if (rozdanie.grywalne_karty.includes(nazwaKarty)) {
                    img.classList.add('grywalna');
                    img.onclick = () => wyslijAkcje(kolejGracza, { typ: 'zagraj_karte', karta: nazwaKarty });
                }
            } else {
                // Jeśli to bot, pokaż rewers
                img.src = '/static/karty/rewers.png';
            }
            kontenerReki.appendChild(img);
        });
    });

    // 4. Renderowanie przycisków akcji
    kontenerAkcjiEl.innerHTML = '';
if (kolejGracza === 'Jakub' && rozdanie.faza !== 'ROZGRYWKA' && rozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
    
    // --- NOWA, POPRAWIONA LOGIKA GRUPOWANIA ---

    const renderujPrzyciski = (typKontraktu = null) => {
        kontenerAkcjiEl.innerHTML = ''; // Zawsze czyść kontener przed renderowaniem

        if (typKontraktu) {
            // === KROK 2: Wyświetlanie kolorów dla wybranego kontraktu ===
            const akcjeKolorow = rozdanie.mozliwe_akcje.filter(a => a.kontrakt === typKontraktu);

            akcjeKolorow.forEach(akcja => {
                const btn = document.createElement('button');
                btn.textContent = akcja.atut;
                btn.onclick = () => wyslijAkcje(kolejGracza, akcja);
                kontenerAkcjiEl.appendChild(btn);
            });

            // Dodaj przycisk "Cofnij"
            const cofnijBtn = document.createElement('button');
            cofnijBtn.textContent = 'Cofnij';
            cofnijBtn.style.backgroundColor = '#6c757d';
            cofnijBtn.onclick = () => renderujPrzyciski(null); // Wróć do menu głównego
            kontenerAkcjiEl.appendChild(cofnijBtn);

        } else {
            // === KROK 1: Wyświetlanie głównych opcji licytacji ===
            const akcjeGlowne = [];
            const kontraktyDoGrupowania = new Set();

            rozdanie.mozliwe_akcje.forEach(akcja => {
                if (akcja.kontrakt === 'NORMALNA' || akcja.kontrakt === 'BEZ_PYTANIA') {
                    kontraktyDoGrupowania.add(akcja.kontrakt);
                } else {
                    akcjeGlowne.push(akcja); // Dodaj inne akcje (Gorsza, Lepsza, Lufa itp.)
                }
            });

            // Dodaj przyciski grupujące na początku
            kontraktyDoGrupowania.forEach(nazwaKontraktu => {
                const btn = document.createElement('button');
                btn.textContent = nazwaKontraktu;
                btn.onclick = () => renderujPrzyciski(nazwaKontraktu);
                kontenerAkcjiEl.appendChild(btn);
            });

            // Dodaj pozostałe przyciski
            akcjeGlowne.forEach(akcja => {
                const btn = document.createElement('button');
                btn.textContent = akcja.kontrakt || akcja.typ;
                btn.onclick = () => wyslijAkcje(kolejGracza, akcja);
                kontenerAkcjiEl.appendChild(btn);
            });
        }
    };

    // Uruchom renderowanie głównego menu licytacji
    renderujPrzyciski(null);
}

    // 5. Renderowanie kart na stole
    stolGryEl.innerHTML = '';
    rozdanie.karty_na_stole.forEach(item => {
        const kartaDiv = document.createElement('div');
        kartaDiv.className = 'karta-na-stole';
        kartaDiv.innerHTML = `<p>${item.gracz}</p><img class="karta" src="/static/karty/${item.karta.replace(' ', '')}.png">`;
        stolGryEl.appendChild(kartaDiv);
    });

    // 6. Obsługa końca rozdania i partii
    pokazPodsumowanie(rozdanie.podsumowanie, stanGry.punkty_meczu, stanGry.status_partii);
    if (stanGry.status_partii === 'ZAKONCZONA') {
        document.getElementById('podsumowanie-tytul').textContent = `!!! KONIEC GRY !!! Wygrywa: ${stanGry.punkty_meczu.My >= 66 ? "My" : "Oni"}`;
        nastepneRozdanieBtn.textContent = "Powrót do menu";
    } else {
        document.getElementById('podsumowanie-tytul').textContent = "Koniec Rozdania!";
        nastepneRozdanieBtn.textContent = "Dalej";
    }
    sprawdzTureBota(stanGry);
}

// === FUNKCJE API ===
async function pobierzStanGry() {
    if (!idGry) return;
    try {
        const response = await fetch(`/gra/${idGry}`);
        if (!response.ok) { console.error("Nie udało się pobrać stanu gry."); return; }
        const stanGry = await response.json();
        aktualizujWidok(stanGry); // Wywołujemy po otrzymaniu danych
    } catch (error) { console.error("Błąd podczas pobierania stanu gry:", error); }
}

async function wyslijAkcje(gracz, akcja) {
    if (!idGry) return;
    try {
        const response = await fetch(`/gra/${idGry}/akcja`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gracz, akcja })
        });
        if (!response.ok) {
            const err = await response.json();
            console.error("Błąd akcji:", err.detail);
            return;
        }
        aktualizujWidok(await response.json());
    } catch (error) { console.error("Błąd podczas wysyłania akcji:", error); }
}

// === INICJALIZACJA GRY ===
nastepneRozdanieBtn.onclick = przejdzDoNastepnegoRozdania;

window.onload = () => {
    const params = new URLSearchParams(window.location.search);
    idGry = params.get('id');
    if (idGry) {
        pobierzStanGry();
    } else {
        window.location.href = "/";
    }
};