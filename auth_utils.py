from passlib.context import CryptContext

# Używamy standardowego i bezpiecznego algorytmu bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Sprawdza, czy podane hasło (plain_password) pasuje do 
    zapisanego w bazie hasha (hashed_password).
    """
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """
    Zwraca bezpieczny hash dla podanego hasła.
    """
    return pwd_context.hash(password)