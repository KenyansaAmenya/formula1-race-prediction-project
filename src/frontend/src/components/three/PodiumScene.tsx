import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei'
import DriverCard from './DriverCard'
import F1Car from './F1Car'

interface PodiumDriver {
    driver_id: number
    driver_name: string
    team_color: string
    position: number
    probability: number
    nationality: string
}

interface PodiumSceneProps {
    drivers: PodiumDriver[]
    showCar?: boolean
}

export default function PodiumScene({ drivers, showCar = true }: PodiumSceneProps) {
    const [hoveredDriver, setHoveredDriver] = useState<number | null>(null)

    return (
        <div className="h-[500px] w-full rounded-xl overflow-hidden bg-gradient-to-b from-slate-900 to-slate-950">
            <Canvas camera={{ position: [0, 2, 8], fov: 50 }}>
                <ambientLight intensity={0.3} />
                <spotLight
                    position={[10, 10, 10]}
                    angle={0.3}
                    penumbra={1}
                    intensity={1}
                    castShadow
                />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#ef4444" />

                {showCar && (
                    <F1Car
                        teamColor="#ef4444"
                        scale={0.8}
                        rotationSpeed={0.2}
                        isAnimating={true}
                    />
                )}

                {drivers.slice(0, 3).map((driver, index) => (
                    <DriverCard
                        key={driver.driver_id}
                        driver={driver}
                        index={index}
                        isHovered={hoveredDriver === driver.driver_id}
                        onHover={setHoveredDriver}
                    />
                ))}

                <ContactShadows
                    position={[0, -2, 0]}
                    opacity={0.5}
                    scale={20}
                    blur={2}
                    far={4}
                />

                <Environment preset="city" />
                <OrbitControls
                    enablePan={false}
                    enableZoom={true}
                    minDistance={5}
                    maxDistance={15}
                    maxPolarAngle={Math.PI / 2}
                />
            </Canvas>
        </div>
    )
}