import { useNavigate, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import useAuthStore from '../../store/authStore'
import { statsAPI } from '../../services/api'

function Profile() {
  const navigate = useNavigate()
  const { username } = useParams()
  const { user } = useAuthStore()
  
  // Jeśli nie podano username, pokaż własny profil
  const profileUsername = username || user?.username
  const isOwnProfile = profileUsername === user?.username
  
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (profileUsername) {
      loadStats()
    }
  }, [profileUsername])

  const loadStats = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await statsAPI.getPlayerStats(profileUsername)
      setStats(data)
    } catch (err) {
      console.error('Błąd ładowania statystyk:', err)
      if (err.response?.status === 404) {
        setError('Użytkownik nie znaleziony')
      } else {
        setError('Nie udało się załadować statystyk')
      }
    } finally {
      setLoading(false)
    }
  }

  const getRankBadge = (rank, size = 'normal') => {
    if (!rank) return null
    const sizeClasses = size === 'large' 
      ? 'px-4 py-2 text-lg' 
      : 'px-2 py-0.5 text-xs'
    
    // Dla Mistrza pokaż punkty
    const displayName = rank.master_points !== undefined 
      ? `${rank.name} ${rank.master_points}` 
      : rank.name
    
    return (
      <span 
        className={`${sizeClasses} rounded font-semibold`}
        style={{ 
          backgroundColor: `${rank.color}20`,
          color: rank.color
        }}
      >
        {rank.emoji} {displayName}
      </span>
    )
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Nieznana'
    const date = new Date(dateStr)
    return date.toLocaleDateString('pl-PL', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  return (
    <div className="min-h-screen bg-[#1a2736] flex flex-col">
      {/* Header */}
      <header className="bg-[#1e2a3a] border-b border-gray-700/50 p-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg transition-all"
              title="Powrót"
            >
              ← Powrót
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <span>👤</span>
                <span>Profil gracza</span>
              </h1>
              <p className="text-gray-400 text-sm">{profileUsername}</p>
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
      <main className="flex-1 p-6">
        <div className="max-w-4xl mx-auto">
          
          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-teal-500"></div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
              <div className="text-4xl mb-4">😕</div>
              <p className="text-red-400 text-lg">{error}</p>
              <button 
                onClick={() => navigate('/dashboard')}
                className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all"
              >
                Wróć do dashboard
              </button>
            </div>
          )}

          {/* Stats loaded */}
          {!loading && !error && stats && (
            <div className="space-y-6">
              
              {/* Główna karta profilu */}
              <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-6">
                <div className="flex items-start gap-6">
                  {/* Avatar */}
                  <div className={`w-24 h-24 rounded-2xl flex items-center justify-center text-4xl font-bold text-white
                    ${stats.is_bot ? 'bg-gradient-to-br from-purple-500 to-pink-500' : 'bg-gradient-to-br from-teal-500 to-cyan-500'}
                  `}>
                    {stats.is_bot ? '🤖' : stats.username[0]?.toUpperCase()}
                  </div>
                  
                  {/* Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-2xl font-bold text-white">{stats.username}</h2>
                      {stats.is_bot && (
                        <span className="px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded-full">
                          Bot
                        </span>
                      )}
                      {isOwnProfile && (
                        <span className="px-2 py-1 bg-teal-500/20 text-teal-400 text-xs rounded-full">
                          Twój profil
                        </span>
                      )}
                    </div>
                    
                    {/* Ranga */}
                    <div className="mb-3">
                      {getRankBadge(stats.global_stats?.rank, 'large')}
                    </div>
                    
                    {/* Data dołączenia */}
                    <p className="text-gray-400 text-sm">
                      📅 Dołączył: {formatDate(stats.created_at)}
                    </p>
                  </div>
                  
                  {/* Pozycja w rankingu */}
                  <div className="text-right">
                    <p className="text-gray-400 text-sm mb-1">Pozycja w rankingu</p>
                    <p className="text-4xl font-bold text-teal-400">#{stats.global_stats?.position || '?'}</p>
                  </div>
                </div>
              </div>

              {/* Globalne statystyki */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-4 text-center">
                  <p className="text-gray-400 text-sm mb-1">ELO</p>
                  <p className="text-3xl font-bold text-white font-mono">{stats.global_stats?.elo || 1200}</p>
                </div>
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-4 text-center">
                  <p className="text-gray-400 text-sm mb-1">Rozegrane gry</p>
                  <p className="text-3xl font-bold text-blue-400">{stats.global_stats?.total_games || 0}</p>
                </div>
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-4 text-center">
                  <p className="text-gray-400 text-sm mb-1">Wygrane</p>
                  <p className="text-3xl font-bold text-green-400">{stats.global_stats?.total_wins || 0}</p>
                </div>
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-4 text-center">
                  <p className="text-gray-400 text-sm mb-1">Win Rate</p>
                  <p className={`text-3xl font-bold ${
                    (stats.global_stats?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {stats.global_stats?.win_rate || 0}%
                  </p>
                </div>
              </div>

              {/* Statystyki per gra */}
              {stats.game_stats && stats.game_stats.length > 0 && (
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-6">
                  <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                    <span>🎮</span>
                    <span>Statystyki per gra</span>
                  </h3>
                  
                  <div className="space-y-4">
                    {stats.game_stats.map((gameStat, index) => (
                      <div 
                        key={index}
                        className="bg-[#1a2736] rounded-lg p-4"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">
                              {gameStat.game_type === '66' ? '🃏' : '💰'}
                            </span>
                            <div>
                              <h4 className="text-white font-semibold">{gameStat.game_type}</h4>
                              <p className="text-gray-400 text-sm">
                                {gameStat.games_played} gier
                              </p>
                            </div>
                          </div>
                          {getRankBadge(gameStat.rank)}
                        </div>
                        
                        {/* Progress bar */}
                        <div className="mb-2">
                          <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>Wygrane: {gameStat.games_won}</span>
                            <span>Przegrane: {gameStat.games_lost}</span>
                          </div>
                          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all"
                              style={{ width: `${gameStat.win_rate}%` }}
                            />
                          </div>
                        </div>
                        
                        {/* Stats row */}
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400">
                            ELO: <span className="text-white font-mono">{gameStat.elo}</span>
                          </span>
                          <span className={`font-semibold ${
                            gameStat.win_rate >= 50 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {gameStat.win_rate}% Win Rate
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Brak gier */}
              {(!stats.game_stats || stats.game_stats.length === 0) && (
                <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-8 text-center">
                  <div className="text-5xl mb-4">🎲</div>
                  <h3 className="text-xl font-semibold text-white mb-2">
                    {isOwnProfile ? 'Nie masz jeszcze żadnych gier' : 'Ten gracz nie ma jeszcze żadnych gier'}
                  </h3>
                  <p className="text-gray-400 mb-4">
                    {isOwnProfile 
                      ? 'Zagraj swoją pierwszą grę, aby zobaczyć statystyki!' 
                      : 'Statystyki pojawią się po pierwszej rozegranej grze.'
                    }
                  </p>
                  {isOwnProfile && (
                    <button
                      onClick={() => navigate('/dashboard')}
                      className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
                    >
                      Zagraj teraz
                    </button>
                  )}
                </div>
              )}

              {/* Przycisk do rankingu */}
              <div className="flex justify-center">
                <button
                  onClick={() => navigate('/ranking')}
                  className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all flex items-center gap-2"
                >
                  <span>🏆</span>
                  <span>Zobacz pełny ranking</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default Profile
