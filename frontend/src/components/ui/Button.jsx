import { cn } from '@/utils/cn'
import Spinner from './Spinner'

const variants = {
    primary: 'bg-brand-500 hover:bg-brand-600 text-white shadow-lg shadow-brand-500/25',
    secondary: 'bg-surface-muted hover:bg-surface-border text-white border border-surface-border',
    ghost: 'bg-transparent hover:bg-white/5 text-white/70 hover:text-white',
    danger: 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30',
}
const sizes = {
    sm: 'px-3 py-1.5 text-xs rounded-lg',
    md: 'px-4 py-2 text-sm rounded-lg',
    lg: 'px-6 py-3 text-base rounded-xl',
}

export default function Button({
    variant = 'primary', size = 'md', isLoading = false,
    leftIcon, children, className, disabled, ...props
}) {
    return (
        <button
            className={cn(
                'inline-flex items-center gap-2 font-medium transition-all duration-200 cursor-pointer',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                variants[variant], sizes[size], className
            )}
            disabled={disabled || isLoading}
            {...props}
        >
            {isLoading ? <Spinner size="sm" /> : leftIcon}
            {children}
        </button>
    )
}