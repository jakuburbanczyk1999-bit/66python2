"""
Router: Game (rozgrywka)
Odpowiedzialność: State, play, finalize-trick, next-round
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import traceback
import asyncio
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
        
        # Przygotuj publiczny stan (dla dymków akcji)
        state = engine.game_state
        public_state = {
            'faza': state.faza.name if hasattr(state.faza, 'name') else str(state.faza),
            'rece_graczy': {g.nazwa: len(g.reka) for g in state.gracze},
            'kolej_gracza': state.gracze[state.kolej_gracza_idx].nazwa if state.kolej_gracza_idx is not None else None
        }
        
        # Broadcast akcji gracza (z publicznym stanem dla dymków)
        await manager.broadcast(game_id, {
            'type': 'action_performed',
            'player': player_id,
            'action': convert_enums_to_strings(action),
            'state': public_state
        })
        
        # Wyślij spersonalizowany stan każdemu graczowi
        await manager.broadcast_state_update(game_id)
        
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
                'state': public_state
            })
        # === KONIEC BROADCAST MELDUNKU ===
        
        # === AUTOMATYCZNA FINALIZACJA LEWY (z opóźnieniem) ===
        # Jeśli lewa jest kompletna i czeka na finalizację, sfinalizuj automatycznie
        if (hasattr(engine.game_state, 'lewa_do_zamkniecia') and 
            engine.game_state.lewa_do_zamkniecia):
            
            print(f"[Game] Auto-finalizacja lewy w grze {game_id}")
            
            # Opóźnienie 1.5s, żeby gracze zobaczyli kompletną lewę
            await asyncio.sleep(1.5)
            
            # Finalizuj lewę
            engine.game_state.finalizuj_lewe()
            print(f"[Game] Lewa sfinalizowana automatycznie")
            
            # Zapisz po finalizacji
            await redis.save_game_engine(game_id, engine)
            
            # Broadcast po finalizacji
            await manager.broadcast(game_id, {
                'type': 'trick_finalized'
            })
            
            # Wyślij spersonalizowany stan każdemu graczowi
            await manager.broadcast_state_update(game_id)
        # === KONIEC AUTO-FINALIZACJI ===
        
        # === AUTOMATYCZNIE WYKONAJ AKCJE BOTÓW (W TLE) ===
        asyncio.create_task(bot_service.process_bot_actions(game_id, engine, redis))
        
        # Pobierz stan (boty grają w tle, aktualizacje przyjdą przez WebSocket)
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
            
            # Sprawdź jaki to silnik
            from engines.tysiac_engine import TysiacEngine
            
            if isinstance(engine, TysiacEngine):
                # Dla Tysiąca - użyj FazaGry z silnika Tysiąca
                from silnik_tysiac import FazaGry as FazaGryTysiac
                if engine.game_state.faza != FazaGryTysiac.PODSUMOWANIE_ROZDANIA:
                    print(f"[Game] Tysiąc - rozdanie zakończone - wymuszam PODSUMOWANIE_ROZDANIA")
                    engine.game_state.faza = FazaGryTysiac.PODSUMOWANIE_ROZDANIA
                    engine.game_state.kolej_gracza_idx = None
                    
                    # Rozlicz jeśli jeszcze nie rozliczone
                    if not hasattr(engine.game_state, 'podsumowanie') or not engine.game_state.podsumowanie:
                        engine.game_state.rozlicz_rozdanie()
            else:
                # Dla 66 - użyj FazaGry z silnika 66
                from silnik_gry import FazaGry
                if engine.game_state.faza != FazaGry.PODSUMOWANIE_ROZDANIA:
                    print(f"[Game] 66 - rozdanie zakończone - wymuszam PODSUMOWANIE_ROZDANIA")
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
            'type': 'trick_finalized'
        })
        
        # Wyślij spersonalizowany stan każdemu graczowi
        await manager.broadcast_state_update(game_id)
        
        # Auto-wykonaj akcje botów (W TLE)
        asyncio.create_task(bot_service.process_bot_actions(game_id, engine, redis))
        
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
# VOTE FOR NEXT ROUND
# ============================================

@router.post("/{game_id}/next-round")
async def vote_next_round(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Głosuj za rozpoczęciem następnej rundy.
    Runda rozpocznie się gdy wszyscy gracze zagłosują.
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Stan gry i info o głosowaniu
    
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
        
        player_id = current_user['username']
        
        # === SPRAWDŹ CZY MECZ SIĘ ZAKOŃCZYŁ (66 PUNKTÓW MECZOWYCH) ===
        from engines.tysiac_engine import TysiacEngine
        
        mecz_zakonczony = False
        zwyciezca_meczu = None
        punkty_meczowe = {}
        
        if isinstance(engine, TysiacEngine):
            # Tysiąc - sprawdź czy ktoś ma >= 1000 punktów
            if hasattr(engine.game_state, 'gracze'):
                for gracz in engine.game_state.gracze:
                    if hasattr(gracz, 'punkty_meczu'):
                        punkty_meczowe[gracz.nazwa] = gracz.punkty_meczu
                        if gracz.punkty_meczu >= 1000:
                            mecz_zakonczony = True
                            zwyciezca_meczu = gracz.nazwa
                            break
        else:
            # 66 - sprawdź czy drużyna/gracz ma >= 66 punktów meczowych
            if hasattr(engine.game_state, 'druzyny') and engine.game_state.druzyny:
                for druzyna in engine.game_state.druzyny:
                    if hasattr(druzyna, 'punkty_meczu'):
                        punkty_meczowe[druzyna.nazwa] = druzyna.punkty_meczu
                        if druzyna.punkty_meczu >= 66:
                            mecz_zakonczony = True
                            zwyciezca_meczu = druzyna.nazwa
                            break
            elif hasattr(engine.game_state, 'gracze'):
                for gracz in engine.game_state.gracze:
                    if hasattr(gracz, 'punkty_meczu'):
                        punkty_meczowe[gracz.nazwa] = gracz.punkty_meczu
                        if gracz.punkty_meczu >= 66:
                            mecz_zakonczony = True
                            zwyciezca_meczu = gracz.nazwa
                            break
        
        if mecz_zakonczony:
            print(f"[Game] 🏆 MECZ ZAKOŃCZONY! Zwycięzca: {zwyciezca_meczu}")
            
            # Ustaw fazę na ZAKONCZONE
            if isinstance(engine, TysiacEngine):
                from silnik_tysiac import FazaGry as FazaGryTysiac
                engine.game_state.faza = FazaGryTysiac.ZAKONCZONE
            else:
                from silnik_gry import FazaGry
                engine.game_state.faza = FazaGry.ZAKONCZONE
            
            engine.game_state.kolej_gracza_idx = None
            
            # Zapisz informację o końcu meczu w podsumowaniu
            if not hasattr(engine.game_state, 'podsumowanie') or not engine.game_state.podsumowanie:
                engine.game_state.podsumowanie = {}
            engine.game_state.podsumowanie['mecz_zakonczony'] = True
            engine.game_state.podsumowanie['zwyciezca_meczu'] = zwyciezca_meczu
            engine.game_state.podsumowanie['punkty_meczowe_koncowe'] = punkty_meczowe
            
            # Zapisz silnik
            await redis.save_game_engine(game_id, engine)
            
            # Aktualizuj status lobby na ZAKONCZONA
            lobby_data = await redis.get_lobby(game_id)
            if lobby_data:
                lobby_data['status_partii'] = 'ZAKONCZONA'
                await redis.save_lobby(game_id, lobby_data)
            
            # === INKREMENTUJ LICZNIK ROZEGRANYCH GIER ===
            try:
                await redis.redis.incr("stats:total_games")
                print(f"[📊 Stats] Rozegrano grę - inkrementacja total_games")
            except Exception as stats_err:
                print(f"[⚠️ Stats] Błąd inkrementacji: {stats_err}")
            # === KONIEC INKREMENTACJI ===
            
            # Pobierz stan dla gracza
            final_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
            final_state['mecz_zakonczony'] = True
            final_state['zwyciezca_meczu'] = zwyciezca_meczu
            final_state['punkty_meczowe_koncowe'] = punkty_meczowe
            
            # Broadcast końca meczu
            await manager.broadcast(game_id, {
                'type': 'game_ended',
                'winner': zwyciezca_meczu,
                'final_scores': punkty_meczowe
            })
            
            # Wyślij spersonalizowany stan
            await manager.broadcast_state_update(game_id)
            
            # Uruchom głosowanie botów za powrotem do lobby (w tle)
            asyncio.create_task(bot_service.trigger_return_to_lobby_voting(game_id, redis))
            
            return {
                "success": True,
                "message": f"Mecz zakończony! Zwycięzca: {zwyciezca_meczu}",
                "game_ended": True,
                "winner": zwyciezca_meczu,
                "state": final_state
            }
        # === KONIEC SPRAWDZENIA KOŃCA MECZU ===
        
        # === SYSTEM GŁOSOWANIA NA NASTĘPNĄ RUNDĘ ===
        
        # Pobierz listę głosów z Redis
        votes_key = f"next_round_votes:{game_id}"
        votes_data = await redis.redis.get(votes_key)
        
        if votes_data:
            import json
            votes = json.loads(votes_data)
        else:
            votes = []
        
        # Dodaj głos gracza (jeśli jeszcze nie głosował)
        if player_id not in votes:
            votes.append(player_id)
            import json
            await redis.redis.set(votes_key, json.dumps(votes), ex=3600)  # 1h TTL
            print(f"[Game] Gracz {player_id} głosuje za następną rundą ({len(votes)} głosów)")
        
        # Pobierz listę wszystkich graczy
        all_players = [g.nazwa for g in engine.game_state.gracze]
        
        # Broadcast info o głosowaniu
        await manager.broadcast(game_id, {
            'type': 'next_round_vote',
            'player': player_id,
            'votes': votes,
            'total_players': len(all_players),
            'ready_players': votes
        })
        
        # Sprawdź czy wszyscy zagłosowali
        if set(votes) >= set(all_players):
            print(f"[Game] Wszyscy zagłosowali! Rozpoczynam następną rundę.")
            
            # Wyczyść głosy
            await redis.redis.delete(votes_key)
            
            # Rozpocznij następną rundę
            return await _start_next_round_internal(game_id, engine, redis, player_id)
        else:
            # Czekamy na pozostałych graczy
            missing = [p for p in all_players if p not in votes]
            print(f"[Game] Czekam na głosy: {missing}")
            
            state = convert_enums_to_strings(engine.get_state_for_player(player_id))
            state['waiting_for_votes'] = True
            state['votes'] = votes
            state['total_players'] = len(all_players)
            state['ready_players'] = votes
            
            return {
                "success": True,
                "message": f"Głos zapisany. Czekam na {len(missing)} graczy.",
                "waiting_for_votes": True,
                "votes": votes,
                "total_players": len(all_players),
                "ready_players": votes,
                "state": state
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in vote_next_round: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


async def _start_next_round_internal(
    game_id: str,
    engine: Any,
    redis: RedisService,
    player_id: str
):
    """
    Wewnętrzna funkcja rozpoczynająca nową rundę.
    Wywoływana gdy wszyscy gracze zagłosowali.
    """
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
    if hasattr(engine.game_state, 'druzyny') and engine.game_state.druzyny:
        engine.game_state.punkty_w_rozdaniu = {
            d.nazwa: 0 for d in engine.game_state.druzyny
        }
    elif hasattr(engine.game_state, 'gracze'):
        engine.game_state.punkty_w_rozdaniu = {
            g.nazwa: 0 for g in engine.game_state.gracze
        }
    
    if hasattr(engine.game_state, 'aktualna_lewa'):
        engine.game_state.aktualna_lewa.clear()
    
    # === RESET FLAG ZAKOŃCZENIA ===
    for attr in ['rozdanie_zakonczone', 'lewa_do_zamkniecia', 'ostatnia_lewa']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, False)
    
    for attr in ['podsumowanie', 'zwyciezca_rozdania', 'zwyciezca_ostatniej_lewy', 
                 'powod_zakonczenia', 'zwyciezca_lewy_tymczasowy']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, None)
    
    if hasattr(engine.game_state, 'karty_ostatniej_lewy'):
        engine.game_state.karty_ostatniej_lewy = []
    
    # === RESET KONTRAKTU I LICYTACJI ===
    for attr in ['kontrakt', 'grajacy', 'atut', 'ostatni_podbijajacy', 
                 'lufa_challenger', 'nieaktywny_gracz']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, None)
    
    if hasattr(engine.game_state, 'mnoznik_lufy'):
        engine.game_state.mnoznik_lufy = 1
    if hasattr(engine.game_state, 'bonus_z_trzech_kart'):
        engine.game_state.bonus_z_trzech_kart = False
    
    # Reset list
    for attr in ['historia_licytacji', 'pasujacy_gracze', 'oferty_przebicia', 
                 'kolejka_licytacji', 'zadeklarowane_meldunki', 'szczegolowa_historia']:
        if hasattr(engine.game_state, attr):
            val = getattr(engine.game_state, attr)
            if hasattr(val, 'clear'):
                val.clear()
            else:
                setattr(engine.game_state, attr, [])
    
    if hasattr(engine.game_state, 'liczba_aktywnych_graczy'):
        engine.game_state.liczba_aktywnych_graczy = len(engine.game_state.gracze)
    
    # === RESET SPECYFICZNE DLA TYSIĄCA ===
    for attr in ['musik_odkryty', 'lufa_wstepna']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, False)
    
    for attr in ['musik_karty', 'musik_1', 'musik_2', 'musik_1_oryginalny', 'musik_2_oryginalny']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, [])
    
    for attr in ['musik_wybrany', 'licytujacy_idx', 'muzyk_idx']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, None)
    
    for attr in ['aktualna_licytacja', 'kontrakt_wartosc', 'muzyk_punkty']:
        if hasattr(engine.game_state, attr):
            setattr(engine.game_state, attr, 0)
    
    if hasattr(engine.game_state, 'bomba_uzyta'):
        engine.game_state.bomba_uzyta = {g.nazwa: False for g in engine.game_state.gracze}
    
    if hasattr(engine.game_state, 'zwyciezca_rozdania_info'):
        engine.game_state.zwyciezca_rozdania_info = {}
    
    # Rozpocznij nowe rozdanie
    if hasattr(engine.game_state, 'rozpocznij_nowe_rozdanie'):
        engine.game_state.rozpocznij_nowe_rozdanie()
    
    # Zapisz silnik
    await redis.save_game_engine(game_id, engine)
    
    # Pobierz nowy stan
    new_state = convert_enums_to_strings(engine.get_state_for_player(player_id))
    
    # Broadcast
    await manager.broadcast(game_id, {
        'type': 'next_round_started'
    })
    
    # Wyślij spersonalizowany stan każdemu graczowi
    await manager.broadcast_state_update(game_id)
    
    # === AUTO-WYKONAJ AKCJE BOTÓW (W TLE) ===
    asyncio.create_task(bot_service.process_bot_actions(game_id, engine, redis))
    
    return {
        "success": True,
        "message": "Nowa runda rozpoczęta",
        "state": new_state
    }


# ============================================
# RETURN TO LOBBY (after game end)
# ============================================

@router.post("/{game_id}/return-to-lobby")
async def return_to_lobby(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Głosuj za powrotem do lobby po zakończeniu meczu.
    Gracz zostaje w lobby, inni mogą wyjść do dashboard.
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Status głosowania
    """
    try:
        lobby_data = await redis.get_lobby(game_id)
        if not lobby_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lobby nie znalezione"
            )
        
        player_id = current_user['username']
        user_id = current_user['id']
        
        # Sprawdź czy gra jest zakończona
        if lobby_data.get('status_partii') != 'ZAKONCZONA':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gra nie jest zakończona"
            )
        
        print(f"[Game] Gracz {player_id} głosuje za powrotem do lobby")
        
        # === SYSTEM GŁOSOWANIA ===
        votes_key = f"return_to_lobby_votes:{game_id}"
        votes_data = await redis.redis.get(votes_key)
        
        import json
        if votes_data:
            votes = json.loads(votes_data)
        else:
            votes = {'stay': [], 'leave': []}
            # Ustaw TTL na decyzję (60 sekund)
            # Po tym czasie automatycznie zostają tylko głosujący
        
        # Dodaj głos za pozostaniem
        if player_id not in votes['stay']:
            votes['stay'].append(player_id)
            # Usuń z leave jeśli był
            if player_id in votes['leave']:
                votes['leave'].remove(player_id)
        
        await redis.redis.set(votes_key, json.dumps(votes), ex=120)  # 2 min TTL
        
        # Pobierz listę wszystkich graczy
        all_players = [
            s['nazwa'] for s in lobby_data.get('slots', []) 
            if s.get('typ') in ['gracz', 'bot'] and s.get('nazwa')
        ]
        
        # Broadcast info o głosowaniu
        await manager.broadcast(game_id, {
            'type': 'return_to_lobby_vote',
            'player': player_id,
            'action': 'stay',
            'votes_stay': votes['stay'],
            'votes_leave': votes['leave'],
            'total_players': len(all_players)
        })
        
        # Sprawdź czy wszyscy już zdecydowali
        decided = set(votes['stay'] + votes['leave'])
        all_decided = decided >= set(all_players)
        
        if all_decided:
            return await _finalize_lobby_return(game_id, lobby_data, votes, redis)
        
        return {
            "success": True,
            "message": "Głos zapisany - zostajesz w lobby",
            "your_choice": "stay",
            "votes_stay": votes['stay'],
            "votes_leave": votes['leave'],
            "waiting": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in return_to_lobby: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{game_id}/leave-to-dashboard")
async def leave_to_dashboard(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    redis: RedisService = Depends(get_redis)
):
    """
    Opuść grę i wróć do dashboard po zakończeniu meczu.
    
    Args:
        game_id: ID gry
        current_user: Zalogowany użytkownik
        redis: Redis service
    
    Returns:
        dict: Status
    """
    try:
        lobby_data = await redis.get_lobby(game_id)
        if not lobby_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lobby nie znalezione"
            )
        
        player_id = current_user['username']
        user_id = current_user['id']
        
        # Sprawdź czy gra jest zakończona
        if lobby_data.get('status_partii') != 'ZAKONCZONA':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gra nie jest zakończona"
            )
        
        print(f"[Game] Gracz {player_id} opuszcza grę (dashboard)")
        
        # === SYSTEM GŁOSOWANIA ===
        votes_key = f"return_to_lobby_votes:{game_id}"
        votes_data = await redis.redis.get(votes_key)
        
        import json
        if votes_data:
            votes = json.loads(votes_data)
        else:
            votes = {'stay': [], 'leave': []}
        
        # Dodaj głos za wyjściem
        if player_id not in votes['leave']:
            votes['leave'].append(player_id)
            # Usuń z stay jeśli był
            if player_id in votes['stay']:
                votes['stay'].remove(player_id)
        
        await redis.redis.set(votes_key, json.dumps(votes), ex=120)
        
        # Pobierz listę wszystkich graczy
        all_players = [
            s['nazwa'] for s in lobby_data.get('slots', []) 
            if s.get('typ') in ['gracz', 'bot'] and s.get('nazwa')
        ]
        
        # Broadcast info o głosowaniu
        await manager.broadcast(game_id, {
            'type': 'return_to_lobby_vote',
            'player': player_id,
            'action': 'leave',
            'votes_stay': votes['stay'],
            'votes_leave': votes['leave'],
            'total_players': len(all_players)
        })
        
        # Sprawdź czy wszyscy już zdecydowali
        decided = set(votes['stay'] + votes['leave'])
        all_decided = decided >= set(all_players)
        
        if all_decided:
            return await _finalize_lobby_return(game_id, lobby_data, votes, redis)
        
        return {
            "success": True,
            "message": "Opuszczasz grę",
            "your_choice": "leave",
            "redirect": "/dashboard"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in leave_to_dashboard: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


async def _finalize_lobby_return(
    game_id: str,
    lobby_data: dict,
    votes: dict,
    redis: RedisService
):
    """
    Finalizuj powrót do lobby - usuń graczy którzy wychodzą,
    wybierz nowego hosta jeśli potrzeba.
    """
    import json
    
    staying_players = votes['stay']
    leaving_players = votes['leave']
    
    print(f"[Game] Finalizacja powrotu: zostają={staying_players}, wychodzą={leaving_players}")
    
    # Jeśli nikt nie zostaje, usuń lobby
    if not staying_players:
        await redis.delete_lobby(game_id)
        await redis.redis.delete(f"game_engine:{game_id}")
        await redis.redis.delete(f"return_to_lobby_votes:{game_id}")
        
        await manager.broadcast(game_id, {
            'type': 'lobby_closed',
            'reason': 'Wszyscy opuścili grę'
        })
        
        return {
            "success": True,
            "message": "Lobby zamknięte - wszyscy wyszli",
            "lobby_closed": True
        }
    
    # Usuń graczy którzy wychodzą ze slotów
    slots = lobby_data.get('slots', [])
    old_host_slot_idx = None
    
    for i, slot in enumerate(slots):
        if slot.get('is_host'):
            old_host_slot_idx = i
        
        if slot.get('nazwa') in leaving_players:
            # Opróżnij slot
            slot['typ'] = 'pusty'
            slot['id_uzytkownika'] = None
            slot['nazwa'] = None
            slot['is_host'] = False
            slot['ready'] = False
            slot['avatar_url'] = None
    
    # Sprawdź czy host został
    current_host_name = None
    for slot in slots:
        if slot.get('is_host') and slot.get('nazwa'):
            current_host_name = slot['nazwa']
            break
    
    # Jeśli host wyszedł, wybierz nowego (najbliżej starego slotu hosta)
    if not current_host_name:
        # Znajdź gracza najbliżej starego slotu hosta (zgodnie z ruchem gry)
        num_slots = len(slots)
        new_host_slot = None
        
        if old_host_slot_idx is not None:
            # Szukaj od następnego slotu (zgodnie z ruchem gry)
            for offset in range(1, num_slots + 1):
                check_idx = (old_host_slot_idx + offset) % num_slots
                slot = slots[check_idx]
                if slot.get('nazwa') in staying_players and slot.get('typ') == 'gracz':
                    new_host_slot = slot
                    break
        
        # Jeśli nie znaleziono gracza, weź pierwszego zostającego
        if not new_host_slot:
            for slot in slots:
                if slot.get('nazwa') in staying_players:
                    new_host_slot = slot
                    break
        
        if new_host_slot:
            new_host_slot['is_host'] = True
            lobby_data['host_id'] = new_host_slot.get('id_uzytkownika')
            print(f"[Game] Nowy host: {new_host_slot['nazwa']}")
    
    # Zresetuj gotowość wszystkich
    for slot in slots:
        if slot.get('typ') in ['gracz', 'bot']:
            slot['ready'] = False
    
    # Zmień status na LOBBY
    lobby_data['status_partii'] = 'LOBBY'
    
    # Zapisz lobby
    await redis.save_lobby(game_id, lobby_data)
    
    # Usuń silnik gry i głosy
    await redis.redis.delete(f"game_engine:{game_id}")
    await redis.redis.delete(f"return_to_lobby_votes:{game_id}")
    
    # Broadcast powrotu do lobby
    await manager.broadcast(game_id, {
        'type': 'returned_to_lobby',
        'lobby': lobby_data,
        'staying_players': staying_players,
        'leaving_players': leaving_players
    })
    
    return {
        "success": True,
        "message": "Powrót do lobby",
        "returned": True,
        "lobby": lobby_data,
        "staying_players": staying_players,
        "leaving_players": leaving_players
    }