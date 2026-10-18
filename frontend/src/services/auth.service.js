import api from './api'

// POST /api/auth/token/  →  { access, refresh }
// SimpleJWT expects { username, password } by default
export const login = ({ username, password }) =>
    api.post('/auth/token/', { username, password }).then((r) => r.data)

// POST /api/auth/register/  →  { id, username, email, date_joined }
// Expects { username, email, password, password2 }
export const register = (payload) =>
    api.post('/auth/register/', payload).then((r) => r.data)

// GET /api/auth/me/  →  { id, username, email, date_joined }
export const getMe = () =>
    api.get('/auth/me/').then((r) => r.data)

// POST /api/auth/token/refresh/
export const refreshToken = (refresh) =>
    api.post('/auth/token/refresh/', { refresh }).then((r) => r.data)