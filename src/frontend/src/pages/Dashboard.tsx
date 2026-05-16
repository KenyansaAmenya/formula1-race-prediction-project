import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Trophy, TrendingUp, Users, Activity } from 'lucide-react'
import { useQuery } from 'react-query'
import PodiumScene from '../components/three/PodiumScene'
import PredictionChart from '../components/charts/PredictionChart'
import { api } from '../lib/api'

interface DashboardStats {
    total_races: number
    total_drivers: number
    total_predictions: number
    accuracy: number
}

export default function Dashboard() {
    const [selectedRace, setSelectedRace] = useState<number | null>(null)

    const { data: stats } = useQuery<DashboardStats>('stats', () =>
        api.get('/health').then(r => r.data)
    )

    const { data: races } = useQuery('races', () =>
        api.get('/data/races?year=2025').then(r => r.data)
    )

    const { data: predictions } = useQuery(
        ['predictions', selectedRace],
        () => api.get(`/predict/race/${selectedRace}`).then(r => r.data),
        { enabled: !!selectedRace }
    )

    const podiumDrivers = predictions?.slice(0, 3).map((p: any, i: number) => ({
        driver_id: p.driver_id,
        driver_name: p.driver_name,
        team_color: i === 0 ? '#ef4444' : i === 1 ? '#3b82f6' : '#eab308',
        position: i + 1,
        probability: p.probability,
        nationality: 'Unknown'
    })) || []

    return (
        <div className="space-y-8">
            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center py-8"
            >
                <h1 className="text-5xl font-black tracking-tight text-white mb-2">
                    F1 <span className="text-red-500">AI</span> PLATFORM
                </h1>
                <p className="text-slate-400 text-lg">
                    Predictive Analytics & Race Intelligence
                </p>
            </motion.div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { icon: Trophy, label: 'Races Analyzed', value: stats?.total_races || 0, color: 'text-yellow-500' },
                    { icon: Users, label: 'Drivers', value: stats?.total_drivers || 0, color: 'text-blue-500' },
                    { icon: Activity, label: 'Predictions', value: stats?.total_predictions || 0, color: 'text-green-500' },
                    { icon: TrendingUp, label: 'Model Accuracy', value: `${(stats?.accuracy || 0).toFixed(1)}%`, color: 'text-red-500' },
                ].map((stat, i) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6"
                    >
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-slate-400 text-sm">{stat.label}</p>
                                <p className="text-3xl font-bold text-white mt-1">{stat.value}</p>
                            </div>
                            <stat.icon className={`w-8 h-8 ${stat.color}`} />
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Race Selector */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {races?.map((race: any) => (
                    <button
                        key={race.race_id}
                        onClick={() => setSelectedRace(race.race_id)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${selectedRace === race.race_id
                                ? 'bg-red-600 text-white'
                                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                            }`}
                    >
                        {race.name}
                    </button>
                ))}
            </div>

            {/* 3D Podium */}
            {selectedRace && podiumDrivers.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5 }}
                >
                    <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                        <Trophy className="text-yellow-500" />
                        Prediction Podium
                    </h2>
                    <PodiumScene drivers={podiumDrivers} showCar={true} />
                </motion.div>
            )}

            {/* Charts */}
            {predictions && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <PredictionChart predictions={predictions} type="probability" />
                    <PredictionChart predictions={predictions} type="confidence" />
                </div>
            )}
        </div>
    )
}