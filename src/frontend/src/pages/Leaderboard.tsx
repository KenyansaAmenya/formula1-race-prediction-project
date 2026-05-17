import { useQuery } from 'react-query'
import { motion } from 'framer-motion'
import { Trophy, Medal, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'

export default function Leaderboard() {
    const { data: standings } = useQuery('leaderboard-2025', () =>
        api.get('/data/standings/2025').then(r => r.data)
    )

    return (
        <div className="space-y-8">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center py-8"
            >
                <h1 className="text-4xl font-black text-white mb-2">
                    Championship <span className="text-red-500">Leaderboard</span>
                </h1>
                <p className="text-slate-400">2025 Season Standings</p>
            </motion.div>

            {/* Podium */}
            <div className="grid grid-cols-3 gap-4 mb-8">
                {[1, 0, 2].map((idx) => {
                    const driver = standings?.[idx]
                    if (!driver) return null

                    const heights = ['h-48', 'h-64', 'h-40']
                    const colors = ['bg-slate-400', 'bg-yellow-500', 'bg-orange-600']
                    const medals = [Medal, Trophy, Medal]
                    const MedalIcon = medals[idx]

                    return (
                        <motion.div
                            key={driver.driver_id}
                            initial={{ opacity: 0, y: 50 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx === 1 ? 0 : 0.2 }}
                            className="flex flex-col items-center"
                        >
                            <div className={`w-full ${heights[idx]} ${colors[idx]} rounded-t-xl flex flex-col items-center justify-end p-4 relative`}>
                                <MedalIcon className="w-8 h-8 text-white mb-2" />
                                <div className="text-white font-bold text-center">
                                    <div className="text-lg">{driver.driver_name}</div>
                                    <div className="text-sm opacity-80">{driver.total_points} pts</div>
                                </div>
                                <div className="absolute -top-4 w-8 h-8 bg-white rounded-full flex items-center justify-center font-bold text-slate-900">
                                    {idx + 1}
                                </div>
                            </div>
                        </motion.div>
                    )
                })}
            </div>

            {/* Full Table */}
            <div className="glass-panel p-6">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <TrendingUp className="text-red-500" />
                    Full Standings
                </h2>
                <div className="space-y-2">
                    {standings?.map((driver: any, i: number) => (
                        <motion.div
                            key={driver.driver_id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.03 }}
                            className="flex items-center gap-4 p-3 rounded-lg hover:bg-slate-800/50 transition-colors"
                        >
                            <div className="w-8 text-center font-bold text-slate-500">
                                {i + 1}
                            </div>
                            <div className="flex-1">
                                <div className="text-white font-medium">{driver.driver_name}</div>
                                <div className="text-sm text-slate-400">{driver.constructor_name}</div>
                            </div>
                            <div className="text-right">
                                <div className="text-red-400 font-bold">{driver.total_points}</div>
                                <div className="text-xs text-slate-500">PTS</div>
                            </div>
                            <div className="text-right w-16">
                                <div className="text-yellow-400 font-bold">{driver.wins}</div>
                                <div className="text-xs text-slate-500">WINS</div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    )
}