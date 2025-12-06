import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Landing from './pages/Landing/Landing'
import Dashboard from './pages/Dashboard/Dashboard'
import Lobby from './pages/Lobby/Lobby'
import Game from './pages/Game/Game'
import Ranking from './pages/Ranking/Ranking'
import Zasady from './pages/Zasady/Zasady'
import Changelog from './pages/Changelog/Changelog'
import ProtectedRoute from './components/ProtectedRoute'
import PublicRoute from './components/PublicRoute'
import AdminPanel from './pages/Admin/AdminPanel'
import useAuthStore from './store/authStore'
import { authAPI } from './services/api'

function App() {
  const [isVerifying, setIsVerifying] = useState(true)
  const { isAuthenticated, logout, login } = useAuthStore()

  // Weryfikacja tokenu przy starcie aplikacji
  useEffect(() => {
    const verifyToken = async () => {
      if (!isAuthenticated) {
        setIsVerifying(false)
        return
      }

      try {
        console.log('🔍 Weryfikacja tokenu...')
        const userData = await authAPI.me()
        console.log('✅ Token ważny, użytkownik:', userData.username)
        // Odśwież dane użytkownika (mogły się zmienić)
        // Token jest ten sam, więc nie musimy go aktualizować
      } catch (error) {
        console.log('❌ Token nieważny lub wygasł - wylogowywanie')
        logout()
      } finally {
        setIsVerifying(false)
      }
    }

    verifyToken()
  }, []) // Tylko przy pierwszym renderze

  // Wylogowanie przy zamknięciu karty (status offline)
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Użyj sendBeacon do wysłania requesta przed zamknięciem
      const token = localStorage.getItem('auth-storage')
      if (token) {
        try {
          const parsed = JSON.parse(token)
          const accessToken = parsed?.state?.token
          if (accessToken) {
            // sendBeacon wymaga Blob z odpowiednim Content-Type dla JSON
            const blob = new Blob(
              [JSON.stringify({ token: accessToken })],
              { type: 'application/json' }
            )
            navigator.sendBeacon('/api/auth/offline', blob)
          }
        } catch (e) {
          // Ignoruj błędy parsowania
        }
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  // Heartbeat - utrzymuj status online
  useEffect(() => {
    if (!isAuthenticated) return

    const sendHeartbeat = async () => {
      try {
        await authAPI.heartbeat()
      } catch (e) {
        // Ignoruj błędy heartbeat
      }
    }

    // Wyślij heartbeat od razu
    sendHeartbeat()

    // Potem co 60 sekund
    const interval = setInterval(sendHeartbeat, 60000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

  // Pokaż loading podczas weryfikacji
  if (isVerifying) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-900 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="text-emerald-400 text-xl">🔄 Ładowanie...</div>
      </div>
    )
  }
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Route - Landing (redirect do dashboard jeśli zalogowany) */}
        <Route 
          path="/" 
          element={
            <PublicRoute>
              <Landing />
            </PublicRoute>
          } 
        />

        {/* Protected Route - Dashboard (wymaga logowania) */}
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />

        {/* Protected Route - Lobby */}
        <Route 
          path="/lobby/:id" 
          element={
            <ProtectedRoute>
              <Lobby />
            </ProtectedRoute>
          } 
        />

        {/* Protected Route - Game */}
        <Route 
          path="/game/:id" 
          element={
            <ProtectedRoute>
              <Game />
            </ProtectedRoute>
          } 
        />
        {/* Admin route */}
        <Route 
        path="/admin" 
        element={
          <ProtectedRoute>
            <AdminPanel />
          </ProtectedRoute>
        } 
      />

        {/* Ranking */}
        <Route 
          path="/ranking" 
          element={
            <ProtectedRoute>
              <Ranking />
            </ProtectedRoute>
          } 
        />

        {/* Zasady */}
        <Route 
          path="/zasady" 
          element={
            <ProtectedRoute>
              <Zasady />
            </ProtectedRoute>
          } 
        />

        {/* Changelog - publiczny */}
        <Route path="/changelog" element={<Changelog />} />

        {/* Fallback - 404 */}
        <Route 
          path="*" 
          element={<Navigate to="/" replace />} 
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App