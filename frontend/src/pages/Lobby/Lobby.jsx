import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { lobbyAPI } from '../../services/api'

function Lobby() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [lobby, setLobby] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  
  const [activeSlotMenu, setActiveSlotMenu] = useState(null)
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  // Swap state
  const [swapMode, setSwapMode] = useState(false)
  const [swapFirstSlot, setSwapFirstSlot] = useState(null)

  const loadLobby = async () => {
    try {
      const data = await lobbyAPI.get(id)
      setLobby(data)
      setError(null)
    } catch (err) {
      console.error('❌ Błąd ładowania lobby:', err)
      setError('Nie udało się załadować lobby')
    } finally {
      setLoading(false)
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

  // Calculate lobby status BEFORE useEffects that depend on it
  const mySlot = lobby?.slots?.find(s => 
    s.id_uzytkownika === user?.id || 
    (s.typ === 'gracz' && s.nazwa === user?.username)
  )
  const isInLobby = !!mySlot

  useEffect(() => {
    loadLobby()
    const interval = setInterval(loadLobby, 2000)
    return () => clearInterval(interval)
  }, [id])

  // Auto-redirect when game starts
  useEffect(() => {
    if (lobby?.status_partii === 'W_GRZE' && isInLobby) {
      console.log('🎮 Gra rozpoczęta - przekierowuję do gry...')
      navigate(`/game/${id}`)
    }
  }, [lobby?.status_partii, isInLobby, id, navigate])

  useEffect(() => {
    if (lobby) {
      loadChat()
    }
  }, [lobby])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])
  const isHost = mySlot?.is_host || false
  const amReady = mySlot?.ready || false

  const playerSlots = lobby?.slots?.filter(s => s.typ !== 'pusty') || []
  // Wszyscy gracze (poza hostem) muszą być gotowi
  const allPlayersReady = playerSlots
    .filter(s => s.typ === 'gracz' && !s.is_host)  // Tylko gracze, nie host
    .every(s => s.ready)
  const hasEnoughPlayers = playerSlots.length === lobby?.max_graczy
  const canStart = isHost && allPlayersReady && hasEnoughPlayers

  const handleSlotClick = (index) => {
    // Jeśli jesteśmy w trybie swap i kliknięto slot
    if (swapMode) {
      handleSwapSlots(index)
      return
    }
    
    setActiveSlotMenu(activeSlotMenu === index ? null : index)
  }

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (activeSlotMenu !== null && !e.target.closest('.slot-card')) {
        setActiveSlotMenu(null)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [activeSlotMenu])

  const handleJoinSlot = async () => {
    if (isInLobby) {
      alert('Już jesteś w lobby!')
      return
    }
    
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.join(id)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się dołączyć')
    } finally {
      setActionLoading(false)
    }
  }

  const handleChangeSlot = async (targetSlotIndex) => {
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.changeSlot(id, targetSlotIndex)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się zmienić slotu')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddBotToSlot = async () => {
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.addBot(id)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się dodać bota')
    } finally {
      setActionLoading(false)
    }
  }

  const handleKickBot = async (slotNumber) => {
    if (!confirm(`Czy na pewno chcesz usunąć bota z tego slotu?`)) return
    
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.kickBot(id, slotNumber)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się usunąć bota')
    } finally {
      setActionLoading(false)
    }
  }

  const handleKickPlayer = async (slotData) => {
    const confirmMsg = `Wyrzucić gracza ${slotData.nazwa}?`
    if (!confirm(confirmMsg)) return
    
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.kick(id, slotData.id_uzytkownika)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się wyrzucić')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSwapSlots = async (slotIndex) => {
    if (!swapMode) {
      // Włącz tryb swap
      setSwapMode(true)
      setSwapFirstSlot(slotIndex)
      setActiveSlotMenu(null)
      console.log('🔄 Tryb zamiany: wybierz drugi slot')
      return
    }
    
    // Mamy już pierwszy slot, teraz drugi
    if (swapFirstSlot === slotIndex) {
      // Kliknięto ten sam slot - anuluj
      setSwapMode(false)
      setSwapFirstSlot(null)
      setActiveSlotMenu(null)
      return
    }
    
    setActionLoading(true)
    setSwapMode(false)
    const firstSlot = swapFirstSlot
    setSwapFirstSlot(null)
    setActiveSlotMenu(null)
    
    try {
      await lobbyAPI.swapSlots(id, firstSlot, slotIndex)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się zamienić slotów')
    } finally {
      setActionLoading(false)
    }
  }

  const handleTransferHost = async (slotData) => {
    const confirmMsg = `Przekazać hosta graczowi ${slotData.nazwa}?`
    if (!confirm(confirmMsg)) return
    
    setActionLoading(true)
    setActiveSlotMenu(null)
    try {
      await lobbyAPI.transferHost(id, slotData.id_uzytkownika)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się przekazać hosta')
    } finally {
      setActionLoading(false)
    }
  }

  const handleLeave = async () => {
    setActionLoading(true)
    try {
      await lobbyAPI.leave(id)
      navigate('/dashboard')
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się wyjść')
      setActionLoading(false)
    }
  }

  const handleReady = async () => {
    setActionLoading(true)
    try {
      await lobbyAPI.toggleReady(id)
      await loadLobby()
      await loadChat()
    } catch (err) {
      alert(err.response?.data?.detail || 'Błąd')
    } finally {
      setActionLoading(false)
    }
  }

  const handleStart = async () => {
    setActionLoading(true)
    try {
      await lobbyAPI.start(id)
      navigate(`/game/${id}`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się wystartować')
    } finally {
      setActionLoading(false)
    }
  }

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

  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-300 text-xl">Ładowanie lobby...</p>
        </div>
      </div>
    )
  }

  if (error || !lobby) {
    return (
      <div className="min-h-screen bg-[#1a2736] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">❌</div>
          <h2 className="text-2xl font-bold text-white mb-2">Błąd</h2>
          <p className="text-gray-400 mb-6">{error || 'Lobby nie znalezione'}</p>
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

  const gameIcon = lobby.opcje?.typ_gry === 'TYSIAC' ? '🎴' : '🃏'

  return (
    <div className="min-h-screen bg-[#1a2736] flex flex-col">
      <div className="bg-[#1e2a3a] border-b border-gray-700/50 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-all"
            >
              ← Dashboard
            </button>
            
            <div className="flex items-center gap-3">
              <span className="text-3xl">{gameIcon}</span>
              <div>
                <h1 className="text-xl font-bold text-white">{lobby.nazwa}</h1>
                <p className="text-xs text-gray-400">ID: {lobby.id_gry?.substring(0, 8)}</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {lobby.opcje?.rankingowa && (
              <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 text-sm font-semibold rounded-full">
                🏆 Rankingowa
              </span>
            )}
            <div className={`px-4 py-2 rounded-full font-semibold text-sm ${
              lobby.status_partii === 'W_GRZE'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-green-500/20 text-green-400'
            }`}>
              {lobby.status_partii === 'W_GRZE' ? '🎮 W grze' : '⏳ Oczekiwanie'}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex">
        <div className="flex-1 p-6 flex items-center justify-center">
          <div className="max-w-4xl w-full">
            {/* Swap Mode Banner */}
            {swapMode && (
              <div className="mb-4 p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-xl text-center animate-pulse">
                <p className="text-yellow-300 font-semibold">
                  🔄 Tryb zamiany: Kliknij drugi slot aby zamienić
                </p>
                <button
                  onClick={() => {
                    setSwapMode(false)
                    setSwapFirstSlot(null)
                  }}
                  className="mt-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm"
                >
                  Anuluj
                </button>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 mb-8">
              {lobby.slots?.map((slot, index) => (
                <SlotCard
                  key={index}
                  slot={slot}
                  index={index}
                  isMe={slot.id_uzytkownika === user?.id || (slot.typ === 'gracz' && slot.nazwa === user?.username)}
                  isHost={isHost}
                  isInLobby={isInLobby}
                  isMenuOpen={activeSlotMenu === index}
                  onClick={() => handleSlotClick(index)}
                  onJoin={handleJoinSlot}
                  onChangeSlot={() => handleChangeSlot(index)}
                  onAddBot={handleAddBotToSlot}
                  onKick={() => {
                    if (slot.typ === 'bot') {
                      handleKickBot(index)
                    } else {
                      handleKickPlayer(slot)
                    }
                  }}
                  onSwap={() => handleSwapSlots(index)}
                  onTransferHost={() => handleTransferHost(slot)}
                  loading={actionLoading}
                  swapMode={swapMode}
                  isSwapTarget={swapFirstSlot === index}
                />
              ))}
            </div>

            {isInLobby && (
              <div className="space-y-3">
                {!isHost && (
                  <button
                    onClick={handleReady}
                    disabled={actionLoading}
                    className={`w-full py-4 rounded-xl font-bold text-lg transition-all ${
                      amReady
                        ? 'bg-green-600 hover:bg-green-700 text-white'
                        : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                    }`}
                  >
                    {amReady ? '✅ Gotowy!' : '⏳ Kliknij gdy gotowy'}
                  </button>
                )}

                {isHost && (
                  <>
                    <button
                      onClick={handleStart}
                      disabled={!canStart || actionLoading}
                      className={`w-full py-4 rounded-xl font-bold text-lg transition-all ${
                        canStart
                          ? 'bg-green-600 hover:bg-green-700 text-white'
                          : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                      }`}
                    >
                      {canStart ? '🚀 Rozpocznij Grę!' : '⏳ Czekaj na graczy...'}
                    </button>
                    
                    {/* Info dlaczego nie można wystartować */}
                    {!canStart && (
                      <div className="text-sm text-gray-400 text-center">
                        {!hasEnoughPlayers && `Potrzeba ${lobby.max_graczy} graczy (jest ${playerSlots.length})`}
                        {hasEnoughPlayers && !allPlayersReady && 'Nie wszyscy gracze są gotowi'}
                      </div>
                    )}
                  </>
                )}

                <button
                  onClick={handleLeave}
                  disabled={actionLoading}
                  className="w-full py-3 bg-red-600/50 hover:bg-red-600 text-white rounded-xl font-semibold transition-all"
                >
                  🚪 Opuść Lobby
                </button>

                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-center">
                  <p className="text-blue-300 text-sm">
                    {isHost
                      ? '👑 Jesteś hostem - możesz wystartować grę gdy wszyscy będą gotowi'
                      : '⏳ Poczekaj aż host wystartuje grę'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        <aside className="w-80 bg-[#1e2a3a] border-l border-gray-700/50 flex flex-col">
          <div className="p-4 border-b border-gray-700/50">
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
              Gracze ({playerSlots.length}/{lobby.max_graczy})
            </h3>
            <div className="space-y-2">
              {playerSlots.map((slot, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <span>{slot.typ === 'bot' ? '🤖' : '👤'}</span>
                  <span className="text-white font-medium">{slot.nazwa}</span>
                  {slot.is_host && <span className="text-yellow-400">👑</span>}
                  {slot.typ === 'gracz' && (
                    <span className={`ml-auto text-xs ${slot.ready ? 'text-green-400' : 'text-gray-500'}`}>
                      {slot.ready ? '✅' : '⏳'}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex-1 flex flex-col">
            <div className="p-4 border-b border-gray-700/50">
              <h3 className="text-sm font-semibold text-gray-400 uppercase">Czat</h3>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {chatMessages.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">
                  Brak wiadomości. Napisz coś! 💬
                </p>
              ) : (
                chatMessages.map(msg => (
                  <div 
                    key={msg.id} 
                    className={`text-sm ${
                      msg.is_system 
                        ? 'text-center text-gray-400 italic py-1' 
                        : ''
                    }`}
                  >
                    {msg.is_system ? (
                      <span>📢 {msg.message}</span>
                    ) : (
                      <div>
                        <span className="text-teal-400 font-semibold">
                          {msg.username}
                        </span>
                        <span className="text-gray-600 text-xs ml-2">
                          {new Date(msg.timestamp * 1000).toLocaleTimeString('pl-PL', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </span>
                        <p className="text-white mt-0.5">{msg.message}</p>
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            <form 
              onSubmit={handleSendMessage} 
              className={`p-4 border-t border-gray-700/50 ${!isInLobby && 'opacity-50 pointer-events-none'}`}
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder={isInLobby ? "Wpisz wiadomość..." : "Dołącz aby pisać"}
                  disabled={!isInLobby || chatLoading}
                  maxLength={500}
                  className="flex-1 px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim() || !isInLobby || chatLoading}
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

function SlotCard({ 
  slot, 
  index, 
  isMe, 
  isHost, 
  isInLobby, 
  isMenuOpen, 
  onClick, 
  onJoin, 
  onChangeSlot, 
  onAddBot, 
  onKick, 
  onSwap, 
  onTransferHost,
  loading,
  swapMode,
  isSwapTarget
}) {
  const isEmpty = slot.typ === 'pusty'
  const isBot = slot.typ === 'bot'
  const isPlayer = slot.typ === 'gracz'
  const showEmptyMenu = isEmpty
  const showOccupiedMenu = !isEmpty && isHost && !isMe

  return (
    <div className="relative slot-card">
      <div 
        onClick={onClick}
        className={`p-6 rounded-xl border-2 transition-all cursor-pointer ${
          isEmpty ? 'bg-gray-800/30 border-gray-700/50 border-dashed hover:border-teal-500/50 hover:bg-gray-800/50' :
          isBot ? 'bg-purple-500/10 border-purple-500/30 hover:border-purple-500/50' :
          isMe ? 'bg-teal-500/20 border-teal-500 ring-4 ring-teal-500/20' :
          'bg-gray-700/30 border-gray-600 hover:border-gray-500'
        } ${isMenuOpen ? 'ring-2 ring-teal-500/50' : ''} ${
          swapMode ? (isSwapTarget ? 'ring-4 ring-yellow-500 animate-pulse' : 'opacity-50') : ''
        }`}
      >
        {swapMode && isSwapTarget && (
          <div className="absolute -top-3 -right-3 w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center text-white font-bold shadow-lg">
            1
          </div>
        )}

        <div className="flex flex-col items-center text-center">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center text-4xl mb-3 ${
            isEmpty ? 'bg-gray-700/50' : isBot ? 'bg-purple-500/30' : 'bg-teal-500/30'
          }`}>
            {isEmpty ? '➕' : isBot ? '🤖' : '👤'}
          </div>
          {isEmpty ? (
            <p className="text-gray-500 font-medium">Kliknij aby wybrać</p>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <p className="text-white font-bold text-lg">{slot.nazwa}</p>
                {slot.is_host && <span className="text-yellow-400">👑</span>}
              </div>
              {isMe && <span className="text-teal-400 text-xs font-semibold mb-2">(Ty)</span>}
              {isPlayer && (
                <div className={`mb-2 px-3 py-1 rounded-full text-sm font-semibold ${
                  slot.ready ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'
                }`}>
                  {slot.ready ? '✅ Gotowy' : '⏳ Nie gotowy'}
                </div>
              )}
              {isBot && (
                <div className="mb-2 px-3 py-1 rounded-full text-sm font-semibold bg-purple-500/20 text-purple-400">
                  🤖 Bot
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {showEmptyMenu && isMenuOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-[#1e2a3a] border border-gray-700 rounded-xl shadow-2xl overflow-hidden z-10" onClick={(e) => e.stopPropagation()}>
          {!isInLobby ? (
            <button onClick={(e) => { e.stopPropagation(); onJoin() }} disabled={loading} className="w-full px-4 py-3 text-left text-white hover:bg-teal-600/20 transition-all flex items-center gap-2 disabled:opacity-50">
              <span>👤</span><span className="font-medium">Dołącz tutaj</span>
            </button>
          ) : (
            <button onClick={(e) => { e.stopPropagation(); onChangeSlot() }} disabled={loading} className="w-full px-4 py-3 text-left text-white hover:bg-blue-600/20 transition-all flex items-center gap-2 disabled:opacity-50">
              <span>🔄</span><span className="font-medium">Zamień się na ten slot</span>
            </button>
          )}
          {isHost && (
            <button onClick={(e) => { e.stopPropagation(); onAddBot() }} disabled={loading} className="w-full px-4 py-3 text-left text-white hover:bg-purple-600/20 transition-all flex items-center gap-2 border-t border-gray-700/50 disabled:opacity-50">
              <span>🤖</span><span className="font-medium">Dodaj bota</span>
            </button>
          )}
          <button disabled className="w-full px-4 py-3 text-left text-gray-500 cursor-not-allowed flex items-center gap-2 border-t border-gray-700/50">
            <span>👥</span><span className="font-medium">Zaproś znajomego</span><span className="text-xs ml-auto">(wkrótce)</span>
          </button>
        </div>
      )}

      {showOccupiedMenu && isMenuOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-[#1e2a3a] border border-gray-700 rounded-xl shadow-2xl overflow-hidden z-10" onClick={(e) => e.stopPropagation()}>
          <button onClick={(e) => { e.stopPropagation(); onKick() }} disabled={loading} className="w-full px-4 py-3 text-left text-red-400 hover:bg-red-600/20 transition-all flex items-center gap-2 disabled:opacity-50">
            <span>🚪</span><span className="font-medium">Wyrzuć {isBot ? 'bota' : 'gracza'}</span>
          </button>
          <button onClick={(e) => { e.stopPropagation(); onSwap() }} disabled={loading} className="w-full px-4 py-3 text-left text-white hover:bg-teal-600/20 transition-all flex items-center gap-2 border-t border-gray-700/50 disabled:opacity-50">
            <span>🔄</span><span className="font-medium">Zamień miejscami</span>
          </button>
          {isPlayer && (
            <button onClick={(e) => { e.stopPropagation(); onTransferHost() }} disabled={loading} className="w-full px-4 py-3 text-left text-yellow-400 hover:bg-yellow-600/20 transition-all flex items-center gap-2 border-t border-gray-700/50 disabled:opacity-50">
              <span>👑</span><span className="font-medium">Przekaż hosta</span>
            </button>
          )}
          <button disabled className="w-full px-4 py-3 text-left text-gray-500 cursor-not-allowed flex items-center gap-2 border-t border-gray-700/50">
            <span>ℹ️</span><span className="font-medium">Zobacz profil</span><span className="text-xs ml-auto">(wkrótce)</span>
          </button>
        </div>
      )}
    </div>
  )
}

export default Lobby