import axios from 'axios'

const api = axios.create({
    baseURL: '/api',   // proxied to http://localhost:8000/api via vite.config.js
    headers: { 'Content-Type': 'application/json' },
})

// ── Attach JWT token on every request ──────────────────────────────────────
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// ── Auto-refresh on 401 ────────────────────────────────────────────────────
let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
    failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)))
    failedQueue = []
}

api.interceptors.response.use(
    (res) => res,
    async (error) => {
        const original = error.config
        if (error.response?.status === 401 && !original._retry) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
                    .then((token) => { original.headers.Authorization = `Bearer ${token}`; return api(original) })
                    .catch(Promise.reject)
            }
            original._retry = true
            isRefreshing = true
            const refresh = localStorage.getItem('refresh_token')
            if (!refresh) { isRefreshing = false; localStorage.clear(); window.location.href = '/login'; return Promise.reject(error) }
            try {
                const { data } = await axios.post('/api/auth/token/refresh/', { refresh })
                localStorage.setItem('access_token', data.access)
                api.defaults.headers.common.Authorization = `Bearer ${data.access}`
                processQueue(null, data.access)
                original.headers.Authorization = `Bearer ${data.access}`
                return api(original)
            } catch (e) {
                processQueue(e, null)
                localStorage.clear()
                window.location.href = '/login'
                return Promise.reject(e)
            } finally { isRefreshing = false }
        }
        return Promise.reject(error)
    }
)

export default api