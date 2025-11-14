import { Navigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'

/**
 * ProtectedRoute - Wrapper dla stron wymagających zalogowania
 * 
 * Użycie:
 * <Route path="/dashboard" element={
 *   <ProtectedRoute>
 *     <Dashboard />
 *   </ProtectedRoute>
 * } />
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()

  // Jeśli NIE zalogowany → redirect do landing
  if (!isAuthenticated) {
    console.log('🚫 Nie zalogowany - redirect do /')
    return <Navigate to="/" replace />
  }

  // Jeśli zalogowany → pokaż stronę
  return children
}

export default ProtectedRoute