import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'

function Ranking() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  return (
    <div className="min-h-screen bg-[#1a2736] flex flex-col">
      {/* Header */}
      <header className="bg-[#1e2a3a] border-b border-gray-700/50 p-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg transition-all"
              title="Powrót do dashboard"
            >
              ← Powrót
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <span>🏆</span>
                <span>Ranking</span>
              </h1>
              <p className="text-gray-400 text-sm">Najlepsi gracze Miedziowych Kart</p>
            </div>
          </div>
          
          {/* User Info */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-teal-500 to-cyan-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <span className="text-gray-300">{user?.username}</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <div className="text-8xl mb-6">🏆</div>
          <h2 className="text-3xl font-bold text-white mb-4">
            Ranking graczy
          </h2>
          <p className="text-gray-400 text-lg mb-8">
            Ta funkcja będzie dostępna wkrótce
          </p>
          <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-6 text-left">
            <h3 className="text-teal-400 font-semibold mb-3">Co będzie dostępne:</h3>
            <ul className="text-gray-300 space-y-2">
              <li className="flex items-center gap-2">
                <span className="text-teal-500">✓</span>
                <span>Globalna tabela najlepszych graczy</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">✓</span>
                <span>System punktów ELO</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">✓</span>
                <span>Twoja pozycja w rankingu</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">✓</span>
                <span>Statystyki zwycięstw i przegranych</span>
              </li>
            </ul>
          </div>
          <button
            onClick={() => navigate('/dashboard')}
            className="mt-8 px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
          >
            Wróć do gry
          </button>
        </div>
      </main>
    </div>
  )
}

export default Ranking
