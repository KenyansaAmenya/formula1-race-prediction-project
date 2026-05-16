import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Home, BarChart3, Users, Trophy, LogOut } from 'lucide-react'

const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/predictions', label: 'Predictions', icon: BarChart3 },
    { path: '/drivers', label: 'Drivers', icon: Users },
    { path: '/leaderboard', label: 'Leaderboard', icon: Trophy },
]

export default function Navigation() {
    const location = useLocation()

    const handleLogout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
    }

    return (
        <nav className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-xl border-b border-slate-800">
            <div className="container mx-auto px-4">
                <div className="flex items-center justify-between h-16">
                    <Link to="/" className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
                            <span className="text-white font-black text-sm">F1</span>
                        </div>
                        <span className="text-white font-bold text-lg hidden sm:block">AI Platform</span>
                    </Link>

                    <div className="flex items-center gap-1">
                        {navItems.map((item) => {
                            const isActive = location.pathname === item.path
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    className="relative px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                                >
                                    <span className={`flex items-center gap-2 ${isActive ? 'text-white' : 'text-slate-400 hover:text-white'}`}>
                                        <item.icon className="w-4 h-4" />
                                        <span className="hidden md:block">{item.label}</span>
                                    </span>
                                    {isActive && (
                                        <motion.div
                                            layoutId="activeNav"
                                            className="absolute inset-0 bg-slate-800 rounded-lg -z-10"
                                            transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                                        />
                                    )}
                                </Link>
                            )
                        })}

                        <button
                            onClick={handleLogout}
                            className="ml-2 p-2 text-slate-400 hover:text-red-400 transition-colors"
                            title="Logout"
                        >
                            <LogOut className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    )
}