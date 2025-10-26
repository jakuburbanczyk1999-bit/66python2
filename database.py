import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String

# 1. Definicja bazy danych:
# To stworzy plik 'gra66.db' w tym samym folderze co projekt.
DATABASE_URL = "sqlite+aiosqlite:///./gra66.db"

# 2. Konfiguracja "silnika" (engine) bazy danych
engine = create_async_engine(DATABASE_URL, echo=True)

# 3. Konfiguracja "sesji" (session) do łączenia się z bazą
# Używamy AsyncSession, aby pasowało do FastAPI
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 4. Klasa bazowa dla naszych modeli
# Wszystkie nasze tabele (np. Użytkownik) będą po niej dziedziczyć
Base = declarative_base()


# --- Definicja Modelu Użytkownika ---

class User(Base):
    """
    Definicja tabeli 'users' w naszej bazie danych.
    """
    __tablename__ = "users" # Nazwa tabeli w bazie

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # W przyszłości dodamy tu np.:
    # elo = Column(Integer, default=1200)


# --- Funkcja inicjalizująca ---

async def init_db():
    """
    Tworzy wszystkie tabele w bazie danych (jeśli jeszcze nie istnieją).
    """
    async with engine.begin() as conn:
        # Ta linia bierze wszystkie klasy dziedziczące po Base (np. User)
        # i tworzy je jako tabele w bazie danych.
        await conn.run_sync(Base.metadata.create_all)