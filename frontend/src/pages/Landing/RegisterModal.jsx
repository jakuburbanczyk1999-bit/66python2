import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI, saveAuth } from '../../services/api'
import useAuthStore from '../../store/authStore'

function RegisterModal({ onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    // Walidacja
    if (!username.trim() || !password.trim() || !passwordConfirm.trim()) {
      setError('Wypełnij wszystkie wymagane pola')
      return
    }

    if (username.length < 3) {
      setError('Nazwa użytkownika musi mieć minimum 3 znaki')
      return
    }

    if (password.length < 6) {
      setError('Hasło musi mieć minimum 6 znaków')
      return
    }

    if (password !== passwordConfirm) {
      setError('Hasła nie są identyczne')
      return
    }

    setLoading(true)

    try {
      // ✅ POPRAWIONE - Backend zwraca cały response
      const response = await authAPI.register(username, password, email || null)
      
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
      
      // Success
      console.log('✅ Rejestracja pomyślna!', userData)
      navigate('/dashboard')
      onClose()
      
    } catch (err) {
      console.error('❌ Błąd rejestracji:', err)
      
      // Parse error
      const errorMsg = err.response?.data?.detail || 
                       err.response?.data?.message ||
                       'Nie udało się zarejestrować. Spróbuj ponownie.'
      
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-[#1e2a3a] rounded-2xl shadow-2xl border border-gray-700/50 max-w-md w-full p-8 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-white">✨ Rejestracja</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Nazwa użytkownika *
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Minimum 3 znaki"
              autoComplete="username"
              disabled={loading}
              minLength={3}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Email (opcjonalnie)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="twoj@email.com"
              autoComplete="email"
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Hasło *
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 6 znaków"
              autoComplete="new-password"
              disabled={loading}
              minLength={6}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-white font-semibold mb-2 text-sm">
              Powtórz hasło *
            </label>
            <input
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              placeholder="Wpisz hasło ponownie"
              autoComplete="new-password"
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 disabled:opacity-50"
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
                <span>Tworzenie konta...</span>
              </span>
            ) : (
              'Stwórz konto'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

export default RegisterModal