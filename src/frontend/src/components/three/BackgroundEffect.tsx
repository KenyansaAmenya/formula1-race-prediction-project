import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function RacingGrid() {
    const meshRef = useRef<THREE.Mesh>(null)
    const count = 50

    const positions = useMemo(() => {
        const pos = new Float32Array(count * 3)
        for (let i = 0; i < count; i++) {
            pos[i * 3] = (Math.random() - 0.5) * 20
            pos[i * 3 + 1] = (Math.random() - 0.5) * 10
            pos[i * 3 + 2] = (Math.random() - 0.5) * 20
        }
        return pos
    }, [])

    useFrame((state) => {
        if (meshRef.current) {
            meshRef.current.rotation.y = state.clock.elapsedTime * 0.05
            meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1
        }
    })

    return (
        <points ref={meshRef}>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    count={count}
                    array={positions}
                    itemSize={3}
                />
            </bufferGeometry>
            <pointsMaterial
                size={0.05}
                color="#ef4444"
                transparent
                opacity={0.6}
                sizeAttenuation
            />
        </points>
    )
}

function MovingLights() {
    const groupRef = useRef<THREE.Group>(null)

    useFrame((state) => {
        if (groupRef.current) {
            groupRef.current.position.z = (state.clock.elapsedTime * 2) % 20 - 10
        }
    })

    return (
        <group ref={groupRef}>
            {[...Array(5)].map((_, i) => (
                <mesh key={i} position={[i * 2 - 4, 0, 0]}>
                    <sphereGeometry args={[0.1, 8, 8]} />
                    <meshBasicMaterial color="#fbbf24" transparent opacity={0.8} />
                </mesh>
            ))}
        </group>
    )
}

export default function BackgroundEffect() {
    return (
        <Canvas camera={{ position: [0, 0, 10], fov: 75 }}>
            <ambientLight intensity={0.1} />
            <RacingGrid />
            <MovingLights />
            <fog attach="fog" args={['#020617', 10, 30]} />
        </Canvas>
    )
}