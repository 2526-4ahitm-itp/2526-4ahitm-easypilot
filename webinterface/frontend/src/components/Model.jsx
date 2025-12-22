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

        ws.onopen = () => {
            console.log('Verbunden mit Python Telemetrie-Server');
        };

        ws.onmessage = (event) => {
            try {

                const data = JSON.parse(event.data);
                setRotation({
                    roll: data.roll,
                    pitch: data.pitch,
                    yaw: data.yaw,
                });
            } catch (e) {
                console.error("Fehler beim Parsen der WebSocket-Daten:", e);
            }
        };

        ws.onclose = () => {
            console.log('Verbindung zum Telemetrie-Server geschlossen.');
        };

        return () => ws.close();
    }, []);


    useFrame(() => {
        if (meshRef.current) {
            const { roll, pitch, yaw } = rotation;

            meshRef.current.rotation.set(
                pitch,
                yaw,
                roll
            );

        }
    });

    return <primitive object={scene} ref={meshRef} {...props} />;
}

useGLTF.preload(modelPath);

export default Model;