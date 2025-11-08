"""
Router: WebSocket
Odpowiedzialność: Real-time communication (WebSocket)
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Optional
import json
import asyncio
import copy

from services.redis_service import RedisService, get_redis_client

# ============================================
# CONNECTION MANAGER
# ============================================

class ConnectionManager:
    """
    Zarządza połączeniami WebSocket.
    Dla prostoty: bez Redis Pub/Sub (dla single-server).
    Jeśli potrzebujesz multi-server: dodaj Redis Pub/Sub.
    """
    
    def __init__(self):
        # Słownik: game_id -> lista WebSocket
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Słownik: WebSocket -> (game_id, player_id)
        self.connection_info: Dict[WebSocket, tuple] = {}
    
    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        """
        Akceptuj i zarejestruj połączenie
        
        Args:
            websocket: WebSocket connection
            game_id: ID gry
            player_id: Username gracza
        """
        await websocket.accept()
        
        # Zapisz info
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        
        self.active_connections[game_id].append(websocket)
        self.connection_info[websocket] = (game_id, player_id)
        
        print(f"✅ WebSocket: {player_id} połączył się z grą {game_id}")
    
    def disconnect(self, websocket: WebSocket):
        """
        Usuń połączenie
        
        Args:
            websocket: WebSocket connection
        """
        if websocket in self.connection_info:
            game_id, player_id = self.connection_info[websocket]
            
            # Usuń z active_connections
            if game_id in self.active_connections:
                if websocket in self.active_connections[game_id]:
                    self.active_connections[game_id].remove(websocket)
                
                # Usuń game_id jeśli puste
                if not self.active_connections[game_id]:
                    del self.active_connections[game_id]
            
            # Usuń z connection_info
            del self.connection_info[websocket]
            
            print(f"👋 WebSocket: {player_id} rozłączył się z gry {game_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Wyślij wiadomość do konkretnego połączenia
        
        Args:
            message: Wiadomość (dict)
            websocket: WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"❌ Błąd wysyłania wiadomości: {e}")
    
    async def broadcast(self, game_id: str, message: dict, exclude: Optional[WebSocket] = None):
        """
        Broadcast wiadomości do wszystkich w grze
        
        Args:
            game_id: ID gry
            message: Wiadomość (dict)
            exclude: Opcjonalnie wyklucz jedno połączenie
        """
        if game_id not in self.active_connections:
            return
        
        # Zrób kopię listy (żeby można było modyfikować podczas iteracji)
        connections = self.active_connections[game_id][:]
        
        tasks = []
        for connection in connections:
            if connection != exclude:
                tasks.append(self._safe_send(connection, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_send(self, websocket: WebSocket, message: dict):
        """
        Bezpieczne wysyłanie (złap błędy)
        
        Args:
            websocket: WebSocket connection
            message: Wiadomość (dict)
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"❌ Błąd wysyłania: {e}")
            # Usuń złe połączenie
            self.disconnect(websocket)
    
    async def broadcast_state_update(self, game_id: str):
        """
        Broadcast aktualizacji stanu gry (pobiera z Redis i wysyła każdemu graczowi)
        
        Args:
            game_id: ID gry
        """
        if game_id not in self.active_connections:
            return
        
        try:
            # Pobierz dane z Redis
            redis = RedisService()
            lobby_data = await redis.get_lobby(game_id)
            engine = await redis.get_game_engine(game_id)
            
            if not lobby_data:
                print(f"⚠️ Brak lobby data dla {game_id}")
                return
            
            # Wyślij spersonalizowany stan każdemu graczowi
            connections = self.active_connections[game_id][:]
            tasks = []
            
            for connection in connections:
                if connection in self.connection_info:
                    _, player_id = self.connection_info[connection]
                    
                    # Zbuduj stan dla gracza
                    state = await self._build_state_for_player(
                        lobby_data,
                        engine,
                        player_id
                    )
                    
                    # Wyślij
                    tasks.append(self._safe_send(connection, {
                        'type': 'state_update',
                        'data': state
                    }))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            print(f"❌ Błąd broadcast_state_update: {e}")
    
    async def _build_state_for_player(
        self,
        lobby_data: dict,
        engine: Optional[any],
        player_id: str
    ) -> dict:
        """
        Zbuduj stan gry dla konkretnego gracza
        
        Args:
            lobby_data: Dane lobby z Redis
            engine: Silnik gry (opcjonalnie)
            player_id: Username gracza
        
        Returns:
            dict: Stan gry
        """
        # Skopiuj bazowe dane lobby
        state = copy.deepcopy(lobby_data)
        
        # Usuń wrażliwe dane
        if 'opcje' in state and 'haslo' in state['opcje']:
            state['opcje'].pop('haslo', None)
        
        # Jeśli gra w trakcie, dodaj stan z silnika
        if engine and lobby_data.get('status_partii') in ['W_GRZE', 'W_TRAKCIE']:
            try:
                engine_state = engine.get_state_for_player(player_id)
                # Zagnieżdż w 'rozdanie' (zgodnie z frontendem)
                state['rozdanie'] = engine_state
            except Exception as e:
                print(f"❌ Błąd get_state_for_player: {e}")
        
        return state
    
    def get_connections_count(self, game_id: str) -> int:
        """
        Ile połączeń jest w grze
        
        Args:
            game_id: ID gry
        
        Returns:
            int: Liczba połączeń
        """
        return len(self.active_connections.get(game_id, []))
    
    def get_all_games(self) -> List[str]:
        """
        Lista wszystkich game_id z aktywnymi połączeniami
        
        Returns:
            List[str]: Lista game_id
        """
        return list(self.active_connections.keys())

# Singleton manager
manager = ConnectionManager()

# ============================================
# ROUTER
# ============================================

router = APIRouter()

# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@router.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    player_id: str,
    password: Optional[str] = Query(None)
):
    """
    WebSocket endpoint dla gry
    
    Args:
        websocket: WebSocket connection
        game_id: ID gry
        player_id: Username gracza
        password: Opcjonalne hasło do lobby
    """
    # Połącz
    await manager.connect(websocket, game_id, player_id)
    
    try:
        # Wyślij potwierdzenie
        await manager.send_personal_message({
            'type': 'connected',
            'message': f'Połączono z grą {game_id}'
        }, websocket)
        
        # Wyślij aktualny stan
        await manager.broadcast_state_update(game_id)
        
        # Pętla odbierania wiadomości
        while True:
            # Odbierz wiadomość
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get('type')
                
                print(f"📨 WebSocket [{player_id}]: {message_type}")
                
                # Obsługa różnych typów wiadomości
                if message_type == 'ping':
                    # Pong
                    await manager.send_personal_message({
                        'type': 'pong'
                    }, websocket)
                
                elif message_type == 'chat':
                    # Broadcast wiadomości czatu
                    await manager.broadcast(game_id, {
                        'type': 'chat',
                        'player': player_id,
                        'message': message.get('message', ''),
                        'timestamp': message.get('timestamp')
                    })
                
                elif message_type == 'request_state':
                    # Żądanie aktualnego stanu
                    await manager.broadcast_state_update(game_id)
                
                else:
                    print(f"⚠️ Nieznany typ wiadomości: {message_type}")
            
            except json.JSONDecodeError:
                print(f"❌ Błąd parsowania JSON: {data}")
            except Exception as e:
                print(f"❌ Błąd obsługi wiadomości: {e}")
    
    except WebSocketDisconnect:
        # Gracz rozłączył się
        manager.disconnect(websocket)
        
        # Opcjonalnie: zamień gracza na bota
        # await bot_service.replace_player_with_bot(game_id, player_id, redis)
        
        # Broadcast info o rozłączeniu
        await manager.broadcast(game_id, {
            'type': 'player_disconnected',
            'player': player_id
        })
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        manager.disconnect(websocket)

# ============================================
# ADMIN ENDPOINTS (opcjonalnie)
# ============================================

@router.get("/ws/stats")
async def websocket_stats():
    """
    Statystyki WebSocket (ile połączeń)
    
    Returns:
        dict: Statystyki
    """
    games = manager.get_all_games()
    
    stats = {
        'total_games': len(games),
        'games': {}
    }
    
    for game_id in games:
        stats['games'][game_id] = {
            'connections': manager.get_connections_count(game_id)
        }
    
    return stats