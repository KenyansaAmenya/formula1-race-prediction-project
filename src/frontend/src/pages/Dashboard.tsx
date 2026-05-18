import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Trophy, TrendingUp, Users, Activity, Zap, Gauge } from 'lucide-react'
import { useQuery } from 'react-query'
import PredictionChart from '../components/charts/PredictionChart'
import { apiClient as api } from '../lib/api'

interface DashboardStats {
    total_races: number
    total_drivers: number
    total_predictions: number
    accuracy: number
}

interface Prediction {
    driver_id: number
    driver_name: string
    probability: number
    confidence_tier: string
    team_color?: string
}

export default function Dashboard() {
    const [selectedRace, setSelectedRace] = useState<number | null>(null)

    const { data: health } = useQuery('health', () =>
        api.get('/health').then(r => r.data).catch(() => ({ status: 'offline' }))
    )

    const { data: races } = useQuery('races', () =>
        api.get('/data/races?year=2025').then(r => r.data).catch(() => [])
    )

    const { data: predictions } = useQuery(
        ['predictions', selectedRace],
        () => api.get(`/predict/race/${selectedRace}`).then(r => r.data),
        { enabled: !!selectedRace }
    )

    const isBackendOnline = health?.status === 'operational' || health?.status === 'healthy'

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
                <div className="flex items-center justify-center gap-2 mt-4">
                    <div className={`w-2 h-2 rounded-full ${isBackendOnline ? 'bg-green-500' : 'bg-red-500'} animate-pulse`} />
                    <span className={`text-sm ${isBackendOnline ? 'text-green-400' : 'text-red-400'}`}>
                        {isBackendOnline ? 'Backend Online' : 'Backend Offline — Start API server'}
                    </span>
                </div>
            </motion.div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { icon: Trophy, label: 'Races Analyzed', value: '24', color: 'text-yellow-500' },
                    { icon: Users, label: 'Drivers', value: '20', color: 'text-blue-500' },
                    { icon: Activity, label: 'Predictions', value: '480', color: 'text-green-500' },
                    { icon: TrendingUp, label: 'Model Accuracy', value: '78.5%', color: 'text-red-500' },
                ].map((stat, i) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-red-500/50 transition-colors"
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
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${selectedRace === race.race_id
                                ? 'bg-red-600 text-white shadow-lg shadow-red-600/25'
                                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                            }`}
                    >
                        {race.name}
                    </button>
                ))}
                {!races?.length && (
                    <span className="text-slate-500 text-sm">No races loaded — check API connection</span>
                )}
            </div>

            {/* Prediction Podium — CSS Version (No Three.js) */}
            {predictions && predictions.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5 }}
                >
                    <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                        <Trophy className="text-yellow-500" />
                        Prediction Podium
                    </h2>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {predictions.slice(0, 3).map((pred: Prediction, index: number) => (
                            <motion.div
                                key={pred.driver_id}
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.15 }}
                                className={`relative bg-slate-900/80 border rounded-xl p-6 ${index === 0 ? 'border-yellow-500/50 md:scale-105 md:-translate-y-4' :
                                        index === 1 ? 'border-gray-400/50' :
                                            'border-orange-700/50'
                                    }`}
                            >
                                {/* Position Badge */}
                                <div className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                        index === 1 ? 'bg-gray-400 text-black' :
                                            'bg-orange-700 text-white'
                                    }`}>
                                    {index === 0 ? '1st' : index === 1 ? '2nd' : '3rd'}
                                </div>

                                <div className="text-center mt-2">
                                    <h3 className="text-xl font-bold text-white">{pred.driver_name}</h3>
                                    <div className="mt-4">
                                        <div className="text-4xl font-black" style={{ color: pred.team_color || '#ef4444' }}>
                                            {(pred.probability * 100).toFixed(1)}%
                                        </div>
                                        <div className="text-sm text-slate-400 mt-1">Win Probability</div>
                                    </div>

                                    <div className="mt-4">
                                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                            <motion.div
                                                className="h-full rounded-full"
                                                style={{ backgroundColor: pred.team_color || '#ef4444' }}
                                                initial={{ width: 0 }}
                                                animate={{ width: `${pred.probability * 100}%` }}
                                                transition={{ duration: 1, delay: index * 0.2 }}
                                            />
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-center gap-2 mt-3">
                                        <Zap className="w-4 h-4 text-yellow-500" />
                                        <span className={`text-xs uppercase tracking-wider ${pred.confidence_tier === 'high' ? 'text-green-400' :
                                                pred.confidence_tier === 'medium' ? 'text-yellow-400' :
                                                    'text-slate-400'
                                            }`}>
                                            {pred.confidence_tier} Confidence
                                        </span>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>
            )}

            {/* Charts */}
            {predictions && predictions.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <PredictionChart predictions={predictions} type="probability" />
                    <PredictionChart predictions={predictions} type="confidence" />
                </div>
            )}

            {/* Empty State */}
            {!predictions && selectedRace && (
                <div className="text-center py-12 bg-slate-900/30 rounded-xl border border-slate-800 border-dashed">
                    <Gauge className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                    <p className="text-slate-500">Loading predictions...</p>
                </div>
            )}
        </div>
    )
}
