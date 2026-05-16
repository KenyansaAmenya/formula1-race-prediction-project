import { Outlet } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navigation from './Navigation'
import BackgroundEffect from './three/BackgroundEffect'

export default function Layout() {
    return (
        <div className="relative min-h-screen bg-slate-950 text-white overflow-hidden">
            {/* 3D Background */}
            <div className="fixed inset-0 z-0 opacity-30">
                <BackgroundEffect />
            </div>

            {/* Content */}
            <div className="relative z-10">
                <Navigation />
                <motion.main
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.5 }}
                    className="container mx-auto px-4 py-8"
                >
                    <Outlet />
                </motion.main>
            </div>
        </div>
    )
}