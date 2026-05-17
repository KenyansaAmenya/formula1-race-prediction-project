import { useQuery } from 'react-query'
import { motion } from 'framer-motion'
import { Users, TrendingUp, Award } from 'lucide-react'
import { api } from '../lib/api'

export default function DriverAnalysis() {
    const { data: drivers } = useQuery('all-drivers', () =>
        api.get('/data/drivers').then(r => r.data)
    )

    const { data: standings } = useQuery('standings-2025', () =>
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
                    Driver <span className="text-red-500">Analysis</span>
                </h1>
                <p className="text-slate-400">Performance metrics and insights</p>
            </motion.div>

            {/* Standings Table */}
            <div className="glass-panel p-6">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <Award className="text-yellow-500" />
                    2025 Championship Standings
                </h2>
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="border-b border-slate-700">
                                <th className="pb-3 text-slate-400 font-medium">Pos</th>
                                <th className="pb-3 text-slate-400 font-medium">Driver</th>
                                <th className="pb-3 text-slate-400 font-medium">Team</th>
                                <th className="pb-3 text-slate-400 font-medium text-right">Points</th>
                                <th className="pb-3 text-slate-400 font-medium text-right">Wins</th>
                            </tr>
                        </thead>
                        <tbody>
                            {standings?.map((driver: any, i: number) => (
                                <motion.tr
                                    key={driver.driver_id}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                    className="border-b border-slate-800 hover:bg-slate-800/50"
                                >
                                    <td className="py-3 text-white font-bold">{i + 1}</td>
                                    <td className="py-3 text-white">{driver.driver_name}</td>
                                    <td className="py-3 text-slate-400">{driver.constructor_name}</td>
                                    <td className="py-3 text-right text-red-400 font-bold">{driver.total_points}</td>
                                    <td className="py-3 text-right text-yellow-400">{driver.wins}</td>
                                </motion.tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Driver Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {drivers?.slice(0, 6).map((driver: any, i: number) => (
                    <motion.div
                        key={driver.driver_id}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.1 }}
                        className="glass-panel p-6 hover:border-red-500/50 transition-colors"
                    >
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-full bg-slate-700 flex items-center justify-center">
                                <Users className="w-6 h-6 text-slate-400" />
                            </div>
                            <div>
                                <h3 className="text-white font-bold">
                                    {driver.forename} {driver.surname}
                                </h3>
                                <p className="text-slate-400 text-sm">{driver.nationality}</p>
                            </div>
                        </div>
                        <div className="mt-4 flex items-center gap-2 text-sm">
                            <TrendingUp className="w-4 h-4 text-green-500" />
                            <span className="text-slate-300">Active Driver</span>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    )
}