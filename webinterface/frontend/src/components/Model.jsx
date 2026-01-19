import React, { useRef, useState, useEffect } from 'react';
import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';

const modelPath = '/models/drohne-compressed.glb';

export function Model(props) {
  const { scene } = useGLTF(modelPath);
  const meshRef = useRef();
  const [rotation, setRotation] = useState({ roll: 0, pitch: 0, yaw: 0 });

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Wir reagieren nur auf die Lage-Daten (Attitude)
      if (data.type === "attitude") {
        setRotation({
          roll: data.roll,
          pitch: data.pitch,
          yaw: data.yaw,
        });
      }
    };

    return () => ws.close();
  }, []);

  useFrame(() => {
    if (meshRef.current) {
      // Die Drohne rotiert basierend auf den Sensordaten
      meshRef.current.rotation.set(rotation.pitch, rotation.yaw, rotation.roll);
    }
  });

  return <primitive object={scene} ref={meshRef} {...props} />;
}

useGLTF.preload(modelPath);
export default Model;