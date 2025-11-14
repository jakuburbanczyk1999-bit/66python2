import { useState, useEffect } from 'react'

function ActionBubble({ action, playerPosition, onComplete }) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    // Ukryj dymek po 2 sekundach
    const timer = setTimeout(() => {
      setIsVisible(false)
      if (onComplete) onComplete()
    }, 2000)

    return () => clearTimeout(timer)
  }, [onComplete])

  if (!isVisible) return null

  // Mapuj typ akcji na tekst (z dodatkowymi szczegółami)
  const getActionDisplay = (action) => {
    const actionType = action.typ
    
    // Helper do mapowania symboli kolorów
    const getSuitSymbol = (suit) => {
      if (!suit) return ''
      const symbols = {
        'CZERWIEN': '♥️', 'Czerwien': '♥️',
        'DZWONEK': '♦️', 'Dzwonek': '♦️',
        'ZOLADZ': '♣️', 'Zoladz': '♣️',
        'WINO': '♠️', 'Wino': '♠️'
      }
      return symbols[suit] || ''
    }
    
    switch(actionType) {
      // === MELDUNEK ===
      case 'meldunek':
        const punktyMeldunek = action.punkty || 0
        if (punktyMeldunek === 40) {
          return { text: 'Para (Duża)' } // Meldunek atutowy
        } else if (punktyMeldunek === 20) {
          return { text: 'Para! (Mała)' } // Meldunek bez atutu
        }
        return { text: 'Para!' } // Fallback
        
      // === DEKLARACJA ===
      case 'deklaracja':
        const kontrakt = action.kontrakt
        const atut = getSuitSymbol(action.atut)
        
        if (kontrakt === 'NORMALNA') {
          return { text: atut || '?' }
        } else if (kontrakt === 'LEPSZA') {
          return { text: 'Lepsza' }
        } else if (kontrakt === 'GORSZA') {
          return { text: 'Gorsza' }
        } else if (kontrakt === 'BEZ_PYTANIA') {
          return { text: `${atut || '?'} Nie pyta` }
        }
        return { text: kontrakt || 'Deklaracja' }
        
      // === FAZA LUFY ===
      case 'lufa':
        return { text: 'Lufa!' }
        
      case 'pas_lufa':
        return null // NIE WYŚWIETLAJ
        
      // === FAZA PYTANIA ===
      case 'pytanie':
        return { text: 'Pytam' }
        
      case 'nie_pytam':
        const atutNiePyta = getSuitSymbol(action.atut)
        return { text: `${atutNiePyta || '?'} Nie pyta` }
        
      // === FAZA LICYTACJI ===
      case 'przebicie':
        const kontraktPrzebicia = action.kontrakt
        if (kontraktPrzebicia === 'LEPSZA') {
          return { text: 'Lepsza' }
        } else if (kontraktPrzebicia === 'GORSZA') {
          return { text: 'Gorsza' }
        }
        return { text: kontraktPrzebicia || 'Przebicie' }
        
      case 'pas':
        return { text: 'Graj' }
        
      case 'kontra':
        const atutKontra = getSuitSymbol(action.atut)
        return { text: `Lufa na ${atutKontra || '?'}` }
        
      // === FAZA DECYZJI PO PASACH ===
      case 'zmiana_kontraktu':
        const nowyKontrakt = action.kontrakt
        return { text: `Zmieniam na ${nowyKontrakt || '?'}` }
        
      case 'graj_normalnie':
        return { text: 'Gramy' }
        
      // === INNE (nie powinny się wyświetlać, ale na wszelki wypadek) ===
      case 'zagraj_karte':
        return null // NIE WYŚWIETLAJ dla zagrania karty
        
      case 'do_konca':
        return { text: 'Do końca!' }
        
      default:
        return { text: actionType }
    }
  }

  const display = getActionDisplay(action)
  
  // Jeśli display jest null, nie wyświetlaj dymka
  if (!display) return null

  // Pozycja dymka względem gracza - DO ŚRODKA STOŁU
  const positionClasses = {
    'top': 'top-full mt-4 left-1/2 -translate-x-1/2',      // Pod graczem (top = góra ekranu)
    'left': 'left-full ml-4 top-1/2 -translate-y-1/2',     // Po prawej od gracza (left = lewa strona)
    'right': 'right-full mr-4 top-1/2 -translate-y-1/2',   // Po lewej od gracza (right = prawa strona)
    'bottom': 'bottom-full mb-4 left-1/2 -translate-x-1/2' // Nad graczem (bottom = dół ekranu)
  }

  return (
    <div 
      className={`absolute ${positionClasses[playerPosition] || positionClasses.bottom} z-50`}
      style={{
        animation: 'bubble-appear 0.3s ease-out, bubble-fade 0.5s ease-in 1.5s forwards'
      }}
    >
      <div className="bg-white/95 backdrop-blur-sm rounded-2xl px-4 py-2 shadow-2xl border-2 border-yellow-400">
        <div className="flex items-center gap-2">
          {/* Usunięto emoji - tylko tekst */}
          <span className="text-gray-900 font-bold text-lg whitespace-nowrap">{display.text}</span>
        </div>
      </div>

      {/* Stylowanie animacji */}
      <style>{`
        @keyframes bubble-appear {
          from {
            opacity: 0;
            transform: scale(0.8);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes bubble-fade {
          from {
            opacity: 1;
          }
          to {
            opacity: 0;
          }
        }
      `}</style>
    </div>
  )
}

export default ActionBubble