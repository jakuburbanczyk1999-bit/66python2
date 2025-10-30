# create_bots.py
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
import sys
import os
import json

# Dodaj ścieżkę do modułów (jeśli skrypt jest w głównym katalogu)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import init_db, async_sessionmaker, User
    from auth_utils import hash_password
    from main import bot_instances # Potrzebne do listy algorytmów
except ImportError as e:
    print(f"Błąd importu: {e}")
    print("Upewnij się, że skrypt jest uruchamiany z głównego katalogu projektu.")
    sys.exit(1)


# === KONFIGURACJA BOTÓW ===
# Tutaj definiujemy, jakie konta botów chcemy stworzyć.
# Hasło jest to samo dla wszystkich, ale zostanie zhashowane inaczej dla każdego.
COMMON_BOT_PASSWORD = "SafeBotPassword123!"

# Pobierz nazwy algorytmów z pliku main.py
DOSTEPNE_ALGORYTMY = list(bot_instances.keys()) # ['mcts', 'mcts_fair', 'heuristic']



# Lista botów do stworzenia
# Format: (NazwaUżytkownika, Algorytm)
BOTY_DO_STWORZENIA = [
    # Boty MCTS (najsilniejsze, "oszukujące")
    ("GG NOOBS XD", "mcts"),
    ("SzescSzescMojeZycie", "mcts"),
    ("Franek_Cipien", "mcts"),
    ("Klopsztang76", "mcts_fair"),
    ("66_66", "mcts_fair"),
    
    # Boty MCTS Fair (silne, ale "uczciwe")
    ("Szefuncio", "mcts_fair"),
    ("SamHui", "mcts_fair"),
    ("Sebastain_x", "mcts_fair"),
    ("Skwarczek", "mcts_fair"),
    ("XXX_SOWA_XXX", "mcts_fair"),

    # Boty Heurystyczne (przewidywalne)
    ("Adasiek", "heuristic"),
    ("Ceper_kruca", "heuristic"),
    ("Tubus", "heuristic"),
    ("Alexandraer", "heuristic"),
    ("WeiPonJi", "heuristic"),

    # Boty Losowe (dla zabawy)
    ("Brzeszczot", "random"),
    ("Ibisz", "random"),
    ("Pitagoras", "random"),
    ("Piekny", "random"),
    ("Miekki", "random"),
]


print(f"Planowane jest stworzenie {len(BOTY_DO_STWORZENIA)} kont botów.")
print(f"Dostępne algorytmy: {DOSTEPNE_ALGORYTMY}")
# ==========================


async def stworz_konta_botow():
    """Główna funkcja tworząca konta botów w bazie danych."""
    print("Inicjalizacja bazy danych...")
    await init_db() # Upewnij się, że tabele istnieją
    print("Baza danych gotowa.")

    async with async_sessionmaker() as session:
        session: AsyncSession
        print(f"Rozpoczynanie tworzenia {len(BOTY_DO_STWORZENIA)} kont botów...")
        
        for username, algorytm in BOTY_DO_STWORZENIA:
            # 1. Sprawdź, czy bot już istnieje
            query = select(User).where(User.username == username)
            result = await session.execute(query)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"  - Bot '{username}' już istnieje. Pomijanie.")
                continue
                
            # 2. Jeśli nie istnieje, stwórz go
            try:
                hashed_pass = hash_password(COMMON_BOT_PASSWORD) # Hashuj hasło
                
                # Boty potrzebują ustawień, aby wiedzieć, jaki algorytm reprezentują.
                # Zapisujemy to w polu 'settings' jako JSON.
                bot_settings = {
                    "jest_botem": True,
                    "algorytm": algorytm
                }
                
                new_bot_user = User(
                    username=username,
                    hashed_password=hashed_pass,
                    elo_rating=1200.0, # Startowe Elo
                    settings=json.dumps(bot_settings) # Prosta konwersja na JSON
                )
                
                session.add(new_bot_user)
                await session.commit()
                print(f"  + STWORZONO bota: '{username}' (Algorytm: {algorytm})")
                
            except Exception as e:
                await session.rollback()
                print(f"  ! BŁĄD podczas tworzenia bota '{username}': {e}")
                
        print("Zakończono tworzenie kont botów.")

if __name__ == "__main__":
    # Uruchom główną funkcję asynchroniczną
    asyncio.run(stworz_konta_botow())