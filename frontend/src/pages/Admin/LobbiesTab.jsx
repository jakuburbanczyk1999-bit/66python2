import { useState, useEffect } from 'react'
import useAuthStore from '../../store/authStore'

const API_URL = 'http://localhost:8000/api'

function LobbiesTab() {
  const { token } = useAuthStore()
  const [lobbies, setLobbies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [successMessage, setSuccessMessage] = useState(null)

  // Pobierz listę lobby
  const loadLobbies = async () => {
    console.log('Token:', token ? 'present' : 'missing', token?.substring(0, 20) + '...')
    
    if (!token) {
      setError('Brak tokenu autoryzacji')
      setLoading(false)
      return
    }
    
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/admin/lobbies`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.error('API Error:', response.status, errorData)
        throw new Error(errorData.detail || `Błąd ${response.status}`)
      }
      
      const data = await response.json()
      setLobbies(data.lobbies || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Czekaj aż token będzie dostępny
    if (token) {
      loadLobbies()
      // Auto-refresh co 10s
      const interval = setInterval(loadLobbies, 10000)
      return () => clearInterval(interval)
    }
  }, [token])

  // Usuń pojedyncze lobby
  const deleteLobby = async (lobbyId) => {
    if (!confirm(`Na pewno usunąć lobby ${lobbyId}?`)) return
    
    try {
      setActionLoading(true)
      const response = await fetch(`${API_URL}/admin/lobbies/${lobbyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Błąd usuwania lobby')
      
      setSuccessMessage(`Lobby ${lobbyId} usunięte`)
      loadLobbies()
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // Wyczyść zombie lobby
  const cleanupZombie = async () => {
    try {
      setActionLoading(true)
      const response = await fetch(`${API_URL}/admin/lobbies/cleanup`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Błąd czyszczenia lobby')
      
      const data = await response.json()
      setSuccessMessage(data.message)
      loadLobbies()
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // Usuń wszystkie lobby
  const cleanupAll = async () => {
    if (!confirm('Na pewno usunąć WSZYSTKIE lobby? Ta operacja jest nieodwracalna!')) return
    if (!confirm('Naprawdę na pewno? Wszystkie gry zostaną przerwane!')) return
    
    try {
      setActionLoading(true)
      const response = await fetch(`${API_URL}/admin/lobbies/cleanup-all`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Błąd czyszczenia lobby')
      
      const data = await response.json()
      setSuccessMessage(data.message)
      loadLobbies()
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // Auto-hide messages
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [successMessage])

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  // Formatuj datę
  const formatDate = (timestamp) => {
    if (!timestamp) return '?'
    const date = new Date(timestamp * 1000)
    return date.toLocaleString('pl-PL')
  }

  // Status badge
  const getStatusBadge = (status) => {
    const styles = {
      'LOBBY': 'bg-green-500/20 text-green-400',
      'W_GRZE': 'bg-yellow-500/20 text-yellow-400',
      'W_TRAKCIE': 'bg-yellow-500/20 text-yellow-400',
      'ZAKONCZONA': 'bg-gray-500/20 text-gray-400'
    }
    return styles[status] || 'bg-gray-500/20 text-gray-400'
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">🎮 Zarządzanie Lobby</h2>
          <p className="text-gray-400">Przeglądaj i zarządzaj aktywnymi grami</p>
        </div>
        
        <div className="flex gap-3">
          <button
            onClick={loadLobbies}
            disabled={loading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all disabled:opacity-50"
          >
            🔄 Odśwież
          </button>
          <button
            onClick={cleanupZombie}
            disabled={actionLoading}
            className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg transition-all disabled:opacity-50"
          >
            🧹 Wyczyść zombie
          </button>
          <button
            onClick={cleanupAll}
            disabled={actionLoading}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-all disabled:opacity-50"
          >
            💣 Usuń wszystkie
          </button>
        </div>
      </div>

      {/* Messages */}
      {successMessage && (
        <div className="mb-4 p-4 bg-green-500/20 border border-green-500/50 rounded-lg">
          <p className="text-green-300">✅ {successMessage}</p>
        </div>
      )}
      
      {error && (
        <div className="mb-4 p-4 bg-red-500/20 border border-red-500/50 rounded-lg">
          <p className="text-red-300">❌ {error}</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-[#243447] rounded-lg p-4">
          <div className="text-3xl font-bold text-white">{lobbies.length}</div>
          <div className="text-sm text-gray-400">Wszystkich lobby</div>
        </div>
        <div className="bg-[#243447] rounded-lg p-4">
          <div className="text-3xl font-bold text-green-400">
            {lobbies.filter(l => l.status === 'LOBBY').length}
          </div>
          <div className="text-sm text-gray-400">W lobby</div>
        </div>
        <div className="bg-[#243447] rounded-lg p-4">
          <div className="text-3xl font-bold text-yellow-400">
            {lobbies.filter(l => l.status === 'W_GRZE' || l.status === 'W_TRAKCIE').length}
          </div>
          <div className="text-sm text-gray-400">W grze</div>
        </div>
        <div className="bg-[#243447] rounded-lg p-4">
          <div className="text-3xl font-bold text-gray-400">
            {lobbies.filter(l => l.status === 'ZAKONCZONA').length}
          </div>
          <div className="text-sm text-gray-400">Zakończone</div>
        </div>
      </div>

      {/* Loading */}
      {loading && lobbies.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-400">Ładowanie lobby...</p>
        </div>
      )}

      {/* Empty */}
      {!loading && lobbies.length === 0 && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🎮</div>
          <h3 className="text-xl font-bold text-white mb-2">Brak lobby</h3>
          <p className="text-gray-400">Nie ma żadnych aktywnych gier</p>
        </div>
      )}

      {/* Lobby Table */}
      {lobbies.length > 0 && (
        <div className="bg-[#243447] rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-700/30">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Nazwa</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Typ</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Gracze</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Utworzono</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">Akcje</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/30">
              {lobbies.map((lobby) => (
                <tr key={lobby.id} className="hover:bg-gray-700/20">
                  <td className="px-4 py-3">
                    <code className="text-sm text-teal-400">{lobby.id}</code>
                  </td>
                  <td className="px-4 py-3 text-white font-medium">
                    {lobby.nazwa || 'Unnamed'}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-1 bg-teal-500/20 text-teal-400 text-xs rounded">
                      {lobby.typ_gry || '66'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 text-xs rounded ${getStatusBadge(lobby.status)}`}>
                      {lobby.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {lobby.gracze?.map((gracz, idx) => (
                        <span 
                          key={idx}
                          className={`px-2 py-0.5 text-xs rounded ${
                            gracz?.startsWith('Bot') || gracz?.includes('Bot')
                              ? 'bg-purple-500/20 text-purple-400'
                              : 'bg-gray-600 text-gray-300'
                          }`}
                        >
                          {gracz}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">
                    {formatDate(lobby.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => deleteLobby(lobby.id)}
                      disabled={actionLoading}
                      className="px-3 py-1 bg-red-600/50 hover:bg-red-600 text-red-300 hover:text-white text-sm rounded transition-all disabled:opacity-50"
                    >
                      🗑️ Usuń
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 p-4 bg-gray-800/30 rounded-lg">
        <h4 className="text-sm font-semibold text-gray-400 mb-2">Legenda:</h4>
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">LOBBY</span>
            <span className="text-gray-400">Oczekuje na graczy</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">W_GRZE</span>
            <span className="text-gray-400">Gra w toku</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-gray-500/20 text-gray-400 rounded text-xs">ZAKONCZONA</span>
            <span className="text-gray-400">Do usunięcia</span>
          </div>
        </div>
        <p className="mt-3 text-xs text-gray-500">
          <strong>🧹 Wyczyść zombie</strong> - usuwa: gry W_GRZE bez połączeń WebSocket, starsze niż 2h, zakończone
        </p>
      </div>
    </div>
  )
}

export default LobbiesTab
