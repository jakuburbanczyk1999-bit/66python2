// src/store/authStore.js

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      // Login
      login: (userData, accessToken) => {
        console.log('🔐 Login:', userData)
        set({
          user: userData,  // Powinno zawierać is_admin!
          token: accessToken,
          isAuthenticated: true,
        })
      },

      // Logout
      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        })
      },

      // Update user (np. po zmianie profilu)
      updateUser: (userData) => {
        set((state) => ({
          user: { ...state.user, ...userData },
        }))
      },
    }),
    {
      name: 'auth-storage', // Key w localStorage
    }
  )
)

export default useAuthStore