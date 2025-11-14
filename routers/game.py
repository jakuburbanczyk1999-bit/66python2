"""
Router: Game (rozgrywka)
Odpowiedzialność: State, play, finalize-trick, next-round
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import traceback
from enum import Enum

from services.redis_service import RedisService
from services.bot_service import BotService
from dependencies import get_current_user, get_redis
from routers.websocket_router import manager

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
        
        # === AUTOMATYCZNA FINALIZACJA LEWY (jeśli gotowa) ===
        if (hasattr(engine.game_state, 'lewa_do_zamkniecia') and 
            engine.game_state.lewa_do_zamkniecia):
            print(f"[Game] Auto-finalizacja lewy w GET state dla gry {game_id}")
            
            # Import FazaGry oraz asyncio
            from silnik_gry import FazaGry
            import asyncio
            
            # Opóźnienie 1.5s, żeby gracze zobaczyli kompletny zestaw kart
            await asyncio.sleep(1.0)
            
            # Finalizuj lewę
            engine.game_state.finalizuj_lewe()
            print(f"[Game] Lewa sfinalizowana automatycznie (GET state)")
            
            # Zapisz po finalizacji
            await redis.save_game_engine(game_id, engine)
            
            # Broadcast po finalizacji
            await manager.broadcast(game_id, {
                'type': 'trick_finalized',
                'state': convert_enums_to_strings(engine.get_state_for_player(player_id))
            })
            
            # Auto-wykonaj akcje botów po finalizacji
            await bot_service.process_bot_actions(game_id, engine, redis)
        # === KONIEC AUTO-FINALIZACJI ===
        
        state = convert_enums_to_strings(engine.get_state_for_player(player_id))
        
        # Dodaj ostatnią akcję (jeśli istnieje)
        if hasattr(engine.game_state, 'szczegolowa_historia') and engine.game_state.szczegolowa_historia:
            # Znajdź ostatnią akcję licytacyjną lub zagranie karty
            for event in reversed(engine.game_state.szczegolowa_historia):
                if event.get('typ') in ['akcja_licytacyjna', 'zagranie_karty']:
                    state['ostatnia_akcja'] = {
                        'gracz': event.get('gracz'),
                        'typ': event.get('typ'),
                        'akcja': event.get('akcja') or {'typ': 'zagraj_karte', 'karta': event.get('karta')}
                    }
                    break
        
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
        
        # Wykonaj akcję gracza i zachowaj wynik
        action_result = None
        try:
            action_result = engine.perform_action(player_id, action)
        except Exception as e:
            print(f"❌ Błąd wykonywania akcji: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Zapisz silnik (ze stanem PRZED finalizacją)
        await redis.save_game_engine(game_id, engine)
        
        # Pobierz stan (z 4 kartami na stole jeśli lewa kompletna) i konwertuj Enumy
        state_with_cards = convert_enums_to_strings(engine.get_state_for_player(player_id))
        
        # Broadcast przez WebSocket (wszyscy zobaczą 4 karty!)
        await manager.broadcast(game_id, {
            'type': 'action_performed',
            'player': player_id,
            'action': action,
            'state': state_with_cards
        })
        
        # === BROADCAST MELDUNKU (jeśli był) ===
        if action_result and action_result.get('meldunek_pkt', 0) > 0:
            meldunek_pkt = action_result.get('meldunek_pkt')
            print(f"[Game] Meldunek {meldunek_pkt} pkt przez {player_id}")
            
            # Wyślij broadcast z informacją o meldunku
            await manager.broadcast(game_id, {
                'type': 'action_performed',
                'player': player_id,
                'action': {
                    'typ': 'meldunek',
                    'punkty': meldunek_pkt
                },
                'state': state_with_cards
            })
        # === KONIEC BROADCAST MELDUNKU ===
        
        # === AUTOMATYCZNA FINALIZACJA LEWY (z opóźnieniem) ===
        # Jeśli lewa jest kompletna i czeka na finalizację, sfinalizuj automatycznie
        if (hasattr(engine.game_state, 'lewa_do_zamkniecia') and 
            engine.game_state.lewa_do_zamkniecia):
            print(f"[Game] Auto-finalizacja lewy w grze {game_id}")
            
            # Import FazaGry oraz asyncio
            from silnik_gry import FazaGry
            import asyncio
            
            # Opóźnienie 1.8s, żeby gracze zobaczyli kompletną lewę
            await asyncio.sleep(1.8)
            
            # Sprawdź czy to będzie ostatnia lewa (PRZED finalizacją)
            aktywni_gracze = [
                g for g in engine.game_state.gracze 
                if g != getattr(engine.game_state, 'nieaktywny_gracz', None)
            ]
            # Ostatnia lewa = wszyscy aktywni gracze mają puste ręce (karty już na stole)
            czy_ostatnia_lewa = all(len(gracz.reka) == 0 for gracz in aktywni_gracze)
            
            print(f"[Game] Czy ostatnia lewa: {czy_ostatnia_lewa}")
            
            # Finalizuj lewę
            engine.game_state.finalizuj_lewe()
            print(f"[Game] Lewa sfinalizowana automatycznie")
            
            # Zapisz po finalizacji
            await redis.save_game_engine(game_id, engine)
            
            # Broadcast po finalizacji
            await manager.broadcast(game_id, {
                'type': 'trick_finalized',
                'state': convert_enums_to_strings(engine.get_state_for_player(player_id))
            })
        # === KONIEC AUTO-FINALIZACJI ===
        
        # === AUTOMATYCZNIE WYKONAJ AKCJE BOTÓW ===
        await bot_service.process_bot_actions(game_id, engine, redis)
        
        # Pobierz finalny stan (po ruchach botów)
        final_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
        
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
            new_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
            
            return {
                "success": True,
                "message": "Lewa już sfinalizowana",
                "state": new_state
            }
        
        print(f"[Game] Finalizacja lewy w grze {game_id}")
        
        # Import FazaGry
        from silnik_gry import FazaGry
        
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
        new_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
        
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
        # Sprawdź jaki to typ gry (Tysiąc czy 66)
        from engines.tysiac_engine import TysiacEngine
        if isinstance(engine, TysiacEngine):
            from silnik_tysiac import Talia as TaliaTysiac
            if hasattr(engine.game_state, 'talia'):
                engine.game_state.talia = TaliaTysiac()
        else:
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
        
        # === RESET FLAG ZAKOŃCZENIA ===
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
        
        # === RESET KONTRAKTU I LICYTACJI ===
        if hasattr(engine.game_state, 'kontrakt'):
            engine.game_state.kontrakt = None
        if hasattr(engine.game_state, 'grajacy'):
            engine.game_state.grajacy = None
        if hasattr(engine.game_state, 'atut'):
            engine.game_state.atut = None
        if hasattr(engine.game_state, 'mnoznik_lufy'):
            engine.game_state.mnoznik_lufy = 1
        if hasattr(engine.game_state, 'bonus_z_trzech_kart'):
            engine.game_state.bonus_z_trzech_kart = False
        
        # === RESET STANU LICYTACJI ===
        if hasattr(engine.game_state, 'historia_licytacji'):
            engine.game_state.historia_licytacji.clear()
        if hasattr(engine.game_state, 'pasujacy_gracze'):
            engine.game_state.pasujacy_gracze.clear()
        if hasattr(engine.game_state, 'oferty_przebicia'):
            engine.game_state.oferty_przebicia.clear()
        if hasattr(engine.game_state, 'ostatni_podbijajacy'):
            engine.game_state.ostatni_podbijajacy = None
        if hasattr(engine.game_state, 'lufa_challenger'):
            engine.game_state.lufa_challenger = None
        if hasattr(engine.game_state, 'kolejka_licytacji'):
            engine.game_state.kolejka_licytacji.clear()
        
        # === RESET GRY SOLO ===
        if hasattr(engine.game_state, 'nieaktywny_gracz'):
            engine.game_state.nieaktywny_gracz = None
        if hasattr(engine.game_state, 'liczba_aktywnych_graczy'):
            # Przywróć domyślną liczbę (4 dla 4p, 3 dla 3p)
            engine.game_state.liczba_aktywnych_graczy = len(engine.game_state.gracze)
        
        # === RESET MELDUNKÓW ===
        if hasattr(engine.game_state, 'zadeklarowane_meldunki'):
            engine.game_state.zadeklarowane_meldunki.clear()
        
        # === RESET LUFY WSTĘPNEJ (tylko dla 3p) ===
        if hasattr(engine.game_state, 'lufa_wstepna'):
            engine.game_state.lufa_wstepna = False
        if hasattr(engine.game_state, 'zwyciezca_rozdania_info'):
            engine.game_state.zwyciezca_rozdania_info = {}
        
        # === RESET SPECYFICZNYCH DLA TYSIĄCA ===
        # Resetuj punkty w rundzie dla Tysiąca
        if hasattr(engine.game_state, 'punkty_w_rozdaniu'):
            engine.game_state.punkty_w_rozdaniu = {g.nazwa: 0 for g in engine.game_state.gracze}
        
        # Resetuj musik/muskat
        if hasattr(engine.game_state, 'musik_odkryty'):
            engine.game_state.musik_odkryty = False
        if hasattr(engine.game_state, 'musik_karty'):
            engine.game_state.musik_karty = []
        if hasattr(engine.game_state, 'musik_1'):
            engine.game_state.musik_1 = []
        if hasattr(engine.game_state, 'musik_2'):
            engine.game_state.musik_2 = []
        if hasattr(engine.game_state, 'musik_1_oryginalny'):
            engine.game_state.musik_1_oryginalny = []
        if hasattr(engine.game_state, 'musik_2_oryginalny'):
            engine.game_state.musik_2_oryginalny = []
        if hasattr(engine.game_state, 'musik_wybrany'):
            engine.game_state.musik_wybrany = None
        
        # Resetuj licytację dla Tysiąca
        if hasattr(engine.game_state, 'aktualna_licytacja'):
            engine.game_state.aktualna_licytacja = 0
        if hasattr(engine.game_state, 'kontrakt_wartosc'):
            engine.game_state.kontrakt_wartosc = 0
        if hasattr(engine.game_state, 'licytujacy_idx'):
            engine.game_state.licytujacy_idx = None
        
        # Resetuj bombę
        if hasattr(engine.game_state, 'bomba_uzyta'):
            engine.game_state.bomba_uzyta = {g.nazwa: False for g in engine.game_state.gracze}
        
        # Resetuj muzyka w 4p
        if hasattr(engine.game_state, 'muzyk_idx'):
            engine.game_state.muzyk_idx = None
        if hasattr(engine.game_state, 'muzyk_punkty'):
            engine.game_state.muzyk_punkty = 0
        
        # Resetuj historię
        if hasattr(engine.game_state, 'szczegolowa_historia'):
            engine.game_state.szczegolowa_historia = []
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
        new_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
        
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