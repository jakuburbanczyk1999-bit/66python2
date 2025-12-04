"""
Services package
Lazy imports to avoid circular dependencies
"""

__all__ = ['redis_service', 'bot_service', 'auth_service', 'game_service']

# Lazy imports - nie importuj automatycznie, żeby uniknąć circular imports
# Użyj: from services.auth_service import AuthService
# zamiast: from services import auth_service
