import SwiftUI
import SceneKit

/// The main dashboard view for the EasyPilot app.
/// Displays real-time telemetry data and a 3D model of the drone.
struct DashboardView: View {
    @StateObject var udpListener = UDPListener()
    @State private var droneScene: SCNScene?
    
    var body: some View {
        VStack {
            Text("Drone Dashboard")
                .font(.largeTitle)
                .padding()
            
            // 3D Model View
            if let scene = droneScene {
                SceneView(
                    scene: scene,
                    options: [.autoenablesDefaultLighting, .allowsCameraControl]
                )
                .frame(height: 300)
                .background(Color.black) // Make background completely black
                .cornerRadius(10)
                .padding()
                .onChange(of: udpListener.telemetry?.roll) { _ in
                    updateSceneRotation(scene: scene)
                }
            } else {
                Text("Loading 3D Model...")
                    .frame(height: 300)
                    .frame(maxWidth: .infinity)
                    .background(Color.black)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                    .padding()
            }
            
            // Telemetry Data Display
            if let data = udpListener.telemetry {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Telemetry Data")
                        .font(.headline)
                    
                    HStack {
                        Text("Roll: \(String(format: "%.2f", data.roll))")
                        Spacer()
                        Text("Pitch: \(String(format: "%.2f", data.pitch))")
                        Spacer()
                        Text("Yaw: \(String(format: "%.2f", data.yaw))")
                    }
                    
                    HStack {
                        Text("Motor 1: \(data.m1 ?? 0)")
                        Spacer()
                        Text("Motor 4: \(data.m4 ?? 0)")
                    }
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(10)
                .padding()
                
            } else {
                Text("Waiting for data...")
                    .foregroundColor(.gray)
                    .padding()
            }
            
            Spacer()
        }
        .onAppear {
            udpListener.startListening()
            loadScene()
        }
    }
    
    /// Loads the SceneKit scene only once when the view appears.
    private func loadScene() {
        guard droneScene == nil else { return } // Only load once
        
        DispatchQueue.global(qos: .userInitiated).async {
            var scene: SCNScene
            if let url = Bundle.main.url(forResource: "drohne-compressed", withExtension: "usdz") {
                do {
                    scene = try SCNScene(url: url, options: nil)
                    
                    // Add a default camera to the scene to guarantee visibility
                    let cameraNode = SCNNode()
                    cameraNode.camera = SCNCamera()
                    // USDZ bounds are ~2 meters, position camera at normal distance
                    cameraNode.position = SCNVector3(x: 0, y: 1, z: 2.5)
                    let lookAtConstraint = SCNLookAtConstraint(target: scene.rootNode)
                    cameraNode.constraints = [lookAtConstraint]
                    scene.rootNode.addChildNode(cameraNode)
                    
                    // Add directional lighting because exported files often lack light sources
                    let lightNode = SCNNode()
                    lightNode.light = SCNLight()
                    lightNode.light?.type = .omni
                    lightNode.position = SCNVector3(x: 0, y: 10, z: 10)
                    scene.rootNode.addChildNode(lightNode)
                    
                    let ambientLightNode = SCNNode()
                    ambientLightNode.light = SCNLight()
                    ambientLightNode.light?.type = .ambient
                    ambientLightNode.light?.intensity = 500 // Moderate ambient light
                    scene.rootNode.addChildNode(ambientLightNode)
                    
                    // USDZ natively scales correctly most of the time
                    let droneNode = scene.rootNode.childNodes.first(where: { $0.camera == nil && $0.light == nil }) ?? scene.rootNode
                    droneNode.scale = SCNVector3(1.0, 1.0, 1.0) 
                    
                    // Force the scene background to clear so it inherits the SwiftUI color
                    scene.background.contents = UIColor.clear
                    
                } catch {
                    print("Failed to load USDZ scene: \(error)")
                    scene = self.createFallbackScene()
                }
            } else {
                print("Could not find drohne-compressed.usdz in bundle")
                scene = self.createFallbackScene()
            }
            
            DispatchQueue.main.async {
                self.droneScene = scene
            }
        }
    }
    
    /// Updates the rotation of the existing scene based on telemetry data.
    private func updateSceneRotation(scene: SCNScene) {
        if let data = udpListener.telemetry {
            // Assuming the ESP32 sends degrees as per the .ino file analysis, convert to radians
            let degToRad: Float = .pi / 180.0
            let roll = CGFloat(data.roll * degToRad)
            let pitch = CGFloat(data.pitch * degToRad)
            let yaw = CGFloat(data.yaw * degToRad)
            
            // Look for the primary object node (usually the first child of the root node)
            let droneNode = scene.rootNode.childNodes.first(where: { $0.camera == nil && $0.light == nil }) ?? scene.rootNode
            
            SCNTransaction.begin()
            SCNTransaction.animationDuration = 0.1
            droneNode.eulerAngles = SCNVector3(pitch, yaw, roll) 
            SCNTransaction.commit()
        }
    }
    
    private func createFallbackScene() -> SCNScene {
        let fallbackScene = SCNScene()
        
        let box = SCNBox(width: 1, height: 0.2, length: 1, chamferRadius: 0)
        box.firstMaterial?.diffuse.contents = UIColor.red
        box.firstMaterial?.isDoubleSided = true
        let node = SCNNode(geometry: box)
        node.position = SCNVector3(0, 0, 0)
        fallbackScene.rootNode.addChildNode(node)
        
        // Add a default camera to the scene to guarantee visibility
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(x: 0, y: 1, z: 3)
        // point camera at the box
        let lookAtConstraint = SCNLookAtConstraint(target: node)
        cameraNode.constraints = [lookAtConstraint]
        fallbackScene.rootNode.addChildNode(cameraNode)
        
        // Add a light so the box is visible even if options fail
        let lightNode = SCNNode()
        lightNode.light = SCNLight()
        lightNode.light?.type = .omni
        lightNode.position = SCNVector3(0, 10, 10)
        fallbackScene.rootNode.addChildNode(lightNode)
        
        // Add an ambient light
        let ambientLightNode = SCNNode()
        ambientLightNode.light = SCNLight()
        ambientLightNode.light?.type = .ambient
        ambientLightNode.light?.color = UIColor.darkGray
        fallbackScene.rootNode.addChildNode(ambientLightNode)
        
        // Ensure background is visible
        fallbackScene.background.contents = UIColor.lightGray
        
        print("Fallback scene created.")
        return fallbackScene
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
    }
}
