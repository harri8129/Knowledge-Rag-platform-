import ProgressSteps from '@/components/ui/ProgressSteps'

const ORDER = ['UPLOADED', 'PROCESSING', 'CHUNKING', 'INDEXING', 'READY']

function stepStatus(doc, targetStatus, altActive = []) {
    if (altActive.includes(doc.status)) return 'active'
    const ci = ORDER.indexOf(doc.status)
    const ti = ORDER.indexOf(targetStatus)
    if (ci > ti) return 'done'
    if (ci === ti) return 'active'
    return 'pending'
}

export default function ProcessingSteps({ document: doc }) {
    if (!doc) return null

    const overallFailed = doc.status === 'FAILED'

    const steps = [
        { label: 'Uploading', status: ORDER.indexOf(doc.status) >= 0 ? 'done' : 'pending' },
        { label: 'Processing', status: stepStatus(doc, 'PROCESSING') },
        {
            label: 'Chunking',
            status: doc.chunking_status === 'processing' ? 'active'
                : doc.chunking_status === 'ready' ? 'done'
                    : doc.chunking_status === 'failed' ? 'error'
                        : 'pending',
        },
        {
            label: 'Indexing',
            status: doc.indexing_status === 'processing' ? 'active'
                : doc.indexing_status === 'ready' ? 'done'
                    : doc.indexing_status === 'failed' ? 'error'
                        : 'pending',
        },
        { label: 'Ready', status: doc.status === 'READY' ? 'done' : 'pending' },
    ]

    if (overallFailed) {
        const firstNonDone = steps.findIndex((s) => s.status !== 'done')
        if (firstNonDone !== -1) steps[firstNonDone].status = 'error'
    }

    return <ProgressSteps steps={steps} />
}