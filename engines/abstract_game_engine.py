# engines/abstract_game_engine.py

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List

class AbstractGameEngine(ABC):
    """
    Abstrakcyjny interfejs silnika gry.
    Definiuje "kontrakt", który musi spełniać każda gra 
    (np. "66", "Tysiąc"), aby serwer mógł nią zarządzać.
    """

    @abstractmethod
    def perform_action(self, player_id: str, action: dict[str, Any]) -> None:
        """
        Główna metoda modyfikująca stan gry na podstawie akcji gracza[cite: 70].
        (np. zagraj kartę, licytuj, spasuj).
        """
        pass

    @abstractmethod
    def get_legal_actions(self, player_id: str) -> list[dict[str, Any]]:
        """
        Zwraca listę wszystkich legalnych akcji dla danego gracza 
        w bieżącym stanie gry.
        """
        pass

    @abstractmethod
    def get_state_for_player(self, player_id: str) -> dict[str, Any]:
        """
        Zwraca pełny, serializowalny stan gry z perspektywy 
        danego gracza (ukrywając prywatne dane innych).
        Ten obiekt JSON będzie wysyłany do klienta.
        """
        pass

    @abstractmethod
    def get_current_player(self) -> Optional[str]:
        """
        Zwraca identyfikator gracza, którego jest aktualnie tura.
        Zwraca None, jeśli tura nie należy do żadnego gracza (np. oczekiwanie).
        """
        pass

    @abstractmethod
    def is_terminal(self) -> bool:
        """
        Zwraca True, jeśli gra (rozdanie) się zakończyła.
        """
        pass

    @abstractmethod
    def get_outcome(self) -> dict[str, float]:
        """
        Jeśli gra jest zakończona (is_terminal() == True), 
        zwraca wyniki dla graczy.
        Np. {'player1': 1.0, 'player2': -1.0, ...}
        """
        pass

    @abstractmethod
    def clone(self) -> 'AbstractGameEngine':
        """
        Zwraca głęboką kopię (klona) bieżącego stanu silnika gry.
        Kluczowe dla bota MCTS, aby mógł bezpiecznie symulować 
        przyszłe stany.
        """
        pass

    # --- Metody opcjonalne ---


    # @abstractmethod
    # def get_all_players(self) -> list[str]:
    #     """Zwraca listę ID wszystkich graczy biorących udział w grze."""
    #     pass
    
    # @abstractmethod
    # def initialize_game(self, player_ids: list[str], settings: dict[str, Any]) -> None:
    #     """Metoda do inicjalizacji i rozpoczęcia nowej gry/rozdania."""
    #    pass