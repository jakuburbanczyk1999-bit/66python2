import { Link } from 'react-router-dom'
import { useState } from 'react'

const CHANGELOG = [
  {
    version: '1.1.1',
    date: '6 grudnia 2024',
    type: 'fix', // 🔧
    title: 'Poprawki i optymalizacje',
    changes: [
      'Grid 2x2 z 4 grami na stronie głównej (Pan, Remik jako placeholdery)',
      'Szybsze boty - zmniejszono opóźnienia akcji',
      'Naprawiono błąd 404 po zakończeniu meczu',
      'Naprawiono naliczanie statystyk rozegranych gier',
      'Nowy system końca meczu - 10s na decyzję o powrocie do lobby',
    ],
  },
  {
    version: '1.1.0',
    date: '6 grudnia 2024',
    type: 'major', // 🎉
    title: 'Tryb 3-osobowy i nowy design',
    changes: [
      'Nowy tryb gry: 66 dla 3 graczy (każdy na każdego)',
      'System timeout/forfeit - 60s na powrót po rozłączeniu',
      'Przeprojektowany interfejs z dark theme',
      'Naprawiono wyświetlanie wyniku w podglądzie gry',
      'Poprawione dymki akcji dla trybu 3-osobowego',
    ],
  },
  {
    version: '1.0.2',
    date: '6 grudnia 2024',
    type: 'fix', // 🔧
    title: 'Ulepszenia UI i statystyk',
    changes: [
      'Nowy checkbox "Gra casual" - rozgrywki bez wpływu na ranking',
      'Nowy checkbox "Gra prywatna" - możliwość ustawienia hasła do lobby',
      'Podgląd gry w toku pokazuje aktualny wynik meczu',
      'Podgląd gry 4-osobowej pokazuje podział na drużyny',
      'Poprawiono licznik aktywnych graczy na stronie głównej',
      'Naprawiono zliczanie rozegranych gier w statystykach',
    ],
  },
  {
    version: '1.0.1',
    date: '5 grudnia 2024',
    type: 'fix', // 🔧
    title: 'Poprawki i ulepszenia',
    changes: [
      'Naprawiono wyświetlanie błędów logowania',
      'Boty dodają się na wybrany slot zamiast pierwszego wolnego',
      'Nowy system powrotu do lobby po zakończeniu meczu',
      'Możliwość dołączenia do gry którą opuściliśmy (60s na powrót)',
      'System heartbeat - dokładniejsze śledzenie statusów online/offline',
      'Agresywniejsze czyszczenie nieaktywnych lobby',
    ],
  },
  {
    version: '1.0.0',
    date: '5 grudnia 2024',
    type: 'major', // 🎉
    title: 'Uruchomienie Miedziowych Kart!',
    changes: [
      'Pierwsza publiczna wersja portalu',
      'Gra w 66 dla 4 graczy',
      'System rejestracji i logowania',
      'Możliwość gry jako gość',
      'Lobby z czatem',
      'Boty do wypełnienia składu',
      'Panel administratora',
    ],
  },
]

function Changelog() {
  // Pierwszy wpis domyślnie rozwinięty, reszta zwinięta
  const [expanded, setExpanded] = useState({ 0: true })

  const toggleExpanded = (index) => {
    setExpanded(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  const getEmoji = (type) => {
    return type === 'major' ? '🎉' : '🔧'
  }

  return (
    <div className="min-h-screen bg-[#1a2736]">
      {/* Header */}
      <header className="bg-[#1a2332] border-b border-gray-700/50">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3">
              <img src="/icon.png" alt="Logo" className="w-8 h-8" />
              <span className="text-white font-bold text-xl">Miedziowe Karty</span>
            </Link>
            <Link
              to="/"
              className="px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-700/50 rounded-lg transition-all"
            >
              ← Powrót
            </Link>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <h1 className="text-4xl font-bold text-white mb-2">📋 Changelog</h1>
        <p className="text-gray-400 mb-8">Historia zmian i aktualizacji</p>

        <div className="space-y-4">
          {CHANGELOG.map((release, index) => {
            const isExpanded = expanded[index] || false
            const isLatest = index === 0
            const emoji = getEmoji(release.type)

            return (
              <div
                key={index}
                className={`bg-[#1e2a3a] border rounded-xl overflow-hidden transition-all ${
                  isLatest 
                    ? 'border-teal-500/50 ring-1 ring-teal-500/20' 
                    : 'border-gray-700/50'
                }`}
              >
                {/* Header - zawsze widoczny, klikalny */}
                <button
                  onClick={() => toggleExpanded(index)}
                  className="w-full p-6 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-center gap-4 flex-wrap">
                    <span className={`px-3 py-1 font-mono font-bold rounded-lg ${
                      isLatest
                        ? 'bg-teal-500/30 text-teal-300'
                        : 'bg-gray-700/50 text-gray-300'
                    }`}>
                      v{release.version}
                    </span>
                    <span className="text-gray-400 text-sm">{release.date}</span>
                    {isLatest && (
                      <span className="px-2 py-0.5 bg-teal-500/20 text-teal-400 text-xs rounded-full">
                        Najnowsza
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <span className="text-xl font-bold text-white">
                      {emoji} {release.title}
                    </span>
                    <span className={`text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                      ▼
                    </span>
                  </div>
                </button>

                {/* Content - zwijany */}
                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-gray-700/30">
                    <ul className="space-y-2 mt-4">
                      {release.changes.map((change, i) => (
                        <li key={i} className="flex items-start gap-3 text-gray-300">
                          <span className="text-teal-400 mt-1">•</span>
                          <span>{change}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Footer info */}
        <div className="mt-12 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <p className="text-blue-300 text-sm">
            💡 Masz pomysł na nową funkcję? Daj nam znać!
          </p>
        </div>
      </main>
    </div>
  )
}

export default Changelog
