import { useState, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { askRAG, getDocumentChatHistory } from '@/services/documents.service'
import { useAuth } from '@/context/AuthContext'

export function useChat() {
    const { user } = useAuth()
    const [unscopedMessages, setUnscopedMessages] = useState([])
    const [activeDocumentId, setActiveDocumentId] = useState(null)
    const queryClient = useQueryClient()
    const historyKey = ['document-chat-history', user?.id, activeDocumentId]
    const {
        data: documentMessages = [],
        isError: historyError,
    } = useQuery({
        queryKey: historyKey,
        queryFn: () => getDocumentChatHistory(activeDocumentId),
        enabled: activeDocumentId !== null,
    })

    const { mutateAsync } = useMutation({ mutationFn: askRAG })

    const sendMessage = useCallback(async (query) => {
        if (!query.trim()) return
        const userId = crypto.randomUUID()
        const aiId = crypto.randomUUID()
        const documentId = activeDocumentId
        const targetKey = ['document-chat-history', user?.id, documentId]
        const setTargetMessages = (update) => {
            if (documentId !== null) {
                queryClient.setQueryData(targetKey, (previous = []) => update(previous))
            } else {
                setUnscopedMessages(update)
            }
        }

        setTargetMessages((prev) => [
            ...prev,
            { id: userId, role: 'user', content: query, timestamp: new Date() },
            { id: aiId, role: 'assistant', content: '', citations: [], timestamp: new Date(), isLoading: true },
        ])

        try {
            const result = await mutateAsync({ query, top_k: 5, document_id: documentId || undefined })
            setTargetMessages((prev) => prev.map((m) =>
                m.id === aiId ? { ...m, content: result.answer, citations: result.citations ?? [], isLoading: false } : m
            ))
            if (documentId !== null) {
                queryClient.invalidateQueries({ queryKey: targetKey })
            }
        } catch {
            setTargetMessages((prev) => prev.map((m) =>
                m.id === aiId ? { ...m, content: '⚠️ Failed to get an answer. Please try again.', isLoading: false, isError: true } : m
            ))
        }
    }, [activeDocumentId, mutateAsync, queryClient, user?.id])

    const messages = activeDocumentId === null ? unscopedMessages : documentMessages

    return { messages, sendMessage, activeDocumentId, setActiveDocumentId, historyError }
}