import { Link } from 'react-router-dom'

const CHANGELOG = [
  {
    version: '1.0.2',
    date: '6 grudnia 2024',
    title: '🎮 Ulepszenia UI i statystyk',
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
    title: '🔧 Poprawki i ulepszenia',
    changes: [
      'Naprawiono wyświetlanie błędów logowania (błędne hasło, użytkownik nie istnieje)',
      'Boty dodają się teraz na wybrany slot zamiast pierwszego wolnego',
      'Nowy system powrotu do lobby po zakończeniu meczu - każdy gracz decyduje osobno',
      'Możliwość dołączenia do gry którą opuściliśmy (60 sekund na powrót)',
      'System heartbeat - dokładniejsze śledzenie statusów online/offline',
      'Agresywniejsze czyszczenie nieaktywnych lobby (co 2 minuty)',
      'Poprawiono linki w nawigacji strony powitalnej',
      'Domyślna nazwa lobby przy tworzeniu gry',
      'Naprawiono generowanie nazw gości',
    ],
  },
  {
    version: '1.0.0',
    date: '5 grudnia 2024',
    title: '🎉 Uruchomienie Miedziowych Kart!',
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

        <div className="space-y-8">
          {CHANGELOG.map((release, index) => (
            <div
              key={index}
              className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-6"
            >
              <div className="flex items-center gap-4 mb-4">
                <span className="px-3 py-1 bg-teal-500/20 text-teal-400 font-mono font-bold rounded-lg">
                  v{release.version}
                </span>
                <span className="text-gray-400 text-sm">{release.date}</span>
              </div>
              
              <h2 className="text-2xl font-bold text-white mb-4">{release.title}</h2>
              
              <ul className="space-y-2">
                {release.changes.map((change, i) => (
                  <li key={i} className="flex items-start gap-3 text-gray-300">
                    <span className="text-teal-400 mt-1">•</span>
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
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
