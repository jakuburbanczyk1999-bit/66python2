"""
Routers package
"""
# Eksportuj wszystkie routery dla wygodnego importu
from . import auth, lobby, game, pages, websocket_router

__all__ = ['auth', 'lobby', 'game', 'pages', 'websocket_router']
