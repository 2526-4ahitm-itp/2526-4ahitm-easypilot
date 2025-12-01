import React from 'react';
import {useGLTF} from '@react-three/drei';


const modelPath = '/models/drohne.gltf';

export function Model(props) {

    const {scene} = useGLTF(modelPath);


    return <primitive object={scene} {...props} />;
}

useGLTF.preload(modelPath);

export default Model;



