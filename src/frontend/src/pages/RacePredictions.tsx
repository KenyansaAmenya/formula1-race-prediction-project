import { useState } from 'react'
import { useQuery } from 'react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Trophy, Zap, Gauge } from 'lucide-react'
import { api } from '../lib/api'

export default function RacePredictions() {
    const [selectedRace, setSelectedRace] = useState<number | null>(null)

    const { data: races } = useQuery('races-2025', () =>
        api.get('/data/races?year=2025').then(r => r.data)
    )

    const { data: predictions } = useQuery(
        ['predictions', selectedRace],
        () => api.get(`/predict/race/${selectedRace}`).then(r => r.data),
        { enabled: !!selectedRace }
    )

    return (
        <div className="space-y-8">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center py-8"
            >
                <h1 className="text-4xl font-black text-white mb-2">
                    Race <span className="text-red-500">Predictions</span>
                </h1>
                <p className="text-slate-400">AI-powered outcome forecasting</p>
            </motion.div>

            {/* Race Selector */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {races?.map((race: any) => (
                    <button
                        key={race.race_id}
                        onClick={() => setSelectedRace(race.race_id)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${selectedRace === race.race_id
                                ? 'bg-red-600 text-white'
                                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                            }`}
                    >
                        {race.name}
                    </button>
                ))}
            </div>

            {/* Predictions */}
            <AnimatePresence mode="wait">
                {predictions && (
                    <motion.div
                        key={selectedRace}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="space-y-4"
                    >
                        {predictions.slice(0, 5).map((pred: any, i: number) => (
                            <div
                                key={pred.driver_id}
                                className="glass-panel p-4 flex items-center gap-4"
                            >
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${i === 0 ? 'bg-yellow-500/20 text-yellow-500' :
                                        i === 1 ? 'bg-slate-400/20 text-slate-300' :
                                            i === 2 ? 'bg-orange-600/20 text-orange-500' :
                                                'bg-slate-800 text-slate-500'
                                    }`}>
                                    {i + 1}
                                </div>

                                <div className="flex-1">
                                    <h3 className="text-white font-bold">{pred.driver_name}</h3>
                                    <div className="flex items-center gap-2 text-sm text-slate-400">
                                        <Zap className="w-3 h-3" />
                                        {pred.confidence_tier} confidence
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-2xl font-bold text-red-500">
                                        {(pred.probability * 100).toFixed(1)}%
                                    </div>
                                    <div className="text-xs text-slate-500">win probability</div>
                                </div>

                                <div className="w-32">
                                    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                                        <motion.div
                                            className="h-full bg-red-500 rounded-full"
                                            initial={{ width: 0 }}
                                            animate={{ width: `${pred.probability * 100}%` }}
                                            transition={{ duration: 1, delay: i * 0.1 }}
                                        />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            {!selectedRace && (
                <div className="text-center py-12 text-slate-500">
                    <Gauge className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Select a race to view AI predictions</p>
                </div>
            )}
        </div>
    )
}