# database.py

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, 
    Boolean, BigInteger
)
from sqlalchemy.sql import func
from datetime import datetime

# ==========================================================================
# SEKCJA 1: KONFIGURACJA POŁĄCZENIA Z BAZĄ DANYCH
# ==========================================================================

DATABASE_URL = "postgresql+asyncpg://gra66user:gra66password@localhost/gra66db"

engine = create_async_engine(DATABASE_URL)

async_sessionmaker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# ==========================================================================
# SEKCJA 2: BAZOWY MODEL DEKLARATYWNY
# ==========================================================================

Base = declarative_base()

# ==========================================================================
# SEKCJA 3: ROZSZERZONY MODEL UŻYTKOWNIKA (TABELA 'users')
# ==========================================================================

class User(Base):
    """
    Rozszerzona definicja tabeli 'users'[cite: 124, 132].
    Przechowuje podstawowe dane profilowe.
    Statystyki gier są przeniesione do 'player_game_stats'.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True) # Dodane z planu
    
    # Rozszerzenia profilu [cite: 124, 132]
    avatar_url = Column(String, nullable=True, default='default_avatar.png')
    status = Column(String, nullable=False, default='offline') # np. 'offline', 'online', 'in_game'
    created_at = Column(DateTime, server_default=func.now())
    
    # Pole 'settings' z oryginalnego pliku, możemy je zostawić
    settings = Column(Text, nullable=True) 

    # Pola elo_rating, games_played, games_won zostały usunięte
    # i przeniesione do player_game_stats [cite: 129]

# ==========================================================================
# SEKCJA 4: NOWE TABELE (GAME_TYPES, STATS, SOCIAL) 
# ==========================================================================

class GameType(Base):
    """
    Tabela przechowująca definicje gier dostępnych na platformie[cite: 103, 132].
    """
    __tablename__ = "game_types"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False) # np. '66 (4p)', 'Tysiąc'
    rules_url = Column(String, nullable=True) # Link do zasad
    # Można dodać min/max graczy, jeśli logika lobby ma być dynamiczna
    # min_players = Column(Integer, nullable=False, default=2)
    # max_players = Column(Integer, nullable=False, default=4)

class PlayerGameStats(Base):
    """
    Tabela łącząca użytkowników i typy gier, przechowująca statystyki
    i ranking Elo dla każdej gry z osobna[cite: 129, 132].
    """
    __tablename__ = "player_game_stats"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    game_type_id = Column(Integer, ForeignKey("game_types.id"), primary_key=True)
    
    elo_rating = Column(Float, nullable=False, default=1200.0)
    games_played = Column(Integer, nullable=False, default=0)
    games_won = Column(Integer, nullable=False, default=0)
    # Można dodać więcej statystyk, np. games_lost, games_drawn

class Friendship(Base):
    """
    Tabela modelująca relacje (znajomych) między użytkownikami[cite: 130, 132].
    Używa złożonego klucza głównego (user_id_1, user_id_2).
    """
    __tablename__ = "friendships"
    
    user_id_1 = Column(Integer, ForeignKey("users.id"), primary_key=True)
    user_id_2 = Column(Integer, ForeignKey("users.id"), primary_key=True)
    
    # status: 'pending', 'accepted', 'blocked'
    status = Column(String, nullable=False, default='pending')
    
    # Kto wysłał zaproszenie / wykonał ostatnią akcję
    action_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

class Message(Base):
    """
    Tabela przechowująca prywatne wiadomości między użytkownikami[cite: 131, 132].
    """
    __tablename__ = "messages"
    
    id = Column(BigInteger, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    is_read = Column(Boolean, nullable=False, default=False)

# ==========================================================================
# SEKCJA 5: FUNKCJA INICJALIZUJĄCA BAZĘ DANYCH
# ==========================================================================

async def init_db():
    """
    Asynchroniczna funkcja do tworzenia wszystkich tabel zdefiniowanych w modelach
    (dziedziczących po 'Base') w bazie danych.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)