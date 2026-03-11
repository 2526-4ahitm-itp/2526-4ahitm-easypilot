import SwiftUI
import SceneKit

/// The main dashboard view for the EasyPilot app.
/// Displays real-time telemetry data and a 3D model of the drone.
struct DashboardView: View {
    @StateObject var udpListener = UDPListener()
    
    var body: some View {
        VStack {
            Text("Drone Dashboard")
                .font(.largeTitle)
                .padding()
            
            // 3D Model View
            SceneView(
                scene: createScene(),
                options: [.autoenablesDefaultLighting, .allowsCameraControl]
            )
            .frame(height: 300)
            .cornerRadius(10)
            .padding()
            
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
                        Text("Motor 1: \(data.m1)")
                        Spacer()
                        Text("Motor 4: \(data.m4)")
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
        }
    }
    
    /// Creates the SceneKit scene with the drone model.
    func createScene() -> SCNScene {
        // Load the drone model from the bundle
        // Note: Ensure "drohne-compressed.glb" is added to your Xcode project resources.
        guard let scene = SCNScene(named: "drohne-compressed.glb") else {
            // Fallback to a simple box if the model is not found
            let scene = SCNScene()
            let box = SCNBox(width: 1, height: 0.2, length: 1, chamferRadius: 0)
            box.firstMaterial?.diffuse.contents = UIColor.red
            let node = SCNNode(geometry: box)
            scene.rootNode.addChildNode(node)
            return scene
        }
        
        // Apply rotation based on telemetry data
        if let data = udpListener.telemetry {
            // Convert degrees to radians if necessary, or use raw values if they are already in radians
            // Assuming the ESP32 sends radians as per the .ino file analysis
            let roll = CGFloat(data.roll)
            let pitch = CGFloat(data.pitch)
            let yaw = CGFloat(data.yaw)
            
            // Rotate the root node or a specific child node representing the drone body
            scene.rootNode.eulerAngles = SCNVector3(pitch, yaw, roll) 
        }
        
        return scene
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
    }
}
