import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing/Landing'
import Dashboard from './pages/Dashboard/Dashboard'
import Lobby from './pages/Lobby/Lobby'
import Game from './pages/Game/Game'
import ProtectedRoute from './components/ProtectedRoute'
import PublicRoute from './components/PublicRoute'
import AdminPanel from './pages/Admin/AdminPanel'



function App() {
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