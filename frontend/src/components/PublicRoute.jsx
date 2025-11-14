import { Navigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'

/**
 * PublicRoute - Redirect zalogowanych użytkowników
 * 
 * Jeśli użytkownik jest zalogowany i próbuje wejść na landing page,
 * przekieruj go do dashboard
 * 
 * Użycie:
 * <Route path="/" element={
 *   <PublicRoute>
 *     <Landing />
 *   </PublicRoute>
 * } />
 */
function PublicRoute({ children }) {
  const { isAuthenticated } = useAuthStore()

  // Jeśli zalogowany → redirect do dashboard
  if (isAuthenticated) {
    console.log('✅ Już zalogowany - redirect do /dashboard')
    return <Navigate to="/dashboard" replace />
  }

  // Jeśli NIE zalogowany → pokaż landing
  return children
}

export default PublicRoute