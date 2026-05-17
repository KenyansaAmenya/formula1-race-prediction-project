import { useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Text } from '@react-three/drei'

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
  const groupRef = useRef<<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  
  const xPos = (index - 1) * 3.5
  const yPos = index === 0 ? 1.5 : 0
  
  useFrame((state) => {
    if (groupRef.current) {
      const floatOffset = Math.sin(state.clock.elapsedTime * 2 + index) * 0.1
      groupRef.current.position.y = yPos + floatOffset
      
      const targetScale = isHovered ? 1.2 : 1.0
      groupRef.current.scale.lerp(
        new THREE.Vector3(targetScale, targetScale, targetScale),
        0.1
      )
    }
  })
  
  return (
    <group 
      ref={groupRef} 
      position={[xPos, yPos, 0]}
      onPointerOver={() => {
        setHovered(true)
        onHover(driver.driver_id)
      }}
      onPointerOut={() => {
        setHovered(false)
        onHover(null)
      }}
    >
      {/* Podium base */}
      <mesh position={[0, -1.5, 0]}>
        <cylinderGeometry args={[1.2, 1.4, 0.5 + index * 0.3, 32]} />
        <meshStandardMaterial
          color={index === 0 ? '#FFD700' : index === 1 ? '#C0C0C0' : '#CD7F32'}
          metalness={0.8}
          roughness={0.2}
        />
      </mesh>
      
      {/* Driver sphere */}
      <mesh>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshStandardMaterial
          color={driver.team_color}
          metalness={0.6}
          roughness={0.3}
          emissive={driver.team_color}
          emissiveIntensity={isHovered ? 0.3 : 0.1}
        />
      </mesh>
      
      {/* Name label — using drei Text instead of Html */}
      <Text
        position={[0, 1.0, 0]}
        fontSize={0.25}
        color="white"
        anchorX="center"
        anchorY="middle"
        font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuBWYAZ9hjp-Ek-_EeA.woff2"
      >
        {driver.driver_name}
      </Text>
      
      {/* Probability label */}
      <Text
        position={[0, 0.7, 0]}
        fontSize={0.2}
        color={driver.team_color}
        anchorX="center"
        anchorY="middle"
      >
        {(driver.probability * 100).toFixed(1)}%
      </Text>
      
      {/* Position label */}
      <Text
        position={[0, -0.8, 0]}
        fontSize={0.18}
        color="#94a3b8"
        anchorX="center"
        anchorY="middle"
      >
        {index === 0 ? '1st' : index === 1 ? '2nd' : '3rd'}
      </Text>
    </group>
  )
}