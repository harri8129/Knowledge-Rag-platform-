import { Link } from 'react-router-dom'
import { BookOpen, ArrowRight, Zap, Shield, FileText } from 'lucide-react'

export default function LandingPage() {
    return (
        <div className="min-h-screen bg-surface overflow-x-hidden">
            <div className="fixed top-0 left-1/4 w-96 h-96 rounded-full blur-3xl pointer-events-none"
                style={{ background: 'color-mix(in srgb, var(--color-brand-500) 8%, transparent)' }} />
            <div className="fixed top-1/2 right-0 w-64 h-64 rounded-full blur-3xl pointer-events-none"
                style={{ background: 'color-mix(in srgb, #8b5cf6 8%, transparent)' }} />

            {/* Navbar */}
            <nav className="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-brand-500/20 border border-brand-500/40 rounded-xl flex items-center justify-center">
                        <BookOpen size={16} className="text-brand-400" />
                    </div>
                    <span className="font-bold">Knowledge RAG</span>
                </div>
                <div className="flex items-center gap-6 text-sm text-white/50">
                    <span className="hover:text-white cursor-pointer transition-colors">Features</span>
                    <span className="hover:text-white cursor-pointer transition-colors">How it works</span>
                    <Link to="/login" className="hover:text-white transition-colors">Login</Link>
                    <Link to="/register"
                        className="bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg transition-colors font-medium">
                        Get Started
                    </Link>
                </div>
            </nav>

            {/* Hero */}
            <section className="max-w-6xl mx-auto px-8 pt-20 pb-28 text-center">
                <div className="inline-flex items-center gap-2 text-xs text-brand-300 bg-brand-500/10 border border-brand-500/30 rounded-full px-3 py-1 mb-8">
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
                    Powered by RAG technology
                </div>
                <h1 className="text-6xl font-extrabold leading-tight mb-6">
                    Chat with your{' '}
                    <span style={{ background: 'linear-gradient(to right, #818cf8, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        documents
                    </span>
                </h1>
                <p className="text-lg text-white/40 max-w-2xl mx-auto mb-10 leading-relaxed">
                    Upload your PDFs, text files, or markdown documents and get accurate, cited answers using advanced RAG technology.
                </p>
                <div className="flex items-center justify-center gap-4">
                    <Link to="/register"
                        className="inline-flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white px-6 py-3 rounded-xl font-semibold transition-all shadow-xl"
                        style={{ boxShadow: '0 10px 30px color-mix(in srgb, var(--color-brand-500) 30%, transparent)' }}>
                        Get Started <ArrowRight size={18} />
                    </Link>
                    <Link to="/login"
                        className="inline-flex items-center gap-2 border border-surface-border hover:border-white/30 text-white/70 hover:text-white px-6 py-3 rounded-xl font-medium transition-all">
                        Learn More
                    </Link>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-4 mt-14">
                    {[
                        { icon: Zap, text: 'Accurate answers with citations' },
                        { icon: Shield, text: 'Your data stays private' },
                        { icon: FileText, text: 'PDF, TXT, Markdown support' },
                    ].map(({ icon: Icon, text }) => (
                        <div key={text} className="flex items-center gap-2 text-sm text-white/50 bg-white/4 border border-surface-border rounded-full px-4 py-2">
                            <Icon size={14} className="text-brand-400" /> {text}
                        </div>
                    ))}
                </div>
            </section>

            {/* How it works */}
            <section className="max-w-4xl mx-auto px-8 pb-24 text-center">
                <h2 className="text-3xl font-bold mb-3">How it works</h2>
                <p className="text-white/40 mb-12">Three simple steps to get started</p>
                <div className="grid grid-cols-3 gap-6">
                    {[
                        { step: '01', title: 'Upload', desc: 'Upload your PDF, TXT, or Markdown files.' },
                        { step: '02', title: 'Process', desc: 'Our AI chunks, embeds and indexes your documents.' },
                        { step: '03', title: 'Chat', desc: 'Ask questions and get cited, accurate answers instantly.' },
                    ].map(({ step, title, desc }) => (
                        <div key={step} className="bg-surface-card border border-surface-border rounded-xl p-6 text-left relative overflow-hidden">
                            <span className="text-5xl font-black text-white/4 absolute top-3 right-4 select-none">{step}</span>
                            <div className="w-8 h-8 rounded-lg bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-xs font-bold text-brand-400 mb-4">
                                {step}
                            </div>
                            <h3 className="font-semibold mb-1">{title}</h3>
                            <p className="text-sm text-white/40">{desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            <footer className="border-t border-surface-border py-6 text-center text-sm text-white/20">
                © 2026 Knowledge RAG. All rights reserved.
            </footer>
        </div>
    )
}