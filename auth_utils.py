# auth_utils.py

from passlib.context import CryptContext

# ==========================================================================
# SEKCJA 1: KONTEKST HASŁA (Password Context)
# ==========================================================================

# Inicjalizacja kontekstu passlib do hashowania i weryfikacji haseł.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==========================================================================
# SEKCJA 2: FUNKCJE POMOCNICZE DO OBSŁUGI HASEŁ
# ==========================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Sprawdza, czy podane hasło w postaci jawnej (plain_password)
    pasuje do zapisanego w bazie danych hasha (hashed_password).

    Args:
        plain_password: Hasło podane przez użytkownika.
        hashed_password: Hash hasła pobrany z bazy danych.

    Returns:
        True, jeśli hasła pasują, False w przeciwnym razie.
    """
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """
    Generuje i zwraca bezpieczny hash bcrypt dla podanego hasła.

    Args:
        password: Hasło w postaci jawnej do zahashowania.

    Returns:
        String zawierający hash hasła (wraz z solą i informacjami o algorytmie).
    """
    return pwd_context.hash(password)