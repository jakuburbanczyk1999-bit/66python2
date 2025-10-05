const nowaGraBtn = document.getElementById('nowa-gra-btn');
const graczeKontenerEl = document.getElementById('gracze-kontener');
const kartyNaStoleKontenerEl = document.getElementById('karty-na-stole-kontener');
const historiaListaEl = document.getElementById('historia-lista');

let idGry = null;

function formatujAkcjeLicytacyjna(log) {
    let tekst = `<strong>${log.gracz}</strong>: ${log.akcja.typ}`;
    if (log.akcja.kontrakt) tekst += ` - ${log.akcja.kontrakt}`;
    if (log.akcja.atut) tekst += ` (${log.akcja.atut})`;
    return tekst;
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
    // Automatyczne przewijanie do dołu
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
            
            if (rozdanie.faza === 'ROZGRYWKA' && nazwaGracza === kolejGracza) {
                img.classList.add('grywalna');
                img.onclick = () => wyslijAkcje(kolejGracza, {
                    typ: 'zagraj_karte',
                    karta: nazwaKarty
                });
            }
            rekaDiv.appendChild(img);
        });
        graczDiv.appendChild(rekaDiv);

        if (nazwaGracza === kolejGracza && rozdanie.faza !== 'ROZGRYWKA') {
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

    if(stanGry.status_partii === 'ZAKONCZONA') {
        const zwyciezca = stanGry.punkty_meczu.My >= 66 ? "My" : "Oni";
        const komunikat = document.createElement('h2');
        komunikat.textContent = `!!! KONIEC GRY !!! Wygrywa drużyna: ${zwyciezca}`;
        graczeKontenerEl.prepend(komunikat);
    }
}

async function rozpocznijNowaGre() {
    const response = await fetch('/gra/nowa', { method: 'POST' });
    const data = await response.json();
    idGry = data.id_gry;
    if (idGry) pobierzStanGry();
}

async function pobierzStanGry() {
    if (!idGry) return;
    const response = await fetch(`/gra/${idGry}`);
    aktualizujWidok(await response.json());
}

async function wyslijAkcje(gracz, akcja) {
    if (!idGry) return;
    const response = await fetch(`/gra/${idGry}/akcja`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gracz, akcja })
    });
    aktualizujWidok(await response.json());
}

nowaGraBtn.onclick = rozpocznijNowaGre;