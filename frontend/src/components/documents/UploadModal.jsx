import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, X } from 'lucide-react'
import toast from 'react-hot-toast'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { useUploadDocument } from '@/hooks/useDocuments'
import { formatFileSize } from '@/utils/formatters'
import { cn } from '@/utils/cn'

export default function UploadModal({ isOpen, onClose }) {
    const [file, setFile] = useState(null)
    const [title, setTitle] = useState('')
    const { mutateAsync: upload, isPending } = useUploadDocument()

    const onDrop = useCallback((accepted) => {
        const f = accepted[0]
        if (!f) return
        setFile(f)
        setTitle(f.name.replace(/\.[^.]+$/, ''))
    }, [])

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'], 'text/markdown': ['.md'] },
        maxFiles: 1,
    })

    const reset = () => { setFile(null); setTitle('') }
    const handleClose = () => { reset(); onClose() }

    const handleUpload = async () => {
        if (!file) return
        try {
            await upload({ file, title: title.trim() || undefined })
            toast.success('Document uploaded!')
            handleClose()
        } catch (err) {
            toast.error(err.response?.data?.file?.[0] || 'Upload failed')
        }
    }

    return (
        <Modal isOpen={isOpen} onClose={handleClose} title="Upload Document">
            <div {...getRootProps()} className={cn(
                'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200',
                isDragActive ? 'border-brand-500 bg-brand-500/10' : 'border-surface-border hover:border-brand-500/50'
            )}>
                <input {...getInputProps()} />
                <Upload className="mx-auto text-brand-400 mb-3" size={30} />
                <p className="text-sm font-medium">Drop your document here</p>
                <p className="text-xs text-white/30 mt-1">or <span className="text-brand-400">click to browse</span></p>
                <p className="text-xs text-white/20 mt-3">Supports PDF, TXT, Markdown</p>
            </div>

            {file && (
                <div className="mt-4 flex items-center gap-3 p-3 bg-white/4 rounded-lg border border-surface-border">
                    <File size={15} className="text-brand-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{file.name}</p>
                        <p className="text-xs text-white/30">{formatFileSize(file.size)}</p>
                    </div>
                    <button onClick={() => setFile(null)} className="text-white/30 hover:text-white transition-colors">
                        <X size={14} />
                    </button>
                </div>
            )}

            <div className="mt-4">
                <Input label="Title (optional)" placeholder="Auto-filled from filename"
                    value={title} onChange={(e) => setTitle(e.target.value)}
                    hint="Leave blank to use the filename" />
            </div>

            <div className="flex gap-3 mt-6">
                <Button variant="secondary" className="flex-1 justify-center" onClick={handleClose}>Cancel</Button>
                <Button className="flex-1 justify-center" onClick={handleUpload} isLoading={isPending} disabled={!file}>
                    Upload
                </Button>
            </div>
        </Modal>
    )
}