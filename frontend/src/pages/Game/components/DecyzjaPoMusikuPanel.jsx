import { useState } from 'react'

/**
 * Panel decyzji po oddaniu kart do musiku (Tysiąc 2p)
 * Pozwala na:
 * 1. Zmianę wartości kontraktu (podwyższenie - limit zależy od meldunków)
 * 2. Rzucenie bomby (max 1 na mecz)
 * 3. Kontynuację bez zmian
 */
function DecyzjaPoMusikuPanel({ onAction, loading, gameState }) {
  const [showKontraktOptions, setShowKontraktOptions] = useState(false)
  
  const currentKontrakt = gameState?.kontrakt_wartosc || 100
  const bombaDostepna = gameState?.bomba_dostepna !== false
  
  // Pobierz możliwe akcje z backendu
  const mozliweAkcje = gameState?.mozliwe_akcje || []
  const akcjaZmienKontrakt = mozliweAkcje.find(a => a.typ === 'zmien_kontrakt')
  
  // Możliwe wartości kontraktu z backendu (już ograniczone przez meldunki)
  const mozliweKontrakty = akcjaZmienKontrakt?.mozliwe_wartosci || []
  const maxKontrakt = akcjaZmienKontrakt?.max_wartosc || currentKontrakt
  const meldunki = akcjaZmienKontrakt?.meldunki || []
  
  // Oblicz sumę meldunków
  const sumaMeldunkow = meldunki.reduce((sum, m) => sum + m.punkty, 0)
  
  const handleKontynuuj = () => {
    if (loading) return
    onAction({ typ: 'kontynuuj' })
  }
  
  const handleZmienKontrakt = (wartosc) => {
    if (loading) return
    onAction({ typ: 'zmien_kontrakt', wartosc })
    setShowKontraktOptions(false)
  }
  
  const handleBomba = () => {
    if (loading || !bombaDostepna) return
    
    if (window.confirm('Czy na pewno chcesz rzucić bombę? Przeciwnik otrzyma 120 punktów!')) {
      onAction({ typ: 'bomba' })
    }
  }

  // Symbole kolorów dla meldunków
  const getKolorSymbol = (kolorName) => {
    const suits = {
      'CZERWIEN': { symbol: '♥', color: 'text-red-500' },
      'DZWONEK': { symbol: '♦', color: 'text-pink-400' },
      'ZOLADZ': { symbol: '♣', color: 'text-gray-400' },
      'WINO': { symbol: '♠', color: 'text-gray-800' }
    }
    return suits[kolorName] || { symbol: '', color: '' }
  }
  
  return (
    <div className="bg-gray-900/95 border-2 border-purple-500/50 rounded-xl p-6 backdrop-blur-sm shadow-2xl max-w-md">
      <h3 className="text-xl font-bold text-purple-300 mb-4 text-center">
        Decyzja po musiku
      </h3>
      
      {/* Obecny kontrakt */}
      <div className="text-center mb-3">
        <span className="text-gray-400">Obecny kontrakt:</span>
        <span className="text-2xl font-bold text-yellow-400 ml-2">{currentKontrakt}</span>
      </div>

      {/* Info o meldunkach i limicie */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-4">
        <p className="text-blue-300 text-sm text-center">
          Twój limit: <span className="font-bold text-yellow-300">{maxKontrakt}</span>
        </p>
        {meldunki.length > 0 ? (
          <div className="text-center mt-2">
            <p className="text-blue-200/70 text-xs">Meldunki w ręce:</p>
            <div className="flex justify-center gap-2 mt-1">
              {meldunki.map((m, idx) => {
                const suitInfo = getKolorSymbol(m.kolor)
                return (
                  <span key={idx} className="text-sm bg-gray-700/50 px-2 py-1 rounded">
                    <span className={suitInfo.color}>{suitInfo.symbol}</span> {m.punkty}
                  </span>
                )
              })}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Suma: {sumaMeldunkow} pkt
            </p>
          </div>
        ) : (
          <p className="text-blue-200/70 text-xs text-center mt-1">
            Brak meldunków w ręce
          </p>
        )}
      </div>
      
      {/* Opcje */}
      <div className="space-y-3">
        
        {/* Opcja 1: Kontynuuj bez zmian */}
        <button
          onClick={handleKontynuuj}
          disabled={loading}
          className="w-full px-4 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 
                     text-white font-bold rounded-xl transition-all transform hover:scale-105 
                     disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          Graj z kontraktem {currentKontrakt}
        </button>
        
        {/* Opcja 2: Zmień kontrakt */}
        {mozliweKontrakty.length > 0 && (
          <div>
            <button
              onClick={() => setShowKontraktOptions(!showKontraktOptions)}
              disabled={loading}
              className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 
                         text-white font-bold rounded-xl transition-all transform hover:scale-105 
                         disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              Podwyższ kontrakt (max {maxKontrakt}) {showKontraktOptions ? '▲' : '▼'}
            </button>
            
            {/* Lista możliwych kontraktów */}
            {showKontraktOptions && (
              <div className="mt-2 bg-gray-800/80 rounded-lg p-3 max-h-48 overflow-y-auto">
                <div className="grid grid-cols-4 gap-2">
                  {mozliweKontrakty.map((wartosc) => (
                    <button
                      key={wartosc}
                      onClick={() => handleZmienKontrakt(wartosc)}
                      disabled={loading}
                      className="px-3 py-2 rounded-lg font-bold text-sm transition-all
                                bg-gray-700 hover:bg-yellow-600 text-white
                                disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {wartosc}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Info jeśli nie można podwyższyć */}
        {mozliweKontrakty.length === 0 && currentKontrakt >= maxKontrakt && (
          <div className="text-center text-yellow-400 text-sm py-2 bg-yellow-500/10 rounded-lg">
            Osiągnięto limit kontraktu ({maxKontrakt})
          </div>
        )}
        
        {/* Opcja 3: Bomba */}
        <button
          onClick={handleBomba}
          disabled={loading || !bombaDostepna}
          className={`w-full px-4 py-3 font-bold rounded-xl transition-all transform 
                      flex items-center justify-center gap-2
                      ${bombaDostepna 
                        ? 'bg-red-600 hover:bg-red-700 hover:scale-105 text-white' 
                        : 'bg-gray-600 text-gray-400 cursor-not-allowed'}`}
        >
          Rzuć bombę
          {!bombaDostepna && <span className="text-xs">(już użyta)</span>}
        </button>
        
        {/* Info o bombie */}
        {bombaDostepna && (
          <p className="text-xs text-gray-500 text-center">
            Bomba anuluje rozdanie - przeciwnik dostaje 120 pkt
          </p>
        )}
      </div>
    </div>
  )
}

export default DecyzjaPoMusikuPanel
