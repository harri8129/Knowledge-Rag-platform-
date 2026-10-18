import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/utils/cn'

export default function Modal({ isOpen, onClose, title, children, className }) {
    useEffect(() => {
        if (!isOpen) return
        const handler = (e) => { if (e.key === 'Escape') onClose() }
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [isOpen, onClose])

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
            <div className={cn(
                'relative z-10 w-full max-w-md p-6 rounded-xl animate-slide-up',
                'bg-surface-card border border-surface-border shadow-2xl shadow-black/60',
                className
            )}>
                <div className="flex items-center justify-between mb-5">
                    <h2 className="text-lg font-semibold">{title}</h2>
                    <button onClick={onClose}
                        className="text-white/30 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/5">
                        <X size={18} />
                    </button>
                </div>
                {children}
            </div>
        </div>
    )
}