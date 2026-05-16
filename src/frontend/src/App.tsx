import { Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import RacePredictions from './pages/RacePredictions'
import DriverAnalysis from './pages/DriverAnalysis'
import Leaderboard from './pages/Leaderboard'
import Login from './pages/Login'

function App() {
    return (
        <AnimatePresence mode="wait">
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route element={<Layout />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/predictions" element={<RacePredictions />} />
                    <Route path="/drivers" element={<DriverAnalysis />} />
                    <Route path="/leaderboard" element={<Leaderboard />} />
                </Route>
            </Routes>
        </AnimatePresence>
    )
}

export default App