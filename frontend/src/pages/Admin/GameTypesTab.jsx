import { useState, useEffect } from 'react'
import { adminAPI } from '../../services/api'

function GameTypesTab() {
  const [gameTypes, setGameTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // Form state
  const [newGameType, setNewGameType] = useState({
    name: '',
    rules_url: ''
  })

  useEffect(() => {
    loadGameTypes()
  }, [])

  const loadGameTypes = async () => {
    try {
      const response = await adminAPI.getGameTypes()
      setGameTypes(response.data.game_types)
      setError(null)
    } catch (err) {
      console.error('Failed to load game types:', err)
      setError(err.response?.data?.detail || 'Nie udało się załadować typów gier')
    } finally {
      setLoading(false)
    }
  }

  const handleAddGameType = async (e) => {
    e.preventDefault()
    
    if (!newGameType.name.trim()) {
      alert('Nazwa gry jest wymagana!')
      return
    }

    setActionLoading(true)
    try {
      await adminAPI.createGameType(newGameType)
      await loadGameTypes()
      setShowAddModal(false)
      setNewGameType({ name: '', rules_url: '' })
      alert('Typ gry dodany pomyślnie!')
    } catch (err) {
      alert(err.response?.data?.detail || 'Nie udało się dodać typu gry')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-bounce">⏳</div>
          <p className="text-gray-300">Ładowanie typów gier...</p>
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
            onClick={loadGameTypes}
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
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Typy gier</h1>
          <p className="text-gray-400">Zarządzaj dostępnymi grami na platformie</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold flex items-center gap-2"
        >
          <span>➕</span>
          <span>Dodaj typ gry</span>
        </button>
      </div>

      {/* Game Types Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {gameTypes.map(gameType => (
          <div
            key={gameType.id}
            className="bg-[#1e2a3a] border border-gray-700/50 rounded-xl p-6 hover:border-teal-500/50 transition-all"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="text-4xl">🎮</div>
              <span className="text-xs text-gray-500">ID: {gameType.id}</span>
            </div>
            
            <h3 className="text-xl font-bold text-white mb-2">{gameType.name}</h3>
            
            {gameType.rules_url && (
              <a
                href={gameType.rules_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-400 hover:text-teal-300 text-sm flex items-center gap-1"
              >
                <span>📄</span>
                <span>Zasady gry</span>
              </a>
            )}
          </div>
        ))}
      </div>

      {gameTypes.length === 0 && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🎮</div>
          <p className="text-gray-400 mb-4">Brak typów gier</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
          >
            Dodaj pierwszy typ gry
          </button>
        </div>
      )}

      {/* Add Game Type Modal */}
      {showAddModal && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => setShowAddModal(false)}
        >
          <div 
            className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-2xl font-bold text-white mb-4">Dodaj nowy typ gry</h2>

            <form onSubmit={handleAddGameType} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Nazwa gry *
                </label>
                <input
                  type="text"
                  value={newGameType.name}
                  onChange={(e) => setNewGameType({ ...newGameType, name: e.target.value })}
                  placeholder="np. Tysiąc, 66 (4p), Preferans"
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Link do zasad (opcjonalnie)
                </label>
                <input
                  type="url"
                  value={newGameType.rules_url}
                  onChange={(e) => setNewGameType({ ...newGameType, rules_url: e.target.value })}
                  placeholder="https://..."
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="flex-1 px-4 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white rounded-lg transition-all font-semibold"
                >
                  {actionLoading ? 'Dodawanie...' : 'Dodaj'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all font-semibold"
                >
                  Anuluj
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default GameTypesTab