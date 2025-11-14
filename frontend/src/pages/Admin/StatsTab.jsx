import { useState, useEffect } from 'react'
import { adminAPI } from '../../services/api'

function StatsTab() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const response = await adminAPI.getStats()
      setStats(response.data)
      setError(null)
    } catch (err) {
      console.error('Failed to load stats:', err)
      setError(err.response?.data?.detail || 'Nie udało się załadować statystyk')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-300">Ładowanie statystyk...</p>
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
            onClick={loadStats}
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
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">Przegląd statystyk platformy</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {/* Total Users */}
        <StatCard
          icon="👥"
          label="Wszyscy użytkownicy"
          value={stats?.users?.total || 0}
          color="blue"
        />

        {/* Online Users */}
        <StatCard
          icon="🟢"
          label="Online"
          value={stats?.users?.online || 0}
          color="green"
        />

        {/* Today Users */}
        <StatCard
          icon="📅"
          label="Dzisiaj"
          value={stats?.users?.today || 0}
          color="purple"
        />

        {/* Admins */}
        <StatCard
          icon="👑"
          label="Administratorzy"
          value={stats?.users?.admins || 0}
          color="yellow"
        />
      </div>

      {/* Social Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard
          icon="🤝"
          label="Znajomości"
          value={stats?.social?.friendships || 0}
          color="teal"
        />

        <StatCard
          icon="💬"
          label="Wiadomości"
          value={stats?.social?.messages || 0}
          color="indigo"
        />

        <StatCard
          icon="📨"
          label="Nieprzeczytane"
          value={stats?.social?.unread_messages || 0}
          color="red"
        />
      </div>

      {/* Note */}
      {stats?.note && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <p className="text-blue-300 text-sm">ℹ️ {stats.note}</p>
        </div>
      )}

      {/* Refresh Button */}
      <div className="mt-8">
        <button
          onClick={loadStats}
          className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
        >
          🔄 Odśwież statystyki
        </button>
      </div>
    </div>
  )
}

// Stat Card Component
function StatCard({ icon, label, value, color }) {
  const colorClasses = {
    blue: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
    green: 'bg-green-500/20 border-green-500/50 text-green-400',
    purple: 'bg-purple-500/20 border-purple-500/50 text-purple-400',
    yellow: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400',
    teal: 'bg-teal-500/20 border-teal-500/50 text-teal-400',
    indigo: 'bg-indigo-500/20 border-indigo-500/50 text-indigo-400',
    red: 'bg-red-500/20 border-red-500/50 text-red-400',
  }

  return (
    <div className={`${colorClasses[color]} border-2 rounded-xl p-6`}>
      <div className="flex items-center gap-4">
        <div className="text-5xl">{icon}</div>
        <div>
          <p className="text-sm text-gray-400">{label}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
        </div>
      </div>
    </div>
  )
}

export default StatsTab