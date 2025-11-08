"""
Utils: Helpers
Odpowiedzialność: Helper functions (formatowanie, walidacja, etc.)
"""
import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

# ============================================
# ID GENERATION
# ============================================

def generate_game_id() -> str:
    """
    Wygeneruj unikalny ID gry
    
    Returns:
        str: 8-znakowy ID (np. "a3f5b2c9")
    
    Example:
        >>> game_id = generate_game_id()
        >>> len(game_id)
        8
    """
    return str(uuid.uuid4())[:8]

def generate_lobby_name(game_id: str) -> str:
    """
    Wygeneruj nazwę lobby z ID
    
    Args:
        game_id: ID gry
    
    Returns:
        str: Nazwa lobby (np. "Lobby_a3f5")
    
    Example:
        >>> generate_lobby_name("a3f5b2c9")
        'Lobby_a3f5'
    """
    return f"Lobby_{game_id[:4]}"

# ============================================
# VALIDATION
# ============================================

def is_valid_username(username: str) -> bool:
    """
    Waliduj username
    
    Args:
        username: Username do sprawdzenia
    
    Returns:
        bool: True jeśli prawidłowy
    
    Example:
        >>> is_valid_username("John123")
        True
        >>> is_valid_username("a")
        False
    """
    if not username or len(username) < 3 or len(username) > 15:
        return False
    # Tylko alfanumeryczne
    return bool(re.match(r'^[a-zA-Z0-9]+$', username))

def is_bot(player_name: str) -> bool:
    """
    Sprawdź czy gracz to bot
    
    Args:
        player_name: Nazwa gracza
    
    Returns:
        bool: True jeśli bot
    
    Example:
        >>> is_bot("Bot #1")
        True
        >>> is_bot("John")
        False
    """
    return player_name.startswith('Bot')

# ============================================
# FORMATTING
# ============================================

def format_timestamp(timestamp: float) -> str:
    """
    Formatuj timestamp na czytelny string
    
    Args:
        timestamp: Unix timestamp
    
    Returns:
        str: Sformatowana data (np. "2024-01-15 14:30:25")
    
    Example:
        >>> format_timestamp(1705327825.0)
        '2024-01-15 14:30:25'
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_duration(seconds: float) -> str:
    """
    Formatuj czas trwania na czytelny string
    
    Args:
        seconds: Czas w sekundach
    
    Returns:
        str: Sformatowany czas (np. "2h 30m", "45m 30s")
    
    Example:
        >>> format_duration(9030)
        '2h 30m 30s'
        >>> format_duration(90)
        '1m 30s'
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def format_player_count(current: int, max_players: int) -> str:
    """
    Formatuj licznik graczy
    
    Args:
        current: Obecna liczba graczy
        max_players: Maksymalna liczba
    
    Returns:
        str: Sformatowany licznik (np. "3/4")
    
    Example:
        >>> format_player_count(3, 4)
        '3/4'
    """
    return f"{current}/{max_players}"

# ============================================
# DATA EXTRACTION
# ============================================

def extract_player_names(lobby_data: dict) -> List[str]:
    """
    Wyciągnij nazwy wszystkich graczy z lobby
    
    Args:
        lobby_data: Dane lobby
    
    Returns:
        List[str]: Lista nazw graczy
    
    Example:
        >>> lobby = {'slots': [{'typ': 'gracz', 'nazwa': 'John'}, {'typ': 'pusty'}]}
        >>> extract_player_names(lobby)
        ['John']
    """
    names = []
    for slot in lobby_data.get('slots', []):
        if slot['typ'] != 'pusty' and slot.get('nazwa'):
            names.append(slot['nazwa'])
    return names

def extract_bots(lobby_data: dict) -> List[str]:
    """
    Wyciągnij nazwy botów z lobby
    
    Args:
        lobby_data: Dane lobby
    
    Returns:
        List[str]: Lista nazw botów
    
    Example:
        >>> lobby = {'slots': [{'typ': 'bot', 'nazwa': 'Bot #1'}]}
        >>> extract_bots(lobby)
        ['Bot #1']
    """
    bots = []
    for slot in lobby_data.get('slots', []):
        if slot['typ'] == 'bot' and slot.get('nazwa'):
            bots.append(slot['nazwa'])
    return bots

def count_players(lobby_data: dict) -> tuple[int, int]:
    """
    Policz graczy i boty
    
    Args:
        lobby_data: Dane lobby
    
    Returns:
        tuple[int, int]: (liczba_graczy, liczba_botów)
    
    Example:
        >>> lobby = {'slots': [{'typ': 'gracz'}, {'typ': 'bot'}, {'typ': 'pusty'}]}
        >>> count_players(lobby)
        (1, 1)
    """
    players = 0
    bots = 0
    
    for slot in lobby_data.get('slots', []):
        if slot['typ'] == 'gracz':
            players += 1
        elif slot['typ'] == 'bot':
            bots += 1
    
    return players, bots

# ============================================
# CARD HELPERS
# ============================================

def parse_card(card_str: str) -> Optional[Dict[str, str]]:
    """
    Parsuj string karty na dict
    
    Args:
        card_str: String karty (np. "As Czerwien")
    
    Returns:
        Optional[Dict]: {'ranga': 'As', 'kolor': 'Czerwien'} lub None
    
    Example:
        >>> parse_card("As Czerwien")
        {'ranga': 'As', 'kolor': 'Czerwien'}
    """
    try:
        parts = card_str.split()
        if len(parts) == 2:
            return {'ranga': parts[0], 'kolor': parts[1]}
    except:
        pass
    return None

def card_to_string(ranga: str, kolor: str) -> str:
    """
    Konwertuj rangę i kolor na string karty
    
    Args:
        ranga: Ranga (np. "As")
        kolor: Kolor (np. "Czerwien")
    
    Returns:
        str: String karty (np. "As Czerwien")
    
    Example:
        >>> card_to_string("As", "Czerwien")
        'As Czerwien'
    """
    return f"{ranga} {kolor}"

# ============================================
# SANITIZATION
# ============================================

def sanitize_lobby_data(lobby_data: dict) -> dict:
    """
    Usuń wrażliwe dane z lobby (hasła, etc.)
    
    Args:
        lobby_data: Dane lobby
    
    Returns:
        dict: Oczyszczone dane
    
    Example:
        >>> lobby = {'opcje': {'haslo': 'secret123'}}
        >>> sanitized = sanitize_lobby_data(lobby)
        >>> 'haslo' in sanitized['opcje']
        False
    """
    import copy
    clean = copy.deepcopy(lobby_data)
    
    # Usuń hasło
    if 'opcje' in clean and 'haslo' in clean['opcje']:
        clean['opcje'].pop('haslo', None)
    
    # Usuń klucze tymczasowe
    clean.pop('timer_task', None)
    clean.pop('bot_loop_lock', None)
    
    return clean

# ============================================
# COMPARISON
# ============================================

def compare_versions(v1: str, v2: str) -> int:
    """
    Porównaj dwie wersje (semver)
    
    Args:
        v1: Pierwsza wersja (np. "1.2.3")
        v2: Druga wersja (np. "1.3.0")
    
    Returns:
        int: -1 jeśli v1 < v2, 0 jeśli równe, 1 jeśli v1 > v2
    
    Example:
        >>> compare_versions("1.2.3", "1.3.0")
        -1
        >>> compare_versions("2.0.0", "1.9.9")
        1
    """
    def parse_version(v: str) -> List[int]:
        return [int(x) for x in v.split('.')]
    
    try:
        parts1 = parse_version(v1)
        parts2 = parse_version(v2)
        
        if parts1 < parts2:
            return -1
        elif parts1 > parts2:
            return 1
        else:
            return 0
    except:
        return 0