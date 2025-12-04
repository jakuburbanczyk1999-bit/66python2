function LufaPanel({ onAction, loading, gameState }) {
  const currentContract = gameState.kontrakt?.typ || 'Nieznany'
  const currentTrump = gameState.kontrakt?.atut
  const currentStake = gameState.aktualna_stawka || 0

  // Kolorowe symbole kolorów
  const getSuitSymbol = (suit) => {
    if (!suit || suit === 'Brak' || suit === 'brak') return null
    
    const suits = {
      'CZERWIEN': { symbol: '♥', color: 'text-red-500' },
      'DZWONEK': { symbol: '♦', color: 'text-pink-400' },
      'ZOLADZ': { symbol: '♣', color: 'text-gray-400' },
      'WINO': { symbol: '♠', color: 'text-gray-900' },
      'Czerwien': { symbol: '♥', color: 'text-red-500' },
      'Dzwonek': { symbol: '♦', color: 'text-pink-400' },
      'Zoladz': { symbol: '♣', color: 'text-gray-400' },
      'Wino': { symbol: '♠', color: 'text-gray-900' }
    }
    
    return suits[suit] || null
  }

  // Oblicz czy "Do Końca" jest możliwe
  const potentialStake = currentStake * 2 // Stawka po podwojeniu
  
  // Sprawdź max punkty potrzebne do zakończenia meczu (66 punktów do wygranej)
  const teamScores = gameState.punkty_meczu || {}
  const maxPointsNeeded = Math.max(
    ...Object.values(teamScores).map(score => Math.max(0, 66 - score))
  )
  
  const canDoKonca = potentialStake >= maxPointsNeeded && maxPointsNeeded > 0

  const handleLufa = () => {
    onAction({
      typ: 'lufa',
      kontrakt: currentContract,
      atut: currentTrump
    })
  }

  const handlePas = () => {
    onAction({
      typ: 'pas_lufa'
    })
  }

  const handleDoKonca = () => {
    onAction({
      typ: 'do_konca'
    })
  }

  const suitInfo = getSuitSymbol(currentTrump)

  return (
    <div className="bg-gray-900/95 backdrop-blur-sm rounded-xl p-6 border-2 border-yellow-600/50 shadow-2xl max-w-md">
      <h3 className="text-white font-bold text-xl mb-4 text-center">Lufa!</h3>
      
      {/* INFO O KONTRAKCIE */}
      <div className="mb-4 p-3 bg-gray-800/50 rounded-lg text-center">
        <div className="text-gray-400 text-sm mb-1">Aktualny kontrakt</div>
        <div className="text-white font-bold text-lg flex items-center justify-center gap-2">
          <span>{currentContract}</span>
          {suitInfo && (
            <span className={suitInfo.color}>{suitInfo.symbol}</span>
          )}
        </div>
        {currentStake > 0 && (
          <div className="text-yellow-400 text-sm mt-1">Stawka: {currentStake} pkt</div>
        )}
      </div>
      
      {/* PRZYCISKI AKCJI */}
      <div className="space-y-3">
        {/* Lufa lub Do Końca (warunkowe wyświetlanie) */}
        {canDoKonca ? (
          <button
            onClick={handleDoKonca}
            disabled={loading}
            className="
              w-full py-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600
              text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            Do Końca!
          </button>
        ) : (
          <button
            onClick={handleLufa}
            disabled={loading}
            className="
              w-full py-4 bg-red-600 hover:bg-red-700 disabled:bg-gray-600
              text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            Lufa! (x2 stawka)
          </button>
        )}

        {/* Pas */}
        <button
          onClick={handlePas}
          disabled={loading}
          className="
            w-full py-3 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600
            text-white font-bold rounded-lg transition-all
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Pas
        </button>
      </div>
    </div>
  )
}

export default LufaPanel
