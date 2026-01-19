import React, { useRef, useState, useEffect } from 'react';
import { useGLTF, Html } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';

const modelPath = '/models/drohne-compressed.glb';

export function Model(props) {
  const { scene } = useGLTF(modelPath);
  const meshRef = useRef();
  
  const [rotation, setRotation] = useState({ roll: 0, pitch: 0, yaw: 0 });
  const [motors, setMotors] = useState({ m1: 1000, m4: 1000 });

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "attitude") {
        setRotation({ roll: data.roll, pitch: data.pitch, yaw: data.yaw });
      } else if (data.type === "motor_data") {
        setMotors({ m1: data.m1, m4: data.m4 });
      }
    };

    ws.onerror = (err) => console.error("WebSocket Error:", err);

    return () => ws.close();
  }, []);

  useFrame(() => {
    if (meshRef.current) {
      // Note: Ensure these units are in Radians. 
      // If your WS sends Degrees, multiply by (Math.PI / 180)
      meshRef.current.rotation.set(rotation.pitch, rotation.yaw, rotation.roll);
    }
  });

  // Calculation for bar height (1000-2000 -> 0-100)
  const getBarHeight = (val) => Math.max(0, Math.min(100, (val - 1000) / 10));

  return (
    <group>
      {/* Telemetry Bars */}
      <Html position={[0, 1.5, 0]} center>
        <div style={{ 
          display: 'flex', 
          gap: '10px', 
          background: 'rgba(0,0,0,0.7)', 
          padding: '10px', 
          borderRadius: '5px', 
          color: 'white', 
          pointerEvents: 'none',
          fontFamily: 'sans-serif' 
        }}>
          <div>
            <div style={{ width: '15px', height: '100px', background: '#333', position: 'relative' }}>
              {/* FIXED: Corrected template literal syntax below */}
              <div style={{ 
                position: 'absolute', 
                bottom: 0, 
                width: '100%', 
                height: `${getBarHeight(motors.m1)}px`, 
                background: '#00ff00',
                transition: 'height 0.1s ease-out' 
              }} />
            </div>
            <small style={{ display: 'block', textAlign: 'center' }}>M1</small>
          </div>
          <div>
            <div style={{ width: '15px', height: '100px', background: '#333', position: 'relative' }}>
              {/* FIXED: Corrected template literal syntax below */}
              <div style={{ 
                position: 'absolute', 
                bottom: 0, 
                width: '100%', 
                height: `${getBarHeight(motors.m4)}px`, 
                background: '#00ff00',
                transition: 'height 0.1s ease-out' 
              }} />
            </div>
            <small style={{ display: 'block', textAlign: 'center' }}>M4</small>
          </div>
        </div>
      </Html>

      <primitive object={scene} ref={meshRef} {...props} />
    </group>
  );
}

useGLTF.preload(modelPath);
export default Model;