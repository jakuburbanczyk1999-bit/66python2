"""
Routers package
"""
# Eksportuj wszystkie routery dla wygodnego importu
from . import auth, lobby, game, pages, websocket_router, admin, stats

__all__ = ['auth', 'lobby', 'game', 'pages', 'websocket_router', 'admin', 'stats']
