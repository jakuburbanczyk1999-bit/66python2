import { useState } from 'react'
import useAuthStore from '../store/authStore'

function LobbyCard({ lobby, onJoin, onRefresh }) {
  const [showPreview, setShowPreview] = useState(false)
  const { user } = useAuthStore()
  
  const { id_gry, nazwa, opcje, slots, status_partii } = lobby
  
  // Nazwa lobby
  const displayName = 
    nazwa ||
    lobby.name ||
    opcje?.nazwa ||
    'Unnamed Game'
  
  // Count players
  const playerCount = slots?.filter(s => s.typ !== 'pusty').length || 0
  const maxPlayers = opcje?.max_graczy || lobby.max_graczy || 4
  const isFull = playerCount >= maxPlayers
  const isInGame = status_partii === 'W_GRZE' || status_partii === 'W_TRAKCIE'

  // Sprawdź czy aktualny użytkownik jest w tej grze
  const isUserInGame = slots?.some(s => 
    s.typ === 'gracz' && 
    (s.id_uzytkownika === user?.id || s.nazwa === user?.username)
  ) || false

  // Get host
  const hostSlot = slots?.find(s => s.is_host)
  const host = hostSlot?.nazwa || slots?.find(s => s.typ === 'gracz')?.nazwa || 'Unknown'

  // Game type badge
  const gameType = opcje?.typ_gry || '66'
  const gameLabel = gameType === 'tysiac' ? 'Tysiąc' : '66'

  // Gracze w lobby
  const players = slots?.filter(s => s.typ !== 'pusty') || []
  
  // Drużyny dla gry 66 (4 gracze)
  const isTysiac = gameType === 'tysiac'
  const hasTeams = !isTysiac && maxPlayers === 4
  
  // Podział na drużyny: slot 0,2 = drużyna 1, slot 1,3 = drużyna 2
  const team1 = hasTeams ? slots?.filter((s, idx) => s.typ !== 'pusty' && idx % 2 === 0) || [] : []
  const team2 = hasTeams ? slots?.filter((s, idx) => s.typ !== 'pusty' && idx % 2 === 1) || [] : []
  
  // Punkty meczowe (jeśli gra w toku) - sprawdź różne ścieżki
  const matchScore = lobby?.punkty_meczowe || lobby?.rozdanie?.punkty_meczowe || lobby?.game_state?.punkty_meczowe || null

  return (
    <>
      <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-5 hover:border-teal-500/50 transition-all">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 bg-teal-500/20 text-teal-400 text-xs font-semibold rounded">{gameLabel}</span>
              <h3 className="text-xl font-bold text-white">{displayName}</h3>
            </div>
            <p className="text-sm text-gray-400">Host: {host}</p>
          </div>
          
          {/* Status Badge */}
          <div className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${
            isUserInGame
              ? 'bg-green-500/20 text-green-400 animate-pulse'
              : isInGame 
                ? 'bg-red-500/20 text-red-400'
                : isFull
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-green-500/20 text-green-400'
          }`}>
            {isUserInGame ? '🔄 Twoja gra' : isInGame ? 'W grze' : isFull ? 'Pełne' : 'Dostępne'}
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
              
              const getTooltip = () => {
                if (!hasPlayer) return 'Pusty slot'
                const prefixes = []
                if (slot.typ === 'bot') prefixes.push('Bot')
                if (slot.is_host) prefixes.push('Host')
                const prefix = prefixes.length > 0 ? `[${prefixes.join(' · ')}] ` : ''
                return `${prefix}${slot.nazwa}`
              }
              
              return (
                <div
                  key={i}
                  className={`flex-1 h-10 rounded-lg flex items-center justify-center text-xs font-medium ${
                    hasPlayer
                      ? slot.typ === 'bot'
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : slot.is_host
                          ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                          : 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                      : 'bg-gray-700/30 text-gray-600 border border-gray-700/30'
                  }`}
                  title={getTooltip()}
                >
                  {hasPlayer ? (
                    slot.typ === 'bot' ? '🤖' : slot.is_host ? '👑' : slot.nazwa?.charAt(0)?.toUpperCase() || '?'
                  ) : '+'}
                </div>
              )
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          {isUserInGame ? (
            // Użytkownik jest w tej grze - może wrócić
            <button
              onClick={onJoin}
              className="flex-1 py-2 rounded-lg font-semibold transition-all bg-green-600 hover:bg-green-700 text-white animate-pulse"
            >
              🔄 Wróć do gry
            </button>
          ) : !isFull && !isInGame ? (
            // Można dołączyć
            <button
              onClick={onJoin}
              className="flex-1 py-2 rounded-lg font-semibold transition-all bg-teal-600 hover:bg-teal-700 text-white"
            >
              Dołącz
            </button>
          ) : (
            // Pełne lub w grze - pokaż podgląd
            <button
              onClick={() => setShowPreview(true)}
              className="flex-1 py-2 rounded-lg font-semibold transition-all bg-gray-600 hover:bg-gray-500 text-white"
            >
              👁️ Podgląd
            </button>
          )}
          
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
            {opcje?.rankingowa && <span className="text-yellow-400">⭐ Rankingowa</span>}
            {opcje?.haslo && <span>🔒 Hasło</span>}
          </div>
        </div>
      </div>

      {/* Modal podglądu */}
      {showPreview && (
        <div 
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => setShowPreview(false)}
        >
          <div 
            className="bg-[#1e2a3a] border border-gray-700 rounded-2xl p-6 max-w-md w-full shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 bg-teal-500/20 text-teal-400 text-xs font-semibold rounded">
                    {gameLabel}
                  </span>
                  <h2 className="text-xl font-bold text-white">{displayName}</h2>
                </div>
                <p className="text-sm text-gray-400">
                  {isInGame ? '🎮 Gra w toku' : '⏳ Oczekiwanie na start'}
                </p>
              </div>
              <button
                onClick={() => setShowPreview(false)}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>

            {/* Wynik meczu - jeśli gra w toku */}
            {isInGame && (
              <div className="mb-6 p-4 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/30 rounded-xl">
                <h3 className="text-sm font-semibold text-yellow-400 uppercase mb-3 text-center">
                  🏆 Wynik meczu
                </h3>
                {hasTeams ? (
                  // Wyświetl wynik drużynowy
                  <div className="flex items-center justify-center gap-4">
                    <div className="text-center">
                      <div className="text-xs text-teal-400 mb-1">Drużyna 1</div>
                      <div className="text-3xl font-bold text-white">
                        {matchScore?.['Drużyna 1'] ?? matchScore?.['Team 1'] ?? 0}
                      </div>
                    </div>
                    <div className="text-2xl text-gray-500">:</div>
                    <div className="text-center">
                      <div className="text-xs text-pink-400 mb-1">Drużyna 2</div>
                      <div className="text-3xl font-bold text-white">
                        {matchScore?.['Drużyna 2'] ?? matchScore?.['Team 2'] ?? 0}
                      </div>
                    </div>
                  </div>
                ) : (
                  // Wyświetl wynik indywidualny (Tysiąc)
                  <div className="space-y-2">
                    {matchScore && Object.keys(matchScore).length > 0 ? (
                      Object.entries(matchScore).map(([name, points]) => (
                        <div key={name} className="flex justify-between items-center">
                          <span className="text-gray-300">{name}</span>
                          <span className="text-xl font-bold text-yellow-400">{points}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-400">Gra rozpoczęta</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Lista graczy - z podziałem na drużyny */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                Gracze ({playerCount}/{maxPlayers})
              </h3>
              
              {hasTeams ? (
                // Widok drużynowy
                <div className="grid grid-cols-2 gap-4">
                  {/* Drużyna 1 */}
                  <div>
                    <div className="text-xs text-teal-400 font-semibold mb-2 flex items-center gap-1">
                      <span className="w-2 h-2 bg-teal-400 rounded-full"></span>
                      Drużyna 1
                    </div>
                    <div className="space-y-2">
                      {team1.length > 0 ? team1.map((player, idx) => (
                        <div 
                          key={idx}
                          className={`flex items-center gap-2 p-2 rounded-lg border ${
                            player.typ === 'bot'
                              ? 'bg-purple-500/10 border-purple-500/30'
                              : player.is_host
                                ? 'bg-yellow-500/10 border-yellow-500/30'
                                : 'bg-teal-500/10 border-teal-500/30'
                          }`}
                        >
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                            player.typ === 'bot' ? 'bg-purple-500/30 text-purple-300' : 'bg-teal-500/30 text-teal-300'
                          }`}>
                            {player.typ === 'bot' ? '🤖' : player.nazwa?.charAt(0)?.toUpperCase() || '?'}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-white text-sm truncate">{player.nazwa}</div>
                            <div className="text-xs text-gray-500 flex items-center gap-1">
                              {player.is_host && <span className="text-yellow-400">👑</span>}
                              {player.typ === 'bot' && <span className="text-purple-400">Bot</span>}
                              {!isInGame && player.ready && <span className="text-green-400">✓</span>}
                            </div>
                          </div>
                        </div>
                      )) : (
                        <div className="text-gray-500 text-sm text-center py-2">Brak graczy</div>
                      )}
                    </div>
                  </div>
                  
                  {/* Drużyna 2 */}
                  <div>
                    <div className="text-xs text-pink-400 font-semibold mb-2 flex items-center gap-1">
                      <span className="w-2 h-2 bg-pink-400 rounded-full"></span>
                      Drużyna 2
                    </div>
                    <div className="space-y-2">
                      {team2.length > 0 ? team2.map((player, idx) => (
                        <div 
                          key={idx}
                          className={`flex items-center gap-2 p-2 rounded-lg border ${
                            player.typ === 'bot'
                              ? 'bg-purple-500/10 border-purple-500/30'
                              : player.is_host
                                ? 'bg-yellow-500/10 border-yellow-500/30'
                                : 'bg-pink-500/10 border-pink-500/30'
                          }`}
                        >
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                            player.typ === 'bot' ? 'bg-purple-500/30 text-purple-300' : 'bg-pink-500/30 text-pink-300'
                          }`}>
                            {player.typ === 'bot' ? '🤖' : player.nazwa?.charAt(0)?.toUpperCase() || '?'}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-white text-sm truncate">{player.nazwa}</div>
                            <div className="text-xs text-gray-500 flex items-center gap-1">
                              {player.is_host && <span className="text-yellow-400">👑</span>}
                              {player.typ === 'bot' && <span className="text-purple-400">Bot</span>}
                              {!isInGame && player.ready && <span className="text-green-400">✓</span>}
                            </div>
                          </div>
                        </div>
                      )) : (
                        <div className="text-gray-500 text-sm text-center py-2">Brak graczy</div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                // Widok standardowy (bez drużyn)
                <div className="space-y-2">
                  {players.map((player, idx) => (
                    <div 
                      key={idx}
                      className={`flex items-center gap-3 p-3 rounded-lg ${
                        player.typ === 'bot'
                          ? 'bg-purple-500/10 border border-purple-500/30'
                          : player.is_host
                            ? 'bg-yellow-500/10 border border-yellow-500/30'
                            : 'bg-gray-700/30 border border-gray-600/30'
                      }`}
                    >
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${
                        player.typ === 'bot' ? 'bg-purple-500/30 text-purple-300' : 'bg-teal-500/30 text-teal-300'
                      }`}>
                        {player.typ === 'bot' ? '🤖' : player.nazwa?.charAt(0)?.toUpperCase() || '?'}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">{player.nazwa}</span>
                          {player.is_host && (
                            <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">
                              👑 Host
                            </span>
                          )}
                          {player.typ === 'bot' && (
                            <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">
                              Bot
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500">
                          Slot {player.numer_gracza + 1}
                          {!isInGame && player.ready && <span className="text-green-400 ml-2">✓ Gotowy</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Info o grze */}
            <div className="bg-gray-800/50 rounded-lg p-4 mb-6">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-500">Typ gry:</span>
                  <span className="text-white ml-2">{gameLabel}</span>
                </div>
                <div>
                  <span className="text-gray-500">Tryb:</span>
                  <span className="text-white ml-2">{maxPlayers} graczy</span>
                </div>
                <div>
                  <span className="text-gray-500">Rankingowa:</span>
                  <span className={`ml-2 ${opcje?.rankingowa ? 'text-yellow-400' : 'text-gray-400'}`}>
                    {opcje?.rankingowa ? 'Tak ⭐' : 'Nie'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Status:</span>
                  <span className={`ml-2 ${isInGame ? 'text-red-400' : 'text-green-400'}`}>
                    {isInGame ? 'W grze' : 'Lobby'}
                  </span>
                </div>
              </div>
            </div>

            {/* Przycisk zamknij */}
            <button
              onClick={() => setShowPreview(false)}
              className="w-full py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold transition-all"
            >
              Zamknij
            </button>

            {/* Info o trybie obserwatora */}
            <p className="text-center text-xs text-gray-500 mt-3">
              🔜 Tryb obserwatora wkrótce dostępny
            </p>
          </div>
        </div>
      )}
    </>
  )
}

export default LobbyCard
