import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI, saveAuth } from '../../services/api'
import useAuthStore from '../../store/authStore'

function GuestModal({ onClose }) {
  const [guestName, setGuestName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!guestName.trim()) {
      setError('Wpisz swoją nazwę')
      return
    }

    if (guestName.length < 3) {
      setError('Nazwa musi mieć minimum 3 znaki')
      return
    }

    setLoading(true)

    try {
      // ✅ POPRAWIONE - Backend zwraca cały response
      const response = await authAPI.guest(guestName.trim())
      
      // Wyciągnij token
      const token = response.access_token
      
      // Stwórz user object (tylko potrzebne dane!)
      const userData = {
        id: response.user_id,
        username: response.username,
        is_guest: response.is_guest || true,
        is_admin: false
      }
      
      // Zapisz do Zustand store
      login(userData, token)
      
      // Zapisz do localStorage (dla api.js interceptora)
      saveAuth(token, userData)
      
      // Success
      console.log('✅ Guest login pomyślny!', userData)
      navigate('/dashboard')
      onClose()
      
    } catch (err) {
      console.error('❌ Błąd guest login:', err)
      
      const errorMsg = err.response?.data?.detail || 
                       err.response?.data?.message ||
                       'Nie udało się zalogować. Spróbuj ponownie.'
      
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-md w-full p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-white">👤 Zagraj jako Gość</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>

        <p className="text-gray-300 mb-6">
          Wybierz swoją nazwę (nie musisz się rejestrować)
        </p>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={guestName}
            onChange={(e) => setGuestName(e.target.value)}
            placeholder="Wpisz swoją nazwę..."
            maxLength={15}
            minLength={3}
            disabled={loading}
            className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
            autoFocus
          />

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 py-3 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-all font-semibold disabled:opacity-50"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={!guestName.trim() || loading}
              className="flex-1 py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-all font-semibold"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">⏳</span>
                  <span>...</span>
                </span>
              ) : (
                'Zagraj!'
              )}
            </button>
          </div>
        </form>

        {/* Info */}
        <div className="mt-6 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <p className="text-blue-300 text-xs">
            💡 Jako gość możesz grać, ale Twoje statystyki nie będą zapisywane
          </p>
        </div>
      </div>
    </div>
  )
}

export default GuestModal