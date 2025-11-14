import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI, saveAuth } from '../../services/api'
import useAuthStore from '../../store/authStore'

function LoginModal({ onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    // Walidacja
    if (!username.trim() || !password.trim()) {
      setError('Wypełnij wszystkie pola')
      return
    }

    setLoading(true)

    try {
      // ✅ POPRAWIONE - Backend zwraca cały response
      const response = await authAPI.login(username, password)
      
      // Wyciągnij token
      const token = response.access_token
      
      // Stwórz user object (tylko potrzebne dane!)
      const userData = {
        id: response.user_id,
        username: response.username,
        is_guest: response.is_guest || false,
        is_admin: response.is_admin || false
      }
      
      // Zapisz do Zustand store
      login(userData, token)
      
      // Zapisz do localStorage (dla api.js interceptora)
      saveAuth(token, userData)
      
      // Success - redirect
      console.log('✅ Logowanie pomyślne!', userData)
      navigate('/dashboard')
      onClose()
      
    } catch (err) {
      console.error('❌ Błąd logowania:', err)
      
      // Parse error message
      const errorMsg = err.response?.data?.detail || 
                       err.response?.data?.message ||
                       'Nieprawidłowa nazwa użytkownika lub hasło'
      
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
      <div className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-md w-full p-8 animate-slideUp">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-white">
            🔐 Logowanie
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl transition-colors"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Nazwa użytkownika
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Wpisz swoją nazwę"
              autoComplete="username"
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 transition-all disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Hasło
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Wpisz hasło"
              autoComplete="current-password"
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 transition-all disabled:opacity-50"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-all font-semibold shadow-lg mt-6"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⏳</span>
                <span>Logowanie...</span>
              </span>
            ) : (
              'Zaloguj się'
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-gray-400 text-sm">
            Nie masz konta?{' '}
            <button 
              onClick={() => {
                onClose()
                // TODO: Otwórz register modal
              }}
              className="text-teal-400 hover:text-teal-300 font-semibold"
            >
              Zarejestruj się
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginModal