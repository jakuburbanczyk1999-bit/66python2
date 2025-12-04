import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import StatsTab from './StatsTab'
import UsersTab from './UsersTab'
import LobbiesTab from './LobbiesTab'

function AdminPanel() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('stats')

  // Sprawdź czy użytkownik jest adminem
  // TODO: Dodaj pole is_admin do user store
  // Na razie zakładamy że jak ktoś tu wszedł to jest adminem

  const tabs = [
    { id: 'stats', icon: '📊', label: 'Dashboard', component: StatsTab },
    { id: 'users', icon: '👥', label: 'Użytkownicy', component: UsersTab },
    { id: 'lobbies', icon: '🏠', label: 'Lobby', component: LobbiesTab },
  ]

  const ActiveComponent = tabs.find(t => t.id === activeTab)?.component || StatsTab

  return (
    <div className="min-h-screen bg-[#1a2736] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1e2a3a] border-r border-gray-700/50 flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700/50">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">👑</span>
            <div>
              <h1 className="text-xl font-bold text-white">Admin Panel</h1>
              <p className="text-xs text-gray-400">{user?.username}</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <div className="space-y-2">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full px-4 py-3 rounded-lg text-left transition-all flex items-center gap-3 ${
                  activeTab === tab.id
                    ? 'bg-teal-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700/50 hover:text-white'
                }`}
              >
                <span className="text-2xl">{tab.icon}</span>
                <span className="font-medium">{tab.label}</span>
              </button>
            ))}
          </div>
        </nav>

        {/* Back button */}
        <div className="p-4 border-t border-gray-700/50">
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full px-4 py-3 bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-all flex items-center justify-center gap-2"
          >
            <span>←</span>
            <span>Wróć do Dashboard</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <ActiveComponent />
      </main>
    </div>
  )
}

export default AdminPanel