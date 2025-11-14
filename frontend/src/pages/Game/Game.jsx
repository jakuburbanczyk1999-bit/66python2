import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { gameAPI, lobbyAPI } from '../../services/api'
import {
  LufaPanel,
  DeclarationPanel,
  PytaniePanel,
  LicytacjaPanel,
  DecyzjaPoLicytacjiPanel,
  RoundSummary,
  CardImage,
  InfoBox,
  ActionBubble,
  LicytacjaTysiacPanel,
  WymianaMuszkuPanel
} from './components'

function Game() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [gameState, setGameState] = useState(null)
  const [lobby, setLobby] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  
  // State dla widoczności musików na koniec
  const [showMusikCards, setShowMusikCards] = useState(false)
  const [hideRoundSummary, setHideRoundSummary] = useState(false)
  
  // State dla oddawania kart (Tysiąc 2p)
  const [selectedCardsToDiscard, setSelectedCardsToDiscard] = useState([])
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  // Action bubbles state
  const [actionBubbles, setActionBubbles] = useState([])
  
  // WebSocket state
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  // ============================================
  // LOAD GAME STATE
  // ============================================
  const loadGameState = async () => {
    try {
      const state = await gameAPI.getState(id)
      setGameState(state)
      setError(null)
    } catch (err) {
      console.error('❌ Błąd ładowania stanu gry:', err)
      setError('Nie udało się załadować stanu gry')
    }
  }

  const loadLobby = async () => {
    try {
      const data = await lobbyAPI.get(id)
      setLobby(data)
    } catch (err) {
      console.error('❌ Błąd ładowania lobby:', err)
    }
  }

  const loadChat = async () => {
    if (!lobby) return
    try {
      const response = await lobbyAPI.getChatMessages(id)
      setChatMessages(response || [])
    } catch (err) {
      console.error('Błąd ładowania czatu:', err)
    }
  }

  // ============================================
  // WEBSOCKET
  // ============================================
  
  // Funkcja do pokazywania dymków akcji z WebSocket
  const showActionBubbleFromWebSocket = (playerName, action, currentPhase, playersList) => {
    if (!playersList || playersList.length === 0) {
      console.log('🔍 Brak graczy dla dymku:', playerName)
      return
    }
    
    // Pokazuj dymki TYLKO w fazach licytacyjnych
    const licytacyjneFazy = ['DEKLARACJA_1', 'LUFA', 'FAZA_PYTANIA_START', 'LICYTACJA', 'FAZA_DECYZJI_PO_PASACH']
    if (!licytacyjneFazy.includes(currentPhase)) {
      console.log('🔍 Faza nie licytacyjna:', currentPhase)
      return
    }
    
    // Znajdź pozycję gracza
    const myIndex = playersList.findIndex(p => p.name === user?.username)
    const playerIndex = playersList.findIndex(p => p.name === playerName)
    
    if (myIndex === -1 || playerIndex === -1) {
      console.log('🔍 Nie znaleziono gracza:', playerName, 'myIndex:', myIndex, 'playerIndex:', playerIndex)
      return
    }
    
    const relativePos = (playerIndex - myIndex + 4) % 4
    const positions = ['bottom', 'left', 'top', 'right']
    const position = positions[relativePos]
    
    console.log('💬 Dodaję dymek:', playerName, action, position)
    
    // Dodaj dymek
    const bubbleId = Date.now() + Math.random()
    setActionBubbles(prev => [...prev, {
      id: bubbleId,
      action: action,
      playerPosition: position
    }])
    
    // Usuń dymek po 2.5s
    setTimeout(() => {
      setActionBubbles(prev => prev.filter(b => b.id !== bubbleId))
    }, 2500)
  }
  
  const connectWebSocket = () => {
    if (!user || !id) return
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return // Już połączony
    }
    
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//localhost:8000/ws/${id}/${user.username}`
      
      console.log('🔌 WebSocket: Łączenie...', wsUrl)
      
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('✅ WebSocket: Połączony!')
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('📨 WebSocket:', data.type)
          
          switch(data.type) {
            case 'connected':
              console.log('✅ WebSocket: Potwierdzenie połączenia')
              break
              
            case 'state_update':
              console.log('🔄 WebSocket: Aktualizacja stanu')
              if (data.data) {
                if (data.data.nazwa) setLobby(data.data)
                if (data.data.rozdanie) {
                  setGameState(data.data.rozdanie)
                }
              }
              break
              
            case 'action_performed':
              console.log('🎮 WebSocket: Akcja wykonana przez', data.player)
              console.log('🔍 data.action:', data.action)
              console.log('🔍 data.state:', data.state ? 'OK' : 'BRAK')
              console.log('🔍 data.state.faza:', data.state?.faza)
              console.log('🔍 data.state.rece_graczy:', data.state?.rece_graczy)
              
              // Pokaż dymek akcji (przed setGameState!)
              if (data.player && data.action && data.state) {
                // Wyciągnij players z state (z rece_graczy)
                const playersList = data.state.rece_graczy ? 
                  Object.keys(data.state.rece_graczy).map(name => ({
                    name: name,
                    is_bot: name.startsWith('Bot')
                  })) : []
                
                console.log('🎮 Players list:', playersList)
                showActionBubbleFromWebSocket(data.player, data.action, data.state.faza, playersList)
              } else {
                console.log('❌ Warunek nie spełniony:', {
                  player: !!data.player,
                  action: !!data.action,
                  state: !!data.state
                })
              }
              
              if (data.state) {
                setGameState(data.state)
              }
              break
              
            case 'bot_action':
              console.log('🤖 WebSocket: Akcja bota', data.player)
              console.log('🔍 data.action:', data.action)
              console.log('🔍 data.state:', data.state ? 'OK' : 'BRAK')
              console.log('🔍 data.state.faza:', data.state?.faza)
              console.log('🔍 data.state.rece_graczy:', data.state?.rece_graczy)
              
              // Pokaż dymek akcji bota (przed setGameState!)
              if (data.player && data.action && data.state) {
                // Wyciągnij players z state (z rece_graczy)
                const playersList = data.state.rece_graczy ? 
                  Object.keys(data.state.rece_graczy).map(name => ({
                    name: name,
                    is_bot: name.startsWith('Bot')
                  })) : []
                
                console.log('🤖 Players list:', playersList)
                showActionBubbleFromWebSocket(data.player, data.action, data.state.faza, playersList)
              } else {
                console.log('❌ Warunek nie spełniony:', {
                  player: !!data.player,
                  action: !!data.action,
                  state: !!data.state
                })
              }
              
              // Używaj stanu z WebSocket (bez HTTP request = natychmiastowa reakcja!)
              if (data.state) {
                setGameState(data.state)
              }
              break
              
            case 'trick_finalized':
              console.log('✅ WebSocket: Lewa sfinalizowana')
              if (data.state) {
                setGameState(data.state)
              }
              break
              
            case 'next_round_started':
              console.log('🔄 WebSocket: Nowa runda')
              if (data.state) {
                setGameState(data.state)
              }
              break
              
            case 'player_disconnected':
              console.log('👋 WebSocket: Gracz rozłączony', data.player)
              break
              
            case 'pong':
              // Odpowiedź na ping (keepalive)
              break
              
            default:
              console.log('⚠️ WebSocket: Nieznany typ:', data.type)
          }
        } catch (err) {
          console.error('❌ WebSocket: Błąd parsowania:', err)
        }
      }
      
      ws.onerror = (error) => {
        console.error('❌ WebSocket: Błąd połączenia:', error)
      }
      
      ws.onclose = (event) => {
        console.log('👋 WebSocket: Rozłączony (kod:', event.code, ')')
        wsRef.current = null
        
        // Reconnect tylko jeśli nie został celowo zamknięty (kod 1000)
        if (event.code !== 1000) {
          console.log('🔄 WebSocket: Ponowne łączenie za 3s...')
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket()
          }, 3000)
        }
      }
      
      wsRef.current = ws
    } catch (err) {
      console.error('❌ WebSocket: Błąd inicjalizacji:', err)
    }
  }
  
  const disconnectWebSocket = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close(1000) // 1000 = normalny close
      wsRef.current = null
    }
  }

  // ============================================
  // EXTRACT DATA FROM STATE (wcześniej, przed effectami)
  // ============================================
  // Wykryj typ gry
  const gameType = lobby?.opcje?.typ_gry || '66'
  const isTysiac = gameType === 'tysiac'
  
  console.log('🎮 Typ gry:', gameType, '| Tysiąc:', isTysiac)
  
  const players = lobby?.slots?.filter(s => s.typ !== 'pusty').map(s => ({
    name: s.nazwa,
    is_bot: s.typ === 'bot'
  })) || []

  // ============================================
  // EFFECTS
  // ============================================
  useEffect(() => {
    const initGame = async () => {
      await loadLobby()
      await loadGameState()
      setLoading(false)
    }
    
    initGame()
    
    // Włącz WebSocket dla real-time synchronizacji
    connectWebSocket()
    
    // Polling jako backup (co 10s) na wypadek problemów z WebSocket
    const interval = setInterval(loadGameState, 10000)
    
    // Cleanup
    return () => {
      clearInterval(interval)
      disconnectWebSocket()
    }
  }, [id])

  useEffect(() => {
    if (lobby) {
      loadChat()
    }
  }, [lobby])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // Effect do pokazywania musików na koniec gry (tryb 2p)
  useEffect(() => {
    if (isTysiac && players.length === 2 && gameState && gameState.faza === 'PODSUMOWANIE_ROZDANIA') {
      console.log('[MUSIK DEBUG] Podsumowanie rozdania - pokazuję karty')
      console.log('[MUSIK DEBUG] musik_1:', gameState.musik_1)
      console.log('[MUSIK DEBUG] musik_2:', gameState.musik_2)
      console.log('[MUSIK DEBUG] Array.isArray(musik_1):', Array.isArray(gameState.musik_1))
      console.log('[MUSIK DEBUG] Array.isArray(musik_2):', Array.isArray(gameState.musik_2))
      
      // Ukryj panel podsumowania na początek
      setHideRoundSummary(true)
      
      // Pokaż karty z musików
      setShowMusikCards(true)
      
      // Po 2 sekundach ukryj karty i pokaż panel podsumowania
      const timer = setTimeout(() => {
        setShowMusikCards(false)
        setHideRoundSummary(false)
      }, 2000)
      
      return () => clearTimeout(timer)
    } else {
      // Reset stanów gdy nie jesteśmy w podsumowaniu
      setShowMusikCards(false)
      setHideRoundSummary(false)
    }
  }, [isTysiac, players.length, gameState])

  // ============================================
  // GAME ACTIONS
  // ============================================
  const handlePlayCard = async (card) => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      const response = await gameAPI.play(id, {
        typ: 'zagraj_karte',
        karta: card
      })
      
      if (response?.state?.meldunek_pkt && response.state.meldunek_pkt > 0) {
        alert(`🎵 Meldunek! +${response.state.meldunek_pkt} punktów!`)
      }
      
      await loadGameState()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie można zagrać tej karty')
    } finally {
      setActionLoading(false)
    }
  }

  // Funkcja obsługi kliknięcia karty podczas oddawania (Tysiąc 2p)
  const handleCardClickForDiscard = (card) => {
    if (selectedCardsToDiscard.includes(card)) {
      // Odklikaj kartę
      setSelectedCardsToDiscard(selectedCardsToDiscard.filter(c => c !== card))
    } else if (selectedCardsToDiscard.length < 2) {
      // Dodaj kartę do wyboru
      setSelectedCardsToDiscard([...selectedCardsToDiscard, card])
    }
  }

  // Funkcja oddania wybranych kart
  const handleConfirmDiscard = async () => {
    if (selectedCardsToDiscard.length !== 2 || actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.play(id, { typ: 'oddaj_karty', karty: selectedCardsToDiscard })
      await loadGameState()
      setSelectedCardsToDiscard([]) // Reset
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd oddawania kart')
      setSelectedCardsToDiscard([]) // Reset on error
    } finally {
      setActionLoading(false)
    }
  }

  const handleBid = async (kontrakt, atut = null) => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.play(id, {
        typ: 'deklaracja',
        kontrakt,
        atut
      })
      await loadGameState()
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd deklaracji')
    } finally {
      setActionLoading(false)
    }
  }

  const handleLufaAction = async (action) => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.play(id, action)
      await loadGameState()
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd akcji lufy')
    } finally {
      setActionLoading(false)
    }
  }

  const handleFinalizeTrick = async () => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.finalizeTrick(id)
      await loadGameState()
    } catch (err) {
      console.error('Błąd finalizacji lewy:', err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleNextRound = async () => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.nextRound(id)
      await loadGameState()
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd rozpoczęcia nowej rundy')
    } finally {
      setActionLoading(false)
    }
  }

  // ============================================
  // CHAT
  // ============================================
  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!chatInput.trim() || chatLoading) return
    
    setChatLoading(true)
    try {
      await lobbyAPI.sendChatMessage(id, chatInput.trim())
      setChatInput('')
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się wysłać wiadomości')
    } finally {
      setChatLoading(false)
    }
  }

  // ============================================
  // RENDER HELPERS
  // ============================================
  const getSuitSymbol = (suit) => {
    // Obsługa null, undefined, pusty string, i "brak" (kompatybilność wsteczna)
    if (!suit || suit === 'Brak' || suit === 'brak') return ''
    
    // Mapowanie - obsługuje różne formaty nazw
    const symbols = {
      // Wszystkie wielkie
      'CZERWIEN': '♥️',
      'DZWONEK': '♦️', 
      'ZOLADZ': '♣️',
      'WINO': '♠️',
      // Pierwsza wielka (z silnika gry)
      'Czerwien': '♥️',
      'Dzwonek': '♦️',
      'Zoladz': '♣️',
      'Wino': '♠️'
    }
    
    return symbols[suit] || ''
  }

  // ============================================
  // LOADING / ERROR
  // ============================================
  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-300 text-xl">Ładowanie gry...</p>
        </div>
      </div>
    )
  }

  if (error || !gameState) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">❌</div>
          <h2 className="text-2xl font-bold text-white mb-2">Błąd</h2>
          <p className="text-gray-400 mb-6">{error || 'Gra nie znaleziona'}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg"
          >
            ← Wróć do Dashboard
          </button>
        </div>
      </div>
    )
  }

  // ============================================
  // EXTRACT DATA FROM STATE (reszta)
  // ============================================
  const myHand = gameState.rece_graczy?.[user?.username] || []
  const currentPhase = gameState.faza || 'UNKNOWN'
  const isMyTurn = gameState.kolej_gracza === user?.username
  const currentTrick = gameState.karty_na_stole || []
  const trumpSuit = gameState.kontrakt?.atut
  const canFinalizeTrick = gameState.lewa_do_zamkniecia
  const isRoundOver = currentPhase === 'PODSUMOWANIE_ROZDANIA'
  const roundSummary = gameState.podsumowanie
  const playableCards = gameState.grywalne_karty || []
  const currentContract = gameState.kontrakt?.typ
  const playingPlayer = gameState.gracz_grajacy
  const roundPoints = gameState.punkty_w_rozdaniu || {}
  const currentStake = gameState.aktualna_stawka || 0

  // Gracze ustawieni wokół stołu
  const myIndex = players.findIndex(p => p.name === user?.username)
  
  // Moja drużyna (gracze parzyści = Drużyna 1, nieparzyści = Drużyna 2)
  const myTeam = myIndex !== -1 && myIndex % 2 === 0 ? 'Drużyna 1' : 'Drużyna 2'
  
  const getOpponentAtPosition = (position) => {
    if (myIndex === -1) return null
    const targetIndex = (myIndex + position) % players.length
    return players[targetIndex]
  }

  const leftOpponent = isTysiac && players.length === 2 ? null : getOpponentAtPosition(1)
  const topOpponent = isTysiac && players.length === 2 ? players.find(p => p.name !== user?.username) || null : getOpponentAtPosition(2)
  const rightOpponent = isTysiac && players.length === 2 ? null : getOpponentAtPosition(3)

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a2736] via-[#1e3a52] to-[#1a2736] flex flex-col">
      {/* HEADER */}
      <div className="bg-[#1e2a3a]/80 backdrop-blur-sm border-b border-gray-700/50 p-3">
        <div className="flex items-center justify-between">
          {/* Lewy górny róg - Dashboard */}
          <button
            onClick={() => navigate('/dashboard')}
            className="px-3 py-2 bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-all text-sm"
          >
            ← Dashboard
          </button>
          
          {/* Środek - Nazwa gry */}
          <div className="flex items-center gap-2">
            <span className="text-2xl">🎴</span>
            <div>
              <h1 className="text-lg font-bold text-white">{lobby?.nazwa || 'Gra'}</h1>
              <p className="text-xs text-gray-400">Faza: {currentPhase}</p>
            </div>
          </div>

          {/* Prawy górny róg - Status */}
          <div className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full font-semibold text-sm">
            🎮 W grze
          </div>
        </div>
      </div>

      {/* MAIN GAME AREA */}
      <div className="flex-1 flex overflow-hidden">
        {/* GAME TABLE */}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="relative w-full max-w-6xl h-full max-h-[850px]">
            
            {/* GRACZ TOP */}
            {topOpponent && (
              <div className="absolute top-0 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
                {/* Dymki akcji */}
                {actionBubbles.filter(b => b.playerPosition === 'top').map(bubble => (
                  <ActionBubble
                    key={bubble.id}
                    action={bubble.action}
                    playerPosition="top"
                  />
                ))}

                <div className={`
                  ${gameState.kolej_gracza === topOpponent.name ? 'bg-yellow-500/20 border-yellow-500 shadow-lg shadow-yellow-500/20' : 'bg-gray-800/70 border-gray-700'}
                  border-2 rounded-xl p-2 backdrop-blur-sm transition-all flex items-center gap-2
                `}>
                  <div className="text-xl">
                    {topOpponent.is_bot ? '🤖' : '👤'}
                  </div>
                  <p className="text-white font-bold text-sm">{topOpponent.name}</p>
                </div>
                
                <div className="flex gap-1 flex-row">
                  {Array.from({ length: Math.min(
                    typeof gameState.rece_graczy?.[topOpponent.name] === 'number' 
                      ? gameState.rece_graczy[topOpponent.name] 
                      : 0
                  , isTysiac ? 10 : 6) }).map((_, idx) => (
                    <img 
                      key={idx}
                      src="/karty/rewers.png" 
                      alt="Karta" 
                      className="w-12 h-20 rounded-lg shadow-xl"
                    />
                  ))}
                </div>
              </div>
            )}

            {/* MUSIK LEFT - widoczny przez całą grę w trybie 2p */}
            {isTysiac && players.length === 2 && currentPhase !== 'PODSUMOWANIE_ROZDANIA' && (
              <div 
                onClick={() => {
                  // Klikalne tylko podczas wyboru musiku
                  if (currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn) {
                    console.log('🎴 Kliknięto Musik 1')
                    if (!actionLoading) {
                      handleLufaAction({ typ: 'wybierz_musik', musik: 1 })
                    }
                  }
                }}
                className={`absolute left-16 top-1/2 -translate-y-1/2 flex flex-col gap-2 z-50 ${
                  currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                    ? 'cursor-pointer group'
                    : ''
                }`}
              >
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-sm font-bold text-purple-400 mb-1 group-hover:text-purple-300 transition-colors">
                    Musik 1
                  </div>
                )}
                <div className={`flex flex-col gap-1 ${
                  currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                    ? 'group-hover:scale-105 transition-transform'
                    : ''
                }`}>
                  {showMusikCards && gameState?.musik_1 && Array.isArray(gameState.musik_1) ? (
                    // Pokaż karty z musiku (na koniec gry) z animacją
                    <div className="animate-pulse">
                      {gameState.musik_1.map((card, idx) => (
                        <CardImage key={idx} card={card} size="sm" />
                      ))}
                    </div>
                  ) : (
                    // Pokaż zakryte karty
                    [1, 2].map((idx) => (
                      <img 
                        key={idx}
                        src="/karty/rewers.png" 
                        alt="Musik 1" 
                        className={`w-14 h-22 rounded-lg shadow-xl ${
                          currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                            ? 'group-hover:shadow-purple-500/50 transition-shadow'
                            : ''
                        }`}
                      />
                    ))
                  )}
                </div>
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-xs text-gray-400 group-hover:text-purple-300 transition-colors">
                    ⬅ Kliknij
                  </div>
                )}
              </div>
            )}

            {/* MUSIK RIGHT - widoczny przez całą grę w trybie 2p */}
            {isTysiac && players.length === 2 && currentPhase !== 'PODSUMOWANIE_ROZDANIA' && (
              <div 
                onClick={() => {
                  // Klikalne tylko podczas wyboru musiku
                  if (currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn) {
                    console.log('🎴 Kliknięto Musik 2')
                    if (!actionLoading) {
                      handleLufaAction({ typ: 'wybierz_musik', musik: 2 })
                    }
                  }
                }}
                className={`absolute right-16 top-1/2 -translate-y-1/2 flex flex-col gap-2 z-50 ${
                  currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                    ? 'cursor-pointer group'
                    : ''
                }`}
              >
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-sm font-bold text-purple-400 mb-1 group-hover:text-purple-300 transition-colors">
                    Musik 2
                  </div>
                )}
                <div className={`flex flex-col gap-1 ${
                  currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                    ? 'group-hover:scale-105 transition-transform'
                    : ''
                }`}>
                  {showMusikCards && gameState?.musik_2 && Array.isArray(gameState.musik_2) ? (
                    // Pokaż karty z musiku (na koniec gry) z animacją
                    <div className="animate-pulse">
                      {gameState.musik_2.map((card, idx) => (
                        <CardImage key={idx} card={card} size="sm" />
                      ))}
                    </div>
                  ) : (
                    // Pokaż zakryte karty
                    [1, 2].map((idx) => (
                      <img 
                        key={idx}
                        src="/karty/rewers.png" 
                        alt="Musik 2" 
                        className={`w-14 h-22 rounded-lg shadow-xl ${
                          currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn
                            ? 'group-hover:shadow-purple-500/50 transition-shadow'
                            : ''
                        }`}
                      />
                    ))
                  )}
                </div>
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-xs text-gray-400 group-hover:text-purple-300 transition-colors">
                    Kliknij ➡
                  </div>
                )}
              </div>
            )}

            {/* GRACZ LEFT - tylko dla 3p/4p */}
            {leftOpponent && !(isTysiac && players.length === 2) && (
              <div className="absolute -left-28 top-1/2 -translate-y-1/2 flex flex-row items-center gap-2">
                {/* Dymki akcji */}
                {actionBubbles.filter(b => b.playerPosition === 'left').map(bubble => (
                  <ActionBubble
                    key={bubble.id}
                    action={bubble.action}
                    playerPosition="left"
                  />
                ))}

                <div className={`
                  ${gameState.kolej_gracza === leftOpponent.name ? 'bg-yellow-500/20 border-yellow-500 shadow-lg shadow-yellow-500/20' : 'bg-gray-800/70 border-gray-700'}
                  border-2 rounded-xl p-2 backdrop-blur-sm transition-all flex items-center gap-2
                `}>
                  <div className="text-xl">
                    {leftOpponent.is_bot ? '🤖' : '👤'}
                  </div>
                  <p className="text-white font-bold text-sm">{leftOpponent.name}</p>
                </div>
                
                <div className="flex gap-1 flex-col">
                  {Array.from({ length: Math.min(
                    typeof gameState.rece_graczy?.[leftOpponent.name] === 'number' 
                      ? gameState.rece_graczy[leftOpponent.name] 
                      : 0
                  , 6) }).map((_, idx) => (
                    <img 
                      key={idx}
                      src="/karty/rewers.png" 
                      alt="Karta" 
                      className="w-12 h-20 rounded-lg shadow-xl"
                    />
                  ))}
                </div>
              </div>
            )}

            {/* GRACZ RIGHT - tylko dla 3p/4p */}
            {rightOpponent && !(isTysiac && players.length === 2) && (
              <div className="absolute -right-28 top-1/2 -translate-y-1/2 flex flex-row items-center gap-2">
                <div className="flex gap-1 flex-col">
                  {Array.from({ length: Math.min(
                    typeof gameState.rece_graczy?.[rightOpponent.name] === 'number' 
                      ? gameState.rece_graczy[rightOpponent.name] 
                      : 0
                  , 6) }).map((_, idx) => (
                    <img 
                      key={idx}
                      src="/karty/rewers.png" 
                      alt="Karta" 
                      className="w-12 h-20 rounded-lg shadow-xl"
                    />
                  ))}
                </div>
                
                {/* Dymki akcji */}
                {actionBubbles.filter(b => b.playerPosition === 'right').map(bubble => (
                  <ActionBubble
                    key={bubble.id}
                    action={bubble.action}
                    playerPosition="right"
                  />
                ))}

                <div className={`
                  ${gameState.kolej_gracza === rightOpponent.name ? 'bg-yellow-500/20 border-yellow-500 shadow-lg shadow-yellow-500/20' : 'bg-gray-800/70 border-gray-700'}
                  border-2 rounded-xl p-2 backdrop-blur-sm transition-all flex items-center gap-2
                `}>
                  <div className="text-xl">
                    {rightOpponent.is_bot ? '🤖' : '👤'}
                  </div>
                  <p className="text-white font-bold text-sm">{rightOpponent.name}</p>
                </div>
              </div>
            )}

            {/* STÓŁ - CENTRALNY OBSZAR GRY */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-[60%] h-[50%] bg-gradient-to-br from-green-800/50 to-green-900/50 rounded-[2.5rem] border-4 border-green-700/40 shadow-2xl backdrop-blur-sm relative">
                
                {/* INFO O TURZE */}
                <div className="absolute top-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3">
                  {/* Wybór musiku w trybie 2p */}
                  {isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                    <div className="px-6 py-3 bg-purple-500/20 border-2 border-purple-500/50 rounded-lg animate-pulse">
                      <p className="text-purple-300 font-bold text-lg">🎴 Wybierz jeden z musików</p>
                      <p className="text-purple-200 text-sm mt-1">⬅ Kliknij na karty po bokach ➡</p>
                    </div>
                  )}
                  
                  {/* Standardowa info o turze */}
                  {isMyTurn && !isRoundOver && 
                   currentPhase !== 'DEKLARACJA_1' && 
                   currentPhase !== 'LUFA' && 
                   currentPhase !== 'FAZA_PYTANIA_START' && 
                   currentPhase !== 'LICYTACJA' && 
                   currentPhase !== 'FAZA_DECYZJI_PO_PASACH' && 
                   !(isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty) && 
                   !(isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty) && (
                    <div className="px-4 py-2 bg-yellow-500/20 border-2 border-yellow-500/50 rounded-lg animate-pulse">
                      <p className="text-yellow-300 font-bold">🎯 Twoja kolej!</p>
                    </div>
                  )}
                </div>

                {/* PANEL DEKLARACJI NA STOLE */}
                {currentPhase === 'DEKLARACJA_1' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <DeclarationPanel 
                      onDeclare={handleBid}
                      loading={actionLoading}
                    />
                  </div>
                )}

                {/* PANEL PYTANIA NA STOLE */}
                {currentPhase === 'FAZA_PYTANIA_START' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <PytaniePanel 
                      onAction={handleLufaAction}
                      loading={actionLoading}
                    />
                  </div>
                )}

                {/* PANEL LICYTACJI NA STOLE */}
                {currentPhase === 'LICYTACJA' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    {isTysiac ? (
                      <LicytacjaTysiacPanel 
                        onAction={handleLufaAction}
                        loading={actionLoading}
                        gameState={gameState}
                      />
                    ) : (
                      <LicytacjaPanel 
                        onAction={handleLufaAction}
                        loading={actionLoading}
                        gameState={gameState}
                      />
                    )}
                  </div>
                )}

                {/* PANEL WYMIANY MUSZKU - tylko dla 3p/4p (w 2p wszystko na stole) */}
                {currentPhase === 'WYMIANA_MUSZKU' && isMyTurn && isTysiac && players.length > 2 && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <WymianaMuszkuPanel 
                      onAction={handleLufaAction}
                      loading={actionLoading}
                      gameState={gameState}
                      myHand={myHand}
                    />
                  </div>
                )}

                {/* PANEL DECYZJI PO PASACH NA STOLE */}
                {currentPhase === 'FAZA_DECYZJI_PO_PASACH' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <DecyzjaPoLicytacjiPanel 
                      onAction={handleLufaAction}
                      loading={actionLoading}
                    />
                  </div>
                )}

                {/* PANEL LUFY NA STOLE */}
                {currentPhase === 'LUFA' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <LufaPanel 
                      onAction={handleLufaAction}
                      loading={actionLoading}
                      gameState={gameState}
                    />
                  </div>
                )}

                {/* KARTY NA STOLE */}
                {currentTrick.length > 0 && !isRoundOver && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="grid grid-cols-2 gap-6">
                      {currentTrick.map((play, idx) => (
                        <div key={idx} className="flex flex-col items-center gap-2">
                          <div className="px-3 py-1 bg-gray-900/80 rounded-full text-xs text-white font-semibold">
                            {play.gracz}
                          </div>
                          <CardImage card={play.karta} size="md" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* PRZYCISK FINALIZACJI LEWY - UKRYTY (finalizacja automatyczna) */}
                {/* Pozostawiono kod na wypadek przyszłych zmian */}
                {false && canFinalizeTrick && !isRoundOver && (
                  <div className="absolute bottom-6 left-1/2 -translate-x-1/2">
                    <button
                      onClick={handleFinalizeTrick}
                      disabled={actionLoading}
                      className="px-8 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white font-bold rounded-xl shadow-lg transition-all transform hover:scale-105"
                    >
                      ✅ Zakończ lewę
                    </button>
                  </div>
                )}

                {/* PODSUMOWANIE ROZDANIA - ukryj na 2 sekundy gdy pokazujemy musiki */}
                {isRoundOver && roundSummary && !hideRoundSummary && (
                  <RoundSummary 
                    summary={roundSummary} 
                    onNextRound={handleNextRound} 
                    loading={actionLoading}
                    myTeam={myTeam}
                  />
                )}
              </div>
            </div>

            {/* MOJA RĘKA - DÓŁ */}
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full">
              {/* Informacja o oddawaniu kart w trybie 2p */}
              {isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn && (
                <div className="text-center mb-3">
                  <div className="inline-flex items-center gap-4 px-6 py-3 bg-purple-500/20 border-2 border-purple-500/50 rounded-lg">
                    <div>
                      <p className="text-purple-300 font-bold text-lg">🎴 Oddaj 2 karty do musiku</p>
                      <p className="text-purple-200 text-sm mt-1">Kliknij 2 karty z ręki ⬇</p>
                      <p className="text-yellow-300 text-xs mt-1">✨ Złote ramki = karty z musiku</p>
                    </div>
                    {selectedCardsToDiscard.length === 2 && (
                      <button
                        onClick={handleConfirmDiscard}
                        disabled={actionLoading}
                        className="px-6 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white font-bold rounded-xl transition-all transform hover:scale-105 disabled:cursor-not-allowed"
                      >
                        {actionLoading ? '⏳' : '✅ Oddaj karty'}
                      </button>
                    )}
                  </div>
                  {selectedCardsToDiscard.length > 0 && (
                    <div className="mt-2 text-yellow-300 text-sm font-semibold animate-pulse">
                      Wybrano: {selectedCardsToDiscard.length}/2
                    </div>
                  )}
                </div>
              )}
              
              <div className="flex justify-center gap-2 pb-4">
                {myHand.length > 0 ? (
                  myHand.map((card, idx) => {
                    const isPlayable = playableCards.includes(card)
                    
                    // W trybie oddawania kart (2p, musik odkryty) - sprawdź które karty są z musiku
                    const kartyZMusiku = gameState?.karty_z_musiku || []
                    const isFromMusik = isTysiac && players.length === 2 && 
                                       currentPhase === 'WYMIANA_MUSZKU' && 
                                       gameState?.musik_odkryty && 
                                       kartyZMusiku.includes(card)
                    
                    return (
                      <CardImage
                        key={idx}
                        card={card}
                        size="lg"
                        onClick={() => {
                          // W trybie oddawania kart (2p Tysiąc)
                          if (isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn) {
                            handleCardClickForDiscard(card)
                          } else {
                            // Normalne zagranie karty
                            handlePlayCard(card)
                          }
                        }}
                        disabled={
                          !isMyTurn || 
                          actionLoading || 
                          (!isPlayable && currentPhase !== 'WYMIANA_MUSZKU') || 
                          currentPhase === 'DEKLARACJA_1' || 
                          currentPhase === 'LUFA' ||
                          currentPhase === 'FAZA_PYTANIA_START' ||
                          currentPhase === 'LICYTACJA' ||
                          currentPhase === 'FAZA_DECYZJI_PO_PASACH'
                        }
                        playable={
                          (isPlayable && 
                          currentPhase !== 'DEKLARACJA_1' && 
                          currentPhase !== 'LUFA' &&
                          currentPhase !== 'FAZA_PYTANIA_START' &&
                          currentPhase !== 'LICYTACJA' &&
                          currentPhase !== 'FAZA_DECYZJI_PO_PASACH') ||
                          (isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn)
                        }
                        highlight={isFromMusik}
                        selected={isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn && selectedCardsToDiscard.includes(card)}
                      />
                    )
                  })
                ) : (
                  <div className="text-gray-400 text-center py-8">
                    <p>Brak kart w ręce</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* SIDEBAR */}
        <aside className="w-64 bg-[#1e2a3a]/80 backdrop-blur-sm border-l border-gray-700/50 flex flex-col">
          {/* INFORMACJE (z punktami rozdania) */}
          <div className="p-3 border-b border-gray-700/50">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Informacje</h3>
            <div className="space-y-1.5">
              {isTysiac ? (
                // Info dla Tysiąca
                <>
                  {gameState?.kontrakt_wartosc > 0 && (
                    <InfoBox 
                      label="Kontrakt" 
                      value={`${gameState.kontrakt_wartosc}`}
                      color="blue" 
                    />
                  )}
                  {gameState?.atut && (
                    <InfoBox 
                      label="Atut" 
                      value={getSuitSymbol(gameState.atut)}
                      color="red" 
                    />
                  )}
                  {playingPlayer && (
                    <InfoBox label="Grający" value={playingPlayer} color="yellow" />
                  )}
                  {gameState?.muzyk_idx !== null && gameState?.muzyk_idx !== undefined && (
                    <InfoBox 
                      label="Muzyk" 
                      value={players[gameState.muzyk_idx]?.name || 'Brak'}
                      color="purple" 
                    />
                  )}
                </>
              ) : (
                // Info dla 66 (oryginalny kod)
                <>
                  {currentContract && (
                    <InfoBox 
                      label="Kontrakt" 
                      value={
                        trumpSuit 
                          ? `${currentContract} ${getSuitSymbol(trumpSuit)}`.trim()
                          : currentContract
                      } 
                      color="blue" 
                    />
                  )}
                  {playingPlayer && (
                    <InfoBox label="Gra" value={playingPlayer} color="yellow" />
                  )}
                  {currentStake > 0 && (
                    <InfoBox label="Stawka" value={`${currentStake} pkt`} color="green" />
                  )}
                </>
              )}
              
              {/* Punkty w rozdaniu - jako część Informacji */}
              {/* Ukryj dla kontraktów Lepsza/Gorsza i dla Tysiąca */}
              {!isTysiac && Object.keys(roundPoints).length > 0 && currentContract !== 'LEPSZA' && currentContract !== 'GORSZA' && (
                <div className="mt-2 pt-2 border-t border-gray-700/30">
                  <p className="text-xs text-gray-500 uppercase mb-1.5">Punkty w rozdaniu</p>
                  {(() => {
                    const teams = Object.entries(roundPoints);
                    if (teams.length === 2) {
                      return (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-teal-400 font-semibold">{teams[0][0]}</span>
                          <span className={`font-bold ${
                            teams[0][1] >= 66 || teams[1][1] >= 66 ? 'text-green-400' : 'text-white'
                          }`}>
                            {teams[0][1]} : {teams[1][1]}
                          </span>
                          <span className="text-pink-400 font-semibold">{teams[1][0]}</span>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>
              )}
              
              {/* Punkty w rozdaniu dla Tysiąca (indywidualne) */}
              {isTysiac && Object.keys(roundPoints).length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-700/30">
                  <p className="text-xs text-gray-500 uppercase mb-1.5">Punkty w rozdaniu</p>
                  <div className="space-y-1">
                    {Object.entries(roundPoints).map(([name, points]) => (
                      <div key={name} className="flex justify-between text-xs">
                        <span className={name === user?.username ? 'text-teal-400' : 'text-gray-300'}>
                          {name}
                        </span>
                        <span className="text-white font-bold">{points}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* GRACZE (2 kolumny dla 66, lista dla Tysiąca) */}
          <div className="p-3 border-b border-gray-700/50">
            {isTysiac ? (
              // Tysiąc - prosta lista (bez drużyn)
              <>
                <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Gracze</h3>
                <div className="space-y-1">
                  {players.map((player, idx) => (
                    <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                      <div className="flex items-center gap-1">
                        <span className="text-xs">{player.is_bot ? '🤖' : '👤'}</span>
                        <span className={`font-medium text-xs truncate ${
                          player.name === user?.username ? 'text-teal-400' : 'text-white'
                        }`}>
                          {player.name}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">
                          {gameState.punkty_meczowe?.[player.name] || 0}
                        </span>
                        {gameState.kolej_gracza === player.name && (
                          <span className="text-yellow-400 text-xs">⏱️</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              // 66 - 2 kolumny (drużyny)
              <>
                {/* Nagłówki drużyn */}
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div className="text-xs text-teal-400 font-semibold">Drużyna 1</div>
                  <div className="text-xs text-pink-400 font-semibold">Drużyna 2</div>
                </div>
                
                {/* Gracze w 2 kolumnach */}
                <div className="grid grid-cols-2 gap-2">
                  {/* Kolumna 1 - Drużyna 1 */}
                  <div className="space-y-1">
                    {players.filter((_, idx) => idx % 2 === 0).map((player, idx) => (
                      <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                        <div className="flex items-center gap-1">
                          <span className="text-xs">{player.is_bot ? '🤖' : '👤'}</span>
                          <span className={`font-medium text-xs truncate ${
                            player.name === user?.username ? 'text-teal-400' : 'text-white'
                          }`}>
                            {player.name}
                          </span>
                        </div>
                        {gameState.kolej_gracza === player.name && (
                          <span className="text-yellow-400 text-xs">⏱️</span>
                        )}
                      </div>
                    ))}
                  </div>
                  
                  {/* Kolumna 2 - Drużyna 2 */}
                  <div className="space-y-1">
                    {players.filter((_, idx) => idx % 2 === 1).map((player, idx) => (
                      <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                        <div className="flex items-center gap-1">
                          <span className="text-xs">{player.is_bot ? '🤖' : '👤'}</span>
                          <span className={`font-medium text-xs truncate ${
                            player.name === user?.username ? 'text-teal-400' : 'text-white'
                          }`}>
                            {player.name}
                          </span>
                        </div>
                        {gameState.kolej_gracza === player.name && (
                          <span className="text-yellow-400 text-xs">⏱️</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* PUNKTY W MECZU */}
          <div className="p-3 border-b border-gray-700/50">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Punkty w meczu</h3>
            {isTysiac ? (
              // Tysiąc - punkty indywidualne (do 1000)
              <div className="space-y-1.5">
                {players.map((player, idx) => {
                  const punkty = gameState.punkty_meczowe?.[player.name] || 0
                  const progress = (punkty / 1000) * 100
                  
                  return (
                    <div key={idx} className="p-2 rounded-lg bg-gray-800/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-xs font-semibold ${
                          player.name === user?.username ? 'text-teal-400' : 'text-white'
                        }`}>
                          {player.name}
                        </span>
                        <span className="text-yellow-400 font-bold text-sm">
                          {punkty}
                        </span>
                      </div>
                      {/* Progress bar */}
                      <div className="w-full bg-gray-700/50 rounded-full h-1.5">
                        <div 
                          className="bg-gradient-to-r from-teal-500 to-yellow-500 h-1.5 rounded-full transition-all"
                          style={{ width: `${Math.min(progress, 100)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
                <div className="text-center text-xs text-gray-500 mt-2">
                  🏆 Cel: 1000 punktów
                </div>
              </div>
            ) : (
              // 66 - punkty drużynowe
              (() => {
                const teams = gameState.punkty_meczowe ? Object.entries(gameState.punkty_meczowe) : [];
                if (teams.length === 2) {
                  return (
                    <div className="flex items-center justify-between p-2 rounded-lg bg-gradient-to-r from-gray-800/70 to-gray-800/30">
                      <span className="text-teal-400 font-semibold text-sm">{teams[0][0]}</span>
                      <span className="text-2xl font-bold text-yellow-400">
                        {teams[0][1]} : {teams[1][1]}
                      </span>
                      <span className="text-pink-400 font-semibold text-sm">{teams[1][0]}</span>
                    </div>
                  );
                }
                return <p className="text-gray-500 text-sm text-center py-2">Brak danych</p>;
              })()
            )}
          </div>

          {/* CHAT */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="p-3 border-b border-gray-700/50 flex-shrink-0">
              <h3 className="text-xs font-semibold text-gray-400 uppercase">Czat</h3>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-1.5 min-h-0">
              {chatMessages.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">Brak wiadomości</p>
              ) : (
                chatMessages.map(msg => (
                  <div key={msg.id} className={`text-sm break-words ${msg.is_system ? 'text-center text-gray-400 italic py-1' : ''}`}>
                    {msg.is_system ? (
                      <span>📢 {msg.message}</span>
                    ) : (
                      <div className="break-words">
                        <span className="text-teal-400 font-semibold break-all">{msg.username}</span>
                        <span className="text-gray-600 text-xs ml-2">
                          {new Date(msg.timestamp * 1000).toLocaleTimeString('pl-PL', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </span>
                        <p className="text-white mt-0.5 break-words">{msg.message}</p>
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            <form onSubmit={handleSendMessage} className="p-3 border-t border-gray-700/50 flex-shrink-0">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Wpisz wiadomość..."
                  disabled={chatLoading}
                  maxLength={500}
                  className="flex-1 px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim() || chatLoading}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg text-sm font-semibold transition-all"
                >
                  {chatLoading ? '...' : '→'}
                </button>
              </div>
            </form>
          </div>
        </aside>
      </div>
    </div>
  )
}

export default Game