"""
Router: WebSocket
Odpowiedzialność: Real-time communication (WebSocket)
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Optional
import json
import asyncio
import copy
from enum import Enum

from services.redis_service import RedisService, get_redis_client

# ============================================
# HELPER FUNCTIONS
# ============================================

def convert_enums_to_strings(obj):
    """Konwertuje wszystkie Enumy i obiekty Karta w obiekcie na stringi dla JSON serialization"""
    # Import klas Karta z obu silników
    from silnik_gry import Karta as Karta66
    from silnik_tysiac import Karta as KartaTysiac
    
    if isinstance(obj, dict):
        return {k: convert_enums_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_enums_to_strings(item) for item in obj]
    elif isinstance(obj, Enum):
        return obj.name
    elif isinstance(obj, (Karta66, KartaTysiac)):
        return str(obj)  # Konwertuj obiekt Karta na string
    else:
        return obj

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
        
        # === REJOIN - Usuń klucz disconnect jeśli gracz wraca ===
        try:
            redis = RedisService()
            disconnect_key = f"disconnected:{game_id}:{player_id}"
            was_disconnected = await redis.redis.get(disconnect_key)
            
            if was_disconnected:
                await redis.redis.delete(disconnect_key)
                
                # Anuluj task timeout
                cancel_disconnect_timeout(game_id, player_id)
                
                print(f"✅ WebSocket: {player_id} wrócił do gry {game_id} (rejoin)")
                
                # Broadcast info o powrocie
                await self.broadcast(game_id, {
                    'type': 'player_reconnected',
                    'player': player_id
                })
            else:
                print(f"✅ WebSocket: {player_id} połączył się z grą {game_id}")
        except Exception as e:
            print(f"✅ WebSocket: {player_id} połączył się z grą {game_id} (rejoin check failed: {e})")
    
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
            # Konwertuj Enumy i Karty na stringi przed wysłaniem
            safe_message = convert_enums_to_strings(message)
            await websocket.send_json(safe_message)
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
            # Konwertuj Enumy i Karty na stringi przed wysłaniem
            safe_message = convert_enums_to_strings(message)
            await websocket.send_json(safe_message)
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
                # Konwertuj Enumy na stringi dla JSON serialization
                engine_state = convert_enums_to_strings(engine_state)
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
# DISCONNECT TIMEOUT HANDLER
# ============================================

# Globalna lista aktywnych tasków timeout (żeby nie zostały garbage collected)
_disconnect_timeout_tasks: Dict[str, asyncio.Task] = {}

async def _handle_disconnect_timeout(game_id: str, player_id: str):
    """
    Obsługa timeout po rozłączeniu gracza.
    Jeśli gracz nie wróci w ciągu 60 sekund, przegrywa grę.
    """
    task_key = f"{game_id}:{player_id}"
    
    try:
        print(f"⏳ Timeout task dla {player_id} w grze {game_id} - czekam 60s...")
        await asyncio.sleep(60)  # Czekaj 60 sekund
        print(f"⏰ Timeout minął dla {player_id} w grze {game_id} - sprawdzam status...")
        
        # Nowa instancja Redis (stara mogła zostać zamknięta)
        redis = RedisService()
        
        # Sprawdź czy klucz nadal istnieje (gracz nie wrócił)
        disconnect_key = f"disconnected:{game_id}:{player_id}"
        disconnect_timestamp = await redis.redis.get(disconnect_key)
        
        print(f"🔍 Klucz {disconnect_key} = {disconnect_timestamp}")
        
        if not disconnect_timestamp:
            # Klucz nie istnieje = gracz wrócił (klucz został usunięty przy rejoin)
            print(f"✅ Gracz {player_id} wrócił do gry {game_id} (klucz usunięty = rejoin)")
            return
        
        # Sprawdź czy gra nadal trwa
        lobby_data = await redis.get_lobby(game_id)
        print(f"🔍 Lobby status = {lobby_data.get('status_partii') if lobby_data else 'BRAK'}")
        
        if not lobby_data or lobby_data.get('status_partii') not in ['W_GRZE', 'W_TRAKCIE']:
            # Gra już się skończyła
            print(f"ℹ️ Gra {game_id} już nie jest aktywna - pomijam forfeit")
            await redis.redis.delete(disconnect_key)
            return
        
        print(f"❌ Gracz {player_id} nie wrócił w ciągu 60s - walkower w grze {game_id}")
        
        # Usuń klucz disconnect
        await redis.redis.delete(disconnect_key)
        
        # === FORFEIT - Gracz przegrywa ===
        engine = await redis.get_game_engine(game_id)
        
        # Znajdź zwycięzców (wszyscy oprócz gracza który wyszedł)
        winners = []
        if engine:
            # Ustaw fazę na ZAKONCZONE i oznacz przegranego
            from engines.tysiac_engine import TysiacEngine
            
            if isinstance(engine, TysiacEngine):
                from silnik_tysiac import FazaGry as FazaGryTysiac
                engine.game_state.faza = FazaGryTysiac.ZAKONCZONE
            else:
                from silnik_gry import FazaGry
                engine.game_state.faza = FazaGry.ZAKONCZONE
            
            engine.game_state.kolej_gracza_idx = None
            
            # Zapisz info o forfeit
            if not hasattr(engine.game_state, 'podsumowanie') or not engine.game_state.podsumowanie:
                engine.game_state.podsumowanie = {}
            engine.game_state.podsumowanie['forfeit'] = True
            engine.game_state.podsumowanie['forfeit_player'] = player_id
            engine.game_state.podsumowanie['forfeit_reason'] = 'Przekroczono czas na powrót'
            
            # Pobierz listę zwycięzców
            for gracz in engine.game_state.gracze:
                if gracz.nazwa != player_id:
                    winners.append(gracz.nazwa)
            
            await redis.save_game_engine(game_id, engine)
        
        # Zmień status lobby
        lobby_data['status_partii'] = 'ZAKONCZONA'
        await redis.save_lobby(game_id, lobby_data)
        
        # Broadcast końca gry - użyj game_forfeit (frontend tego oczekuje)
        await manager.broadcast(game_id, {
            'type': 'game_forfeit',
            'disconnected_player': player_id,
            'winners': winners,
            'reason': 'Przekroczono czas na powrót'
        })
        
    except asyncio.CancelledError:
        print(f"ℹ️ Task timeout dla {player_id} w grze {game_id} został anulowany")
    except Exception as e:
        print(f"❌ Błąd _handle_disconnect_timeout: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Usuń task z globalnej listy
        if task_key in _disconnect_timeout_tasks:
            del _disconnect_timeout_tasks[task_key]


def cancel_disconnect_timeout(game_id: str, player_id: str):
    """Anuluj task timeout dla gracza (gdy wraca do gry)."""
    task_key = f"{game_id}:{player_id}"
    if task_key in _disconnect_timeout_tasks:
        _disconnect_timeout_tasks[task_key].cancel()
        del _disconnect_timeout_tasks[task_key]
        print(f"ℹ️ Anulowano timeout dla {player_id} w grze {game_id}")

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
        
        # === SYSTEM REJOIN - Zapisz info o opuszczeniu ===
        try:
            redis = RedisService()
            lobby_data = await redis.get_lobby(game_id)
            
            # Tylko jeśli gra jest w trakcie
            if lobby_data and lobby_data.get('status_partii') in ['W_GRZE', 'W_TRAKCIE']:
                import time
                
                # Zapisz timestamp opuszczenia (90 sekund TTL - więcej niż timeout 60s)
                disconnect_key = f"disconnected:{game_id}:{player_id}"
                await redis.redis.set(disconnect_key, str(time.time()), ex=90)
                
                print(f"📴 Gracz {player_id} opuścił grę {game_id} - ma 60s na powrót")
                
                # Broadcast info o rozłączeniu z countdown
                await manager.broadcast(game_id, {
                    'type': 'player_disconnected',
                    'player': player_id,
                    'reconnect_timeout': 60
                })
                
                # Uruchom task który sprawdzi po 60s (zapisz w globalnej liście)
                task_key = f"{game_id}:{player_id}"
                task = asyncio.create_task(
                    _handle_disconnect_timeout(game_id, player_id)
                )
                _disconnect_timeout_tasks[task_key] = task
            else:
                # Gra nie jest w trakcie - zwykłe rozłączenie
                await manager.broadcast(game_id, {
                    'type': 'player_disconnected',
                    'player': player_id
                })
        except Exception as e:
            print(f"❌ Błąd obsługi disconnect: {e}")
    
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