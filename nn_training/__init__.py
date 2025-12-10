# nn_training/__init__.py
"""
Neural Network Training Package for 66 Card Game.

Moduły:
- config: Konfiguracja sieci i treningu
- state_encoder: Kodowanie stanu gry na tensor
- network: Architektura sieci neuronowej
- game_interface: Interfejs do silnika gry
- self_play: Generowanie danych przez self-play
- trainer: Trening sieci
- nn_bot: Bot używający sieci (zamiennik MCTS)

Użycie:
    from nn_training import NeuralNetworkBot, CardGameNetwork
    
    # Załaduj wytrenowany model
    bot = NeuralNetworkBot(model_path='checkpoints/best_model.pt')
    
    # Użyj w grze
    action = bot.znajdz_najlepszy_ruch(engine, player_name)
"""

from .config import NETWORK_CONFIG, TRAINING_CONFIG
from .network import CardGameNetwork, LightweightNetwork
from .state_encoder import StateEncoder, ENCODER
from .nn_bot import NeuralNetworkBot, create_nn_bot, create_nn_bot_by_name

__all__ = [
    'NETWORK_CONFIG',
    'TRAINING_CONFIG', 
    'CardGameNetwork',
    'LightweightNetwork',
    'StateEncoder',
    'ENCODER',
    'NeuralNetworkBot',
    'create_nn_bot',
    'create_nn_bot_by_name',
]

__version__ = '1.0.0'
