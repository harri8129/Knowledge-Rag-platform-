import { useState, useRef, useEffect } from 'react'
import { Plus, Search, BookOpen } from 'lucide-react'
import toast from 'react-hot-toast'
import { useDocuments, useDeleteDocument, useProcessDocument, useRetryDocument } from '@/hooks/useDocuments'
import { useChat } from '@/hooks/useChat'
import DocumentCard from '@/components/documents/DocumentCard'
import ChatMessage from '@/components/chat/ChatMessage'
import ChatInput from '@/components/chat/ChatInput'
import SuggestedQueries from '@/components/chat/SuggestedQueries'
import UploadModal from '@/components/documents/UploadModal'
import Button from '@/components/ui/Button'
import Spinner from '@/components/ui/Spinner'

export default function DashboardPage() {
    const [search, setSearch] = useState('')
    const [uploadOpen, setUploadOpen] = useState(false)
    const { data: docs = [], isLoading } = useDocuments()
    const { messages, sendMessage, activeDocumentId, setActiveDocumentId, historyError } = useChat()
    const { mutate: del } = useDeleteDocument()
    const { mutate: process } = useProcessDocument()
    const { mutate: retry } = useRetryDocument()
    const bottomRef = useRef(null)

    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

    const filtered = docs.filter((d) => d.title.toLowerCase().includes(search.toLowerCase()))

    return (
        <div className="flex h-screen">
            {/* Left panel */}
            <div className="w-72 h-full border-r border-surface-border flex flex-col bg-surface-muted">
                <div className="flex items-center justify-between px-4 py-4 border-b border-surface-border">
                    <div>
                        <h2 className="text-sm font-semibold">Knowledge Engine</h2>
                        <p className="text-xs text-white/30">Chat with your docs using AI</p>
                    </div>
                    <Button size="sm" leftIcon={<Plus size={13} />} onClick={() => setUploadOpen(true)}>Upload</Button>
                </div>
                <div className="px-3 pt-3">
                    <div className="relative">
                        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                        <input className="w-full bg-surface-input border border-surface-border rounded-lg pl-8 pr-3 py-2 text-xs text-white placeholder-white/25 outline-none focus:border-brand-500 transition-all"
                            placeholder="Search documents..." value={search} onChange={(e) => setSearch(e.target.value)} />
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-2 pt-3">
                    <p className="text-xs text-white/30 px-2 mb-1 font-medium">Documents</p>
                    {isLoading ? <div className="flex justify-center pt-8"><Spinner /></div>
                        : filtered.length === 0 ? <p className="text-xs text-white/20 text-center pt-8">No documents yet</p>
                            : filtered.map((doc) => (
                                <DocumentCard key={doc.id} document={doc}
                                    isActive={activeDocumentId === doc.id}
                                    onClick={(d) => setActiveDocumentId(activeDocumentId === d.id ? null : d.id)}
                                    onDelete={(id) => del(id, { onSuccess: () => toast.success('Deleted') })}
                                    onProcess={(id) => process(id, { onSuccess: () => toast.success('Processing started') })}
                                    onRetry={(id) => retry(id, { onSuccess: () => toast.success('Retrying...') })} />
                            ))
                    }
                </div>
            </div>

            {/* Right panel — chat */}
            <div className="flex-1 flex flex-col h-full">
                <div className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5">
                    {historyError && (
                        <p className="text-sm text-red-400 text-center">
                            Could not load this document's chat history. Please try again.
                        </p>
                    )}
                    {messages.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center gap-5 animate-fade-in">
                            <div className="text-center">
                                <div className="w-12 h-12 bg-brand-500/15 border border-brand-500/30 rounded-xl flex items-center justify-center mx-auto mb-3">
                                    <BookOpen size={24} className="text-brand-400" />
                                </div>
                                <h2 className="text-lg font-semibold">Ask your documents</h2>
                                <p className="text-sm text-white/40 mt-1">Get accurate answers with citations from your uploaded documents.</p>
                            </div>
                            <SuggestedQueries onSelect={sendMessage} />
                        </div>
                    ) : (
                        <>{messages.map((m) => <ChatMessage key={m.id} message={m} />)}<div ref={bottomRef} /></>
                    )}
                </div>
                <div className="px-8 pb-6 pt-2">
                    <ChatInput onSend={sendMessage} />
                </div>
            </div>
            <UploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} />
        </div>
    )
}