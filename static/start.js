document.getElementById('start-btn').onclick = async () => {
    // 1. Wyślij żądanie do serwera, aby utworzył nową grę
    const response = await fetch('/gra/nowa', { method: 'POST' });
    const data = await response.json();
    
    // 2. Jeśli gra została pomyślnie utworzona, przekieruj na stronę gry
    if (data.id_gry) {
        window.location.href = `/gra.html?id=${data.id_gry}`;
    } else {
        alert("Nie udało się utworzyć nowej gry.");
    }
};