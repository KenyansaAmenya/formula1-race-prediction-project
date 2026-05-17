import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface F1CarProps {
  teamColor?: string
  scale?: number
  rotationSpeed?: number
  isAnimating?: boolean
}

export default function F1Car({
  teamColor = '#ef4444',
  scale = 1,
  rotationSpeed = 0.5,
  isAnimating = true
}: F1CarProps) {
  const groupRef = useRef<<THREE.Group>(null)
  const wheelsRef = useRef<<THREE.Group>(null)
  
  const carBody = useMemo(() => {
    const shape = new THREE.Shape()
    shape.moveTo(0, 0)
    shape.lineTo(3, 0)
    shape.lineTo(3.2, 0.3)
    shape.lineTo(2.8, 0.5)
    shape.lineTo(1.5, 0.8)
    shape.lineTo(0.5, 1.0)
    shape.lineTo(0, 0.9)
    shape.lineTo(-0.3, 0.5)
    shape.lineTo(-0.3, 0.2)
    shape.lineTo(0, 0)
    
    const extrudeSettings = {
      steps: 1,
      depth: 0.8,
      bevelEnabled: true,
      bevelThickness: 0.05,
      bevelSize: 0.05,
      bevelSegments: 2
    }
    
    return new THREE.ExtrudeGeometry(shape, extrudeSettings)
  }, [])
  
  useFrame((state) => {
    if (groupRef.current && isAnimating) {
      groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 2) * 0.1
      groupRef.current.rotation.y += rotationSpeed * 0.01
    }
    
    if (wheelsRef.current && isAnimating) {
      wheelsRef.current.children.forEach((wheel, i) => {
        wheel.rotation.x += 0.1 * (i % 2 === 0 ? 1 : -1)
      })
    }
  })
  
  return (
    <group ref={groupRef} scale={scale}>
      {/* Car Body */}
      <mesh geometry={carBody} position={[-1.5, 0, -0.4]}>
        <meshStandardMaterial
          color={teamColor}
          metalness={0.8}
          roughness={0.2}
          envMapIntensity={1}
        />
      </mesh>
      
      {/* Wheels */}
      <group ref={wheelsRef}>
        {/* Front Left */}
        <mesh position={[2.2, 0.25, 0.6]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.25, 0.25, 0.15, 16]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
        {/* Front Right */}
        <mesh position={[2.2, 0.25, -0.6]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.25, 0.25, 0.15, 16]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
        {/* Rear Left */}
        <mesh position={[-0.3, 0.3, 0.65]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.28, 0.28, 0.2, 16]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
        {/* Rear Right */}
        <mesh position={[-0.3, 0.3, -0.65]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.28, 0.28, 0.2, 16]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
      </group>
      
      {/* Rear Wing */}
      <mesh position={[-0.4, 0.9, 0]} rotation={[0, 0, -0.1]}>
        <boxGeometry args={[0.1, 0.4, 1.2]} />
        <meshStandardMaterial color={teamColor} metalness={0.9} roughness={0.1} />
      </mesh>
      
      {/* Front Wing */}
      <mesh position={[3.1, 0.2, 0]} rotation={[0, 0, 0.2]}>
        <boxGeometry args={[0.1, 0.05, 1.0]} />
        <meshStandardMaterial color={teamColor} metalness={0.9} roughness={0.1} />
      </mesh>
      
      {/* Halo */}
      <mesh position={[1.2, 0.9, 0]} rotation={[0, 0, 0.3]}>
        <torusGeometry args={[0.2, 0.02, 8, 16, Math.PI]} />
        <meshStandardMaterial color="#333333" metalness={0.9} />
      </mesh>
      
      {/* Lights */}
      <pointLight position={[2.5, 0.5, 0]} color="#ffffff" intensity={0.5} distance={2} />
      <pointLight position={[-0.5, 0.8, 0]} color="#ff0000" intensity={0.3} distance={1.5} />
    </group>
  )
}