import { useState } from 'react'
import CardImage from './CardImage'

/**
 * Panel wymiany muszku w Tysiącu
 */
function WymianaMuszkuPanel({ onAction, loading, gameState, myHand }) {
  const [selectedCards, setSelectedCards] = useState([])
  const [selectedMusik, setSelectedMusik] = useState(null)
  
  const tryb = gameState?.tryb || '3p'
  const musikOdkryty = gameState?.musik_odkryty || false
  const grajacy = gameState?.gracz_grajacy
  const musik = gameState?.musik || []

  // Dla trybu 2p - wybór musiku
  if (tryb === '2p' && !musikOdkryty) {
    return (
      <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-lg rounded-2xl p-8 border-2 border-purple-500/30 shadow-2xl max-w-lg">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-white mb-2">
            🎴 Wybierz Musik
          </h2>
          <p className="text-gray-400 text-sm">
            Wybierz jeden z dwóch musików
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => onAction({ typ: 'wybierz_musik', musik: 1 })}
            disabled={loading}
            className="p-6 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-xl transition-all transform hover:scale-105"
          >
            <div className="text-4xl mb-2">1️⃣</div>
            <div className="text-white font-bold">Musik 1</div>
          </button>

          <button
            onClick={() => onAction({ typ: 'wybierz_musik', musik: 2 })}
            disabled={loading}
            className="p-6 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-xl transition-all transform hover:scale-105"
          >
            <div className="text-4xl mb-2">2️⃣</div>
            <div className="text-white font-bold">Musik 2</div>
          </button>
        </div>
      </div>
    )
  }

  // Dla trybu 2p - oddawanie kart
  if (tryb === '2p' && musikOdkryty) {
    const toggleCard = (card) => {
      if (selectedCards.includes(card)) {
        setSelectedCards(selectedCards.filter(c => c !== card))
      } else if (selectedCards.length < 2) {
        setSelectedCards([...selectedCards, card])
      }
    }

    const handleOddajKarty = () => {
      if (selectedCards.length === 2) {
        onAction({ typ: 'oddaj_karty', karty: selectedCards })
      }
    }

    return (
      <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-lg rounded-2xl p-8 border-2 border-purple-500/30 shadow-2xl max-w-2xl">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-white mb-2">
            🎴 Oddaj 2 karty do musiku
          </h2>
          <p className="text-gray-400 text-sm">
            Wybrano: {selectedCards.length}/2
          </p>
        </div>

        {/* Musik (jeśli widoczny) */}
        {musik.length > 0 && (
          <div className="mb-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <p className="text-blue-300 text-sm mb-2">Musik:</p>
            <div className="flex gap-2 justify-center">
              {musik.map((card, idx) => (
                <CardImage key={idx} card={card} size="sm" />
              ))}
            </div>
          </div>
        )}

        {/* Moja ręka */}
        <div className="flex flex-wrap gap-2 justify-center mb-4">
          {myHand.map((card, idx) => (
            <div
              key={idx}
              onClick={() => toggleCard(card)}
              className={`cursor-pointer transform transition-all ${
                selectedCards.includes(card)
                  ? 'scale-110 ring-4 ring-yellow-500'
                  : 'hover:scale-105'
              }`}
            >
              <CardImage card={card} size="md" />
            </div>
          ))}
        </div>

        <button
          onClick={handleOddajKarty}
          disabled={loading || selectedCards.length !== 2}
          className="w-full py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded-xl"
        >
          {selectedCards.length === 2 ? '✅ Oddaj karty' : `Wybierz 2 karty (${selectedCards.length}/2)`}
        </button>
      </div>
    )
  }

  // Dla trybu 3p/4p - podstawowy panel (TODO: rozdawanie kart)
  return (
    <div className="bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-lg rounded-2xl p-8 border-2 border-purple-500/30 shadow-2xl max-w-lg">
      <div className="text-center mb-6">
        <h2 className="text-3xl font-bold text-white mb-2">
          🎴 Wymiana muszku
        </h2>
        <p className="text-gray-400 text-sm">
          Gra: {grajacy}
        </p>
      </div>

      {/* Musik */}
      {musik.length > 0 && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <p className="text-blue-300 text-sm mb-2 text-center">📦 Musik:</p>
          <div className="flex gap-2 justify-center">
            {musik.map((card, idx) => (
              <CardImage key={idx} card={card} size="md" />
            ))}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 text-center">
        <p className="text-yellow-300 text-sm">
          🚧 Rozdawanie kart w budowie
        </p>
        <p className="text-gray-400 text-xs mt-2">
          Na razie boty grają automatycznie
        </p>
      </div>

      {/* Bomba */}
      <button
        onClick={() => onAction({ typ: 'bomba' })}
        disabled={loading}
        className="w-full mt-4 py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white font-bold rounded-xl"
      >
        💣 Bomba
      </button>
    </div>
  )
}

export default WymianaMuszkuPanel
