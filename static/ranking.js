// static/js/ranking.js

window.addEventListener('DOMContentLoaded', () => {
    fetchRanking();
});

async function fetchRanking() {
    const tableBody = document.getElementById('ranking-body');
    if (!tableBody) return;

    try {
        const response = await fetch('/ranking/lista');
        if (!response.ok) {
            throw new Error(`Błąd serwera: ${response.statusText}`);
        }
        const rankingData = await response.json();

        // Wyczyść tabelę z "Ładowanie..."
        tableBody.innerHTML = '';

        if (rankingData.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6">Nie ma jeszcze żadnych graczy w rankingu.</td></tr>';
            return;
        }

        // Wypełnij tabelę danymi
        rankingData.forEach((player, index) => {
            const tr = document.createElement('tr');
            

            // Oblicz Win Ratio
            let winRatio = 0;
            if (player.games_played > 0) {
                winRatio = (player.games_won / player.games_played) * 100;
            }

            // Stwórz komórki tabeli
            tr.innerHTML = `
                <td>${index + 1}</td>
                <td>${escapeHTML(player.username)}</td>
                <td><strong>${Math.round(player.elo_rating)}</strong></td>
                <td>${player.games_played}</td>
                <td>${player.games_won}</td>
                <td>${winRatio.toFixed(1)}%</td>
            `;

            tableBody.appendChild(tr);
        });

    } catch (error) {
        console.error("Nie udało się pobrać rankingu:", error);
        tableBody.innerHTML = '<tr><td colspan="6">Wystąpił błąd podczas ładowania rankingu.</td></tr>';
    }
}

// Prosta funkcja do uniknięcia XSS (na wypadek dziwnych nazw użytkowników)
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, function(m) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[m];
    });
}