import { Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import CitationCard from './CitationCard'
import Spinner from '@/components/ui/Spinner'
import { cn } from '@/utils/cn'

export default function ChatMessage({ message }) {
    if (message.role === 'user') {
        return (
            <div className="flex justify-end animate-fade-in">
                <div className="max-w-3/4 bg-brand-500/15 border border-brand-500/25 rounded-2xl rounded-tr-sm px-4 py-3">
                    <p className="text-sm">{message.content}</p>
                </div>
            </div>
        )
    }
    return (
        <div className="flex gap-3 animate-fade-in">
            <div className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/40 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot size={14} className="text-brand-400" />
            </div>
            <div className="flex-1">
                <div className="bg-surface-card border border-surface-border rounded-2xl rounded-tl-sm px-4 py-3">
                    {message.isLoading ? (
                        <div className="flex items-center gap-2">
                            <Spinner size="sm" />
                            <span className="text-sm text-white/40">Thinking...</span>
                        </div>
                    ) : (
                        <div className={cn('text-sm text-white/90 prose prose-invert prose-sm max-w-none',
                            message.isError && 'text-red-400')}>
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>
                    )}
                </div>
                {!message.isLoading && message.citations?.length > 0 && (
                    <div className="mt-2 flex flex-col gap-1.5">
                        <p className="text-xs text-white/30 px-1">Sources</p>
                        {message.citations.map((c, i) => <CitationCard key={i} citation={c} index={i} />)}
                    </div>
                )}
            </div>
        </div>
    )
}