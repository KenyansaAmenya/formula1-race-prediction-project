import { useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import * as THREE from 'three'
import { motion } from 'framer-motion'

interface DriverCardProps {
    driver: {
        driver_id: number
        driver_name: string
        team_color: string
        position: number
        probability: number
        nationality: string
    }
    index: number
    isHovered: boolean
    onHover: (id: number | null) => void
}

export default function DriverCard({
    driver,
    index,
    isHovered,
    onHover
}: DriverCardProps) {
    const meshRef = useRef<THREE.Mesh>(null)
    const [hovered, setHovered] = useState(false)

    const xPos = (index - 1) * 3.5
    const yPos = index === 0 ? 1.5 : 0

    useFrame((state) => {
        if (meshRef.current) {
            // Floating animation
            const floatOffset = Math.sin(state.clock.elapsedTime * 2 + index) * 0.1
            meshRef.current.position.y = yPos + floatOffset

            // Scale on hover
            const targetScale = isHovered ? 1.2 : 1.0
            meshRef.current.scale.lerp(
                new THREE.Vector3(targetScale, targetScale, targetScale),
                0.1
            )
        }
    })

    return (
        <group position={[xPos, yPos, 0]}>
            {/* Podium base */}
            <mesh position={[0, -1.5, 0]}>
                <cylinderGeometry args={[1.2, 1.4, 0.5 + index * 0.3, 32]} />
                <meshStandardMaterial
                    color={index === 0 ? '#FFD700' : index === 1 ? '#C0C0C0' : '#CD7F32'}
                    metalness={0.8}
                    roughness={0.2}
                />
            </mesh>

            {/* Driver avatar placeholder */}
            <mesh
                ref={meshRef}
                onPointerOver={() => {
                    setHovered(true)
                    onHover(driver.driver_id)
                }}
                onPointerOut={() => {
                    setHovered(false)
                    onHover(null)
                }}
            >
                <sphereGeometry args={[0.6, 32, 32]} />
                <meshStandardMaterial
                    color={driver.team_color}
                    metalness={0.6}
                    roughness={0.3}
                    emissive={driver.team_color}
                    emissiveIntensity={isHovered ? 0.3 : 0.1}
                />
            </mesh>

            {/* Driver info overlay */}
            <Html distanceFactor={10} position={[0, 1.2, 0]} center>
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: isHovered ? 1 : 0.7, y: 0 }}
                    className="bg-slate-900/90 backdrop-blur-md rounded-lg p-3 border border-slate-700 min-w-[180px]"
                >
                    <div className="text-center">
                        <div className="text-xs text-slate-400 uppercase tracking-wider">
                            {index === 0 ? '1st' : index === 1 ? '2nd' : '3rd'} Place
                        </div>
                        <div className="text-lg font-bold text-white mt-1">
                            {driver.driver_name}
                        </div>
                        <div className="text-sm text-slate-300 mt-1">
                            {driver.nationality}
                        </div>
                        <div className="mt-2">
                            <div className="text-xs text-slate-400">Win Probability</div>
                            <div className="text-2xl font-bold" style={{ color: driver.team_color }}>
                                {(driver.probability * 100).toFixed(1)}%
                            </div>
                        </div>
                        <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full rounded-full"
                                style={{ backgroundColor: driver.team_color }}
                                initial={{ width: 0 }}
                                animate={{ width: `${driver.probability * 100}%` }}
                                transition={{ duration: 1, delay: index * 0.2 }}
                            />
                        </div>
                    </div>
                </motion.div>
            </Html>
        </group>
    )
}