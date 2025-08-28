import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react'
import { authApi, tokenManager } from '@/lib/api-client'
import type { AuthUser, LoginRequest } from '@/types/api'

interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

type AuthAction =
  | { type: 'AUTH_START' }
  | { type: 'AUTH_SUCCESS'; payload: AuthUser }
  | { type: 'AUTH_ERROR'; payload: string }
  | { type: 'AUTH_LOGOUT' }
  | { type: 'CLEAR_ERROR' }

interface AuthContextType extends AuthState {
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
  checkPermission: (permission: string) => boolean
  hasRole: (roles: string | string[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'AUTH_START':
      return {
        ...state,
        isLoading: true,
        error: null,
      }
    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      }
    case 'AUTH_ERROR':
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: action.payload,
      }
    case 'AUTH_LOGOUT':
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      }
    case 'CLEAR_ERROR':
      return {
        ...state,
        error: null,
      }
    default:
      return state
  }
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState)

  // Check if user is already authenticated on app load
  useEffect(() => {
    const initAuth = async () => {
      const token = tokenManager.getToken()
      if (token) {
        try {
          dispatch({ type: 'AUTH_START' })
          const user = await authApi.getCurrentUser()
          dispatch({ type: 'AUTH_SUCCESS', payload: user })
        } catch (error) {
          dispatch({ type: 'AUTH_ERROR', payload: 'Authentication failed' })
          tokenManager.clearToken()
        }
      } else {
        dispatch({ type: 'AUTH_LOGOUT' })
      }
    }

    initAuth()
  }, [])

  const login = async (credentials: LoginRequest): Promise<void> => {
    try {
      dispatch({ type: 'AUTH_START' })
      const loginResponse = await authApi.login(credentials)
      dispatch({ type: 'AUTH_SUCCESS', payload: loginResponse.user })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed'
      dispatch({ type: 'AUTH_ERROR', payload: message })
      throw error
    }
  }

  const logout = async (): Promise<void> => {
    try {
      await authApi.logout()
    } catch (error) {
      console.warn('Logout API call failed:', error)
    } finally {
      dispatch({ type: 'AUTH_LOGOUT' })
    }
  }

  const clearError = (): void => {
    dispatch({ type: 'CLEAR_ERROR' })
  }

  const checkPermission = (permission: string): boolean => {
    if (!state.user) return false
    return state.user.permissions.includes(permission)
  }

  const hasRole = (roles: string | string[]): boolean => {
    if (!state.user) return false
    const roleArray = Array.isArray(roles) ? roles : [roles]
    return roleArray.includes(state.user.role)
  }

  const contextValue: AuthContextType = {
    ...state,
    login,
    logout,
    clearError,
    checkPermission,
    hasRole,
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}