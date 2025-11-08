"""
Router: Game (rozgrywka)
Odpowiedzialność: State, play, finalize-trick, next-round
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import traceback

from services.redis_service import RedisService
from services.bot_service import BotService
from dependencies import get_current_user, get_redis
from routers.websocket_router import manager

# ============================================
# PYDANTIC MODELS
# ============================================

class GameActionRequest(BaseModel):
    """Request body dla akcji w grze"""
    typ: str
    karta: Optional[str] = None
    kontrakt: Optional[str] = None
    atut: Optional[str] = None
    
    class Config:
        extra = "allow"  # Pozwól na dodatkowe pola

# ============================================
# ROUTER
# ============================================

router = APIRouter()
bot_service = BotService()

# ============================================
# GET GAME STATE
# ============================================

@router.get("/{game_id}/state")
async def get_game_state(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Pobierz aktualny stan gry
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Stan gry dostosowany do perspektywy gracza
    
    Raises:
        HTTPException: 404 jeśli gra nie istnieje, 403 jeśli nie jesteś w grze
    """
    try:
        # Sprawdź czy gra istnieje
        lobby_data = await redis.get_lobby(game_id)
        if not lobby_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gra nie znaleziona"
            )
        
        # Sprawdź czy użytkownik jest w grze
        player_in_game = any(
            s['typ'] in ['gracz', 'bot'] and 
            (s.get('id_uzytkownika') == current_user['id'] or 
             s.get('nazwa') == current_user['username'])
            for s in lobby_data.get('slots', [])
        )
        
        if not player_in_game:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nie jesteś w tej grze"
            )
        
        # Pobierz silnik z Redis
        engine = await redis.get_game_engine(game_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Silnik gry nie znaleziony"
            )
        
        # Pobierz stan dla tego gracza
        player_id = current_user['username']
        state = engine.get_state_for_player(player_id)
        
        # Dodaj dodatkowe info z lobby
        state['lobby_id'] = game_id
        state['status_partii'] = lobby_data.get('status_partii', 'IN_PROGRESS')
        
        # Mapuj nazwy graczy na avatary/info z lobby
        players_info = []
        for slot in lobby_data.get('slots', []):
            if slot['typ'] != 'pusty':
                players_info.append({
                    'id': slot.get('id_uzytkownika') if slot['typ'] == 'gracz' else slot.get('nazwa'),
                    'name': slot.get('nazwa'),
                    'is_bot': slot['typ'] == 'bot',
                    'avatar_url': slot.get('avatar_url', 'default_avatar.png')
                })
        
        state['players'] = players_info
        
        return state
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting game state: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Błąd serwera"
        )

# ============================================
# PLAY ACTION
# ============================================

@router.post("/{game_id}/play")
async def play_action(
    game_id: str,
    action: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Wykonaj akcję w grze (licytacja, zagranie karty, itp.)
    
    Args:
        game_id: ID gry
        action: Akcja do wykonania (dict z 'typ' i innymi polami)
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Nowy stan gry po wykonaniu akcji
    
    Raises:
        HTTPException: 400 jeśli akcja nieprawidłowa, 404 jeśli gra nie istnieje
    """
    try:
        # Pobierz silnik
        engine = await redis.get_game_engine(game_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Silnik gry nie znaleziony"
            )
        
        player_id = current_user['username']
        
        print(f"[Game] Gracz {player_id} wykonuje akcję: {action}")
        
        # Wykonaj akcję gracza
        try:
            engine.perform_action(player_id, action)
        except Exception as e:
            print(f"❌ Błąd wykonywania akcji: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Zapisz silnik
        await redis.save_game_engine(game_id, engine)
        
        # Pobierz nowy stan
        new_state = engine.get_state_for_player(player_id)
        
        # Broadcast przez WebSocket
        await manager.broadcast(game_id, {
            'type': 'action_performed',
            'player': player_id,
            'action': action,
            'state': new_state
        })
        
        # === AUTOMATYCZNIE WYKONAJ AKCJE BOTÓW ===
        await bot_service.process_bot_actions(game_id, engine, redis)
        
        # Pobierz finalny stan (po ruchach botów)
        final_state = engine.get_state_for_player(player_id)
        
        return {
            "success": True,
            "message": "Akcja wykonana",
            "state": final_state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in play_action: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# FINALIZE TRICK
# ============================================

@router.post("/{game_id}/finalize-trick")
async def finalize_trick(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Finalizuj lewę (po zagraniu wszystkich kart)
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Nowy stan gry po finalizacji lewy
    
    Raises:
        HTTPException: 404 jeśli gra nie istnieje
    """
    try:
        # Pobierz silnik
        engine = await redis.get_game_engine(game_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Silnik gry nie znaleziony"
            )
        
        # Sprawdź czy lewa czeka na finalizację
        if not hasattr(engine.game_state, 'lewa_do_zamkniecia') or not engine.game_state.lewa_do_zamkniecia:
            # Jeśli lewa już sfinalizowana, zwróć aktualny stan (nie błąd!)
            print(f"[Game] Lewa już sfinalizowana w grze {game_id}")
            player_id = current_user['username']
            new_state = engine.get_state_for_player(player_id)
            
            return {
                "success": True,
                "message": "Lewa już sfinalizowana",
                "state": new_state
            }
        
        print(f"[Game] Finalizacja lewy w grze {game_id}")
        
        # Finalizuj lewę
        engine.game_state.finalizuj_lewe()
        
        # === WYMUSZENIE PODSUMOWANIA GDY ROZDANIE ZAKOŃCZONE ===
        if (hasattr(engine.game_state, 'rozdanie_zakonczone') and 
            engine.game_state.rozdanie_zakonczone and 
            hasattr(engine.game_state, 'faza')):
            
            # Import FazaGry dla porównania
            from silnik_gry import FazaGry
            
            if engine.game_state.faza != FazaGry.PODSUMOWANIE_ROZDANIA:
                print(f"[Game] Rozdanie zakończone - wymuszam PODSUMOWANIE_ROZDANIA")
                engine.game_state.faza = FazaGry.PODSUMOWANIE_ROZDANIA
                engine.game_state.kolej_gracza_idx = None
                
                # Rozlicz jeśli jeszcze nie rozliczone
                if not hasattr(engine.game_state, 'podsumowanie') or not engine.game_state.podsumowanie:
                    engine.game_state.rozlicz_rozdanie()
        # === KONIEC WYMUSZENIA ===
        
        # Zapisz silnik
        await redis.save_game_engine(game_id, engine)
        
        # Pobierz nowy stan
        player_id = current_user['username']
        new_state = engine.get_state_for_player(player_id)
        
        # Broadcast
        await manager.broadcast(game_id, {
            'type': 'trick_finalized',
            'state': new_state
        })
        
        # Auto-wykonaj akcje botów
        await bot_service.process_bot_actions(game_id, engine, redis)
        
        return {
            "success": True,
            "message": "Lewa sfinalizowana",
            "state": new_state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error finalizing trick: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# START NEXT ROUND
# ============================================

@router.post("/{game_id}/next-round")
async def start_next_round(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Rozpocznij następną rundę
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Stan gry w nowej rundzie
    
    Raises:
        HTTPException: 404 jeśli gra nie istnieje
    """
    try:
        # Pobierz silnik
        engine = await redis.get_game_engine(game_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Silnik gry nie znaleziony"
            )
        
        print(f"[Game] Rozpoczynam następną rundę w grze {game_id}")
        
        # Zmień rozdającego
        if hasattr(engine.game_state, 'rozdajacy_idx') and hasattr(engine.game_state, 'gracze'):
            engine.game_state.rozdajacy_idx = (
                engine.game_state.rozdajacy_idx + 1
            ) % len(engine.game_state.gracze)
        
        # === WYCZYŚĆ RĘCE I WYGRANE KARTY ===
        if hasattr(engine.game_state, 'gracze'):
            for gracz in engine.game_state.gracze:
                if hasattr(gracz, 'reka'):
                    gracz.reka.clear()
                if hasattr(gracz, 'wygrane_karty'):
                    gracz.wygrane_karty.clear()
        
        # === ZRESETUJ TALIĘ ===
        from silnik_gry import Talia
        if hasattr(engine.game_state, 'talia'):
            engine.game_state.talia = Talia()
        
        # === ZRESETUJ PUNKTY I FLAGI ROZDANIA ===
        if hasattr(engine.game_state, 'druzyny'):
            engine.game_state.punkty_w_rozdaniu = {
                d.nazwa: 0 for d in engine.game_state.druzyny
            }
        
        if hasattr(engine.game_state, 'aktualna_lewa'):
            engine.game_state.aktualna_lewa.clear()
        
        # Reset flag
        if hasattr(engine.game_state, 'rozdanie_zakonczone'):
            engine.game_state.rozdanie_zakonczone = False
        if hasattr(engine.game_state, 'podsumowanie'):
            engine.game_state.podsumowanie = None
        if hasattr(engine.game_state, 'zwyciezca_rozdania'):
            engine.game_state.zwyciezca_rozdania = None
        if hasattr(engine.game_state, 'zwyciezca_ostatniej_lewy'):
            engine.game_state.zwyciezca_ostatniej_lewy = None
        if hasattr(engine.game_state, 'powod_zakonczenia'):
            engine.game_state.powod_zakonczenia = None
        if hasattr(engine.game_state, 'lewa_do_zamkniecia'):
            engine.game_state.lewa_do_zamkniecia = False
        if hasattr(engine.game_state, 'zwyciezca_lewy_tymczasowy'):
            engine.game_state.zwyciezca_lewy_tymczasowy = None
        # === KONIEC RESETU ===
        
        # Rozpocznij nowe rozdanie
        if hasattr(engine.game_state, 'rozpocznij_nowe_rozdanie'):
            engine.game_state.rozpocznij_nowe_rozdanie()
        
        # Zapisz silnik
        await redis.save_game_engine(game_id, engine)
        
        # === AUTO-WYKONAJ AKCJE BOTÓW (np. licytacja) ===
        await bot_service.process_bot_actions(game_id, engine, redis)
        
        # Pobierz nowy stan
        player_id = current_user['username']
        new_state = engine.get_state_for_player(player_id)
        
        # Broadcast
        await manager.broadcast(game_id, {
            'type': 'next_round_started',
            'state': new_state
        })
        
        return {
            "success": True,
            "message": "Nowa runda rozpoczęta",
            "state": new_state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting next round: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )