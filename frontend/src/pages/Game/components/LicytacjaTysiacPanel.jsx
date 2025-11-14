import { useState } from 'react'

/**
 * Panel licytacji w Tysiącu (100-360)
 */
function LicytacjaTysiacPanel({ onAction, loading, gameState }) {
  const [hoveredAction, setHoveredAction] = useState(null)
  
  const currentBid = gameState?.aktualna_licytacja || 100
  const nextBid = currentBid + 10
  const canBid = nextBid <= 360

  const handleAction = (action) => {
    if (loading) return
    onAction(action)
  }

  return (
    <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-lg rounded-2xl p-8 border-2 border-teal-500/30 shadow-2xl max-w-md">
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-3xl font-bold text-white mb-2">
          🎴 Licytacja
        </h2>
        <p className="text-gray-400 text-sm">
          Aktualna licytacja: <span className="text-yellow-400 font-bold">{currentBid}</span>
        </p>
      </div>

      {/* Info */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-6">
        <p className="text-blue-300 text-sm text-center">
          💡 Licytacja od 100 do 360 (co 10)
        </p>
      </div>

      {/* Akcje */}
      <div className="space-y-3">
        {/* Pas */}
        <button
          onClick={() => handleAction({ typ: 'pas' })}
          disabled={loading}
          onMouseEnter={() => setHoveredAction('pas')}
          onMouseLeave={() => setHoveredAction(null)}
          className="w-full py-4 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-all transform hover:scale-105 active:scale-95"
        >
          {loading && hoveredAction === 'pas' ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⏳</span>
              <span>Pasuję...</span>
            </span>
          ) : (
            '❌ Pas'
          )}
        </button>

        {/* Licytuj */}
        {canBid && (
          <button
            onClick={() => handleAction({ typ: 'licytuj', wartosc: nextBid })}
            disabled={loading}
            onMouseEnter={() => setHoveredAction('licytuj')}
            onMouseLeave={() => setHoveredAction(null)}
            className="w-full py-4 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-all transform hover:scale-105 active:scale-95"
          >
            {loading && hoveredAction === 'licytuj' ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⏳</span>
                <span>Licytuję...</span>
              </span>
            ) : (
              `✅ Licytuję ${nextBid}`
            )}
          </button>
        )}

        {!canBid && (
          <div className="text-center text-gray-400 text-sm py-2">
            Osiągnięto maksymalną licytację (360)
          </div>
        )}
      </div>

      {/* Hint */}
      <div className="mt-6 text-center">
        <p className="text-gray-500 text-xs">
          {canBid ? 'Wybierz akcję' : 'Możesz tylko spasować'}
        </p>
      </div>
    </div>
  )
}

export default LicytacjaTysiacPanel
