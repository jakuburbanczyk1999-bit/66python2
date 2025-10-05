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

    // 3. Renderowanie rąk graczy i podświetlanie aktywnego gracza
    const kolejGracza = rozdanie.kolej_gracza;
    
    // POPRAWKA: Prawidłowe mapowanie do głównych kontenerów graczy i ich rąk
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

        // Podświetlanie aktywnego gracza
        kontenerGracza.classList.remove('aktywny-gracz');
        if (nazwa === kolejGracza) {
            kontenerGracza.classList.add('aktywny-gracz');
        }

        // Renderowanie kart
        kontenerReki.innerHTML = ''; 
        const reka = rozdanie.rece_graczy[nazwa] || [];
        reka.forEach(nazwaKarty => {
            const img = document.createElement('img');
            img.className = 'karta';
            img.src = `/static/karty/${nazwaKarty.replace(' ', '')}.png`;
            if (nazwa === kolejGracza && rozdanie.grywalne_karty.includes(nazwaKarty)) {
                img.classList.add('grywalna');
                img.onclick = () => wyslijAkcje(kolejGracza, { typ: 'zagraj_karte', karta: nazwaKarty });
            }
            kontenerReki.appendChild(img);
        });
    });

    // 4. Renderowanie przycisków akcji
    kontenerAkcjiEl.innerHTML = '';
    if (kolejGracza === 'Jakub' && rozdanie.faza !== 'ROZGRYWKA' && rozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
        rozdanie.mozliwe_akcje.forEach(akcja => {
            const btn = document.createElement('button');
            let etykieta = akcja.typ;
            if (akcja.kontrakt) etykieta += ` - ${akcja.kontrakt}`;
            if (akcja.atut) etykieta += ` (${akcja.atut})`;
            btn.textContent = etykieta;
            btn.onclick = () => wyslijAkcje(kolejGracza, akcja);
            kontenerAkcjiEl.appendChild(btn);
        });
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
}

// === FUNKCJE API ===
async function pobierzStanGry() {
    if (!idGry) return;
    try {
        const response = await fetch(`/gra/${idGry}`);
        if (!response.ok) { console.error("Nie udało się pobrać stanu gry."); return; }
        aktualizujWidok(await response.json());
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