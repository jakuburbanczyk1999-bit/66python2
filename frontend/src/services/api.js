import axios from 'axios'

// Base URL - zmień jeśli backend na innym porcie
const API_URL = 'http://localhost:8000/api'

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10s timeout
})

// Request interceptor - dodaj token do każdego requesta
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - obsługa błędów
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Unauthorized - wyloguj
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/'
    }
    
    // Log error
    console.error('API Error:', error.response?.data || error.message)
    
    return Promise.reject(error)
  }
)

// ============================================
// AUTH ENDPOINTS
// ============================================

export const authAPI = {
  /**
   * Login user
   * @param {string} username 
   * @param {string} password 
   * @returns {Promise} { token, user }
   */
  login: async (username, password) => {
    const response = await api.post('/auth/login', { username, password })
    return response.data
  },

  /**
   * Register new user
   * @param {string} username 
   * @param {string} password 
   * @param {string} email (optional)
   * @returns {Promise} { token, user }
   */
  register: async (username, password, email = null) => {
    const response = await api.post('/auth/register', { 
      username, 
      password, 
      email 
    })
    return response.data
  },

  /**
   * Guest login
   * @param {string} username 
   * @returns {Promise} { token, user }
   */
  guest: async (username) => {
    const response = await api.post('/auth/guest', { username })
    return response.data
  },

  /**
   * Logout
   * @returns {Promise}
   */
  logout: async () => {
    const response = await api.post('/auth/logout')
    return response.data
  },

  /**
   * Get current user info
   * @returns {Promise} user object
   */
  me: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// ============================================
// LOBBY ENDPOINTS
// ============================================

export const lobbyAPI = {
  /**
   * Get all lobbies
   * @returns {Promise} array of lobbies
   */
  list: async () => {
    const response = await api.get('/lobby/list')
    return response.data // Backend zwraca array bezpośrednio
  },

  /**
   * Get lobby details
   * @param {string} lobbyId 
   * @returns {Promise} lobby object
   */
  get: async (lobbyId) => {
    const response = await api.get(`/lobby/${lobbyId}`)
    return response.data
  },

  /**
   * Create new lobby
   * @param {object} data { nazwa, opis, max_graczy, etc }
   * @returns {Promise} created lobby
   */
  create: async (data) => {
    const response = await api.post('/lobby/create', data)
    return response.data
  },

  /**
   * Join lobby
   * @param {string} lobbyId 
   * @returns {Promise} updated lobby
   */
  join: async (lobbyId) => {
    const response = await api.post(`/lobby/${lobbyId}/join`)
    return response.data
  },

  /**
   * Leave lobby
   * @param {string} lobbyId 
   * @returns {Promise}
   */
  leave: async (lobbyId) => {
    const response = await api.post(`/lobby/${lobbyId}/leave`)
    return response.data
  },

  /**
   * Toggle ready status
   * @param {string} lobbyId 
   * @returns {Promise}
   */
  toggleReady: async (lobbyId) => {
    const response = await api.post(`/lobby/${lobbyId}/ready`)
    return response.data
  },

  /**
   * Add bot to lobby
   * @param {string} lobbyId 
   * @returns {Promise}
   */
  addBot: async (lobbyId) => {
    const response = await api.post(`/lobby/${lobbyId}/add-bot`)
    return response.data
  },

  /**
   * Start game
   * @param {string} lobbyId 
   * @returns {Promise}
   */
  start: async (lobbyId) => {
    const response = await api.post(`/lobby/${lobbyId}/start`)
    return response.data
  },

  /**
   * Delete lobby (host only)
   * @param {string} lobbyId 
   * @returns {Promise}
   */
  delete: async (lobbyId) => {
    const response = await api.delete(`/lobby/${lobbyId}`)
    return response.data
  },
  /**
   * Change slot (move to different slot)
   * @param {string} lobbyId 
   * @param {number} targetSlot 
   * @returns {Promise}
   */
  changeSlot: async (lobbyId, targetSlot) => {
    const response = await api.post(`/lobby/${lobbyId}/change-slot/${targetSlot}`)
    return response.data
  },

  /**
   * Kick bot from slot (host only)
   * @param {string} lobbyId 
   * @param {number} slotNumber 
   * @returns {Promise}
   */
  kickBot: async (lobbyId, slotNumber) => {
    const response = await api.post(`/lobby/${lobbyId}/kick-bot/${slotNumber}`)
    return response.data
  },

  /**
   * Kick player by user_id (host only)
   * @param {string} lobbyId 
   * @param {number} userId 
   * @returns {Promise}
   */
  kick: async (lobbyId, userId) => {
    const response = await api.post(`/lobby/${lobbyId}/kick/${userId}`)
    return response.data
  },

  /**
   * Get chat messages
   * @param {string} lobbyId 
   * @param {number} limit 
   * @returns {Promise}
   */
  getChatMessages: async (lobbyId, limit = 50) => {
    const response = await api.get(`/lobby/${lobbyId}/chat`, { params: { limit } })
    return response.data
  },

  /**
   * Send chat message
   * @param {string} lobbyId 
   * @param {string} message 
   * @returns {Promise}
   */
  sendChatMessage: async (lobbyId, message) => {
    const response = await api.post(`/lobby/${lobbyId}/chat`, { message })
    return response.data
  },
  /**
   * Swap slots (host only)
   * @param {string} lobbyId 
   * @param {number} slotA 
   * @param {number} slotB 
   * @returns {Promise}
   */
  swapSlots: async (lobbyId, slotA, slotB) => {
    const response = await api.post(`/lobby/${lobbyId}/swap-slots`, null, {
      params: { slot_a: slotA, slot_b: slotB }
    })
    return response.data
  },

  /**
   * Transfer host (host only)
   * @param {string} lobbyId 
   * @param {number} newHostUserId 
   * @returns {Promise}
   */
  transferHost: async (lobbyId, newHostUserId) => {
    const response = await api.post(`/lobby/${lobbyId}/transfer-host/${newHostUserId}`)
    return response.data
  },
}

// ============================================
// GAME ENDPOINTS
// ============================================

export const gameAPI = {
  /**
   * Get game state
   * @param {string} gameId 
   * @returns {Promise} game state
   */
  getState: async (gameId) => {
    const response = await api.get(`/game/${gameId}/state`)
    return response.data
  },

  /**
   * Play card
   * @param {string} gameId 
   * @param {object} data { card, action }
   * @returns {Promise}
   */
  play: async (gameId, data) => {
    const response = await api.post(`/game/${gameId}/play`, data)
    return response.data
  },

  /**
   * Finalize trick
   * @param {string} gameId 
   * @returns {Promise}
   */
  finalizeTrick: async (gameId) => {
    const response = await api.post(`/game/${gameId}/finalize-trick`)
    return response.data
  },

  /**
   * Next round
   * @param {string} gameId 
   * @returns {Promise}
   */
  nextRound: async (gameId) => {
    const response = await api.post(`/game/${gameId}/next-round`)
    return response.data
  },
}

// ============================================
// HELPERS
// ============================================

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export const isAuthenticated = () => {
  return !!localStorage.getItem('token')
}

/**
 * Get stored user data
 * @returns {object|null}
 */
export const getStoredUser = () => {
  try {
    const user = localStorage.getItem('user')
    if (!user || user === 'undefined' || user === 'null') {
      return null
    }
    return JSON.parse(user)
  } catch (error) {
    console.warn('⚠️ Błąd parsowania user z localStorage:', error)
    localStorage.removeItem('user') // Wyczyść zepsuty
    return null
  }
}

/**
 * Save auth data
 * @param {string} token 
 * @param {object} user 
 */
export const saveAuth = (token, user) => {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}

/**
 * Clear auth data
 */
export const clearAuth = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export default api

// ============================================
// ADMIN API 
// ============================================

export const adminAPI = {
  // Stats
  getStats: () => api.get('/admin/stats'),
  
  // Users
  getUsers: (params = {}) => api.get('/admin/users', { params }),
  getUserDetails: (userId) => api.get(`/admin/users/${userId}`),
  deleteUser: (userId) => api.delete(`/admin/users/${userId}`),
  toggleAdmin: (userId, grant) => api.patch(`/admin/users/${userId}/admin`, null, { params: { grant } }),
  changeUserStatus: (userId, status) => api.patch(`/admin/users/${userId}/status`, null, { params: { status } }),
  
  // Game Types
  getGameTypes: () => api.get('/admin/game-types'),
  createGameType: (data) => api.post('/admin/game-types', null, { params: data }),
  
  // Messages
  getMessages: (limit = 50) => api.get('/admin/messages', { params: { limit } }),
  deleteMessage: (messageId) => api.delete(`/admin/messages/${messageId}`),
}