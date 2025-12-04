"""
Service: Autentykacja
Odpowiedzialność: Token generation, password hashing, user verification
"""
import secrets
from passlib.context import CryptContext
from typing import Optional
from config import settings

class AuthService:
    """Service do autentykacji"""
    
    def __init__(self):
        # Passlib context dla bcrypt
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # ============================================
    # PASSWORD HASHING
    # ============================================
    
    def hash_password(self, password: str) -> str:
        """
        Hashuj hasło przy użyciu bcrypt
        
        Args:
            password: Plaintext password
        
        Returns:
            str: Hashed password (z solą)
        
        Example:
            >>> auth = AuthService()
            >>> hashed = auth.hash_password("mypassword123")
            >>> print(hashed)
            $2b$12$...
        """
        # bcrypt ma limit 72 bajtów - truncate jeśli dłuższe
        password_bytes = password.encode('utf-8')[:72]
        return self.pwd_context.hash(password_bytes.decode('utf-8'))
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Weryfikuj hasło
        
        Args:
            plain_password: Plaintext password (od użytkownika)
            hashed_password: Hashed password (z bazy)
        
        Returns:
            bool: True jeśli hasło poprawne
        
        Example:
            >>> auth = AuthService()
            >>> hashed = auth.hash_password("test123")
            >>> auth.verify_password("test123", hashed)
            True
            >>> auth.verify_password("wrong", hashed)
            False
        """
        # bcrypt ma limit 72 bajtów - truncate jeśli dłuższe (musi być spójne z hash_password)
        password_bytes = plain_password.encode('utf-8')[:72]
        return self.pwd_context.verify(password_bytes.decode('utf-8'), hashed_password)
    
    # ============================================
    # TOKEN GENERATION
    # ============================================
    
    def generate_token(self) -> str:
        """
        Wygeneruj bezpieczny losowy token
        
        Returns:
            str: URL-safe token (43 znaki)
        
        Example:
            >>> auth = AuthService()
            >>> token = auth.generate_token()
            >>> len(token)
            43
            >>> print(token)
            'Xj3k9mP2nQ...'
        """
        return secrets.token_urlsafe(32)
    
    # ============================================
    # TOKEN VALIDATION
    # ============================================
    
    async def validate_token(self, token: str, redis_service) -> Optional[int]:
        """
        Zwaliduj token i zwróć user_id
        
        Args:
            token: Token do walidacji
            redis_service: RedisService instance
        
        Returns:
            Optional[int]: user_id jeśli token prawidłowy, None jeśli nie
        
        Example:
            >>> auth = AuthService()
            >>> token = auth.generate_token()
            >>> await redis.set(f"token:{token}", "123", ex=86400)
            >>> user_id = await auth.validate_token(token, redis)
            >>> print(user_id)
            123
        """
        try:
            # Pobierz user_id z Redis
            user_id_bytes = await redis_service.redis.get(f"token:{token}")
            if user_id_bytes:
                return int(user_id_bytes.decode('utf-8'))
            return None
        except Exception as e:
            print(f"❌ Token validation error: {e}")
            return None
    
    async def save_token(self, token: str, user_id: int, redis_service, expiration: int = 86400) -> bool:
        """
        Zapisz token w Redis
        
        Args:
            token: Token
            user_id: ID użytkownika
            redis_service: RedisService instance
            expiration: Czas wygaśnięcia w sekundach (domyślnie 24h)
        
        Returns:
            bool: True jeśli sukces
        
        Example:
            >>> auth = AuthService()
            >>> token = auth.generate_token()
            >>> await auth.save_token(token, 123, redis)
            True
        """
        try:
            await redis_service.redis.set(
                f"token:{token}",
                str(user_id),
                ex=expiration
            )
            return True
        except Exception as e:
            print(f"❌ Save token error: {e}")
            return False
    
    async def revoke_token(self, token: str, redis_service) -> bool:
        """
        Unieważnij token (usuń z Redis)
        
        Args:
            token: Token do unieważnienia
            redis_service: RedisService instance
        
        Returns:
            bool: True jeśli sukces
        
        Example:
            >>> auth = AuthService()
            >>> await auth.revoke_token(token, redis)
            True
        """
        try:
            await redis_service.redis.delete(f"token:{token}")
            return True
        except Exception as e:
            print(f"❌ Revoke token error: {e}")
            return False
    
    # ============================================
    # VALIDATION HELPERS
    # ============================================
    
    @staticmethod
    def validate_username(username: str) -> tuple[bool, str]:
        """
        Waliduj username
        
        Args:
            username: Username do walidacji
        
        Returns:
            tuple[bool, str]: (is_valid, error_message)
        
        Example:
            >>> AuthService.validate_username("john")
            (True, "")
            >>> AuthService.validate_username("ab")
            (False, "Nazwa: 3-15 znaków")
        """
        if len(username) < 3:
            return False, "Nazwa: min 3 znaki"
        if len(username) > 15:
            return False, "Nazwa: max 15 znaków"
        if not username.isalnum():
            return False, "Nazwa: tylko litery i cyfry"
        return True, ""
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """
        Waliduj password
        
        Args:
            password: Password do walidacji
        
        Returns:
            tuple[bool, str]: (is_valid, error_message)
        
        Example:
            >>> AuthService.validate_password("test123")
            (True, "")
            >>> AuthService.validate_password("123")
            (False, "Hasło: min 6 znaków")
        """
        if len(password) < 6:
            return False, "Hasło: min 6 znaków"
        if len(password) > 50:
            return False, "Hasło: max 50 znaków"
        return True, ""
    
    @staticmethod
    def validate_email(email: str) -> tuple[bool, str]:
        """
        Waliduj email (prosta walidacja)
        
        Args:
            email: Email do walidacji
        
        Returns:
            tuple[bool, str]: (is_valid, error_message)
        
        Example:
            >>> AuthService.validate_email("user@example.com")
            (True, "")
            >>> AuthService.validate_email("notanemail")
            (False, "Nieprawidłowy email")
        """
        if "@" not in email or "." not in email:
            return False, "Nieprawidłowy email"
        if len(email) < 5 or len(email) > 100:
            return False, "Email: 5-100 znaków"
        return True, ""