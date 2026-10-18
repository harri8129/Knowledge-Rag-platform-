const SUGGESTIONS = [
    'What is the refund policy?',
    'How to set up the system?',
    'What are the key features?',
    'Summarize the main points',
]

export default function SuggestedQueries({ onSelect }) {
    return (
        <div className="flex flex-wrap gap-2 justify-center">
            {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => onSelect(s)}
                    className="px-3 py-1.5 text-xs text-white/60 hover:text-white border border-surface-border hover:border-brand-500/40 rounded-full transition-all duration-150 hover:bg-brand-500/8 cursor-pointer">
                    {s}
                </button>
            ))}
        </div>
    )
}