// Mapowanie kolorów na symbole, polskie nazwy i kolory CSS
const KOLOR_INFO = {
  CZERWIEN: { symbol: '♥', nazwa: 'czerwień', color: 'text-red-500' },
  DZWONEK: { symbol: '♦', nazwa: 'dzwonek', color: 'text-pink-400' },
  ZOLADZ: { symbol: '♣', nazwa: 'żołądź', color: 'text-gray-400' },
  WINO: { symbol: '♠', nazwa: 'wino', color: 'text-gray-800' },
}

function LicytacjaPanel({ onAction, loading, gameState, canGiveLufa = true }) {
  const currentContract = gameState.kontrakt?.typ || 'Nieznany'
  const currentAtut = gameState.kontrakt?.atut || gameState.atut
  const playingPlayer = gameState.gracz_grajacy

  // Pobierz info o kolorze atutu
  const atutInfo = KOLOR_INFO[currentAtut] || { symbol: '?', nazwa: currentAtut }

  const handlePas = () => {
    onAction({ typ: 'pas' })
  }

  const handlePrzebicie = (kontrakt) => {
    onAction({ typ: 'przebicie', kontrakt })
  }

  const handleLufa = () => {
    onAction({
      typ: 'lufa',
      kontrakt: currentContract,
      atut: currentAtut
    })
  }

  return (
    <div className="bg-gray-900/95 backdrop-blur-sm rounded-xl p-6 border-2 border-orange-600/50 shadow-2xl max-w-md">
      <h3 className="text-white font-bold text-xl mb-4 text-center">Licytacja</h3>
      
      <div className="mb-4 p-3 bg-gray-800/50 rounded-lg text-center">
        <p className="text-gray-400 text-sm">Grający zapytał o przebicie</p>
        <p className="text-teal-400 font-bold text-lg mt-1">{playingPlayer}</p>
        {currentAtut && (
          <p className="text-yellow-400 text-sm mt-1">
            Atut: <span className={atutInfo.color}>{atutInfo.symbol}</span> {atutInfo.nazwa}
          </p>
        )}
      </div>

      {/* PRZYCISKI AKCJI */}
      <div className="space-y-3">
        {/* Przebicie - Gorsza */}
        <button
          onClick={() => handlePrzebicie('GORSZA')}
          disabled={loading}
          className="
            w-full py-4 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Przebijam na gorszą
        </button>

        {/* Przebicie - Lepsza */}
        <button
          onClick={() => handlePrzebicie('LEPSZA')}
          disabled={loading}
          className="
            w-full py-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Przebijam na lepszą
        </button>

        {/* Lufa (tylko dla przeciwników grającego) */}
        {canGiveLufa && (
          <button
            onClick={handleLufa}
            disabled={loading}
            className="
              w-full py-4 bg-red-600 hover:bg-red-700 disabled:bg-gray-600
              text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            Lufa na <span className={atutInfo.color}>{atutInfo.symbol}</span> {atutInfo.nazwa}
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

export default LicytacjaPanel
