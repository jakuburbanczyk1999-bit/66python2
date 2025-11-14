"""
Konfiguracja logowania - filtruje requesty do /state
"""
import logging


class StateEndpointFilter(logging.Filter):
    """
    Filtr który ukrywa logi requestów GET do /api/game/{game_id}/state
    """
    def filter(self, record):
        # Ukryj tylko requesty GET do /state
        message = record.getMessage()
        if 'GET /api/game/' in message and '/state HTTP' in message:
            return False
        return True


def setup_logging():
    """
    Konfiguruje logowanie z filtrem dla /state
    """
    # Pobierz logger Uvicorn access
    uvicorn_access = logging.getLogger("uvicorn.access")
    
    # Dodaj filtr
    state_filter = StateEndpointFilter()
    
    # Dodaj filtr do wszystkich handlerów
    for handler in uvicorn_access.handlers:
        handler.addFilter(state_filter)
    
    print("✅ Logging config: requesty do /state są ukryte")