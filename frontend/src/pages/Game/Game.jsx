import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { gameAPI, lobbyAPI, statsAPI } from '../../services/api'
import {
  LufaPanel,
  DeclarationPanel,
  PytaniePanel,
  LicytacjaPanel,
  DecyzjaPoLicytacjiPanel,
  RoundSummary,
  RoundSummaryTysiac,
  CardImage,
  InfoBox,
  ActionBubble,
  LicytacjaTysiacPanel,
  WymianaMuszkuPanel,
  DecyzjaPoMusikuPanel
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
  
  // State dla oddawania kart (Tysiąc 2p)
  const [selectedCardsToDiscard, setSelectedCardsToDiscard] = useState([])
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  // Action bubbles state
  const [actionBubbles, setActionBubbles] = useState([])
  
  // Disconnect state
  const [disconnectedPlayer, setDisconnectedPlayer] = useState(null)
  const [disconnectTimer, setDisconnectTimer] = useState(0)
  const [forfeitInfo, setForfeitInfo] = useState(null)
  
  // Game ended state
  const [gameEndedInfo, setGameEndedInfo] = useState(null)
  
  // Voting state
  const [nextRoundVotes, setNextRoundVotes] = useState(null)
  const [returnToLobbyVotes, setReturnToLobbyVotes] = useState(null)
  const [hasVotedNextRound, setHasVotedNextRound] = useState(false)
  const [hasVotedReturnToLobby, setHasVotedReturnToLobby] = useState(false)
  
  // WebSocket state
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const heartbeatIntervalRef = useRef(null)
  const isMountedRef = useRef(true)
  const isConnectingRef = useRef(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [wsReconnectAttempts, setWsReconnectAttempts] = useState(0)

  // Rangi graczy
  const [playerRanks, setPlayerRanks] = useState({})

  // ============================================
  // LOAD GAME STATE
  // ============================================
  const loadGameState = async () => {
    try {
      const state = await gameAPI.getState(id)
      // Tylko aktualizuj jeśli mamy prawidłowy stan (nie nadpisuj pustym)
      if (state && (state.faza || state.rece_graczy)) {
        setGameState(state)
        setError(null)
        
        // Reset głosowania gdy faza to podsumowanie
        if (state.faza === 'PODSUMOWANIE_ROZDANIA') {
          setHasVotedNextRound(false)
          setNextRoundVotes(null)
        }
        
        // Sprawdź czy mecz jest zakończony (gracz wchodzi do zakończonej gry)
        if (state.faza === 'ZAKONCZONE' && state.podsumowanie?.mecz_zakonczony) {
          setGameEndedInfo({
            winner: state.podsumowanie.zwyciezca_meczu,
            finalScores: state.podsumowanie.punkty_meczowe_koncowe || state.punkty_meczowe || {}
          })
        }
      }
    } catch (err) {
      console.error('Błąd ładowania stanu gry:', err)
      // Nie ustawiaj błędu jeśli mamy już jakiś stan (zachowaj poprzedni)
      if (!gameState) {
        setError('Nie udało się załadować stanu gry')
      }
    }
  }

  const loadLobby = async () => {
    try {
      const data = await lobbyAPI.get(id)
      setLobby(data)
    } catch (err) {
      console.error('Błąd ładowania lobby:', err)
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
      return
    }
    
    // Pokazuj dymki TYLKO w fazach licytacyjnych
    const licytacyjneFazy = ['DEKLARACJA_1', 'LUFA', 'FAZA_PYTANIA_START', 'LICYTACJA', 'FAZA_DECYZJI_PO_PASACH']
    if (!licytacyjneFazy.includes(currentPhase)) {
      return
    }
    
    // Znajdź pozycję gracza
    const myIndex = playersList.findIndex(p => p.name === user?.username)
    const playerIndex = playersList.findIndex(p => p.name === playerName)
    
    if (myIndex === -1 || playerIndex === -1) {
      return
    }
    
    const numPlayers = playersList.length
    const relativePos = (playerIndex - myIndex + numPlayers) % numPlayers
    
    // Pozycje zależne od liczby graczy
    let position = 'bottom'
    if (numPlayers === 2) {
      // 2 graczy: ja (dół) + przeciwnik (góra)
      const positions2p = ['bottom', 'top']
      position = positions2p[relativePos] || 'bottom'
    } else if (numPlayers === 3) {
      // 3 graczy: ja (dół) + lewy + prawy
      const positions3p = ['bottom', 'left', 'right']
      position = positions3p[relativePos] || 'bottom'
    } else {
      // 4 graczy: ja (dół) + lewy + góra + prawy
      const positions4p = ['bottom', 'left', 'top', 'right']
      position = positions4p[relativePos] || 'bottom'
    }
    
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
    
    // Zapobiegaj wielokrotnym połączeniom
    if (isConnectingRef.current) {
      console.log('WebSocket: Już trwa łączenie, pomijam')
      return
    }
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }
    
    // Zamknij stare połączenie jeśli istnieje
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close(1000)
      wsRef.current = null
    }
    
    isConnectingRef.current = true
    
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host
      const wsUrl = `${protocol}//${host}/ws/${id}/${user.username}`
      
      console.log('WebSocket: Łączenie...', wsUrl)
      
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('WebSocket: Połączony')
        isConnectingRef.current = false
        setWsConnected(true)
        setWsReconnectAttempts(0)
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        
        // Uruchom heartbeat (ping co 30s)
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current)
        }
        heartbeatIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000)
        
        // Po ponownym połączeniu odśwież stan gry
        loadGameState()
      }
      
      ws.onmessage = (event) => {
        // Sprawdź czy komponent jest jeszcze zamontowany
        if (!isMountedRef.current) return
        
        try {
          const data = JSON.parse(event.data)
          
          switch(data.type) {
            case 'connected':
              break
              
            case 'state_update':
              if (data.data) {
                if (data.data.nazwa) setLobby(data.data)
                if (data.data.rozdanie && (data.data.rozdanie.faza || data.data.rozdanie.rece_graczy)) {
                  setGameState(data.data.rozdanie)
                  
                  // Reset głosowania gdy pojawia się nowe podsumowanie
                  if (data.data.rozdanie.faza === 'PODSUMOWANIE_ROZDANIA') {
                    setHasVotedNextRound(false)
                    setNextRoundVotes(null)
                  }
                }
              }
              break
              
            case 'action_performed':
              // Pokaż dymek akcji
              if (data.player && data.action && data.state) {
                const playersList = data.state.rece_graczy ? 
                  Object.keys(data.state.rece_graczy).map(name => ({
                    name: name,
                    is_bot: name.startsWith('Bot')
                  })) : []
                
                showActionBubbleFromWebSocket(data.player, data.action, data.state.faza, playersList)
              }
              // NIE aktualizuj gameState - pełny stan przyjdzie w state_update
              break
              
            case 'bot_action':
              // Pokaż dymek akcji
              if (data.player && data.action && data.state) {
                const playersList = data.state.rece_graczy ? 
                  Object.keys(data.state.rece_graczy).map(name => ({
                    name: name,
                    is_bot: name.startsWith('Bot')
                  })) : []
                
                showActionBubbleFromWebSocket(data.player, data.action, data.state.faza, playersList)
              }
              // NIE aktualizuj gameState z bot_action - pełny stan przyjdzie w state_update
              break
              
            case 'trick_finalized':
              // Stan przyjdzie osobno w state_update
              // Można tu dodać animację lub dźwięk finalizacji lewy
              break
              
            case 'next_round_started':
              // Stan przyjdzie osobno w state_update
              // Wyczyść głosy i reset stanu głosowania
              setNextRoundVotes(null)
              setHasVotedNextRound(false)
              break
              
            case 'next_round_vote':
              // Aktualizuj stan głosowania
              setNextRoundVotes({
                votes: data.votes || [],
                totalPlayers: data.total_players,
                readyPlayers: data.ready_players || []
              })
              break
              
            case 'return_to_lobby_vote':
              // Aktualizuj stan głosowania za powrotem (nowy format)
              setReturnToLobbyVotes({
                votesStay: data.votes_stay || [],
                votesLeave: data.votes_leave || [],
                totalPlayers: data.total_players
              })
              break
              
            case 'returned_to_lobby':
              // Powrót do lobby - sprawdź czy ja zostałem
              if (data.staying_players?.includes(user?.username)) {
                navigate(`/lobby/${id}`)
              } else if (data.leaving_players?.includes(user?.username)) {
                navigate('/dashboard')
              } else {
                // Fallback - przekieruj do lobby
                navigate(`/lobby/${id}`)
              }
              break
            
            case 'lobby_closed':
              // Lobby zamknięte - wszyscy wyszli
              navigate('/dashboard')
              break
            
            case 'player_staying':
              // Gracz (lub bot) kliknął "zostań w lobby" - ignorujemy, czekamy na returned_to_lobby
              console.log('Gracz zostaje:', data.player)
              break
            
            case 'player_leaving':
              // Gracz kliknął "dashboard" - ignorujemy, czekamy na returned_to_lobby
              console.log('Gracz wychodzi:', data.player)
              break
              
            case 'player_disconnected':
              // Gracz się rozłączył - pokaż timer
              if (data.player && data.player !== user?.username) {
                setDisconnectedPlayer(data.player)
                setDisconnectTimer(data.reconnect_timeout || 60)
              }
              break
              
            case 'player_reconnected':
              // Gracz wrócił - ukryj timer
              if (data.player === disconnectedPlayer) {
                setDisconnectedPlayer(null)
                setDisconnectTimer(0)
              }
              break
              
            case 'player_left':
              // Gracz opuścił lobby (nie w grze)
              break
              
            case 'game_forfeit':
              // Gra zakończona walkowerem
              setForfeitInfo({
                disconnectedPlayer: data.disconnected_player,
                winners: data.winners,
                reason: data.reason
              })
              setDisconnectedPlayer(null)
              setDisconnectTimer(0)
              break
            
            case 'game_ended':
              // Mecz zakończony - ktoś osiągnął 66 punktów
              console.log('🏆 Mecz zakończony!', data)
              setGameEndedInfo({
                winner: data.winner,
                finalScores: data.final_scores
              })
              break
              
            case 'pong':
              break
              
            default:
              console.log('WebSocket: Nieznany typ:', data.type)
          }
        } catch (err) {
          console.error('WebSocket: Błąd parsowania:', err)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket: Błąd połączenia:', error)
        isConnectingRef.current = false
        setWsConnected(false)
      }
      
      ws.onclose = (event) => {
        console.log('WebSocket: Rozłączony (kod:', event.code, ')')
        wsRef.current = null
        isConnectingRef.current = false
        setWsConnected(false)
        
        // Reconnect tylko jeśli komponent jest zamontowany i nie było to zamierzone zamknięcie
        if (isMountedRef.current && event.code !== 1000) {
          setWsReconnectAttempts(prev => prev + 1)
          const delay = Math.min(3000 * Math.pow(1.5, wsReconnectAttempts), 30000) // exponential backoff, max 30s
          console.log(`WebSocket: Ponowne łączenie za ${Math.round(delay/1000)}s... (próba ${wsReconnectAttempts + 1})`)
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              connectWebSocket()
            }
          }, delay)
        }
      }
      
      wsRef.current = ws
    } catch (err) {
      console.error('WebSocket: Błąd inicjalizacji:', err)
      isConnectingRef.current = false
    }
  }
  
  const manualReconnectWebSocket = () => {
    console.log('WebSocket: Ręczne ponowne łączenie...')
    setWsReconnectAttempts(0)
    disconnectWebSocket()
    setTimeout(() => {
      if (isMountedRef.current) {
        connectWebSocket()
      }
    }, 500)
  }
  
  const disconnectWebSocket = () => {
    // Najpierw wyczyść timeout reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    // Wyczyść heartbeat
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
    
    // Reset flag
    isConnectingRef.current = false
    
    // Zamknij WebSocket
    if (wsRef.current) {
      // Usuń handlery żeby uniknąć callbacks po zamknięciu
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
      wsRef.current.onopen = null
      
      if (wsRef.current.readyState === WebSocket.OPEN || 
          wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close(1000)
      }
      wsRef.current = null
    }
  }

  // ============================================
  // EXTRACT DATA FROM STATE (wcześniej, przed effectami)
  // ============================================
  // Wykryj typ gry
  const gameType = lobby?.opcje?.typ_gry || '66'
  const isTysiac = gameType === 'tysiac'
  
  // Pobierz pełne dane slotów z lobby
  const slots = lobby?.slots?.filter(s => s.typ !== 'pusty') || []
  const hostName = lobby?.host
  
  const players = slots.map((s, idx) => ({
    name: s.nazwa,
    is_bot: s.typ === 'bot',
    is_host: s.nazwa === hostName,
    is_admin: s.nazwa === user?.username && user?.is_admin,
    team: !isTysiac ? (idx % 2 === 0 ? 1 : 2) : null
  }))
  
  // Helper do generowania przedrostków gracza
  const getPlayerPrefix = (player, showTeam = false) => {
    const prefixes = []
    if (player.is_bot) prefixes.push('Bot')
    if (player.is_admin) prefixes.push('Admin')
    if (player.is_host && !player.is_bot) prefixes.push('Host')
    if (showTeam && player.team) prefixes.push(`Dr. ${player.team}`)
    return prefixes.length > 0 ? prefixes.join(' · ') : null
  }

  // ============================================
  // EFFECTS
  // ============================================
  useEffect(() => {
    // Ustaw flagę montowania
    isMountedRef.current = true
    
    const initGame = async () => {
      await loadLobby()
      await loadGameState()
      if (isMountedRef.current) {
        setLoading(false)
      }
    }
    
    initGame()
    
    // Małe opóźnienie przed połączeniem WebSocket (zapobiega race condition w Strict Mode)
    const wsTimeout = setTimeout(() => {
      if (isMountedRef.current) {
        connectWebSocket()
      }
    }, 100)
    
    const interval = setInterval(() => {
      if (isMountedRef.current) {
        loadGameState()
      }
    }, 10000)
    
    return () => {
      // Oznacz jako odmontowany PRZED czyszczeniem
      isMountedRef.current = false
      clearTimeout(wsTimeout)
      clearInterval(interval)
      disconnectWebSocket()
    }
  }, [id])

  useEffect(() => {
    if (lobby) {
      loadChat()
    }
  }, [lobby])

  // Pobierz rangi graczy
  const slotsKey = JSON.stringify(lobby?.slots?.map(s => s.nazwa).filter(Boolean) || [])
  useEffect(() => {
    const loadRanks = async () => {
      if (!lobby?.slots) return
      
      const usernames = lobby.slots
        .filter(s => s.typ !== 'pusty' && s.nazwa)
        .map(s => s.nazwa)
      
      if (usernames.length === 0) return
      
      try {
        const data = await statsAPI.getRanksBatch(usernames)
        console.log('Rangi pobrane (gra):', data)
        setPlayerRanks(data.ranks || {})
      } catch (err) {
        console.error('Błąd pobierania rang:', err)
      }
    }
    
    loadRanks()
  }, [slotsKey])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // Timer dla rozłączonego gracza
  useEffect(() => {
    if (disconnectTimer > 0) {
      const interval = setInterval(() => {
        setDisconnectTimer(prev => Math.max(0, prev - 1))
      }, 1000)
      return () => clearInterval(interval)
    }
  }, [disconnectTimer > 0])

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
        alert(`Meldunek! +${response.state.meldunek_pkt} punktów!`)
      }
      
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie można zagrać tej karty')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCardClickForDiscard = (card) => {
    if (selectedCardsToDiscard.includes(card)) {
      setSelectedCardsToDiscard(selectedCardsToDiscard.filter(c => c !== card))
    } else if (selectedCardsToDiscard.length < 2) {
      setSelectedCardsToDiscard([...selectedCardsToDiscard, card])
    }
  }

  const handleConfirmDiscard = async () => {
    if (selectedCardsToDiscard.length !== 2 || actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.play(id, { typ: 'oddaj_karty', karty: selectedCardsToDiscard })
      setSelectedCardsToDiscard([])
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd oddawania kart')
      setSelectedCardsToDiscard([])
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
    } catch (err) {
      console.error('Błąd finalizacji lewy:', err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleNextRound = async () => {
    if (actionLoading || hasVotedNextRound) return
    
    setActionLoading(true)
    try {
      const response = await gameAPI.nextRound(id)
      
      // Oznacz że zagłosowaliśmy
      setHasVotedNextRound(true)
      
      // Sprawdź czy mecz się zakończył
      if (response?.game_ended) {
        setGameEndedInfo({
          winner: response.winner,
          finalScores: response.state?.punkty_meczowe_koncowe || {}
        })
      }
      
      // Aktualizuj stan głosowania jeśli response zawiera info
      if (response?.votes) {
        setNextRoundVotes({
          votes: response.votes,
          totalPlayers: response.total_players,
          readyPlayers: response.ready_players || response.votes
        })
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd głosowania')
      setHasVotedNextRound(false)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReturnToLobby = async () => {
    if (actionLoading || hasVotedReturnToLobby) return
    
    setActionLoading(true)
    try {
      const response = await gameAPI.returnToLobby(id)
      
      // Oznacz że zagłosowaliśmy
      setHasVotedReturnToLobby(true)
      
      // Jeśli wróciliśmy do lobby, przekieruj
      if (response?.returned) {
        navigate(`/lobby/${id}`)
      }
      
      // Aktualizuj stan głosowania (nowy format)
      if (response?.votes_stay || response?.votes_leave) {
        setReturnToLobbyVotes({
          votesStay: response.votes_stay || [],
          votesLeave: response.votes_leave || [],
          totalPlayers: (response.votes_stay?.length || 0) + (response.votes_leave?.length || 0)
        })
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd głosowania')
      setHasVotedReturnToLobby(false)
    } finally {
      setActionLoading(false)
    }
  }

  const handleLeaveToDashboard = async () => {
    if (actionLoading) return
    
    setActionLoading(true)
    try {
      await gameAPI.leaveToDashboard(id)
      navigate('/dashboard')
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd wyjścia')
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
    if (!suit || suit === 'Brak' || suit === 'brak') return null
    
    const suits = {
      'CZERWIEN': { symbol: '♥', color: 'text-red-500' },
      'DZWONEK': { symbol: '♦', color: 'text-pink-400' },
      'ZOLADZ': { symbol: '♣', color: 'text-gray-400' },
      'WINO': { symbol: '♠', color: 'text-gray-800' },
      'Czerwien': { symbol: '♥', color: 'text-red-500' },
      'Dzwonek': { symbol: '♦', color: 'text-pink-400' },
      'Zoladz': { symbol: '♣', color: 'text-gray-400' },
      'Wino': { symbol: '♠', color: 'text-gray-800' }
    }
    
    return suits[suit] || null
  }

  // ============================================
  // LOADING / ERROR
  // ============================================
  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">...</div>
          <p className="text-gray-300 text-xl">Ładowanie gry...</p>
        </div>
      </div>
    )
  }

  if (error || !gameState) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Błąd</h2>
          <p className="text-gray-400 mb-6">{error || 'Gra nie znaleziona'}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg"
          >
            Wróć do Dashboard
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

  const myIndex = players.findIndex(p => p.name === user?.username)
  const myTeam = myIndex !== -1 && myIndex % 2 === 0 ? 'Drużyna 1' : 'Drużyna 2'
  
  const getOpponentAtPosition = (position) => {
    if (myIndex === -1) return null
    const targetIndex = (myIndex + position) % players.length
    return players[targetIndex]
  }

  // Logika pozycjonowania zależna od liczby graczy:
  // 2 graczy: ja (dół) + przeciwnik (góra)
  // 3 graczy: ja (dół) + lewy + prawy (bez góry!)
  // 4 graczy: ja (dół) + lewy + góra + prawy
  let leftOpponent = null
  let topOpponent = null  
  let rightOpponent = null
  
  if (players.length === 2) {
    // Tysiąc 2p lub inne 2-osobowe
    topOpponent = players.find(p => p.name !== user?.username) || null
  } else if (players.length === 3) {
    // 3-osobowe (66 lub Tysiąc) - lewy i prawy, BEZ góry
    leftOpponent = getOpponentAtPosition(1)
    rightOpponent = getOpponentAtPosition(2)
  } else if (players.length === 4) {
    // 4-osobowe - pełny układ
    leftOpponent = getOpponentAtPosition(1)
    topOpponent = getOpponentAtPosition(2)
    rightOpponent = getOpponentAtPosition(3)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a2736] via-[#1e3a52] to-[#1a2736] flex flex-col">
      {/* HEADER */}
      <div className="bg-[#1e2a3a]/80 backdrop-blur-sm border-b border-gray-700/50 p-3">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/dashboard')}
            className="px-3 py-2 bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-all text-sm"
          >
            ← Dashboard
          </button>
          
          <div className="flex items-center gap-2">
            <div>
              <h1 className="text-lg font-bold text-white">{lobby?.nazwa || 'Gra'}</h1>
              <p className="text-xs text-gray-400">Faza: {currentPhase}</p>
            </div>
          </div>

          <div className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full font-semibold text-sm">
            W grze
          </div>
        </div>
      </div>

      {/* MODAL WALKOWERA */}
      {forfeitInfo && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-[#1e2a3a] border-2 border-red-500/50 rounded-2xl p-8 max-w-md text-center shadow-2xl">
            <div className="text-6xl mb-4">🚫</div>
            <h2 className="text-2xl font-bold text-red-400 mb-4">Gra zakończona</h2>
            <p className="text-gray-300 mb-4">
              <span className="text-red-400 font-bold">{forfeitInfo.disconnectedPlayer}</span> opuścił grę
              <br />i nie wrócił w wyznaczonym czasie.
            </p>
            {forfeitInfo.winners?.length > 0 && (
              <div className="mb-6">
                <p className="text-green-400 font-bold text-lg">
                  🏆 Zwycięzcy: {forfeitInfo.winners.join(', ')}
                </p>
              </div>
            )}
            <button
              onClick={() => navigate('/dashboard')}
              className="px-8 py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl transition-all"
            >
              Wróć do Dashboard
            </button>
          </div>
        </div>
      )}

      {/* MODAL KOŃCA MECZU */}
      {gameEndedInfo && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-[#1e2a3a] border-2 border-yellow-500/50 rounded-2xl p-8 max-w-lg text-center shadow-2xl">
            <div className="text-6xl mb-4">🏆</div>
            <h2 className="text-3xl font-bold text-yellow-400 mb-2">Mecz zakończony!</h2>
            <p className="text-gray-300 mb-6 text-lg">
              Zwycięzca: <span className="text-green-400 font-bold">{gameEndedInfo.winner}</span>
            </p>
            
            {/* Końcowe punkty */}
            {gameEndedInfo.finalScores && (
              <div className="mb-6 p-4 bg-gray-800/50 rounded-xl">
                <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Końcowe punkty</h3>
                <div className="space-y-2">
                  {Object.entries(gameEndedInfo.finalScores).map(([name, points]) => (
                    <div 
                      key={name} 
                      className={`flex justify-between items-center p-2 rounded-lg ${
                        name === gameEndedInfo.winner 
                          ? 'bg-yellow-500/20 border border-yellow-500/50' 
                          : 'bg-gray-700/30'
                      }`}
                    >
                      <span className={`font-semibold ${
                        name === gameEndedInfo.winner ? 'text-yellow-400' : 'text-gray-300'
                      }`}>
                        {name === gameEndedInfo.winner && '🏆 '}{name}
                      </span>
                      <span className={`text-xl font-bold ${
                        name === gameEndedInfo.winner ? 'text-yellow-400' : 'text-white'
                      }`}>
                        {points} pkt
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Status głosowania za powrotem do lobby */}
            {returnToLobbyVotes && (
              <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
                <p className="text-sm text-gray-400 mb-2">Decyzje graczy:</p>
                <div className="space-y-2">
                  {returnToLobbyVotes.votesStay?.length > 0 && (
                    <div className="flex flex-wrap gap-2 justify-center">
                      <span className="text-xs text-gray-500">Zostają:</span>
                      {returnToLobbyVotes.votesStay.map((voter, idx) => (
                        <span key={idx} className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded-full">
                          ✓ {voter}
                        </span>
                      ))}
                    </div>
                  )}
                  {returnToLobbyVotes.votesLeave?.length > 0 && (
                    <div className="flex flex-wrap gap-2 justify-center">
                      <span className="text-xs text-gray-500">Wychodzą:</span>
                      {returnToLobbyVotes.votesLeave.map((voter, idx) => (
                        <span key={idx} className="px-2 py-1 bg-red-500/20 text-red-400 text-xs rounded-full">
                          ✗ {voter}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <div className="flex gap-3 justify-center">
              <button
                onClick={handleReturnToLobby}
                disabled={actionLoading || hasVotedReturnToLobby}
                className={`px-6 py-3 font-bold rounded-xl transition-all transform hover:scale-105 ${
                  hasVotedReturnToLobby 
                    ? 'bg-green-600 text-white cursor-default' 
                    : 'bg-teal-600 hover:bg-teal-700 text-white'
                } disabled:cursor-not-allowed`}
              >
                {actionLoading ? '...' : hasVotedReturnToLobby ? '✓ Zostajesz w lobby' : '🔄 Powrót do lobby'}
              </button>
              <button
                onClick={handleLeaveToDashboard}
                disabled={actionLoading}
                className="px-6 py-3 bg-gray-600 hover:bg-gray-700 text-white font-bold rounded-xl transition-all disabled:opacity-50"
              >
                {actionLoading ? '...' : '🚪 Wyjść'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BANNER BRAKU POŁĄCZENIA WEBSOCKET */}
      {!wsConnected && !loading && (
        <div className="bg-orange-500/20 border-b border-orange-500/50 p-2">
          <div className="flex items-center justify-center gap-3">
            <span className="text-xl animate-pulse">⚠️</span>
            <div className="text-center">
              <p className="text-orange-300 font-semibold text-sm">
                Brak połączenia WebSocket
              </p>
              <p className="text-orange-200 text-xs">
                Gra może działać wolniej. {wsReconnectAttempts > 0 && `Próba połączenia #${wsReconnectAttempts}...`}
              </p>
            </div>
            <button
              onClick={manualReconnectWebSocket}
              className="px-3 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg transition-all"
            >
              🔄 Połącz
            </button>
          </div>
        </div>
      )}

      {/* BANNER ROZŁĄCZENIA */}
      {disconnectedPlayer && !forfeitInfo && (
        <div className="bg-red-500/20 border-b border-red-500/50 p-3">
          <div className="flex items-center justify-center gap-4">
            <span className="text-2xl animate-pulse">⚠️</span>
            <div className="text-center">
              <p className="text-red-300 font-bold">
                {disconnectedPlayer} rozłączył się!
              </p>
              <p className="text-red-200 text-sm">
                Ma <span className="font-bold text-yellow-300">{disconnectTimer}s</span> na powrót
                {disconnectTimer <= 10 && <span className="text-red-400 ml-2 animate-pulse">!</span>}
              </p>
            </div>
            <div className="w-16 h-16 relative">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="32" cy="32" r="28"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                  className="text-gray-700"
                />
                <circle
                  cx="32" cy="32" r="28"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                  strokeDasharray={`${(disconnectTimer / 60) * 176} 176`}
                  className="text-red-500 transition-all"
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold">
                {disconnectTimer}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* MAIN GAME AREA */}
      <div className="flex-1 flex overflow-hidden">
        {/* GAME TABLE */}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="relative w-full max-w-6xl h-full max-h-[850px]">
            
            {/* GRACZ TOP */}
            {topOpponent && (
              <div className="absolute top-0 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
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
                  {getPlayerPrefix(topOpponent, !isTysiac) && (
                    <span className="text-xs text-gray-400">
                      {getPlayerPrefix(topOpponent, !isTysiac)}
                    </span>
                  )}
                  {getPlayerPrefix(topOpponent, !isTysiac) && <span className="text-gray-600">·</span>}
                  <p className="text-white font-bold text-sm">{playerRanks[topOpponent.name]?.emoji} {topOpponent.name}</p>
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
                  if (currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn) {
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
                  {[1, 2].map((idx) => (
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
                  ))}
                </div>
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-xs text-gray-400 group-hover:text-purple-300 transition-colors">
                    Kliknij
                  </div>
                )}
              </div>
            )}

            {/* MUSIK RIGHT - widoczny przez całą grę w trybie 2p */}
            {isTysiac && players.length === 2 && currentPhase !== 'PODSUMOWANIE_ROZDANIA' && (
              <div 
                onClick={() => {
                  if (currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn) {
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
                  {[1, 2].map((idx) => (
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
                  ))}
                </div>
                {currentPhase === 'WYMIANA_MUSZKU' && !gameState?.musik_odkryty && !gameState?.musik_wybrany && isMyTurn && (
                  <div className="text-center text-xs text-gray-400 group-hover:text-purple-300 transition-colors">
                    Kliknij
                  </div>
                )}
              </div>
            )}

            {/* GRACZ LEFT - tylko dla 3p/4p */}
            {leftOpponent && !(isTysiac && players.length === 2) && (
              <div className="absolute -left-28 top-1/2 -translate-y-1/2 flex flex-row items-center gap-2">
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
                  {getPlayerPrefix(leftOpponent, !isTysiac) && (
                    <span className="text-xs text-gray-400">
                      {getPlayerPrefix(leftOpponent, !isTysiac)}
                    </span>
                  )}
                  {getPlayerPrefix(leftOpponent, !isTysiac) && <span className="text-gray-600">·</span>}
                  <p className="text-white font-bold text-sm">{playerRanks[leftOpponent.name]?.emoji} {leftOpponent.name}</p>
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
                  {getPlayerPrefix(rightOpponent, !isTysiac) && (
                    <span className="text-xs text-gray-400">
                      {getPlayerPrefix(rightOpponent, !isTysiac)}
                    </span>
                  )}
                  {getPlayerPrefix(rightOpponent, !isTysiac) && <span className="text-gray-600">·</span>}
                  <p className="text-white font-bold text-sm">{playerRanks[rightOpponent.name]?.emoji} {rightOpponent.name}</p>
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
                      <p className="text-purple-300 font-bold text-lg">Wybierz jeden z musików</p>
                      <p className="text-purple-200 text-sm mt-1">Kliknij na karty po bokach</p>
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
                      <p className="text-yellow-300 font-bold">Twoja kolej!</p>
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
                        canGiveLufa={(() => {
                          // Sprawdź czy jestem w innej drużynie niż grający
                          const myPlayer = players.find(p => p.name === user?.username)
                          const playingPlayerObj = players.find(p => p.name === playingPlayer)
                          if (!myPlayer || !playingPlayerObj) return false
                          return myPlayer.team !== playingPlayerObj.team
                        })()}
                      />
                    )}
                  </div>
                )}

                {/* PANEL WYMIANY MUSZKU - tylko dla 3p/4p */}
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

                {/* PANEL DECYZJI PO MUSIKU NA STOLE (Tysiąc 2p) */}
                {currentPhase === 'DECYZJA_PO_MUSIKU' && isMyTurn && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <DecyzjaPoMusikuPanel 
                      onAction={handleLufaAction}
                      loading={actionLoading}
                      gameState={gameState}
                    />
                  </div>
                )}

                {/* KARTY NA STOLE - pozycjonowane przy graczu który je zagrał */}
                {currentTrick.length > 0 && !isRoundOver && (
                  <>
                    {currentTrick.map((play, idx) => {
                      // Znajdź pozycję gracza który zagrał kartę
                      const playerIndex = players.findIndex(p => p.name === play.gracz)
                      const relativePos = myIndex !== -1 && playerIndex !== -1 
                        ? (playerIndex - myIndex + players.length) % players.length 
                        : 0
                      
                      // Pozycje kart na stole zależne od liczby graczy
                      let positionClass = ''
                      if (players.length === 2) {
                        // 2 graczy: dół i góra
                        positionClass = relativePos === 0 
                          ? 'bottom-[30%] left-1/2 -translate-x-1/2' 
                          : 'top-[30%] left-1/2 -translate-x-1/2'
                      } else if (players.length === 3) {
                        // 3 graczy: dół, lewy, prawy (BEZ góry!)
                        const positions3p = [
                          'bottom-[25%] left-1/2 -translate-x-1/2',  // ja (dół)
                          'left-[25%] top-1/2 -translate-y-1/2',     // lewy
                          'right-[25%] top-1/2 -translate-y-1/2'     // prawy
                        ]
                        positionClass = positions3p[relativePos] || positions3p[0]
                      } else {
                        // 4 graczy: dół, lewy, góra, prawy
                        const positions4p = [
                          'bottom-[25%] left-1/2 -translate-x-1/2',  // ja (dół)
                          'left-[25%] top-1/2 -translate-y-1/2',     // lewy
                          'top-[25%] left-1/2 -translate-x-1/2',     // góra
                          'right-[25%] top-1/2 -translate-y-1/2'     // prawy
                        ]
                        positionClass = positions4p[relativePos] || positions4p[0]
                      }
                      
                      return (
                        <div 
                          key={idx} 
                          className={`absolute ${positionClass} z-10`}
                        >
                          <CardImage card={play.karta} size="md" />
                        </div>
                      )
                    })}
                  </>
                )}

                {/* PODSUMOWANIE ROZDANIA */}
                {isRoundOver && roundSummary && (
                  isTysiac ? (
                    <RoundSummaryTysiac
                      gameState={gameState}
                      onNextRound={handleNextRound}
                      loading={actionLoading}
                      user={user}
                      hasVoted={hasVotedNextRound}
                      votes={nextRoundVotes}
                    />
                  ) : (
                    <RoundSummary 
                      summary={roundSummary} 
                      onNextRound={handleNextRound} 
                      loading={actionLoading}
                      myTeam={myTeam}
                      myName={user?.username}
                      playerCount={players.length}
                      hasVoted={hasVotedNextRound}
                      votes={nextRoundVotes}
                    />
                  )
                )}
              </div>
            </div>

            {/* MOJA RĘKA - DÓŁ */}
            <div className={`absolute bottom-0 left-1/2 -translate-x-1/2 w-full ${isRoundOver ? 'pointer-events-none' : ''}`}>
              {/* Informacja o oddawaniu kart w trybie 2p */}
              {isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn && (
                <div className="text-center mb-3">
                  <div className="inline-flex items-center gap-4 px-6 py-3 bg-purple-500/20 border-2 border-purple-500/50 rounded-lg">
                    <div>
                      <p className="text-purple-300 font-bold text-lg">Oddaj 2 karty do musiku</p>
                      <p className="text-purple-200 text-sm mt-1">Kliknij 2 karty z ręki</p>
                      <p className="text-yellow-300 text-xs mt-1">Złote ramki = karty z musiku</p>
                    </div>
                    {selectedCardsToDiscard.length === 2 && (
                      <button
                        onClick={handleConfirmDiscard}
                        disabled={actionLoading}
                        className="px-6 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white font-bold rounded-xl transition-all transform hover:scale-105 disabled:cursor-not-allowed"
                      >
                        {actionLoading ? '...' : 'Oddaj karty'}
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
              
              <div className="flex justify-center gap-2 pb-2">
                {myHand.length > 0 ? (
                  myHand.map((card, idx) => {
                    const isPlayable = playableCards.includes(card)
                    
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
                          if (isTysiac && players.length === 2 && currentPhase === 'WYMIANA_MUSZKU' && gameState?.musik_odkryty && isMyTurn) {
                            handleCardClickForDiscard(card)
                          } else {
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
                          currentPhase === 'FAZA_DECYZJI_PO_PASACH' ||
                          currentPhase === 'DECYZJA_PO_MUSIKU'
                        }
                        playable={
                          (isPlayable && 
                          currentPhase !== 'DEKLARACJA_1' && 
                          currentPhase !== 'LUFA' &&
                          currentPhase !== 'FAZA_PYTANIA_START' &&
                          currentPhase !== 'LICYTACJA' &&
                          currentPhase !== 'FAZA_DECYZJI_PO_PASACH' &&
                          currentPhase !== 'DECYZJA_PO_MUSIKU') ||
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
              
              {/* Moja nazwa pod kartami */}
              {(() => {
                const myPlayer = players.find(p => p.name === user?.username)
                const myPrefix = myPlayer ? getPlayerPrefix(myPlayer, !isTysiac) : null
                return (
                  <div className="flex justify-center mt-2">
                    <div className={`
                      ${isMyTurn ? 'bg-yellow-500/20 border-yellow-500' : 'bg-gray-800/70 border-gray-700'}
                      border-2 rounded-xl px-4 py-2 backdrop-blur-sm transition-all flex items-center gap-2
                    `}>
                      {myPrefix && (
                        <span className="text-xs text-gray-400">{myPrefix}</span>
                      )}
                      {myPrefix && <span className="text-gray-600">·</span>}
                      <span className="text-teal-400 font-bold text-sm">{playerRanks[user?.username]?.emoji} {user?.username}</span>
                    </div>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>

        {/* SIDEBAR */}
        <aside className="w-64 bg-[#1e2a3a]/80 backdrop-blur-sm border-l border-gray-700/50 flex flex-col">
          {/* INFORMACJE */}
          <div className="p-3 border-b border-gray-700/50">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Informacje</h3>
            <div className="space-y-1.5">
              {isTysiac ? (
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
                      value={
                        getSuitSymbol(gameState.atut) ? (
                          <span className={getSuitSymbol(gameState.atut).color}>
                            {getSuitSymbol(gameState.atut).symbol}
                          </span>
                        ) : '-'
                      }
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
                <>
                  {currentContract && (
                    <InfoBox 
                      label="Kontrakt" 
                      value={
                        trumpSuit && getSuitSymbol(trumpSuit) ? (
                          <span>
                            {currentContract}{' '}
                            <span className={getSuitSymbol(trumpSuit).color}>
                              {getSuitSymbol(trumpSuit).symbol}
                            </span>
                          </span>
                        ) : currentContract
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
              
              {/* Punkty w rozdaniu - wyświetlaj dla wszystkich typów gier */}
              {Object.keys(roundPoints).length > 0 && currentContract !== 'LEPSZA' && currentContract !== 'GORSZA' && (
                <div className="mt-2 pt-2 border-t border-gray-700/30">
                  <p className="text-xs text-gray-500 uppercase mb-1.5">Punkty w rozdaniu</p>
                  {players.length === 4 && !isTysiac ? (
                    // 66 4-osobowe - format drużynowy
                    (() => {
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
                    })()
                  ) : (
                    // Tysiąc lub 66 3-osobowe - format indywidualny
                    <div className="space-y-1">
                      {Object.entries(roundPoints).map(([name, points]) => (
                        <div key={name} className="flex justify-between text-xs">
                          <span className={name === user?.username ? 'text-teal-400' : 'text-gray-300'}>
                            {playerRanks[name]?.emoji} {name}
                          </span>
                          <span className="text-white font-bold">{points}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* GRACZE */}
          <div className="p-3 border-b border-gray-700/50">
            {isTysiac ? (
              <>
                <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Gracze</h3>
                <div className="space-y-1">
                  {players.map((player, idx) => (
                    <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                      <div className="flex items-center gap-1">
                        {getPlayerPrefix(player) && (
                          <span className="text-xs text-gray-500">{getPlayerPrefix(player)}</span>
                        )}
                        <span className={`font-medium text-xs truncate ${
                          player.name === user?.username ? 'text-teal-400' : 'text-white'
                        }`}>
                          {playerRanks[player.name]?.emoji} {player.name}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">
                          {gameState.punkty_meczowe?.[player.name] || 0}
                        </span>
                        {gameState.kolej_gracza === player.name && (
                          <span className="w-2 h-2 bg-yellow-400 rounded-full"></span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div className="text-xs text-teal-400 font-semibold">Drużyna 1</div>
                  <div className="text-xs text-pink-400 font-semibold">Drużyna 2</div>
                </div>
                
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    {players.filter((_, idx) => idx % 2 === 0).map((player, idx) => (
                      <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                        <div className="flex flex-col">
                          {getPlayerPrefix(player) && (
                            <span className="text-xs text-gray-500">{getPlayerPrefix(player)}</span>
                          )}
                          <span className={`font-medium text-xs truncate ${
                            player.name === user?.username ? 'text-teal-400' : 'text-white'
                          }`}>
                            {playerRanks[player.name]?.emoji} {player.name}
                          </span>
                        </div>
                        {gameState.kolej_gracza === player.name && (
                          <span className="w-2 h-2 bg-yellow-400 rounded-full"></span>
                        )}
                      </div>
                    ))}
                  </div>
                  
                  <div className="space-y-1">
                    {players.filter((_, idx) => idx % 2 === 1).map((player, idx) => (
                      <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-gray-800/50">
                        <div className="flex flex-col">
                          {getPlayerPrefix(player) && (
                            <span className="text-xs text-gray-500">{getPlayerPrefix(player)}</span>
                          )}
                          <span className={`font-medium text-xs truncate ${
                            player.name === user?.username ? 'text-teal-400' : 'text-white'
                          }`}>
                            {playerRanks[player.name]?.emoji} {player.name}
                          </span>
                        </div>
                        {gameState.kolej_gracza === player.name && (
                          <span className="w-2 h-2 bg-yellow-400 rounded-full"></span>
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
            {isTysiac || players.length === 3 ? (
              // Tysiąc lub 66 3-osobowe - punkty indywidualne
              <div className="space-y-1.5">
                {players.map((player, idx) => {
                  const punkty = gameState.punkty_meczowe?.[player.name] || 0
                  const cel = isTysiac ? 1000 : 66
                  const progress = (punkty / cel) * 100
                  
                  return (
                    <div key={idx} className="p-2 rounded-lg bg-gray-800/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-xs font-semibold ${
                          player.name === user?.username ? 'text-teal-400' : 'text-white'
                        }`}>
                          {playerRanks[player.name]?.emoji} {player.name}
                        </span>
                        <span className="text-yellow-400 font-bold text-sm">
                          {punkty}
                        </span>
                      </div>
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
                  Cel: {isTysiac ? '1000' : '66'} punktów
                </div>
              </div>
            ) : (
              // 66 4-osobowe - punkty drużynowe
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
                      <span>{msg.message}</span>
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
