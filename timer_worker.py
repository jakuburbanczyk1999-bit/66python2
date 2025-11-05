# timer_worker.py
"""
Worker Process dla timerów gry.
Działa niezależnie od głównego serwera i sprawdza timeouty w Redis.

Ten moduł może być:
1. Uruchomiony jako asyncio.Task w głównym serwerze (lifespan)
2. Uruchomiony jako osobny proces Python
3. Uruchomiony jako osobny kontener Docker

Zaleta: Timer działa nawet jeśli serwer obsługujący gracza się restartuje.
"""

import asyncio
import time
import json
import traceback
from typing import Optional, Any, Dict
import redis.asyncio as aioredis

# Import z głównego modułu (gdy uruchamiany jako task)
# Jeśli uruchamiany jako osobny proces, trzeba będzie zmienić na bezpośrednie importy
try:
    from redis_utils import TimerInfo
except ImportError:
    # Fallback dla standalone mode
    class TimerInfo:
        @staticmethod
        def is_expired(timer_info: dict) -> bool:
            if not timer_info:
                return False
            return time.time() >= timer_info.get("deadline_timestamp", float('inf'))
        
        @staticmethod
        def remaining_time(timer_info: dict) -> float:
            if not timer_info:
                return 0.0
            remaining = timer_info.get("deadline_timestamp", time.time()) - time.time()
            return max(0.0, remaining)


class TimerWorker:
    """
    Worker sprawdzający timeouty w grach.
    """
    
    def __init__(
        self, 
        redis_url: str = "redis://localhost",
        check_interval: float = 1.0,
        debug: bool = False
    ):
        """
        Args:
            redis_url: URL do Redis
            check_interval: Interwał sprawdzania (sekundy)
            debug: Czy włączyć szczegółowe logi
        """
        self.redis_url = redis_url
        self.check_interval = check_interval
        self.debug = debug
        self.redis_client: Optional[aioredis.Redis] = None
        self.running = False
    
    async def connect(self):
        """Łączy się z Redis"""
        if not self.redis_client:
            self.redis_client = aioredis.from_url(
                self.redis_url, 
                decode_responses=False
            )
            await self.redis_client.ping()
            print("[Timer Worker] Połączono z Redis")
    
    async def close(self):
        """Zamyka połączenie z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print("[Timer Worker] Zamknięto połączenie z Redis")
    
    async def get_lobby_data(self, id_gry: str) -> Optional[Dict[str, Any]]:
        """Pobiera dane lobby z Redis"""
        try:
            json_data = await self.redis_client.get(f"lobby:{id_gry}")
            if json_data:
                return json.loads(json_data.decode('utf-8'))
            return None
        except Exception as e:
            print(f"[Timer Worker] BŁĄD get_lobby: {e}")
            return None
    
    async def save_lobby_data(self, id_gry: str, lobby_data: Dict[str, Any]):
        """Zapisuje dane lobby do Redis"""
        try:
            # Usuń przejściowe dane (jeśli istnieją)
            lobby_data.pop("timer_task", None)
            lobby_data.pop("bot_loop_lock", None)
            
            json_data = json.dumps(lobby_data)
            await self.redis_client.set(
                f"lobby:{id_gry}", 
                json_data, 
                ex=21600  # 6 godzin
            )
        except Exception as e:
            print(f"[Timer Worker] BŁĄD save_lobby: {e}")
    
    async def publish_state_update(self, id_gry: str):
        """Publikuje powiadomienie o zmianie stanu"""
        try:
            message = json.dumps({"type": "STATE_UPDATE"})
            await self.redis_client.publish(f"channel:{id_gry}", message)
        except Exception as e:
            print(f"[Timer Worker] BŁĄD publish: {e}")
    
    async def publish_chat_message(self, id_gry: str, message_text: str):
        """Publikuje wiadomość systemową na czat"""
        try:
            chat_data = {
                "type": "CHAT",
                "typ_wiadomosci": "czat",
                "gracz": "System",
                "tresc": message_text
            }
            message = json.dumps(chat_data)
            await self.redis_client.publish(f"channel:{id_gry}", message)
        except Exception as e:
            print(f"[Timer Worker] BŁĄD publish_chat: {e}")
    
    async def handle_timeout(self, id_gry: str, player_id: str, timer_info: dict):
        """
        Obsługuje timeout gracza.
        
        Ta funkcja:
        1. Kończy grę
        2. Ustala zwycięzców (wszyscy poza graczem, który timeout'ował)
        3. Aktualizuje Elo (jeśli rankingowa)
        4. Wysyła powiadomienia
        """
        print(f"[Timer Worker] ⏰ TIMEOUT dla {player_id} w grze {id_gry}")
        
        lobby_data = await self.get_lobby_data(id_gry)
        if not lobby_data:
            print(f"[Timer Worker] BŁĄD: Brak lobby dla {id_gry}")
            return
        
        # Sprawdź, czy to wciąż ten sam ruch
        if lobby_data.get("timer_info", {}).get("move_number") != timer_info.get("move_number"):
            if self.debug:
                print(f"[Timer Worker] Timer nieaktualny dla {id_gry} (ruch się zmienił)")
            return
        
        # Sprawdź, czy gra wciąż trwa
        if lobby_data.get("status_partii") != "W_TRAKCIE":
            if self.debug:
                print(f"[Timer Worker] Gra {id_gry} już nie jest W_TRAKCIE")
            return
        
        # === USTAL ZWYCIĘZCÓW ===
        outcome = {}
        max_graczy = lobby_data.get("max_graczy", 4)
        
        if max_graczy == 4:
            # Gra 4-osobowa (drużyny)
            przegrany_slot = next(
                (s for s in lobby_data["slots"] if s["nazwa"] == player_id), 
                None
            )
            
            if przegrany_slot:
                przegrana_druzyna = przegrany_slot.get("druzyna")
                
                # Wszyscy z przegranej drużyny przegrywają
                for slot in lobby_data["slots"]:
                    if slot.get("druzyna") == przegrana_druzyna:
                        outcome[slot["nazwa"]] = 0.0  # Przegrana
                    else:
                        outcome[slot["nazwa"]] = 1.0  # Wygrana
        
        elif max_graczy == 3:
            # Gra 3-osobowa (FFA)
            # Gracz który timeout'ował przegrywa
            # Pozostali dzielą wygraną
            for slot in lobby_data["slots"]:
                if slot["nazwa"] == player_id:
                    outcome[slot["nazwa"]] = 0.0  # Przegrana
                else:
                    outcome[slot["nazwa"]] = 0.5  # Podział wygranej
        
        # === ZAKOŃCZ GRĘ ===
        lobby_data["status_partii"] = "ZAKONCZONA"
        lobby_data["timer_info"] = None  # Usuń timer
        lobby_data["timeout_result"] = {
            "reason": "timeout",
            "player": player_id,
            "outcome": outcome,
            "timestamp": time.time()
        }
        
        # === AKTUALIZUJ ELO (jeśli rankingowa) ===
        if lobby_data.get("opcje", {}).get("rankingowa", False):
            # TODO: Ta część wymaga dostępu do bazy danych
            # Można to zrobić przez:
            # 1. Osobny endpoint HTTP w main.py: POST /internal/update_elo
            # 2. Bezpośrednie połączenie z PostgreSQL (wymaga importu SQLAlchemy)
            # 3. Zapisanie outcome w Redis i przetworzenie przez główny serwer
            
            # Opcja 3 (najprostsza):
            lobby_data["elo_to_process"] = {
                "outcome": outcome,
                "processed": False
            }
            print(f"[Timer Worker] Oznaczono Elo do przetworzenia dla {id_gry}")
        
        # === ZAPISZ ZMIANY ===
        await self.save_lobby_data(id_gry, lobby_data)
        
        # === POWIADOM KLIENTÓW ===
        await self.publish_state_update(id_gry)
        await self.publish_chat_message(
            id_gry, 
            f"Gracz {player_id} przegrał na czas! ⏰"
        )
        
        print(f"[Timer Worker] ✓ Obsłużono timeout dla {player_id} w {id_gry}")
    
    async def check_game_timers(self, id_gry: str):
        """Sprawdza timery dla jednej gry"""
        try:
            lobby_data = await self.get_lobby_data(id_gry)
            if not lobby_data:
                return
            
            # Sprawdź tylko gry w trakcie
            if lobby_data.get("status_partii") != "W_TRAKCIE":
                return
            
            # Sprawdź czy gra jest rankingowa (tylko wtedy są timery)
            if not lobby_data.get("opcje", {}).get("rankingowa", False):
                return
            
            # Pobierz timer info
            timer_info = lobby_data.get("timer_info")
            if not timer_info:
                return
            
            # Sprawdź czy wygasł
            if TimerInfo.is_expired(timer_info):
                player_id = timer_info.get("player_id")
                if player_id:
                    await self.handle_timeout(id_gry, player_id, timer_info)
        
        except Exception as e:
            print(f"[Timer Worker] BŁĄD check_game_timers dla {id_gry}: {e}")
            if self.debug:
                traceback.print_exc()
    
    async def run(self):
        """
        Główna pętla workera.
        Skanuje wszystkie gry i sprawdza timeouty.
        """
        await self.connect()
        self.running = True
        
        print(f"[Timer Worker] Uruchomiono (interwał: {self.check_interval}s)")
        
        iteration = 0
        
        while self.running:
            try:
                iteration += 1
                
                if self.debug and iteration % 10 == 0:
                    print(f"[Timer Worker] Iteracja {iteration}")
                
                # Skanuj wszystkie gry
                game_ids = []
                async for key in self.redis_client.scan_iter("lobby:*"):
                    id_gry = key.decode('utf-8').split(":")[-1]
                    game_ids.append(id_gry)
                
                # Sprawdź timery dla każdej gry
                for id_gry in game_ids:
                    await self.check_game_timers(id_gry)
                
                # Czekaj przed następnym sprawdzeniem
                await asyncio.sleep(self.check_interval)
            
            except Exception as e:
                print(f"[Timer Worker] BŁĄD KRYTYCZNY w pętli: {e}")
                traceback.print_exc()
                await asyncio.sleep(5.0)  # Czekaj dłużej po błędzie
        
        await self.close()
        print("[Timer Worker] Zamknięto")
    
    def stop(self):
        """Zatrzymuje worker"""
        print("[Timer Worker] Zatrzymywanie...")
        self.running = False


# ============================================================================
# URUCHOMIENIE STANDALONE
# ============================================================================

async def main_standalone():
    """
    Uruchamia worker jako osobny proces.
    
    Użycie:
        python timer_worker.py
    """
    worker = TimerWorker(
        redis_url="redis://localhost",
        check_interval=1.0,
        debug=True
    )
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        print("\n[Timer Worker] Przerwano (Ctrl+C)")
        worker.stop()


if __name__ == "__main__":
    # Uruchomienie standalone
    print("=== Timer Worker (Standalone Mode) ===")
    asyncio.run(main_standalone())
