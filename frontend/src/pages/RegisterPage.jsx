import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Mail, Lock, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import AuthLayout from '@/components/layout/AuthLayout'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { register, login as loginApi, getMe } from '@/services/auth.service'
import { useAuth } from '@/context/AuthContext'

export default function RegisterPage() {
    const navigate = useNavigate()
    const { login } = useAuth()
    const [form, setForm] = useState({ username: '', email: '', password: '', password2: '' })
    const [showPass, setShowPass]   = useState(false)
    const [showPass2, setShowPass2] = useState(false)
    const [errors, setErrors] = useState({})
    const [loading, setLoading] = useState(false)

    const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

    // Client-side validation before hitting the API
    const validate = () => {
        const e = {}
        if (!form.username.trim())             e.username  = 'Username is required'
        if (!form.email.includes('@'))         e.email     = 'Enter a valid email'
        if (form.password.length < 8)          e.password  = 'At least 8 characters'
        if (form.password !== form.password2)  e.password2 = 'Passwords do not match'
        return e
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        const errs = validate()
        if (Object.keys(errs).length) { setErrors(errs); return }
        setErrors({})
        setLoading(true)
        try {
            // POST /api/auth/register/ — { username, email, password, password2 }
            await register(form)
            // Log in immediately after registration using username + password
            const tokens = await loginApi({ username: form.username, password: form.password })
            localStorage.setItem('access_token',  tokens.access)
            localStorage.setItem('refresh_token', tokens.refresh)
            const user = await getMe()
            login(tokens, user)
            toast.success('Account created! Welcome 🎉')
            navigate('/app/home')
        } catch (err) {
            const data = err.response?.data
            // Backend returns { field: ["error message"] }
            if (data && typeof data === 'object') {
                const mapped = {}
                Object.entries(data).forEach(([key, val]) => {
                    mapped[key] = Array.isArray(val) ? val[0] : val
                })
                setErrors(mapped)
                if (mapped.non_field_errors) toast.error(mapped.non_field_errors)
            } else {
                toast.error('Registration failed. Try again.')
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <AuthLayout>
            <h1 className="text-2xl font-bold text-center mb-1">Create your account</h1>
            <p className="text-sm text-white/40 text-center mb-6">Join and start chatting with your documents</p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <Input
                    label="Username"
                    type="text"
                    placeholder="johndoe"
                    value={form.username}
                    onChange={set('username')}
                    leftIcon={<User size={15} />}
                    error={errors.username}
                    required
                />
                <Input
                    label="Email"
                    type="email"
                    placeholder="you@example.com"
                    value={form.email}
                    onChange={set('email')}
                    leftIcon={<Mail size={15} />}
                    error={errors.email}
                    required
                />
                <Input
                    label="Password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="Create a password"
                    value={form.password}
                    onChange={set('password')}
                    leftIcon={<Lock size={15} />}
                    rightIcon={
                        <span onClick={() => setShowPass((v) => !v)}>
                            {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                        </span>
                    }
                    error={errors.password}
                    hint="Minimum 8 characters"
                    required
                />
                <Input
                    label="Confirm Password"
                    type={showPass2 ? 'text' : 'password'}
                    placeholder="Repeat your password"
                    value={form.password2}
                    onChange={set('password2')}
                    leftIcon={<Lock size={15} />}
                    rightIcon={
                        <span onClick={() => setShowPass2((v) => !v)}>
                            {showPass2 ? <EyeOff size={15} /> : <Eye size={15} />}
                        </span>
                    }
                    error={errors.password2}
                    required
                />

                {/* General / non-field server error */}
                {errors.detail && (
                    <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                        {errors.detail}
                    </p>
                )}

                <Button type="submit" isLoading={loading} className="w-full justify-center mt-1">
                    Register
                </Button>
            </form>

            <p className="text-sm text-center text-white/40 mt-5">
                Already have an account?{' '}
                <Link to="/login" className="text-brand-400 hover:text-brand-300 transition-colors">Login</Link>
            </p>
        </AuthLayout>
    )
}