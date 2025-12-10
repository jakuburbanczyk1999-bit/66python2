"""
Skrypt do tworzenia kont botów w bazie danych.
Uruchom: python create_bots.py
"""
import asyncio
import json
import sys

# Dodaj ścieżkę projektu
sys.path.insert(0, '.')

from database import init_db, async_sessionmaker, User
from sqlalchemy import select
from passlib.context import CryptContext

# Hasło dla botów (nie używane do logowania)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BOT_PASSWORD = "bot_secret_password_not_used"


# Lista botów do stworzenia
# Format: (NazwaUżytkownika, Algorytm)
BOTY_DO_STWORZENIA = [
    # === TOPPLAYER (neutralny, optymalny) ===
    ("Szefuncio", "topplayer"),
    ("ProPlayer66", "topplayer"),
    
    # === SZALENIEC (kocha solo i lufy) ===
    ("CRAZZYHAMBURGER", "szaleniec"),
    ("LufaKing", "szaleniec"),
    
    # === GORSZA ENJOYER ===
    ("agreSya", "gorsza_enjoyer"),
    ("AlemamSrake", "gorsza_enjoyer"),
    
    # === LEPSZA ENJOYER ===
    ("Kingme", "lepsza_enjoyer"),
    ("LepszyGracz", "lepsza_enjoyer"),
    
    # === BEGINNER (boi się ryzyka) ===
    ("Brzeszczot", "beginner"),
    ("Krzysiu_zwany_Ibisz", "beginner"),
    
    # === CHAOTIC (nieprzewidywalny) ===
    ("Khaos", "chaotic"),
    ("Krolwicz", "chaotic"),
    
    # === COUNTER (kontruje przeciwników) ===
    ("SiemaEniuu", "counter"),
    ("Kaczorrr", "counter"),
    
    # === NIE LUBIĘ PYTAĆ ===
    ("Ktopytal", "nie_lubie_pytac"),
    ("CoCoLubie", "nie_lubie_pytac"),
    
    # === HEURYSTYCZNY (prostszy, przewidywalny) ===
    ("Esssa", "heuristic"),
    ("67676767", "heuristic"),
    
    # === BOTY SIECI NEURONOWEJ (szybkie, 91x szybsze od MCTS) ===
    ("NeuralMaster", "nn_topplayer"),
    ("DeepPlayer66", "nn_topplayer"),
    ("AIAgressor", "nn_aggressive"),
    ("NNKiller", "nn_aggressive"),
    ("SafeBot", "nn_cautious"),
    ("Ostrozny_AI", "nn_cautious"),
    ("RandomNeural", "nn_chaotic"),
    ("ChaoticAI", "nn_chaotic"),
    ("Kalkulator", "nn_calculated"),
    ("PrecyzyjnyBot", "nn_calculated"),
]


async def pokaz_istniejace_boty(skip_init: bool = False):
    """Wyświetl listę istniejących botów w bazie"""
    if not skip_init:
        await init_db()
    
    print("\n" + "=" * 60)
    print("📋 ISTNIEJĄCE BOTY W BAZIE DANYCH")
    print("=" * 60)
    
    async with async_sessionmaker() as session:
        query = select(User)
        result = await session.execute(query)
        users = result.scalars().all()
        
        bots = []
        for user in users:
            try:
                settings = json.loads(user.settings) if user.settings else {}
                if settings.get('jest_botem'):
                    bots.append({
                        'id': user.id,
                        'username': user.username,
                        'algorytm': settings.get('algorytm', 'unknown')
                    })
            except:
                pass
        
        if bots:
            print(f"\nZnaleziono {len(bots)} botów:\n")
            for bot in bots:
                print(f"  ID: {bot['id']:3} | {bot['username']:<25} | Algorytm: {bot['algorytm']}")
        else:
            print("\n❌ Brak botów w bazie danych")
        
        print()
        return bots


async def stworz_konta_botow(skip_init: bool = False):
    """Stwórz konta dla wszystkich botów"""
    if not skip_init:
        await init_db()
    
    print("\n" + "=" * 60)
    print("🤖 TWORZENIE KONT BOTÓW")
    print("=" * 60)
    
    hashed_pass = pwd_context.hash(BOT_PASSWORD)
    created = 0
    skipped = 0
    
    async with async_sessionmaker() as session:
        for username, algorytm in BOTY_DO_STWORZENIA:
            # Sprawdź czy bot już istnieje
            query = select(User).where(User.username == username)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"  ⏭️  {username} - już istnieje (ID: {existing.id})")
                skipped += 1
                continue
            
            # Stwórz nowego bota
            bot_settings = {
                'jest_botem': True,
                'algorytm': algorytm
            }
            
            new_bot_user = User(
                username=username,
                hashed_password=hashed_pass,
                settings=json.dumps(bot_settings)
            )
            
            session.add(new_bot_user)
            await session.flush()  # Żeby dostać ID
            
            print(f"  ✅ {username} - utworzono (ID: {new_bot_user.id}, algorytm: {algorytm})")
            created += 1
        
        await session.commit()
    
    print()
    print(f"📊 Podsumowanie: utworzono {created}, pominięto {skipped}")
    print()


async def usun_wszystkie_boty():
    """Usuń wszystkie konta botów (OSTROŻNIE!)"""
    await init_db()
    
    print("\n" + "=" * 60)
    print("⚠️  USUWANIE WSZYSTKICH BOTÓW")
    print("=" * 60)
    
    confirm = input("\nCzy na pewno chcesz usunąć WSZYSTKIE boty? (wpisz 'TAK'): ")
    if confirm != 'TAK':
        print("Anulowano.")
        return
    
    async with async_sessionmaker() as session:
        query = select(User)
        result = await session.execute(query)
        users = result.scalars().all()
        
        deleted = 0
        for user in users:
            try:
                settings = json.loads(user.settings) if user.settings else {}
                if settings.get('jest_botem'):
                    await session.delete(user)
                    print(f"  🗑️  Usunięto: {user.username}")
                    deleted += 1
            except:
                pass
        
        await session.commit()
        print(f"\n📊 Usunięto {deleted} botów")


async def main():
    """Główna funkcja"""
    print("\n" + "=" * 60)
    print("🎮 MIEDZIOWE KARTY - ZARZĄDZANIE BOTAMI")
    print("=" * 60)
    
    # Inicjalizacja bazy
    print("\n📦 Inicjalizacja bazy danych...")
    await init_db()
    print("✅ Baza danych gotowa.")
    
    # Pokaż istniejące boty
    await pokaz_istniejace_boty(skip_init=True)
    
    # Stwórz nowe boty
    await stworz_konta_botow(skip_init=True)
    
    # Pokaż końcową listę
    await pokaz_istniejace_boty(skip_init=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Zarządzanie kontami botów')
    parser.add_argument('--list', action='store_true', help='Tylko wyświetl istniejące boty')
    parser.add_argument('--create', action='store_true', help='Tylko stwórz boty')
    parser.add_argument('--delete', action='store_true', help='Usuń wszystkie boty')
    
    args = parser.parse_args()
    
    if args.list:
        asyncio.run(pokaz_istniejace_boty())
    elif args.create:
        asyncio.run(stworz_konta_botow())
    elif args.delete:
        asyncio.run(usun_wszystkie_boty())
    else:
        asyncio.run(main())
