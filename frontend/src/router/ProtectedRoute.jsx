import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import Spinner from '@/components/ui/Spinner'

export default function ProtectedRoute({ children }) {
    const { isAuthenticated, isLoading } = useAuth()
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-surface)' }}>
                <Spinner size="lg" />
            </div>
        )
    }
    return isAuthenticated ? children : <Navigate to="/login" replace />
}