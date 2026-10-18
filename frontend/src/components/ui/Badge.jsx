import { cn } from '@/utils/cn'

const STATUSES = {
    READY: { label: 'Ready', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
    PROCESSING: { label: 'Processing', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30', pulse: true },
    CHUNKING: { label: 'Chunking', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30', pulse: true },
    INDEXING: { label: 'Indexing', cls: 'bg-violet-500/15 text-violet-400 border-violet-500/30', pulse: true },
    UPLOADED: { label: 'Uploaded', cls: 'bg-white/10 text-white/60 border-white/20' },
    FAILED: { label: 'Failed', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
    DELETING: { label: 'Deleting', cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30', pulse: true },
    DELETE_FAILED: { label: 'Del. Failed', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
    // lowercase variants (chunking_status / indexing_status)
    pending: { label: 'Pending', cls: 'bg-white/10 text-white/40 border-white/15' },
    processing: { label: 'Processing', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30', pulse: true },
    ready: { label: 'Ready', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
    failed: { label: 'Failed', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
}

export default function Badge({ status, className }) {
    const s = STATUSES[status] ?? { label: status, cls: 'bg-white/10 text-white/40 border-white/15' }
    return (
        <span className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border',
            s.cls, className
        )}>
            {s.pulse && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
            {s.label}
        </span>
    )
}