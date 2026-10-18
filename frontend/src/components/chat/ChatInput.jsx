import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { cn } from '@/utils/cn'

export default function ChatInput({ onSend, isLoading, placeholder = 'Type your question here...' }) {
    const [value, setValue] = useState('')
    const ref = useRef(null)

    useEffect(() => {
        if (!ref.current) return
        ref.current.style.height = 'auto'
        ref.current.style.height = `${Math.min(ref.current.scrollHeight, 160)}px`
    }, [value])

    const send = () => {
        if (!value.trim() || isLoading) return
        onSend(value.trim())
        setValue('')
    }

    return (
        <div className="flex items-end gap-2 p-3 bg-surface-card border border-surface-border rounded-2xl">
            <textarea ref={ref} rows={1} value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder={placeholder}
                className="flex-1 bg-transparent text-sm text-white placeholder-white/25 resize-none outline-none leading-relaxed" />
            <button onClick={send} disabled={!value.trim() || isLoading}
                className={cn(
                    'w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 mb-0.5 flex-shrink-0',
                    value.trim() && !isLoading
                        ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/30 hover:bg-brand-600 cursor-pointer'
                        : 'bg-white/5 text-white/20 cursor-not-allowed'
                )}>
                <Send size={15} />
            </button>
        </div>
    )
}