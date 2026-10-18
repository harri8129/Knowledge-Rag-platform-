import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function AppLayout() {
    return (
        <div className="flex min-h-screen bg-surface">
            <Sidebar />
            <main className="flex-1 ml-60 min-h-screen overflow-auto">
                <Outlet />
            </main>
        </div>
    )
}