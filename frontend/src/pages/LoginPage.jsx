import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Lock, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import AuthLayout from '@/components/layout/AuthLayout'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { login as loginApi, getMe } from '@/services/auth.service'
import { useAuth } from '@/context/AuthContext'

export default function LoginPage() {
    const navigate = useNavigate()
    const { login } = useAuth()
    // SimpleJWT's TokenObtainPairView uses 'username' by default (not email)
    const [form, setForm]     = useState({ username: '', password: '' })
    const [showPass, setShowPass] = useState(false)
    const [error, setError]   = useState('')
    const [loading, setLoading] = useState(false)

    const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            // POST /api/auth/token/ — { username, password }
            const tokens = await loginApi(form)
            localStorage.setItem('access_token',  tokens.access)
            localStorage.setItem('refresh_token', tokens.refresh)
            const user = await getMe()
            login(tokens, user)
            toast.success(`Welcome back, ${user.username}!`)
            navigate('/app/home')
        } catch (err) {
            setError(err.response?.data?.detail || 'Invalid username or password')
        } finally {
            setLoading(false)
        }
    }

    return (
        <AuthLayout>
            <h1 className="text-2xl font-bold text-center mb-1">Welcome back</h1>
            <p className="text-sm text-white/40 text-center mb-6">Sign in to your account to continue</p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <Input
                    label="Username"
                    type="text"
                    placeholder="johndoe"
                    value={form.username}
                    onChange={set('username')}
                    leftIcon={<User size={15} />}
                    required
                />
                <Input
                    label="Password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="Enter your password"
                    value={form.password}
                    onChange={set('password')}
                    leftIcon={<Lock size={15} />}
                    rightIcon={
                        <span onClick={() => setShowPass((v) => !v)}>
                            {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                        </span>
                    }
                    required
                />

                <div className="flex items-center justify-between text-sm">
                    <label className="flex items-center gap-2 text-white/50 cursor-pointer select-none">
                        <input type="checkbox" className="accent-brand-500" /> Remember me
                    </label>
                    <span className="text-brand-400 hover:text-brand-300 cursor-pointer transition-colors text-xs">
                        Forgot password?
                    </span>
                </div>

                {error && (
                    <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                        {error}
                    </p>
                )}

                <Button type="submit" isLoading={loading} className="w-full justify-center mt-1">
                    Login
                </Button>
            </form>

            <p className="text-sm text-center text-white/40 mt-5">
                Don't have an account?{' '}
                <Link to="/register" className="text-brand-400 hover:text-brand-300 transition-colors">Register</Link>
            </p>
        </AuthLayout>
    )
}