import SwiftUI
import SceneKit

/// The main dashboard view for the EasyPilot app.
/// Displays real-time telemetry data and a 3D model of the drone with a modern UI.
struct DashboardView: View {
    @StateObject var udpListener = UDPListener()
    @State private var droneScene: SCNScene?
    
    // Theme Colors
    private let backgroundColor = Color(red: 0.05, green: 0.05, blue: 0.07)
    private let cardBackground = Color.white.opacity(0.05)
    private let accentColor = Color.blue
    private let warningColor = Color.orange
    private let dangerColor = Color.red
    private let successColor = Color.green

    var body: some View {
        ZStack {
            // Background
            backgroundColor.ignoresSafeArea()
            
            VStack(spacing: 20) {
                // Header: Status and Title
                headerView
                
                ScrollView {
                    VStack(spacing: 20) {
                        // 3D Model View Card
                        drone3DCard
                        
                        // Telemetry Grid
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 15) {
                            TelemetryCard(title: "ROLL", value: String(format: "%.1f°", udpListener.telemetry?.roll ?? 0), icon: "arrow.left.and.right")
                            TelemetryCard(title: "PITCH", value: String(format: "%.1f°", udpListener.telemetry?.pitch ?? 0), icon: "arrow.up.and.down")
                            TelemetryCard(title: "YAW", value: String(format: "%.1f°", udpListener.telemetry?.yaw ?? 0), icon: "rotate.right")
                            TelemetryCard(title: "BATTERY", 
                                          value: udpListener.telemetry?.voltage != nil ? String(format: "%.1fV", udpListener.telemetry!.voltage!) : "--.-V", 
                                          icon: "battery.100",
                                          color: batteryColor)
                        }
                        .padding(.horizontal)
                        
                        // Motor Status Card
                        motorStatusCard
                    }
                    .padding(.bottom, 20)
                }
            }
        }
        .onAppear {
            udpListener.startListening()
            loadScene()
        }
    }
    
    // MARK: - Subviews
    
    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("EasyPilot")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
                
                HStack(spacing: 6) {
                    Circle()
                        .fill(udpListener.isConnected ? successColor : dangerColor)
                        .frame(width: 8, height: 8)
                        .shadow(color: udpListener.isConnected ? successColor : dangerColor, radius: 4)
                    
                    Text(udpListener.isConnected ? "CONNECTED" : "DISCONNECTED")
                        .font(.system(size: 12, weight: .black))
                        .foregroundColor(udpListener.isConnected ? successColor : dangerColor)
                }
            }
            
            Spacer()
            
            // Battery Shortcut in Header
            if let voltage = udpListener.telemetry?.voltage {
                HStack(spacing: 4) {
                    Image(systemName: "battery.75")
                        .foregroundColor(batteryColor)
                    Text(String(format: "%.1fV", voltage))
                        .font(.system(.subheadline, design: .monospaced))
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Capsule().fill(cardBackground))
            }
        }
        .padding(.horizontal)
        .padding(.top, 10)
    }
    
    private var drone3DCard: some View {
        VStack {
            if let scene = droneScene {
                SceneView(
                    scene: scene,
                    options: [.autoenablesDefaultLighting, .allowsCameraControl]
                )
                .frame(height: 350)
                .onChange(of: udpListener.telemetry?.roll) { _ in
                    updateSceneRotation(scene: scene)
                }
            } else {
                VStack {
                    ProgressView()
                        .tint(.white)
                    Text("Initializing Avionics...")
                        .font(.caption)
                        .foregroundColor(.gray)
                        .padding(.top)
                }
                .frame(height: 350)
                .frame(maxWidth: .infinity)
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
        )
        .padding(.horizontal)
    }
    
    private var motorStatusCard: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("MOTOR OUTPUT")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(.gray)
            
            HStack(spacing: 20) {
                MotorBar(label: "M1", value: udpListener.telemetry?.m1 ?? 1000)
                MotorBar(label: "M2", value: udpListener.telemetry?.m2 ?? 1000)
                MotorBar(label: "M3", value: udpListener.telemetry?.m3 ?? 1000)
                MotorBar(label: "M4", value: udpListener.telemetry?.m4 ?? 1000)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
        )
        .padding(.horizontal)
    }
    
    private var batteryColor: Color {
        guard let voltage = udpListener.telemetry?.voltage else { return .gray }
        if voltage < 14.0 { return dangerColor }
        if voltage < 15.0 { return warningColor }
        return successColor
    }

    // MARK: - Scene Management
    
    private func loadScene() {
        guard droneScene == nil else { return }
        
        DispatchQueue.global(qos: .userInitiated).async {
            var scene: SCNScene
            if let url = Bundle.main.url(forResource: "drohne-compressed", withExtension: "usdz") {
                do {
                    scene = try SCNScene(url: url, options: nil)
                    setupSceneNodes(scene: scene)
                } catch {
                    print("Failed to load USDZ scene: \(error)")
                    scene = self.createFallbackScene()
                }
            } else {
                scene = self.createFallbackScene()
            }
            
            DispatchQueue.main.async {
                self.droneScene = scene
            }
        }
    }
    
    private func setupSceneNodes(scene: SCNScene) {
        // Camera setup
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(x: 0, y: 0.5, z: 2.0)
        let lookAtConstraint = SCNLookAtConstraint(target: scene.rootNode)
        cameraNode.constraints = [lookAtConstraint]
        scene.rootNode.addChildNode(cameraNode)
        
        // Lighting setup
        let ambientLight = SCNNode()
        ambientLight.light = SCNLight()
        ambientLight.light?.type = .ambient
        ambientLight.light?.intensity = 400
        scene.rootNode.addChildNode(ambientLight)
        
        let directionalLight = SCNNode()
        directionalLight.light = SCNLight()
        directionalLight.light?.type = .directional
        directionalLight.light?.intensity = 800
        directionalLight.position = SCNVector3(x: 5, y: 10, z: 5)
        directionalLight.eulerAngles = SCNVector3(-Float.pi / 4, Float.pi / 4, 0)
        scene.rootNode.addChildNode(directionalLight)
        
        scene.background.contents = UIColor.clear
    }
    
    private func updateSceneRotation(scene: SCNScene) {
        if let data = udpListener.telemetry {
            let degToRad: Float = .pi / 180.0
            let roll = CGFloat(data.roll * degToRad)
            let pitch = CGFloat(data.pitch * degToRad)
            let yaw = CGFloat(data.yaw * degToRad)
            
            let droneNode = scene.rootNode.childNodes.first(where: { $0.camera == nil && $0.light == nil }) ?? scene.rootNode
            
            SCNTransaction.begin()
            SCNTransaction.animationDuration = 0.1
            droneNode.eulerAngles = SCNVector3(pitch, yaw, roll) 
            SCNTransaction.commit()
        }
    }
    
    private func createFallbackScene() -> SCNScene {
        let fallbackScene = SCNScene()
        let box = SCNBox(width: 1, height: 0.1, length: 1, chamferRadius: 0.05)
        box.firstMaterial?.diffuse.contents = UIColor.systemBlue
        let node = SCNNode(geometry: box)
        fallbackScene.rootNode.addChildNode(node)
        setupSceneNodes(scene: fallbackScene)
        return fallbackScene
    }
}

// MARK: - Components

struct TelemetryCard: View {
    let title: String
    let value: String
    let icon: String
    var color: Color = .blue
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(color)
                Spacer()
            }
            
            VStack(alignment: .leading, spacing: 4) {
                Text(value)
                    .font(.system(size: 20, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                
                Text(title)
                    .font(.system(size: 10, weight: .black))
                    .foregroundColor(.gray)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.white.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
        )
    }
}

struct MotorBar: View {
    let label: String
    let value: Int
    
    private let minPWM = 1000
    private let maxPWM = 2000
    
    var body: some View {
        VStack(spacing: 8) {
            GeometryReader { geo in
                ZStack(alignment: .bottom) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.1))
                    
                    let percentage = CGFloat(max(0, min(1, Double(value - minPWM) / Double(maxPWM - minPWM))))
                    
                    RoundedRectangle(cornerRadius: 4)
                        .fill(LinearGradient(colors: [.blue, .cyan], startPoint: .top, endPoint: .bottom))
                        .frame(height: geo.size.height * percentage)
                }
            }
            .frame(width: 12, height: 80)
            
            Text(label)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.gray)
            
            Text("\(value)")
                .font(.system(size: 9, design: .monospaced))
                .foregroundColor(.white.opacity(0.8))
        }
        .frame(maxWidth: .infinity)
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
            .preferredColorScheme(.dark)
    }
}