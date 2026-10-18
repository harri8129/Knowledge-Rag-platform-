import { useState } from 'react'
import { Plus, Search, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'
import { useDocuments, useDeleteDocument, useProcessDocument, useRetryDocument } from '@/hooks/useDocuments'
import DocumentCard from '@/components/documents/DocumentCard'
import UploadModal from '@/components/documents/UploadModal'
import Button from '@/components/ui/Button'
import Spinner from '@/components/ui/Spinner'

export default function DocumentsPage() {
    const [search, setSearch] = useState('')
    const [uploadOpen, setUploadOpen] = useState(false)
    const { data: docs = [], isLoading, refetch } = useDocuments()
    const { mutate: del } = useDeleteDocument()
    const { mutate: process } = useProcessDocument()
    const { mutate: retry } = useRetryDocument()

    const filtered = docs.filter((d) => d.title.toLowerCase().includes(search.toLowerCase()))

    const handleDelete = (id) => {
        if (!confirm('Delete this document? This cannot be undone.')) return
        del(id, {
            onSuccess: () => toast.success('Document deleted'),
            onError: (e) => toast.error(e.response?.data?.error?.message || 'Delete failed'),
        })
    }

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold">Documents</h1>
                    <p className="text-sm text-white/40 mt-0.5">{docs.length} document{docs.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="flex items-center gap-3">
                    <button onClick={() => refetch()}
                        className="text-white/40 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
                        <RefreshCw size={17} />
                    </button>
                    <Button leftIcon={<Plus size={16} />} onClick={() => setUploadOpen(true)}>Upload Document</Button>
                </div>
            </div>

            <div className="relative mb-5">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                    className="w-full bg-surface-input border border-surface-border rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-brand-500 transition-all"
                    placeholder="Search documents..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>
            ) : filtered.length === 0 ? (
                <div className="text-center py-20 text-white/30">
                    <p className="text-lg mb-1">No documents found</p>
                    <p className="text-sm">Upload your first document to get started</p>
                </div>
            ) : (
                <div className="bg-surface-card border border-surface-border rounded-xl divide-y divide-surface-border">
                    {filtered.map((doc) => (
                        <DocumentCard key={doc.id} document={doc}
                            onDelete={handleDelete}
                            onProcess={(id) => process(id, { onSuccess: () => toast.success('Processing started') })}
                            onRetry={(id) => retry(id, { onSuccess: () => toast.success('Retrying...') })} />
                    ))}
                </div>
            )}
            <UploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} />
        </div>
    )
}