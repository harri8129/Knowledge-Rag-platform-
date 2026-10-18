import { useState } from 'react'
import { MoreVertical, Play, RefreshCw, Trash2 } from 'lucide-react'
import Badge from '@/components/ui/Badge'
import { formatDate } from '@/utils/formatters'
import { cn } from '@/utils/cn'

const TYPE_STYLE = {
    pdf: 'bg-red-500/20 text-red-300',
    txt: 'bg-blue-500/20 text-blue-300',
    markdown: 'bg-violet-500/20 text-violet-300',
}

export default function DocumentCard({ document: doc, onProcess, onRetry, onDelete, onClick, isActive }) {
    const [menu, setMenu] = useState(false)

    return (
        <div
            onClick={() => onClick?.(doc)}
            className={cn(
                'flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-150 border cursor-pointer',
                isActive ? 'bg-brand-500/8 border-brand-500/40' : 'border-transparent hover:bg-white/4'
            )}
        >
            {/* File type label */}
            <div className={cn(
                'w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 uppercase',
                TYPE_STYLE[doc.file_type] || 'bg-white/10 text-white/50'
            )}>
                {doc.file_type === 'markdown' ? 'MD' : doc.file_type?.toUpperCase()}
            </div>

            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{doc.title}</p>
                <div className="flex items-center gap-2 mt-0.5">
                    <Badge status={doc.status} />
                    <span className="text-xs text-white/30">{formatDate(doc.created_at)}</span>
                </div>
            </div>

            <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                <button onClick={() => setMenu((v) => !v)}
                    className="text-white/25 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/5">
                    <MoreVertical size={15} />
                </button>
                {menu && (
                    <div className="absolute right-0 top-8 z-10 bg-surface-card border border-surface-border rounded-xl w-36 py-1 shadow-xl">
                        {doc.status === 'UPLOADED' && (
                            <button onClick={() => { onProcess?.(doc.id); setMenu(false) }}
                                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-white/70 hover:text-white hover:bg-white/5 transition-colors">
                                <Play size={12} /> Process
                            </button>
                        )}
                        {doc.status === 'FAILED' && (
                            <button onClick={() => { onRetry?.(doc.id); setMenu(false) }}
                                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-amber-400 hover:bg-white/5 transition-colors">
                                <RefreshCw size={12} /> Retry
                            </button>
                        )}
                        <button onClick={() => { onDelete?.(doc.id); setMenu(false) }}
                            className="flex items-center gap-2 w-full px-3 py-2 text-xs text-red-400 hover:bg-white/5 transition-colors">
                            <Trash2 size={12} /> Delete
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}