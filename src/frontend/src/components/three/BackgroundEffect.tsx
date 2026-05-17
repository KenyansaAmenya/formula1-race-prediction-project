import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function RacingGrid() {
  const pointsRef = useRef<<THREE.Points>(null)
  const count = 50
  
  const [positions, sizes] = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const sz = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20
      pos[i * 3 + 1] = (Math.random() - 0.5) * 10
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20
      sz[i] = Math.random() * 2
    }
    return [pos, sz]
  }, [])
  
  useFrame((state) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y = state.clock.elapsedTime * 0.05
      pointsRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1
    }
  })
  
  return (
    <points ref={pointsRef}>
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
  const groupRef = useRef<<THREE.Group>(null)
  
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
    <div className="fixed inset-0 z-0 opacity-30">
      <Canvas camera={{ position: [0, 0, 10], fov: 75 }}>
        <ambientLight intensity={0.1} />
        <RacingGrid />
        <MovingLights />
        <fog attach="fog" args={['#020617', 10, 30]} />
      </Canvas>
    </div>
  )
}