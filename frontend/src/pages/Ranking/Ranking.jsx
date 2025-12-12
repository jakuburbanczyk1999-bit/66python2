import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import useAuthStore from '../../store/authStore'
import { statsAPI } from '../../services/api'

function Ranking() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  
  const [ranking, setRanking] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [gameTypeFilter, setGameTypeFilter] = useState('')
  const [totalPlayers, setTotalPlayers] = useState(0)
  const [myPosition, setMyPosition] = useState(null)

  useEffect(() => {
    loadRanking()
  }, [gameTypeFilter])

  const loadRanking = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 50 }
      if (gameTypeFilter) {
        params.game_type = gameTypeFilter
      }
      
      const data = await statsAPI.getRanking(params)
      setRanking(data.ranking || [])
      setTotalPlayers(data.total_players || 0)
      
      // Znajdź moją pozycję
      const myEntry = data.ranking?.find(r => r.username === user?.username)
      setMyPosition(myEntry?.position || null)
      
    } catch (err) {
      console.error('Błąd ładowania rankingu:', err)
      setError('Nie udało się załadować rankingu')
    } finally {
      setLoading(false)
    }
  }

  const getRankBadge = (rank) => {
    if (!rank) return null
    
    // Dla Mistrza pokaż punkty
    const displayName = rank.master_points !== undefined 
      ? `${rank.name} ${rank.master_points}` 
      : rank.name
    
    return (
      <span 
        className="px-2 py-0.5 rounded text-xs font-semibold"
        style={{ 
          backgroundColor: `${rank.color}20`,
          color: rank.color
        }}
      >
        {rank.emoji} {displayName}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-[#1a2736] flex flex-col">
      {/* Header */}
      <header className="bg-[#1e2a3a] border-b border-gray-700/50 p-6">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
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
              <p className="text-gray-400 text-sm">
                {totalPlayers} graczy w rankingu
              </p>
            </div>
          </div>
          
          {/* Filtr typu gry */}
          <div className="flex items-center gap-4">
            <select
              value={gameTypeFilter}
              onChange={(e) => setGameTypeFilter(e.target.value)}
              className="px-3 py-2 bg-[#1a2736] border border-gray-600 rounded-lg text-white text-sm focus:border-teal-500 focus:outline-none"
            >
              <option value="">Wszystkie gry</option>
              <option value="66">Gra w 66</option>
              <option value="tysiac">Tysiąc</option>
            </select>
            
            {/* User Info */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-teal-500 to-cyan-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                {user?.username?.[0]?.toUpperCase()}
              </div>
              <span className="text-gray-300">{user?.username}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 p-6">
        <div className="max-w-5xl mx-auto">
          
          {/* Moja pozycja */}
          {myPosition && (
            <div className="mb-6 p-4 bg-teal-500/10 border border-teal-500/30 rounded-xl">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-teal-400 text-2xl">📍</span>
                  <div>
                    <p className="text-teal-300 font-semibold">Twoja pozycja w rankingu</p>
                    <p className="text-gray-400 text-sm">Grasz jako {user?.username}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-teal-400">#{myPosition}</p>
                  <p className="text-gray-400 text-sm">z {totalPlayers}</p>
                </div>
              </div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-teal-500"></div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
              <p className="text-red-400">{error}</p>
              <button 
                onClick={loadRanking}
                className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-all"
              >
                Spróbuj ponownie
              </button>
            </div>
          )}

          {/* Pusta lista */}
          {!loading && !error && ranking.length === 0 && (
            <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-12 text-center">
              <div className="text-6xl mb-4">🎮</div>
              <h3 className="text-xl font-bold text-white mb-2">Brak graczy w rankingu</h3>
              <p className="text-gray-400">Zagraj swoją pierwszą grę, aby pojawić się w rankingu!</p>
            </div>
          )}

          {/* Tabela rankingu */}
          {!loading && !error && ranking.length > 0 && (
            <div className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-[#1a2736] border-b border-gray-700/50">
                    <th className="px-4 py-3 text-left text-gray-400 font-medium text-sm">#</th>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium text-sm">Gracz</th>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium text-sm">Ranga</th>
                    <th className="px-4 py-3 text-center text-gray-400 font-medium text-sm">ELO</th>
                    <th className="px-4 py-3 text-center text-gray-400 font-medium text-sm">Gry</th>
                    <th className="px-4 py-3 text-center text-gray-400 font-medium text-sm">Wygrane</th>
                    <th className="px-4 py-3 text-center text-gray-400 font-medium text-sm">Win %</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.map((player, index) => {
                    const isMe = player.username === user?.username
                    const isTop3 = player.position <= 3
                    
                    return (
                      <tr 
                        key={player.username}
                        className={`border-b border-gray-700/30 transition-colors cursor-pointer
                          ${isMe ? 'bg-teal-500/10 hover:bg-teal-500/20' : 'hover:bg-gray-700/30'}
                        `}
                        onClick={() => navigate(`/profile/${player.username}`)}
                      >
                        {/* Pozycja */}
                        <td className="px-4 py-3">
                          <span className={`font-bold text-lg ${
                            player.position === 1 ? 'text-yellow-400' :
                            player.position === 2 ? 'text-gray-300' :
                            player.position === 3 ? 'text-amber-600' :
                            'text-gray-500'
                          }`}>
                            {player.position === 1 && '🥇'}
                            {player.position === 2 && '🥈'}
                            {player.position === 3 && '🥉'}
                            {player.position > 3 && `#${player.position}`}
                          </span>
                        </td>
                        
                        {/* Gracz */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold bg-gradient-to-br from-teal-500 to-cyan-500">
                              {player.username[0]?.toUpperCase()}
                            </div>
                            <div>
                              <p className={`font-semibold ${isMe ? 'text-teal-300' : 'text-white'}`}>
                                {player.username}
                                {isMe && <span className="ml-2 text-xs text-teal-400">(Ty)</span>}
                              </p>
                            </div>
                          </div>
                        </td>
                        
                        {/* Ranga */}
                        <td className="px-4 py-3">
                          {getRankBadge(player.rank)}
                        </td>
                        
                        {/* ELO */}
                        <td className="px-4 py-3 text-center">
                          <span className="font-mono font-bold text-white">{player.elo}</span>
                        </td>
                        
                        {/* Gry */}
                        <td className="px-4 py-3 text-center text-gray-300">
                          {player.games_played}
                        </td>
                        
                        {/* Wygrane */}
                        <td className="px-4 py-3 text-center text-green-400">
                          {player.games_won}
                        </td>
                        
                        {/* Win % */}
                        <td className="px-4 py-3 text-center">
                          <span className={`font-semibold ${
                            player.win_rate >= 60 ? 'text-green-400' :
                            player.win_rate >= 40 ? 'text-yellow-400' :
                            'text-red-400'
                          }`}>
                            {player.win_rate}%
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Legenda rang */}
          <div className="mt-8 p-6 bg-[#1e2a3a] border border-gray-700/50 rounded-xl">
            <h3 className="text-white font-semibold mb-4">📊 System rang</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="flex items-center gap-2 p-3 bg-[#1a2736] rounded-lg">
                <span className="text-xl">3️⃣</span>
                <div>
                  <p className="text-sm font-semibold" style={{color: '#8B7355'}}>Klasa 3</p>
                  <p className="text-xs text-gray-500">&lt; 1100 ELO</p>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 bg-[#1a2736] rounded-lg">
                <span className="text-xl">2️⃣</span>
                <div>
                  <p className="text-sm font-semibold" style={{color: '#C0C0C0'}}>Klasa 2</p>
                  <p className="text-xs text-gray-500">1100-1249 ELO</p>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 bg-[#1a2736] rounded-lg">
                <span className="text-xl">1️⃣</span>
                <div>
                  <p className="text-sm font-semibold" style={{color: '#FFD700'}}>Klasa 1</p>
                  <p className="text-xs text-gray-500">1250-1349 ELO</p>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 bg-[#1a2736] rounded-lg">
                <span className="text-xl">Ⓜ️</span>
                <div>
                  <p className="text-sm font-semibold" style={{color: '#FF4500'}}>Mistrz</p>
                  <p className="text-xs text-gray-500">1350+ (punkty od 0)</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default Ranking
