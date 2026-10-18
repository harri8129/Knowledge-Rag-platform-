import { createContext, useContext, useEffect, useReducer, useCallback } from 'react'
import { getMe } from '@/services/auth.service'

const AuthContext = createContext(null)

const init = { user: null, isAuthenticated: false, isLoading: true }

function reducer(state, { type, payload }) {
    switch (type) {
        case 'SET_USER': return { user: payload, isAuthenticated: true, isLoading: false }
        case 'LOGOUT': return { user: null, isAuthenticated: false, isLoading: false }
        case 'LOADING': return { ...state, isLoading: payload }
        default: return state
    }
}

export function AuthProvider({ children }) {
    const [state, dispatch] = useReducer(reducer, init)

    // Hydrate on mount
    useEffect(() => {
        const token = localStorage.getItem('access_token')
        if (!token) { dispatch({ type: 'LOADING', payload: false }); return }
        getMe()
            .then((user) => dispatch({ type: 'SET_USER', payload: user }))
            .catch(() => { localStorage.clear(); dispatch({ type: 'LOGOUT' }) })
    }, [])

    const login = useCallback((tokens, user) => {
        localStorage.setItem('access_token', tokens.access)
        localStorage.setItem('refresh_token', tokens.refresh)
        dispatch({ type: 'SET_USER', payload: user })
    }, [])

    const logout = useCallback(() => {
        localStorage.clear()
        dispatch({ type: 'LOGOUT' })
    }, [])

    return (
        <AuthContext.Provider value={{ ...state, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be inside <AuthProvider>')
    return ctx
}