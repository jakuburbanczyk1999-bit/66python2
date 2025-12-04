import { useState, useEffect } from 'react'
import CardImage from './CardImage'

/**
 * Podsumowanie rozdania w Tysiącu - PROSTA WERSJA
 * Faza 1: Musiki (1.5s) -> Faza 2: Wyniki
 */
function RoundSummaryTysiac({ 
  gameState, 
  onNextRound, 
  loading,
  user,
  hasVoted,
  votes
}) {
  const [showMusiks, setShowMusiks] = useState(true)
  
  const summary = gameState?.podsumowanie
  const madeContract = summary?.zrobil_kontrakt
  
  // Karty z musików (tryb 2p)
  const musik1 = gameState?.musik_1_oryginalny || gameState?.musik_1 || []
  const musik2 = gameState?.musik_2_oryginalny || gameState?.musik_2 || []
  const musikWybrany = gameState?.musik_wybrany
  const lastTrickWinner = gameState?.zwyciezca_ostatniej_lewy
  
  // Pokaż musiki przez 1.5s, potem wyniki
  useEffect(() => {
    if (showMusiks && gameState?.tryb === '2p' && (musik1.length > 0 || musik2.length > 0)) {
      const timer = setTimeout(() => setShowMusiks(false), 1500)
      return () => clearTimeout(timer)
    } else {
      setShowMusiks(false)
    }
  }, [])

  // Oblicz punkty w musiku
  const obliczPunktyMusiku = (karty) => {
    return karty.reduce((sum, c) => {
      const ranga = c.split(' ')[0].toUpperCase()
      const wartosci = { AS: 11, DZIESIATKA: 10, KROL: 4, DAMA: 3, WALET: 2, DZIEWIATKA: 0 }
      return sum + (wartosci[ranga] || 0)
    }, 0)
  }

  // FAZA 1: Musiki
  if (showMusiks && gameState?.tryb === '2p' && (musik1.length > 0 || musik2.length > 0)) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm rounded-[3rem] z-50">
        <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-8 max-w-2xl w-full mx-4 border-2 border-yellow-500/30 shadow-2xl">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-white mb-4">
              Karty w musikach
            </h2>
            {lastTrickWinner && (
              <p className="text-yellow-400 text-sm mb-4">
                {lastTrickWinner} wygrywa ostatnią lewę i otrzymuje punkty z obu musików
              </p>
            )}
            
            <div className="grid grid-cols-2 gap-6">
              {/* Musik 1 */}
              <div className={`p-4 rounded-xl ${musikWybrany === 1 ? 'bg-green-500/20 border border-green-500/50' : 'bg-gray-700/50'}`}>
                <h4 className="text-sm text-gray-300 mb-2">
                  Musik 1 {musikWybrany === 1 && '(wybrany)'}
                </h4>
                <div className="flex gap-2 justify-center">
                  {musik1.map((cardStr, idx) => (
                    <div key={idx} className="transform scale-75">
                      <CardImage card={cardStr} />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-2">{obliczPunktyMusiku(musik1)} pkt</p>
              </div>
              
              {/* Musik 2 */}
              <div className={`p-4 rounded-xl ${musikWybrany === 2 ? 'bg-green-500/20 border border-green-500/50' : 'bg-gray-700/50'}`}>
                <h4 className="text-sm text-gray-300 mb-2">
                  Musik 2 {musikWybrany === 2 && '(wybrany)'}
                </h4>
                <div className="flex gap-2 justify-center">
                  {musik2.map((cardStr, idx) => (
                    <div key={idx} className="transform scale-75">
                      <CardImage card={cardStr} />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-2">{obliczPunktyMusiku(musik2)} pkt</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // FAZA 2: Wyniki
  if (!summary) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm rounded-[3rem] z-50">
        <div className="text-white text-xl">Ładowanie wyników...</div>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm rounded-[3rem] z-50">
      <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-8 max-w-2xl w-full mx-4 border-2 border-yellow-500/30 shadow-2xl">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-6">
            Rozdanie zakończone
          </h2>
          
          {/* Wynik kontraktu */}
          <div className={`mb-6 p-6 rounded-xl border-2 ${
            madeContract 
              ? 'bg-green-500/20 border-green-500/50' 
              : 'bg-red-500/20 border-red-500/50'
          }`}>
            <p className="text-lg text-gray-300 mb-2">
              Grający: <span className="font-bold text-white">{summary.grajacy}</span>
            </p>
            <p className="text-lg text-gray-300 mb-2">
              Kontrakt: <span className="font-bold text-yellow-400">{summary.kontrakt}</span>
            </p>
            <p className="text-lg text-gray-300 mb-4">
              Zdobyte punkty: <span className="font-bold text-white">
                {summary.punkty_w_rozdaniu?.[summary.grajacy] || 0}
              </span>
            </p>
            
            <div className={`text-3xl font-bold ${madeContract ? 'text-green-400' : 'text-red-400'}`}>
              {madeContract ? (
                <>Kontrakt zrobiony! +{summary.kontrakt}</>
              ) : (
                <>Kontrakt nie zrobiony! -{summary.kontrakt}</>
              )}
            </div>
          </div>
          
          {/* Punkty wszystkich graczy */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-400 mb-3">Punkty w rozdaniu:</h3>
            <div className="grid grid-cols-2 gap-3">
              {summary.punkty_w_rozdaniu && Object.entries(summary.punkty_w_rozdaniu).map(([player, points]) => (
                <div 
                  key={player} 
                  className={`p-3 rounded-lg ${
                    player === summary.grajacy 
                      ? 'bg-yellow-500/20 border border-yellow-500/30' 
                      : 'bg-gray-700/50'
                  }`}
                >
                  <p className="text-gray-300 text-sm">{player}</p>
                  <p className="text-white font-bold text-xl">{points} pkt</p>
                </div>
              ))}
            </div>
          </div>
          
          {/* Punkty meczowe */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-400 mb-3">Punkty meczowe:</h3>
            <div className="grid grid-cols-2 gap-3">
              {summary.punkty_meczu && Object.entries(summary.punkty_meczu).map(([player, points]) => (
                <div 
                  key={player} 
                  className={`p-3 rounded-lg ${
                    player === user?.username 
                      ? 'bg-teal-500/20 border border-teal-500/30' 
                      : 'bg-gray-700/50'
                  }`}
                >
                  <p className="text-gray-300 text-sm">{player}</p>
                  <p className={`font-bold text-2xl ${points >= 1000 ? 'text-yellow-400' : 'text-white'}`}>
                    {points}
                  </p>
                </div>
              ))}
            </div>
          </div>
          
          {/* Status głosowania */}
          {votes && votes.votes && votes.votes.length > 0 && (
            <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
              <p className="text-xs text-gray-400 mb-2 text-center">Czekam na graczy...</p>
              <div className="flex flex-wrap gap-1 justify-center">
                {votes.votes.map((voter, idx) => (
                  <span key={idx} className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
                    ✓ {voter}
                  </span>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-2 text-center">
                {votes.votes.length} / {votes.totalPlayers} graczy
              </p>
            </div>
          )}
          
          {/* Przycisk następnej rundy */}
          <button
            onClick={onNextRound}
            disabled={loading || hasVoted}
            className={`w-full py-4 font-bold text-lg rounded-xl transition-all 
                       transform hover:scale-105 active:scale-95 ${
              hasVoted 
                ? 'bg-green-600 text-white cursor-default' 
                : 'bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white'
            }`}
          >
            {loading ? 'Ładowanie...' : hasVoted ? '✓ Czekam na innych graczy' : 'Następna runda'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default RoundSummaryTysiac
