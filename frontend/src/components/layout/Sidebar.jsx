import { NavLink, useNavigate } from 'react-router-dom'
import { Home, FileText, MessageSquare, Settings, BookOpen, LogOut } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/utils/cn'

const NAV = [
    { icon: Home, label: 'Home', to: '/app/home' },
    { icon: FileText, label: 'Documents', to: '/app/documents' },
    { icon: MessageSquare, label: 'Chat', to: '/app/chat' },
    { icon: Settings, label: 'Settings', to: '/app/settings' },
]

export default function Sidebar() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const initials = (user?.username?.[0] ?? user?.email?.[0] ?? 'U').toUpperCase()

    return (
        <aside className="w-60 h-screen bg-surface-muted border-r border-surface-border flex flex-col fixed left-0 top-0 z-20">
            {/* Logo */}
            <div className="flex items-center gap-2.5 px-5 py-5 border-b border-surface-border">
                <div className="w-8 h-8 bg-brand-500/20 border border-brand-500/40 rounded-lg flex items-center justify-center">
                    <BookOpen size={16} className="text-brand-400" />
                </div>
                <span className="font-bold">Knowledge RAG</span>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
                {NAV.map(({ icon: Icon, label, to }) => (
                    <NavLink key={to} to={to} className={({ isActive }) => cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                        isActive
                            ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
                            : 'text-white/50 hover:text-white hover:bg-white/5'
                    )}>
                        <Icon size={17} />
                        {label}
                    </NavLink>
                ))}
            </nav>

            {/* User footer */}
            <div className="px-4 py-4 border-t border-surface-border">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-brand-500/25 border border-brand-500/40 flex items-center justify-center text-xs font-bold text-brand-300 flex-shrink-0">
                        {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{user?.username || 'User'}</p>
                        <p className="text-xs text-white/30 truncate">{user?.email}</p>
                    </div>
                    <button onClick={() => { logout(); navigate('/login') }}
                        className="text-white/25 hover:text-red-400 transition-colors p-1 rounded" title="Logout">
                        <LogOut size={16} />
                    </button>
                </div>
            </div>
        </aside>
    )
}