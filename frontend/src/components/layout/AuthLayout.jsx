import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'

export default function AuthLayout({ children }) {
    return (
        <div className="min-h-screen bg-surface flex items-center justify-center p-4">
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-96 h-96 bg-brand-500/8 rounded-full blur-3xl pointer-events-none" />
            <div className="relative w-full max-w-sm animate-slide-up">
                <div className="text-center mb-8">
                    <Link to="/" className="inline-flex items-center gap-2.5 text-white">
                        <div className="w-10 h-10 bg-brand-500/20 border border-brand-500/40 rounded-xl flex items-center justify-center">
                            <BookOpen size={20} className="text-brand-400" />
                        </div>
                        <span className="text-xl font-bold">Knowledge RAG</span>
                    </Link>
                </div>
                <div className="bg-surface-card border border-surface-border rounded-xl p-7 shadow-2xl shadow-black/50">
                    {children}
                </div>
            </div>
        </div>
    )
}