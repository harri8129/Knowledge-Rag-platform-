import { useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import Button from '@/components/ui/Button'

export default function SettingsPage() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const initials = (user?.username?.[0] ?? user?.email?.[0] ?? 'U').toUpperCase()

    return (
        <div className="p-8 max-w-lg mx-auto">
            <h1 className="text-2xl font-bold mb-8">Settings</h1>
            <div className="bg-surface-card border border-surface-border rounded-xl p-6">
                <div className="flex items-center gap-5 mb-6 pb-6 border-b border-surface-border">
                    <div className="w-16 h-16 rounded-2xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-2xl font-bold text-brand-300">
                        {initials}
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold">{user?.username || 'User'}</h2>
                        <p className="text-sm text-white/40">{user?.email}</p>
                    </div>
                </div>
                <Button variant="danger" leftIcon={<LogOut size={15} />} className="w-full justify-center"
                    onClick={() => { logout(); navigate('/login') }}>
                    Sign out
                </Button>
            </div>
        </div>
    )
}