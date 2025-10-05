const graczeKontenerEl = document.getElementById('gracze-kontener');
const kartyNaStoleKontenerEl = document.getElementById('karty-na-stole-kontener');
const historiaListaEl = document.getElementById('historia-lista');
const modalOverlayEl = document.getElementById('modal-overlay');
const podsumowanieTrescEl = document.getElementById('podsumowanie-tresc');
const nastepneRozdanieBtn = document.getElementById('nastepne-rozdanie-btn');

let idGry = null;
let autoCloseTimer = null;

function przejdzDoNastepnegoRozdania() {
    if (autoCloseTimer) clearTimeout(autoCloseTimer);
    modalOverlayEl.classList.add('hidden');
    
    if (nastepneRozdanieBtn.textContent === "Powrót do menu") {
        window.location.href = "/"; // Wróć na stronę startową
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
            if (akcja.atut) {
                deklaracja += ` (${akcja.atut})`;
            }
            return deklaracja;
        case 'lufa':
            return `${gracz}: Lufa!`;
        case 'kontra':
            return `${gracz}: Kontra!`;
        case 'pas_lufa':
            return `${gracz}: Pas`;
        case 'do_konca':
            return `${gracz}: Do końca!`;
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
            case 'zagranie_karty':
                tresc = `<strong>${log.gracz}</strong> zagrywa: ${log.karta}`;
                break;
            case 'akcja_licytacyjna':
                tresc = formatujAkcjeLicytacyjna(log);
                break;
            case 'koniec_lewy':
                tresc = `Lewę bierze <strong>${log.zwyciezca}</strong> (+${log.punkty} pkt).`;
                break;
            case 'meldunek':
                tresc = `<strong>${log.gracz}</strong> melduje za ${log.punkty} pkt!`;
                break;
            case 'koniec_rozdania':
                tresc = `<hr><strong>Koniec rozdania!</strong> Wygrywa: <strong>${log.wygrana_druzyna}</strong> (+${log.punkty_meczu} pkt).<br>Powód: ${log.powod}`;
                break;
            default:
                tresc = JSON.stringify(log);
        }
        p.innerHTML = tresc;
        historiaListaEl.appendChild(p);
    });
    historiaListaEl.scrollTop = historiaListaEl.scrollHeight;
}

function aktualizujWidok(stanGry) {
    if (!stanGry || stanGry.error) return;
    const rozdanie = stanGry.rozdanie;
    if (!rozdanie) return;
    aktualizujHistorie(rozdanie.historia_rozdania);
    const kolejGracza = rozdanie.kolej_gracza;
    graczeKontenerEl.innerHTML = '';
    Object.keys(rozdanie.rece_graczy).forEach(nazwaGracza => {
        const graczDiv = document.createElement('div');
        graczDiv.className = 'gracz';
        let tytul = `<h3>${nazwaGracza}`;
        if (nazwaGracza === kolejGracza) tytul += ' (TERAZ GRA)';
        tytul += '</h3>';
        graczDiv.innerHTML = tytul;
        const rekaDiv = document.createElement('div');
        rekaDiv.className = 'reka';
        rozdanie.rece_graczy[nazwaGracza].forEach(nazwaKarty => {
            const img = document.createElement('img');
            img.className = 'karta';
            const nazwaPliku = nazwaKarty.replace(' ', '') + '.png';
            img.src = `/static/karty/${nazwaPliku}`;
            if (rozdanie.faza === 'ROZGRYWKA' && nazwaGracza === kolejGracza && rozdanie.grywalne_karty.includes(nazwaKarty)) {
                img.classList.add('grywalna');
                img.onclick = () => wyslijAkcje(kolejGracza, { typ: 'zagraj_karte', karta: nazwaKarty });
            }
            rekaDiv.appendChild(img);
        });
        graczDiv.appendChild(rekaDiv);
        if (nazwaGracza === kolejGracza && rozdanie.faza !== 'ROZGRYWKA' && rozdanie.faza !== 'PODSUMOWANIE_ROZDANIA') {
            const akcjeDiv = document.createElement('div');
            akcjeDiv.id = 'akcje-lista';
            rozdanie.mozliwe_akcje.forEach(akcja => {
                const btn = document.createElement('button');
                let etykieta = akcja.typ;
                if (akcja.kontrakt) etykieta += ` - ${akcja.kontrakt}`;
                if (akcja.atut) etykieta += ` (${akcja.atut})`;
                btn.textContent = etykieta;
                btn.onclick = () => wyslijAkcje(kolejGracza, akcja);
                akcjeDiv.appendChild(btn);
            });
            graczDiv.appendChild(akcjeDiv);
        }
        graczeKontenerEl.appendChild(graczDiv);
    });
    kartyNaStoleKontenerEl.innerHTML = '';
    rozdanie.karty_na_stole.forEach(item => {
        const kartaDiv = document.createElement('div');
        kartaDiv.className = 'karta-na-stole';
        const graczP = document.createElement('p');
        graczP.textContent = item.gracz;
        const img = document.createElement('img');
        img.className = 'karta';
        const nazwaPliku = item.karta.replace(' ', '') + '.png';
        img.src = `/static/karty/${nazwaPliku}`;
        kartaDiv.appendChild(graczP);
        kartaDiv.appendChild(img);
        kartyNaStoleKontenerEl.appendChild(kartaDiv);
    });
    pokazPodsumowanie(rozdanie.podsumowanie, stanGry.punkty_meczu, stanGry.status_partii);
    if (stanGry.status_partii === 'ZAKONCZONA') {
        const zwyciezca = stanGry.punkty_meczu.My >= 66 ? "My" : "Oni";
        const tytulPodsumowania = document.getElementById('podsumowanie-tytul');
        tytulPodsumowania.textContent = `!!! KONIEC GRY !!! Wygrywa: ${zwyciezca}`;
        nastepneRozdanieBtn.textContent = "Powrót do menu";
    } else {
         const tytulPodsumowania = document.getElementById('podsumowanie-tytul');
         tytulPodsumowania.textContent = "Koniec Rozdania!";
         nastepneRozdanieBtn.textContent = "Dalej";
    }
}

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

// Przypisanie akcji do przycisku "Dalej" w modalu
nastepneRozdanieBtn.onclick = przejdzDoNastepnegoRozdania;

// --- GŁÓWNA LOGIKA URUCHAMIANA PO ZAŁADOWANIU STRONY ---
window.onload = () => {
    const params = new URLSearchParams(window.location.search);
    idGry = params.get('id');
    if (idGry) {
        // Mamy ID gry, więc od razu pobieramy jej stan
        pobierzStanGry();
    } else {
        // Jeśli nie ma ID w URL, przekieruj na stronę startową
        window.location.href = "/";
    }
};