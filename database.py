# database.py

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Float

# ==========================================================================
# SEKCJA 1: KONFIGURACJA POŁĄCZENIA Z BAZĄ DANYCH
# ==========================================================================

# Adres URL do bazy danych SQLite.
# 'sqlite+aiosqlite:///' oznacza użycie sterownika aiosqlite (asynchronicznego).
# './gra66.db' to nazwa pliku bazy danych, który zostanie utworzony w bieżącym folderze.
DATABASE_URL = "sqlite+aiosqlite:///./gra66.db"

# Silnik (engine) SQLAlchemy do zarządzania połączeniami z bazą danych.
# 'create_async_engine' tworzy silnik obsługujący operacje asynchroniczne.
# 'echo=True' włącza logowanie zapytań SQL (przydatne do debugowania).
engine = create_async_engine(DATABASE_URL)

# Fabryka sesji (session maker) do tworzenia asynchronicznych sesji bazy danych.
# Sesja jest używana do wykonywania zapytań i zarządzania transakcjami.
# 'expire_on_commit=False' zapobiega wygaszaniu obiektów po zatwierdzeniu transakcji,
# co jest często potrzebne w aplikacjach asynchronicznych.
async_sessionmaker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# ==========================================================================
# SEKCJA 2: BAZOWY MODEL DEKLARATYWNY
# ==========================================================================

# Klasa bazowa dla modeli SQLAlchemy.
# Wszystkie definicje tabel (modele) będą dziedziczyć po tej klasie.
Base = declarative_base()

# ==========================================================================
# SEKCJA 3: DEFINICJA MODELU UŻYTKOWNIKA (TABELA 'users')
# ==========================================================================

class User(Base):
    """
    Definicja tabeli 'users' w bazie danych, mapowana na klasę Python.
    Reprezentuje użytkownika gry.
    """
    __tablename__ = "users" # Nazwa tabeli w bazie danych SQL.

    # Kolumny tabeli:
    id = Column(Integer, primary_key=True, index=True) 
    username = Column(String, unique=True, index=True, nullable=False) 
    hashed_password = Column(String, nullable=False) 
    settings = Column(Text, nullable=True) 
    elo_rating = Column(Float, default=1200.0, nullable=False) 
    games_played = Column(Integer, default=0, nullable=False) 
    games_won = Column(Integer, default=0, nullable=False)    

# ==========================================================================
# SEKCJA 4: FUNKCJA INICJALIZUJĄCA BAZĘ DANYCH
# ==========================================================================

async def init_db():
    """
    Asynchroniczna funkcja do tworzenia wszystkich tabel zdefiniowanych w modelach
    (dziedziczących po 'Base') w bazie danych.
    Tworzy tabele tylko wtedy, gdy jeszcze nie istnieją.
    """
    async with engine.begin() as conn:
        # Użyj 'run_sync' do wykonania synchronicznej metody SQLAlchemy w kontekście asynchronicznym.
        # 'Base.metadata.create_all' tworzy wszystkie zdefiniowane tabele.
        await conn.run_sync(Base.metadata.create_all)