import { useState, useEffect } from 'react'

// Mapowanie kolorów na symbole z kolorami CSS
const SUIT_INFO = {
  'CZERWIEN': { symbol: '♥', color: 'text-red-500' },
  'DZWONEK': { symbol: '♦', color: 'text-pink-400' },
  'ZOLADZ': { symbol: '♣', color: 'text-gray-400' },
  'WINO': { symbol: '♠', color: 'text-gray-800' },
  'Czerwien': { symbol: '♥', color: 'text-red-500' },
  'Dzwonek': { symbol: '♦', color: 'text-pink-400' },
  'Zoladz': { symbol: '♣', color: 'text-gray-400' },
  'Wino': { symbol: '♠', color: 'text-gray-800' }
}

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
    
    // Helper do pobierania info o kolorze
    const getSuitInfo = (suit) => {
      if (!suit) return null
      return SUIT_INFO[suit] || null
    }
    
    switch(actionType) {
      // === MELDUNEK ===
      case 'meldunek':
        const punktyMeldunek = action.punkty || 0
        if (punktyMeldunek === 40) {
          return { text: 'Para (Duża)' }
        } else if (punktyMeldunek === 20) {
          return { text: 'Para (Mała)' }
        }
        return { text: 'Para!' }
        
      // === DEKLARACJA ===
      case 'deklaracja':
        const kontrakt = action.kontrakt
        const atutInfo = getSuitInfo(action.atut)
        
        if (kontrakt === 'NORMALNA') {
          return { text: atutInfo?.symbol || '?', suitInfo: atutInfo }
        } else if (kontrakt === 'LEPSZA') {
          return { text: 'Lepsza' }
        } else if (kontrakt === 'GORSZA') {
          return { text: 'Gorsza' }
        } else if (kontrakt === 'BEZ_PYTANIA') {
          return { text: 'Nie pyta', suitInfo: atutInfo, prefix: true }
        }
        return { text: kontrakt || 'Deklaracja' }
        
      // === FAZA LUFY ===
      case 'lufa':
        return { text: 'Lufa!' }
        
      case 'pas_lufa':
        return null
        
      // === FAZA PYTANIA ===
      case 'pytanie':
        return { text: 'Pytam' }
        
      case 'nie_pytam':
        const atutNiePytaInfo = getSuitInfo(action.atut)
        return { text: 'Nie pyta', suitInfo: atutNiePytaInfo, prefix: true }
        
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
        const atutKontraInfo = getSuitInfo(action.atut)
        return { text: 'Lufa na', suitInfo: atutKontraInfo, suffix: true }
        
      // === FAZA DECYZJI PO PASACH ===
      case 'zmiana_kontraktu':
        const nowyKontrakt = action.kontrakt
        return { text: `Zmieniam na ${nowyKontrakt || '?'}` }
        
      case 'graj_normalnie':
        return { text: 'Gramy' }
        
      // === INNE ===
      case 'zagraj_karte':
        return null
        
      case 'do_konca':
        return { text: 'Do końca!' }
        
      default:
        return { text: actionType }
    }
  }

  const display = getActionDisplay(action)
  
  if (!display) return null

  // Pozycja dymka względem gracza - DO ŚRODKA STOŁU
  const positionClasses = {
    'top': 'top-full mt-4 left-1/2 -translate-x-1/2',
    'left': 'left-full ml-4 top-1/2 -translate-y-1/2',
    'right': 'right-full mr-4 top-1/2 -translate-y-1/2',
    'bottom': 'bottom-full mb-4 left-1/2 -translate-x-1/2'
  }

  // Renderuj tekst z kolorowym symbolem
  const renderText = () => {
    if (!display.suitInfo) {
      return <span className="text-gray-900 font-bold text-lg whitespace-nowrap">{display.text}</span>
    }
    
    if (display.prefix) {
      // Symbol przed tekstem
      return (
        <span className="text-gray-900 font-bold text-lg whitespace-nowrap">
          <span className={display.suitInfo.color}>{display.suitInfo.symbol}</span> {display.text}
        </span>
      )
    }
    
    if (display.suffix) {
      // Tekst przed symbolem
      return (
        <span className="text-gray-900 font-bold text-lg whitespace-nowrap">
          {display.text} <span className={display.suitInfo.color}>{display.suitInfo.symbol}</span>
        </span>
      )
    }
    
    // Tylko symbol (np. deklaracja NORMALNA)
    return <span className={`font-bold text-lg whitespace-nowrap ${display.suitInfo.color}`}>{display.text}</span>
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
          {renderText()}
        </div>
      </div>

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
