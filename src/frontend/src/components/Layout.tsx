import { Outlet } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navigation from './Navigation'
import { Suspense, lazy, Component, type ReactNode } from 'react'

const BackgroundEffect = lazy(() => import('./three/BackgroundEffect'))

function BackgroundFallback() {
    return <div className="fixed inset-0 z-0 bg-slate-950" />
}

// Proper class-based error boundary (required for React error boundaries)
class ThreeErrorBoundary extends Component<
    { children: ReactNode },
    { hasError: boolean }
> {
    constructor(props: { children: ReactNode }) {
        super(props)
        this.state = { hasError: false }
    }

    static getDerivedStateFromError() {
        return { hasError: true }
    }

    componentDidCatch(error: Error) {
        console.error('3D Error caught:', error)
    }

    render() {
        if (this.state.hasError) {
            return <div className="fixed inset-0 z-0 bg-slate-950" />
        }
        return this.props.children
    }
}

export default function Layout() {
    return (
        <div className="relative min-h-screen bg-slate-950 text-white overflow-hidden">
            {/* 3D Background */}
            <div className="fixed inset-0 z-0 opacity-30 pointer-events-none">
                <ThreeErrorBoundary>
                    <Suspense fallback={<BackgroundFallback />}>
                        <BackgroundEffect />
                    </Suspense>
                </ThreeErrorBoundary>
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