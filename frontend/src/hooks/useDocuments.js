import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    listDocuments, getDocument, uploadDocument,
    deleteDocument, processDocument, retryDocument,
} from '@/services/documents.service'
import { useAuth } from '@/context/AuthContext'

const TERMINAL = ['READY', 'FAILED', 'DELETE_FAILED']

export const useDocuments = () => {
    const { user } = useAuth()
    return useQuery({
        queryKey: ['documents', user?.id],
        queryFn: listDocuments,
        enabled: Boolean(user?.id),
        // Auto-refresh the document list while any document is still processing
        refetchInterval: (query) => {
            const docs = query.state.data ?? []
            const anyNonTerminal = docs.some(
                (d) => !TERMINAL.includes(d.status)
            )
            return anyNonTerminal ? 3000 : false
        },
    })
}

export const useDocument = (id) => {
    const { user } = useAuth()
    return useQuery({
        queryKey: ['document', user?.id, id],
        queryFn: () => getDocument(id),
        enabled: Boolean(user?.id && id),
        refetchInterval: (query) =>
            TERMINAL.includes(query.state.data?.status) ? false : 3000,
    })
}

export const useUploadDocument = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: uploadDocument,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
    })
}

export const useDeleteDocument = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: deleteDocument,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
    })
}

export const useProcessDocument = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: processDocument,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
    })
}

export const useRetryDocument = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: retryDocument,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
    })
}