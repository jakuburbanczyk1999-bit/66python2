import { useState } from 'react'
import { lobbyAPI } from '../../services/api'

const GAME_MODES = {
  '66': {
    name: 'Gra w 66',
    icon: '🃏',
    players: [3, 4],
    description: 'Klasyczna gra karciana',
  },
  'tysiac': {
    name: 'Tysiąc',
    icon: '🎴',
    players: [2, 3, 4],
    description: 'Popularna polska gra',
    disabled: false, // ✅ WŁĄCZONE!
  },
}

function CreateLobbyModal({ onClose, onSuccess }) {
  const [nazwa, setNazwa] = useState('')
  const [gameMode, setGameMode] = useState('66')
  const [maxGraczy, setMaxGraczy] = useState(4)
  const [haslo, setHaslo] = useState('')
  const [rankingowa, setRankingowa] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedGame = GAME_MODES[gameMode]

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    // Walidacja
    if (!nazwa.trim()) {
      setError('Wpisz nazwę gry')
      return
    }

    if (nazwa.length < 3) {
      setError('Nazwa musi mieć minimum 3 znaki')
      return
    }

    setLoading(true)

    try {
      // Create lobby
      const lobby = await lobbyAPI.create({
        nazwa: nazwa.trim(),
        typ_gry: gameMode,
        max_graczy: maxGraczy,
        haslo: haslo.trim() || null,
        rankingowa: rankingowa,
      })

      console.log('✅ Lobby utworzone:', lobby)
      
      // Success callback
      onSuccess(lobby.id_gry || lobby.id)
      
    } catch (err) {
      console.error('❌ Błąd tworzenia lobby:', err)
      
      const errorMsg = err.response?.data?.detail || 
                       err.response?.data?.message ||
                       'Nie udało się utworzyć gry. Spróbuj ponownie.'
      
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-lg w-full p-8 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-white">➕ Stwórz Grę</h2>
          <button 
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-white text-2xl disabled:opacity-50"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Nazwa */}
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Nazwa gry *
            </label>
            <input
              type="text"
              value={nazwa}
              onChange={(e) => setNazwa(e.target.value)}
              placeholder="np. Szybka rozgrywka"
              disabled={loading}
              maxLength={50}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
              autoFocus
            />
          </div>

          {/* Typ gry */}
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Typ gry *
            </label>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(GAME_MODES).map(([key, game]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    if (!game.disabled) {
                      setGameMode(key)
                      // Reset max graczy do pierwszego dostępnego
                      setMaxGraczy(game.players[game.players.length - 1])
                    }
                  }}
                  disabled={loading || game.disabled}
                  className={`p-4 rounded-lg border-2 transition-all text-left ${
                    gameMode === key
                      ? 'border-teal-500 bg-teal-500/10'
                      : 'border-gray-600 bg-gray-800/30 hover:border-gray-500'
                  } ${game.disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="text-3xl mb-2">{game.icon}</div>
                  <div className="font-semibold text-white mb-1">{game.name}</div>
                  <div className="text-xs text-gray-400">{game.description}</div>
                  {game.disabled && (
                    <div className="text-xs text-yellow-400 mt-2">⏳ Wkrótce</div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Liczba graczy */}
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Liczba graczy *
            </label>
            <div className="flex gap-2">
              {selectedGame.players.map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setMaxGraczy(num)}
                  disabled={loading}
                  className={`flex-1 py-3 rounded-lg font-semibold transition-all ${
                    maxGraczy === num
                      ? 'bg-teal-600 text-white'
                      : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'
                  } disabled:opacity-50`}
                >
                  {num} graczy
                </button>
              ))}
            </div>
          </div>

          {/* Rankingowa */}
          <div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={rankingowa}
                onChange={(e) => setRankingowa(e.target.checked)}
                disabled={loading}
                className="w-5 h-5 rounded border-gray-600 text-teal-600 focus:ring-teal-500 focus:ring-offset-gray-800 bg-gray-700"
              />
              <div>
                <div className="text-white font-semibold text-sm">
                  🏆 Rozgrywka rankingowa
                </div>
                <div className="text-xs text-gray-400">
                  Wynik wpłynie na Twój ranking
                </div>
              </div>
            </label>
          </div>

          {/* Hasło */}
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Hasło (opcjonalnie)
            </label>
            <input
              type="password"
              value={haslo}
              onChange={(e) => setHaslo(e.target.value)}
              placeholder="Zostaw puste dla publicznej gry"
              disabled={loading}
              maxLength={20}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
            />
            <p className="text-xs text-gray-500 mt-1">
              🔒 Jeśli ustawisz hasło, tylko osoby z hasłem będą mogły dołączyć
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 py-3 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-all font-semibold disabled:opacity-50"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={loading || !nazwa.trim()}
              className="flex-1 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-all font-semibold"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">⏳</span>
                  <span>Tworzenie...</span>
                </span>
              ) : (
                'Stwórz Grę'
              )}
            </button>
          </div>
        </form>

        {/* Info */}
        <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <p className="text-blue-300 text-xs">
            💡 Po utworzeniu gry zostaniesz przeniesiony do poczekalni
          </p>
        </div>
      </div>
    </div>
  )
}

export default CreateLobbyModal