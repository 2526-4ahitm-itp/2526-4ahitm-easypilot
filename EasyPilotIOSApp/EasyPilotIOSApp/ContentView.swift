//
//  ContentView.swift
//  EasyPilotIOSApp
//
//  Created by Eder Simon on 29.01.26.
//

import SwiftUI
import SceneKit

struct ContentView: View {
    @StateObject var udpReceiver = UDPReceiver()

    var body: some View {
        ZStack {
            // Hintergrundfarbe
            Color.black.edgesIgnoringSafeArea(.all)

            VStack {
                // Header
                Text("EasyPilot Telemetry")
                    .font(.title)
                    .bold()
                    .foregroundColor(.white)
                    .padding(.top, 40)

                // 3D Modell Ansicht
                DroneView(roll: udpReceiver.roll, pitch: udpReceiver.pitch, yaw: udpReceiver.yaw)
                    .frame(height: 400)
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(15)
                    .padding()

                // Motor Daten Anzeige (Balken)
                HStack(spacing: 40) {
                    MotorBar(label: "M1", value: udpReceiver.m1)
                    MotorBar(label: "M4", value: udpReceiver.m4)
                }
                .padding()

                Spacer()

                // Debug Text
                Text(udpReceiver.receivedMessage)
                    .font(.caption)
                    .foregroundColor(.gray)
                    .padding()
            }
        }
    }
}

// Komponente für einen Motor-Balken
struct MotorBar: View {
    let label: String
    let value: Int // 1000 - 2000

    var normalizedHeight: CGFloat {
        let clamped = min(max(value, 1000), 2000)
        return CGFloat(clamped - 1000) / 1000.0
    }

    var body: some View {
        VStack {
            ZStack(alignment: .bottom) {
                // Hintergrundbalken
                Rectangle()
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 30, height: 150)
                    .cornerRadius(5)

                // Füllstand
                Rectangle()
                    .fill(Color.green)
                    .frame(width: 30, height: 150 * normalizedHeight)
                    .cornerRadius(5)
                    .animation(.easeOut(duration: 0.1), value: normalizedHeight)
            }

            Text(label)
                .foregroundColor(.white)
                .bold()
            Text("\(value)")
                .foregroundColor(.white)
                .font(.caption)
        }
    }
}

// SceneKit View Wrapper für SwiftUI
struct DroneView: UIViewRepresentable {
    var roll: Double
    var pitch: Double
    var yaw: Double

    func makeUIView(context: Context) -> SCNView {
        let sceneView = SCNView()
        sceneView.scene = SCNScene(named: "drohne-compressed.glb") // Lädt das Modell aus dem Bundle
        sceneView.autoenablesDefaultLighting = true
        sceneView.allowsCameraControl = true
        sceneView.backgroundColor = UIColor.clear

        // Kamera positionieren (falls keine im Modell ist)
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(x: 0, y: 2, z: 5)
        sceneView.scene?.rootNode.addChildNode(cameraNode)

        return sceneView
    }

    func updateUIView(_ uiView: SCNView, context: Context) {
        // Wir rotieren den Root-Node oder einen spezifischen Node des Modells
        // Hinweis: SceneKit verwendet Euler Angles in Radians.
        // Die Reihenfolge und Achsen müssen ggf. an das Modell angepasst werden.

        // Versuche den ersten Child Node zu finden (oft der Container für das Mesh)
        if let droneNode = uiView.scene?.rootNode.childNodes.first {
            // Animation für flüssigere Bewegung
            SCNTransaction.begin()
            SCNTransaction.animationDuration = 0.1

            // Rotation setzen (Pitch, Yaw, Roll)
            // Achtung: Achsen können je nach Modell variieren (Y-Up vs Z-Up)
            // Hier Annahme: Y ist oben.
            droneNode.eulerAngles = SCNVector3(pitch, yaw, roll)

            SCNTransaction.commit()
        }
    }
}

#Preview {
    ContentView()
}
