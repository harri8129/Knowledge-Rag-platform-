import { FileText, ChevronDown, ChevronUp } from 'lucide-react'

export default function CitationCard({ citation, isOpened = false, onToggle }) {
    const handleToggle = () => {
        onToggle?.(isOpened ? null : citation.source_id)
    }

    return (
        <div className="border border-surface-border rounded-lg overflow-hidden">
            <button onClick={handleToggle}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/4 transition-colors">
                <span className="text-xs font-bold text-brand-400 bg-brand-500/15 rounded px-1.5 py-0.5">
                    {citation.source_id}
                </span>
                <FileText size={13} className="text-white/40 flex-shrink-0" />
                <span className="text-xs text-white/60 flex-1 truncate">{citation.document_title}</span>
                <span className="text-xs text-white/30 flex-shrink-0">p.{citation.page_number}</span>
                <span className="text-xs text-emerald-400/70 flex-shrink-0">
                    {citation.score != null ? `${Math.round(citation.score * 100)}%` : '—'}
                </span>
                {isOpened ? <ChevronUp size={13} className="text-white/30" /> : <ChevronDown size={13} className="text-white/30" />}
            </button>
            {isOpened && (
                <div className="px-3 pb-3 pt-1 border-t border-surface-border">
                    <p className="text-xs text-white/50 leading-relaxed line-clamp-6">
                        {citation.content || 'No excerpt available.'}
                    </p>
                </div>
            )}
        </div>
    )
}
