import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { lobbyAPI } from '../../services/api'
import CreateLobbyModal from './CreateLobbyModal'
import LobbyCard from '../../components/LobbyCard'

function Dashboard() {
  const [lobbies, setLobbies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [activeTab, setActiveTab] = useState('browse') // 'browse' | 'history' | 'friends'
  const [successMessage, setSuccessMessage] = useState(null)
  
  const navigate = useNavigate()
  const { user, logout } = useAuthStore() // ← POPRAWIONE: usunąłem isGuest
  
  // Ref do śledzenia czy jest pierwszy load
  const isFirstLoad = useRef(true)

  // Load lobbies
  const loadLobbies = async (silent = false) => {
    try {
      if (!silent) {
        setLoading(true)
      }
      setError(null)
      
      const data = await lobbyAPI.list()
      
      // Log tylko przy pierwszym załadowaniu lub jeśli zmiana
      if (isFirstLoad.current || data.length !== lobbies.length) {
        console.log('📋 Lobby:', data.length, 'gier')
        isFirstLoad.current = false
      }
      
      setLobbies(data)
    } catch (err) {
      console.error('❌ Błąd pobierania lobby:', err)
      setError('Nie udało się pobrać listy gier')
    } finally {
      setLoading(false)
    }
  }

  // Load on mount
  useEffect(() => {
    loadLobbies()
    
    // Auto-refresh co 5s (silent - bez loading spinner)
    const interval = setInterval(() => loadLobbies(true), 5000)
    return () => clearInterval(interval)
  }, [])

  // Auto-hide success message
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [successMessage])

  // Handle logout
  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-[#1a2736] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1e2a3a] border-r border-gray-700/50 flex flex-col">
        {/* User Info */}
        <div className="p-6 border-b border-gray-700/50">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-gradient-to-br from-teal-500 to-cyan-500 rounded-full flex items-center justify-center text-white font-bold">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div>
              <div className="text-white font-semibold">{user?.username}</div>
              <div className="text-xs text-gray-400">
                {user?.is_guest ? '👤 Gość' : '✨ Gracz'}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <button
            onClick={() => setActiveTab('browse')}
            className={`w-full px-4 py-3 rounded-lg text-left transition-all mb-2 flex items-center gap-2 ${
              activeTab === 'browse'
                ? 'bg-teal-600 text-white'
                : 'text-gray-300 hover:bg-gray-700/50'
            }`}
          >
            <span>🎮</span>
            <span>Przeglądaj gry</span>
          </button>
          
          <button
            onClick={() => setActiveTab('history')}
            className={`w-full px-4 py-3 rounded-lg text-left transition-all mb-2 flex items-center gap-2 ${
              activeTab === 'history'
                ? 'bg-teal-600 text-white'
                : 'text-gray-300 hover:bg-gray-700/50'
            }`}
          >
            <span>📜</span>
            <span>Historia gier</span>
          </button>

          <button
            onClick={() => setActiveTab('friends')}
            className={`w-full px-4 py-3 rounded-lg text-left transition-all mb-2 flex items-center gap-2 ${
              activeTab === 'friends'
                ? 'bg-teal-600 text-white'
                : 'text-gray-300 hover:bg-gray-700/50'
            }`}
          >
            <span>👥</span>
            <span>Znajomi</span>
          </button>

          <div className="border-t border-gray-700/50 my-4"></div>

          <button 
            onClick={() => navigate('/ranking')}
            className="w-full px-4 py-3 rounded-lg text-left text-gray-300 hover:bg-gray-700/50 transition-all mb-2 flex items-center gap-2"
          >
            <span>🏆</span>
            <span>Ranking</span>
          </button>
          
          <button 
            onClick={() => navigate('/zasady')}
            className="w-full px-4 py-3 rounded-lg text-left text-gray-300 hover:bg-gray-700/50 transition-all mb-2 flex items-center gap-2"
          >
            <span>📖</span>
            <span>Zasady</span>
          </button>
        </nav>

        {/* Admin Panel Button - POPRAWIONA POZYCJA! */}
        {user?.is_admin && (
          <div className="p-4 border-t border-gray-700/50">
            <button
              onClick={() => navigate('/admin')}
              className="w-full px-4 py-3 bg-yellow-600/20 hover:bg-yellow-600/30 border border-yellow-500/50 text-yellow-400 rounded-lg transition-all flex items-center justify-center gap-2 font-semibold"
              title="Panel administratora"
            >
              <span>👑</span>
              <span>Admin Panel</span>
            </button>
          </div>
        )}

        {/* Logout */}
        <div className="p-4 border-t border-gray-700/50">
          <button
            onClick={handleLogout}
            className="w-full px-4 py-3 bg-gray-700/50 hover:bg-red-600/50 text-gray-300 hover:text-white rounded-lg transition-all flex items-center gap-2"
          >
            <span>🚪</span>
            <span>Wyloguj się</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="bg-[#1e2a3a] border-b border-gray-700/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-white mb-1">
                {activeTab === 'browse' && '🎮 Przeglądaj Gry'}
                {activeTab === 'history' && '📜 Historia Gier'}
                {activeTab === 'friends' && '👥 Znajomi'}
              </h1>
              <p className="text-gray-400">
                {activeTab === 'browse' && 'Dołącz do gry lub stwórz własną'}
                {activeTab === 'history' && 'Zobacz swoje poprzednie rozgrywki'}
                {activeTab === 'friends' && 'Zarządzaj swoją listą znajomych'}
              </p>
            </div>
            
            {activeTab === 'browse' && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold shadow-lg flex items-center gap-2"
              >
                <span>➕</span>
                <span>Stwórz Grę</span>
              </button>
            )}
          </div>

          {/* Stats - tylko dla browse */}
          {activeTab === 'browse' && (
            <div className="flex gap-6">
              <div>
                <div className="text-2xl font-bold text-teal-400">{lobbies.length}</div>
                <div className="text-xs text-gray-400">Dostępnych gier</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-teal-400">
                  {lobbies.filter(l => l.status_partii !== 'W_GRZE').length}
                </div>
                <div className="text-xs text-gray-400">Można dołączyć</div>
              </div>
            </div>
          )}
        </header>

        {/* Content */}
        <div className="p-6">
          {/* Success Message */}
          {successMessage && (
            <div className="mb-4 p-4 bg-green-500/20 border border-green-500/50 rounded-lg animate-slideDown">
              <p className="text-green-300 font-semibold">{successMessage}</p>
            </div>
          )}

          {/* BROWSE TAB */}
          {activeTab === 'browse' && (
            <>
              {/* Loading */}
              {loading && lobbies.length === 0 && (
                <div className="text-center py-12">
                  <div className="text-4xl mb-4 animate-bounce">⏳</div>
                  <p className="text-gray-400">Ładowanie gier...</p>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg mb-4">
                  <p className="text-red-300">{error}</p>
                  <button
                    onClick={() => loadLobbies()}
                    className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm"
                  >
                    Spróbuj ponownie
                  </button>
                </div>
              )}

              {/* Empty State */}
              {!loading && lobbies.length === 0 && (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">🎮</div>
                  <h3 className="text-xl font-bold text-white mb-2">
                    Brak dostępnych gier
                  </h3>
                  <p className="text-gray-400 mb-6">
                    Bądź pierwszy - stwórz nową grę!
                  </p>
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
                  >
                    ➕ Stwórz Grę
                  </button>
                </div>
              )}

              {/* Lobby Grid */}
              {!loading && lobbies.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {lobbies.map((lobby) => (
                    <LobbyCard
                      key={lobby.id_gry}
                      lobby={lobby}
                      onJoin={() => navigate(`/lobby/${lobby.id_gry}`)}
                      onRefresh={() => loadLobbies()}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {/* HISTORY TAB */}
          {activeTab === 'history' && (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">📜</div>
              <h3 className="text-xl font-bold text-white mb-2">
                Historia gier
              </h3>
              <p className="text-gray-400">
                Ta funkcja będzie dostępna wkrótce
              </p>
            </div>
          )}

          {/* FRIENDS TAB */}
          {activeTab === 'friends' && (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">👥</div>
              <h3 className="text-xl font-bold text-white mb-2">
                Lista znajomych
              </h3>
              <p className="text-gray-400">
                Ta funkcja będzie dostępna wkrótce
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Create Lobby Modal */}
      {showCreateModal && (
        <CreateLobbyModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={(lobbyId) => {
            setShowCreateModal(false)
            
            // Odśwież listę
            loadLobbies()
            
            // Pokaż komunikat
            setSuccessMessage('✅ Gra utworzona pomyślnie!')
            
            console.log('✅ Gra utworzona! ID:', lobbyId)            
          navigate(`/lobby/${lobbyId}`)
          }}
        />
      )}
    </div>
  )
}

export default Dashboard