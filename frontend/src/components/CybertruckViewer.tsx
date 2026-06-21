import { useEffect, useRef, useState, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useGLTF, Environment, ContactShadows, OrbitControls, Center } from '@react-three/drei';
import * as THREE from 'three';
import styles from './CybertruckViewer.module.css';
import { Cube, Warning } from '@phosphor-icons/react';

interface Props {
  pitch: number;
  roll: number;
  yaw: number;
  isEmergency: boolean;
}

// Preload the model so it's ready quickly
useGLTF.preload('/cybertruck.glb');

// Inner 3D model component
function AttitudeModel({ pitch, roll, yaw, setReady }: any) {
  // useGLTF caches the model automatically
  const { scene } = useGLTF('/cybertruck.glb');
  const groupRef = useRef<THREE.Group>(null);
  
  // Entrance animation state
  const entranceAnim = useRef({ time: 0, completed: false });
  const TARGET_SCALE = 0.3; // Decreased size so sides are visible
  
  // Notify parent that model has loaded
  useEffect(() => {
    setReady(true);
  }, [setReady]);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    
    // Convert degrees to radians
    const deg2rad = (d: number) => (d * Math.PI) / 180;
    
    if (!entranceAnim.current.completed) {
      entranceAnim.current.time += delta;
      // 1.5 second entrance animation
      const progress = Math.min(entranceAnim.current.time / 1.5, 1); 
      
      // easeOutCubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      
      // Animate scale up
      const currentScale = TARGET_SCALE * easeOut;
      groupRef.current.scale.set(currentScale, currentScale, currentScale);
      
      // Spin offset (2 full spins = 4 PI)
      const spinOffset = (1 - easeOut) * Math.PI * 4;
      
      const targetEuler = new THREE.Euler(
        deg2rad(pitch), 
        deg2rad(-yaw) + spinOffset, 
        deg2rad(roll), 
        'YXZ'
      );
      groupRef.current.quaternion.setFromEuler(targetEuler);
      
      if (progress === 1) {
        entranceAnim.current.completed = true;
      }
      return;
    }
    
    // Normal telemetry tracking after entrance
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t = prefersReduced ? 1 : Math.min(delta * 10, 1);
    
    const targetEuler = new THREE.Euler(
      deg2rad(pitch), 
      deg2rad(-yaw), // Invert yaw if necessary to match rotation direction
      deg2rad(roll), 
      'YXZ'
    );
    
    // Smoothly interpolate current rotation to target rotation using quaternion slerp
    const targetQuat = new THREE.Quaternion().setFromEuler(targetEuler);
    if (!groupRef.current.quaternion.equals(targetQuat)) {
      groupRef.current.quaternion.slerp(targetQuat, t);
    }
  });

  return (
    <group ref={groupRef} scale={[0, 0, 0]}>
      <Center>
        <primitive object={scene} />
      </Center>
    </group>
  );
}

export const CybertruckViewer = ({ pitch, roll, yaw, isEmergency }: Props) => {
  const [ready, setReady] = useState(false);

  return (
    <div className={`${styles.viewer} ${isEmergency ? styles.emergency : ''}`}>
      <div className={styles.topBar}>
        <span className={styles.badge}>
          <Cube size={15} weight="duotone" /> Attitude Model
        </span>
        <span className={`${styles.liveDot} ${ready ? styles.liveOn : ''}`}>
          {ready ? 'Tracking' : 'Linking'}
        </span>
      </div>

      <div className={styles.frameWrapper}>
        <Canvas camera={{ position: [12, 3, 12], fov: 45 }}>
          <Suspense fallback={null}>
            <ambientLight intensity={0.5} />
            <directionalLight position={[10, 10, 5]} intensity={1} />
            <Environment preset="city" />
            <AttitudeModel pitch={pitch} roll={roll} yaw={yaw} setReady={setReady} />
            <ContactShadows position={[0, -1, 0]} opacity={0.5} scale={10} blur={2} far={4} />
            <OrbitControls enableZoom={true} enablePan={false} />
          </Suspense>
        </Canvas>
      </div>

      {!ready && (
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <span>Loading Cybertruck...</span>
        </div>
      )}

      <div className={styles.hud}>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Pitch</span>
          <span className={`${styles.hudValue} mono`}>{pitch.toFixed(1)}°</span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Roll</span>
          <span className={`${styles.hudValue} mono`}>{roll.toFixed(1)}°</span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Yaw</span>
          <span className={`${styles.hudValue} mono`}>{yaw.toFixed(1)}°</span>
        </div>
      </div>
    </div>
  );
};
