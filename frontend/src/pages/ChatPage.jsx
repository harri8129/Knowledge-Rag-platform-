import { useEffect, useRef } from 'react'
import { BookOpen, X } from 'lucide-react'
import { useDocuments } from '@/hooks/useDocuments'
import { useChat } from '@/hooks/useChat'
import ChatMessage from '@/components/chat/ChatMessage'
import ChatInput from '@/components/chat/ChatInput'
import SuggestedQueries from '@/components/chat/SuggestedQueries'
import { cn } from '@/utils/cn'

export default function ChatPage() {
    const { data: docs = [] } = useDocuments()
    const { messages, sendMessage, activeDocumentId, setActiveDocumentId, historyError } = useChat()
    const bottomRef = useRef(null)
    const readyDocs = docs.filter((d) => d.status === 'READY')
    const activeDoc = readyDocs.find((d) => d.id === activeDocumentId)

    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

    return (
        <div className="flex h-screen">
            {/* Left — doc selector */}
            <div className="w-64 h-full border-r border-surface-border flex flex-col bg-surface-muted">
                <div className="p-4 border-b border-surface-border">
                    <h2 className="text-sm font-semibold">Documents</h2>
                    <p className="text-xs text-white/30 mt-0.5">Scope your chat to a document</p>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                    <button onClick={() => setActiveDocumentId(null)}
                        className={cn('w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-left transition-all mb-1',
                            !activeDocumentId ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30' : 'text-white/50 hover:text-white hover:bg-white/5')}>
                        <BookOpen size={14} /> All documents
                    </button>
                    {readyDocs.map((d) => (
                        <button key={d.id} onClick={() => setActiveDocumentId(d.id)}
                            className={cn('w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs text-left transition-all',
                                activeDocumentId === d.id ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30' : 'text-white/50 hover:text-white hover:bg-white/5')}>
                            <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
                            <span className="flex-1 truncate">{d.title}</span>
                        </button>
                    ))}
                    {readyDocs.length === 0 && (
                        <p className="text-xs text-white/20 text-center mt-8 px-3">Upload and process documents first</p>
                    )}
                </div>
            </div>

            {/* Right — chat */}
            <div className="flex-1 flex flex-col h-full">
                <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border">
                    <div>
                        <h1 className="text-lg font-semibold">Knowledge Engine</h1>
                        <p className="text-xs text-white/30">Chat with your documents using AI</p>
                    </div>
                    {activeDoc && (
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-brand-500/10 border border-brand-500/30 rounded-full">
                            <span className="text-xs text-brand-300">Scoped: {activeDoc.title}</span>
                            <button onClick={() => setActiveDocumentId(null)} className="text-brand-400/50 hover:text-brand-400 cursor-pointer"><X size={12} /></button>
                        </div>
                    )}
                </div>
                <div className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-5">
                    {historyError && (
                        <p className="text-sm text-red-400 text-center">
                            Could not load this document's chat history. Please try again.
                        </p>
                    )}
                    {messages.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center gap-6 animate-fade-in">
                            <div className="text-center">
                                <div className="w-14 h-14 bg-brand-500/15 border border-brand-500/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                    <BookOpen size={28} className="text-brand-400" />
                                </div>
                                <h2 className="text-xl font-semibold">Ask your documents</h2>
                                <p className="text-sm text-white/40 mt-1">Get accurate answers with citations from your uploaded documents.</p>
                            </div>
                            <SuggestedQueries onSelect={sendMessage} />
                        </div>
                    ) : (
                        <>{messages.map((m) => <ChatMessage key={m.id} message={m} />)}<div ref={bottomRef} /></>
                    )}
                </div>
                <div className="px-6 pb-6 pt-2">
                    <ChatInput onSend={sendMessage} />
                </div>
            </div>
        </div>
    )
}