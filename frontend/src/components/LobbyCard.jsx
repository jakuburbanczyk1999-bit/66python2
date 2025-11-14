function LobbyCard({ lobby, onJoin, onRefresh }) {
  // Debug - pokaż całą strukturę (usuń później)
  console.log('🔍 LobbyCard data:', lobby)
  
  const { id_gry, nazwa, opcje, slots, status_partii } = lobby
  
  // Sprawdź WSZYSTKIE możliwe miejsca gdzie może być nazwa
  const displayName = 
    nazwa ||                          // Bezpośrednio w lobby
    lobby.name ||                     // Angielska nazwa
    opcje?.nazwa ||                   // W opcjach
    lobby.opcje?.nazwa ||             // Zagnieżdżone
    lobby.game_name ||                // Inne pole
    lobby.title ||                    // Jeszcze inne
    'Unnamed Game'                    // Fallback
  
  console.log('📝 Nazwa wyświetlana:', displayName)
  
  // Count players
  const playerCount = slots?.filter(s => s.typ !== 'pusty').length || 0
  const maxPlayers = opcje?.max_graczy || 4
  const isFull = playerCount >= maxPlayers
  const isInGame = status_partii === 'W_GRZE' || status_partii === 'W_TRAKCIE'

  // Get host
  const host = slots?.find(s => s.typ === 'gracz')?.nazwa || 'Unknown'

  // Game type badge
  const gameType = opcje?.typ_gry || '66'
  const gameIcon = gameType === 'TYSIAC' ? '🎴' : '🃏'

  return (
    <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-5 hover:border-teal-500/50 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">{gameIcon}</span>
            <h3 className="text-xl font-bold text-white">{displayName}</h3>
          </div>
          <p className="text-sm text-gray-400">Host: {host}</p>
        </div>
        
        {/* Status Badge */}
        <div className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${
          isInGame 
            ? 'bg-red-500/20 text-red-400'
            : isFull
              ? 'bg-yellow-500/20 text-yellow-400'
              : 'bg-green-500/20 text-green-400'
        }`}>
          {isInGame ? '🎮 W grze' : isFull ? '🔒 Pełne' : '🟢 Dostępne'}
        </div>
      </div>

      {/* Players */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">Gracze</span>
          <span className="text-sm font-semibold text-teal-400">
            {playerCount}/{maxPlayers}
          </span>
        </div>
        
        <div className="flex gap-2">
          {Array.from({ length: maxPlayers }).map((_, i) => {
            const slot = slots?.[i]
            const hasPlayer = slot && slot.typ !== 'pusty'
            
            return (
              <div
                key={i}
                className={`flex-1 h-10 rounded-lg flex items-center justify-center text-xs font-medium ${
                  hasPlayer
                    ? slot.typ === 'bot'
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                    : 'bg-gray-700/30 text-gray-600 border border-gray-700/30'
                }`}
                title={hasPlayer ? slot.nazwa : 'Pusty slot'}
              >
                {hasPlayer ? (
                  slot.typ === 'bot' ? '🤖' : '👤'
                ) : '➕'}
              </div>
            )
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onJoin}
          disabled={isFull || isInGame}
          className={`flex-1 py-2 rounded-lg font-semibold transition-all ${
            isFull || isInGame
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-teal-600 hover:bg-teal-700 text-white'
          }`}
        >
          {isInGame ? 'W trakcie gry' : isFull ? 'Pełne' : 'Dołącz'}
        </button>
        
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-gray-700/50 hover:bg-gray-700 text-gray-300 rounded-lg transition-all"
          title="Odśwież"
        >
          🔄
        </button>
      </div>

      {/* Footer Info */}
      <div className="mt-3 pt-3 border-t border-gray-700/30 flex items-center justify-between text-xs text-gray-500">
        <span>ID: {id_gry?.substring(0, 8)}</span>
        <div className="flex gap-2">
          {opcje?.rankingowa && <span className="text-yellow-400">🏆 Rankingowa</span>}
          {opcje?.haslo && <span>🔒 Hasło</span>}
        </div>
      </div>
    </div>
  )
}

export default LobbyCard