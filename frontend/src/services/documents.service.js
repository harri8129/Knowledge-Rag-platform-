import api from './api'

export const listDocuments = () => api.get('/documents/').then((r) => r.data)
export const getDocument = (id) => api.get(`/documents/${id}/`).then((r) => r.data)
export const getDocumentChatHistory = (id) =>
    api.get(`/documents/${id}/chat-history/`).then((r) => r.data)
export const deleteDocument = (id) => api.delete(`/documents/${id}/`)
export const processDocument = (id) => api.post(`/documents/${id}/process/`).then((r) => r.data)
export const retryDocument = (id) => api.post(`/documents/${id}/retry/`).then((r) => r.data)

export const uploadDocument = ({ file, title }) => {
    const fd = new FormData()
    fd.append('file', file)
    if (title) fd.append('title', title)
    return api.post('/documents/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
}

// POST /api/documents/rag/
// payload: { query, top_k?, score_threshold?, document_id? }
export const askRAG = (payload) =>
    api.post('/documents/rag/', payload).then((r) => r.data)