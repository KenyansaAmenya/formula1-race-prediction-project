import { motion } from 'framer-motion'
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts'

interface PredictionChartProps {
    predictions: any[]
    type: 'probability' | 'confidence'
}

export default function PredictionChart({ predictions, type }: PredictionChartProps) {
    const data = predictions.slice(0, 10).map((p: any) => ({
        name: p.driver_name.split(' ').pop(), // Last name
        value: type === 'probability' ? p.probability * 100 :
            p.confidence_tier === 'high' ? 90 :
                p.confidence_tier === 'medium' ? 60 : 30,
        color: p.probability > 0.5 ? '#ef4444' :
            p.probability > 0.3 ? '#3b82f6' : '#64748b'
    }))

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6"
        >
            <h3 className="text-lg font-semibold text-white mb-4">
                {type === 'probability' ? 'Win Probability' : 'Confidence Tier'}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data} layout="vertical" margin={{ left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis type="number" domain={[0, 100]} stroke="#94a3b8" />
                    <YAxis dataKey="name" type="category" stroke="#94a3b8" width={80} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px'
                        }}
                        labelStyle={{ color: '#f8fafc' }}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </motion.div>
    )
}