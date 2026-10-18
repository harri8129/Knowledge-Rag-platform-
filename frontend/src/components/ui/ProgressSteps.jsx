import { Check, X, Loader } from 'lucide-react'
import { cn } from '@/utils/cn'

// step = { label: string, status: 'pending' | 'active' | 'done' | 'error' }
export default function ProgressSteps({ steps }) {
    return (
        <div className="flex flex-col gap-3">
            {steps.map((step, i) => (
                <div key={i} className="flex items-center gap-3">
                    <div className={cn(
                        'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 border text-xs',
                        step.status === 'done' && 'bg-emerald-500/15 border-emerald-500/50 text-emerald-400',
                        step.status === 'active' && 'bg-brand-500/15  border-brand-500/50  text-brand-400',
                        step.status === 'error' && 'bg-red-500/15    border-red-500/50    text-red-400',
                        step.status === 'pending' && 'bg-white/5       border-white/15      text-white/20',
                    )}>
                        {step.status === 'done' && <Check size={13} />}
                        {step.status === 'active' && <Loader size={13} className="animate-spin" />}
                        {step.status === 'error' && <X size={13} />}
                        {step.status === 'pending' && <span className="w-1.5 h-1.5 rounded-full bg-white/20" />}
                    </div>
                    <p className={cn('text-sm flex-1 font-medium',
                        step.status === 'pending' ? 'text-white/30' : 'text-white'
                    )}>
                        {step.label}
                    </p>
                    <span className={cn('text-xs',
                        step.status === 'done' && 'text-emerald-400',
                        step.status === 'active' && 'text-brand-400',
                        step.status === 'error' && 'text-red-400',
                        step.status === 'pending' && 'text-white/20',
                    )}>
                        {step.status === 'done' && 'Completed'}
                        {step.status === 'active' && 'In progress...'}
                        {step.status === 'error' && 'Failed'}
                        {step.status === 'pending' && 'Pending'}
                    </span>
                </div>
            ))}
        </div>
    )
}