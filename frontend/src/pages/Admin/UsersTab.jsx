import { useState, useEffect } from 'react'
import { adminAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'

const API_URL = 'http://localhost:8000/api'

function UsersTab() {
  const { token } = useAuthStore()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedUser, setSelectedUser] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    loadUsers()
  }, [search, statusFilter])

  const loadUsers = async () => {
    try {
      const params = {}
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      
      const response = await adminAPI.getUsers(params)
      setUsers(response.data.users)
      setError(null)
    } catch (err) {
      console.error('Failed to load users:', err)
      setError(err.response?.data?.detail || 'Nie udało się załadować użytkowników')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteUser = async (userId, username) => {
    if (!confirm(`Czy na pewno usunąć użytkownika ${username}?\n\nTa akcja jest nieodwracalna!`)) {
      return
    }

    setActionLoading(true)
    try {
      await adminAPI.deleteUser(userId)
      await loadUsers()
      alert(`Użytkownik ${username} został usunięty`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się usunąć użytkownika')
    } finally {
      setActionLoading(false)
    }
  }

  const handleToggleAdmin = async (userId, username, currentIsAdmin) => {
    const action = currentIsAdmin ? 'odebrać' : 'nadać'
    if (!confirm(`Czy ${action} uprawnienia admina użytkownikowi ${username}?`)) {
      return
    }

    setActionLoading(true)
    try {
      await adminAPI.toggleAdmin(userId, !currentIsAdmin)
      await loadUsers()
      alert(`Uprawnienia ${currentIsAdmin ? 'odebrane' : 'nadane'}`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się zmienić uprawnień')
    } finally {
      setActionLoading(false)
    }
  }

  const handleChangeStatus = async (userId, username, newStatus) => {
    setActionLoading(true)
    try {
      await adminAPI.changeUserStatus(userId, newStatus)
      await loadUsers()
      alert(`Status użytkownika ${username} zmieniony na: ${newStatus}`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się zmienić statusu')
    } finally {
      setActionLoading(false)
    }
  }

  const handleResetAllStatus = async () => {
    if (!confirm('Zresetować statusy wszystkich użytkowników na offline?\n(Boty nadal będą pokazywane jako online)')) {
      return
    }
    
    setActionLoading(true)
    try {
      const response = await fetch(`${API_URL}/admin/users/reset-status`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) throw new Error('Błąd resetowania')
      
      const data = await response.json()
      await loadUsers()
      alert(`Zresetowano statusy ${data.affected_users} użytkowników`)
    } catch (err) {
      alert('Nie udało się zresetować statusów')
    } finally {
      setActionLoading(false)
    }
  }

  const handleViewDetails = async (userId) => {
    try {
      const response = await adminAPI.getUserDetails(userId)
      setSelectedUser(response.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się załadować szczegółów')
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-300">Ładowanie użytkowników...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-6">
          <h3 className="text-red-400 font-bold mb-2">❌ Błąd</h3>
          <p className="text-red-300">{error}</p>
          <button
            onClick={loadUsers}
            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg"
          >
            Spróbuj ponownie
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Zarządzanie użytkownikami</h1>
        <p className="text-gray-400">Lista wszystkich użytkowników platformy</p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <input
          type="text"
          placeholder="🔍 Szukaj po nazwie lub email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500"
        />
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-teal-500"
        >
          <option value="">Wszystkie statusy</option>
          <option value="online">🟢 Online</option>
          <option value="offline">⚫ Offline</option>
          <option value="in_game">🎮 W grze</option>
        </select>

        <button
          onClick={loadUsers}
          className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
        >
          🔄 Odśwież
        </button>
        
        <button
          onClick={handleResetAllStatus}
          disabled={actionLoading}
          className="px-6 py-3 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white rounded-lg transition-all font-semibold"
          title="Resetuj wszystkie statusy na offline"
        >
          🔄 Reset statusów
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-[#1e2a3a] rounded-xl border border-gray-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-700/50">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">ID</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Użytkownik</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Email</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Gry</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Rejestracja</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Akcje</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/50">
              {users.map(user => (
                <tr key={user.id} className="hover:bg-gray-700/30 transition-colors">
                  <td className="px-6 py-4 text-gray-300">{user.id}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {user.is_bot && <span className="text-purple-400">🤖</span>}
                      <span className="text-white font-medium">{user.username}</span>
                      {user.is_admin && <span className="text-yellow-400">👑</span>}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-gray-300">{user.email || '-'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      user.status === 'online' ? 'bg-green-500/20 text-green-400' :
                      user.status === 'in_game' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {user.status === 'online' ? '🟢 Online' :
                       user.status === 'in_game' ? '🎮 W grze' :
                       '⚫ Offline'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-300">{user.games_played}</td>
                  <td className="px-6 py-4 text-gray-300 text-sm">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString('pl-PL') : '-'}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleViewDetails(user.id)}
                        className="px-3 py-1 bg-blue-600/50 hover:bg-blue-600 text-white text-sm rounded transition-all"
                        title="Zobacz szczegóły"
                      >
                        👁️
                      </button>
                      <button
                        onClick={() => handleToggleAdmin(user.id, user.username, user.is_admin)}
                        disabled={actionLoading}
                        className="px-3 py-1 bg-yellow-600/50 hover:bg-yellow-600 disabled:bg-gray-600 text-white text-sm rounded transition-all"
                        title={user.is_admin ? 'Zabierz admina' : 'Nadaj admina'}
                      >
                        {user.is_admin ? '👑' : '⭐'}
                      </button>
                      <button
                        onClick={() => handleDeleteUser(user.id, user.username)}
                        disabled={actionLoading}
                        className="px-3 py-1 bg-red-600/50 hover:bg-red-600 disabled:bg-gray-600 text-white text-sm rounded transition-all"
                        title="Usuń użytkownika"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {users.length === 0 && (
          <div className="p-8 text-center text-gray-400">
            Nie znaleziono użytkowników
          </div>
        )}
      </div>

      {/* User Details Modal */}
      {selectedUser && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedUser(null)}
        >
          <div 
            className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-2xl w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-2xl font-bold text-white mb-4">
              Szczegóły użytkownika: {selectedUser.username}
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-400">ID</p>
                  <p className="text-white font-medium">{selectedUser.id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Email</p>
                  <p className="text-white font-medium">{selectedUser.email || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Status</p>
                  <p className="text-white font-medium">{selectedUser.status}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Admin</p>
                  <p className="text-white font-medium">{selectedUser.is_admin ? '✅ Tak' : '❌ Nie'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Znajomi</p>
                  <p className="text-white font-medium">{selectedUser.friends_count}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Rejestracja</p>
                  <p className="text-white font-medium">
                    {new Date(selectedUser.created_at).toLocaleDateString('pl-PL')}
                  </p>
                </div>
              </div>

              {/* Game Stats */}
              {selectedUser.game_stats?.length > 0 && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-2">Statystyki gier</h3>
                  <div className="space-y-2">
                    {selectedUser.game_stats.map((stat, idx) => (
                      <div key={idx} className="bg-gray-700/30 rounded-lg p-3">
                        <p className="text-white font-medium">{stat.game_name}</p>
                        <div className="grid grid-cols-4 gap-2 mt-2 text-sm">
                          <div>
                            <p className="text-gray-400">ELO</p>
                            <p className="text-teal-400 font-bold">{Math.round(stat.elo_rating)}</p>
                          </div>
                          <div>
                            <p className="text-gray-400">Gry</p>
                            <p className="text-white font-bold">{stat.games_played}</p>
                          </div>
                          <div>
                            <p className="text-gray-400">Wygrane</p>
                            <p className="text-green-400 font-bold">{stat.games_won}</p>
                          </div>
                          <div>
                            <p className="text-gray-400">Win Rate</p>
                            <p className="text-yellow-400 font-bold">{stat.win_rate.toFixed(1)}%</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button
              onClick={() => setSelectedUser(null)}
              className="mt-6 w-full px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all"
            >
              Zamknij
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default UsersTab