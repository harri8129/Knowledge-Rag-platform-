import { cn } from '@/utils/cn'

export default function Input({ label, error, hint, leftIcon, rightIcon, className, ...props }) {
    return (
        <div className="flex flex-col gap-1.5">
            {label && <label className="text-sm font-medium text-white/70">{label}</label>}
            <div className="relative">
                {leftIcon && (
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none">
                        {leftIcon}
                    </span>
                )}
                <input
                    className={cn(
                        'w-full bg-surface-input border border-surface-border rounded-lg px-4 py-2.5',
                        'text-white placeholder-white/25 text-sm outline-none',
                        'focus:border-brand-500 focus:ring-1 focus:ring-brand-500/40 transition-all duration-200',
                        leftIcon && 'pl-10',
                        rightIcon && 'pr-10',
                        error && 'border-red-500/60 focus:border-red-500 focus:ring-red-500/30',
                        className
                    )}
                    {...props}
                />
                {rightIcon && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 cursor-pointer">
                        {rightIcon}
                    </span>
                )}
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            {hint && !error && <p className="text-xs text-white/30">{hint}</p>}
        </div>
    )
}