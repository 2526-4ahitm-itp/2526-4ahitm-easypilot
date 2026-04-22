import SwiftUI
import SceneKit

/// The main dashboard view for the EasyPilot app.
/// Displays real-time telemetry data and a 3D model of the drone with a modern UI.
struct DashboardView: View {
    @StateObject var wsManager = WebSocketManager()
    @StateObject var motionManager = MotionManager()
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
                            TelemetryCard(title: "ROLL",    value: String(format: "%.1f°", wsManager.telemetry?.roll  ?? 0), icon: "arrow.left.and.right")
                            TelemetryCard(title: "PITCH",   value: String(format: "%.1f°", wsManager.telemetry?.pitch ?? 0), icon: "arrow.up.and.down")
                            TelemetryCard(title: "YAW",     value: String(format: "%.1f°", wsManager.telemetry?.yaw   ?? 0), icon: "rotate.right")
                            TelemetryCard(title: "BATTERY",
                                          value: wsManager.telemetry?.voltage != nil
                                              ? String(format: "%.1fV", wsManager.telemetry!.voltage!)
                                              : "--.-V",
                                          icon: "battery.100",
                                          color: batteryColor)
                        }
                        .padding(.horizontal)

                        // iPhone Motion Indicator Card
                        iphoneMotionCard

                        // Motor Status Card
                        motorStatusCard
                    }
                    .padding(.bottom, 20)
                }
            }

            // Safe Test Overlay
            if isSafeTestActive {
                safeTestOverlay
            }
        }
        .onAppear {
            wsManager.start()
            motionManager.startUpdates()
            loadScene()
        }
        .onDisappear {
            wsManager.stop()
            motionManager.stopUpdates()
        }
        // Send SAFE_TEST command over WebSocket when tilt threshold is crossed
        .onChange(of: isSafeTestActive) { active in
            if active { wsManager.sendSafeTest() }
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
                        .fill(wsManager.isConnected ? successColor : dangerColor)
                        .frame(width: 8, height: 8)
                        .shadow(color: wsManager.isConnected ? successColor : dangerColor, radius: 4)

                    Text(wsManager.isConnected ? "CONNECTED" : "DISCONNECTED")
                        .font(.system(size: 12, weight: .black))
                        .foregroundColor(wsManager.isConnected ? successColor : dangerColor)
                }
            }

            Spacer()

            // Battery Shortcut in Header
            if let voltage = wsManager.telemetry?.voltage {
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
                .frame(height: 300)
                .onChange(of: wsManager.telemetry?.roll) { _ in
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
                .frame(height: 300)
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

    private var iphoneMotionCard: some View {
        HStack(spacing: 20) {
            VStack(alignment: .leading) {
                Text("IPHONE MOTION")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.gray)

                HStack(spacing: 15) {
                    VStack(alignment: .leading) {
                        Text(String(format: "%.1f°", motionManager.pitch))
                            .font(.system(size: 18, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                        Text("PITCH")
                            .font(.system(size: 9))
                            .foregroundColor(.gray)
                    }

                    VStack(alignment: .leading) {
                        Text(String(format: "%.1f°", motionManager.roll))
                            .font(.system(size: 18, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                        Text("ROLL")
                            .font(.system(size: 9))
                            .foregroundColor(.gray)
                    }
                }
            }

            Spacer()

            // Visual indicator of iPhone tilt
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.white.opacity(0.2), lineWidth: 2)
                    .frame(width: 40, height: 70)

                RoundedRectangle(cornerRadius: 4)
                    .fill(accentColor)
                    .frame(width: 30, height: 50)
                    .rotationEffect(.degrees(motionManager.roll))
                    .offset(y: CGFloat(-motionManager.pitch / 2))
            }
            .padding(.trailing, 10)
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

    private var motorStatusCard: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("MOTOR OUTPUT")
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(.gray)

            HStack(spacing: 20) {
                MotorBar(label: "M1", value: wsManager.telemetry?.m1 ?? 1000)
                MotorBar(label: "M2", value: wsManager.telemetry?.m2 ?? 1000)
                MotorBar(label: "M3", value: wsManager.telemetry?.m3 ?? 1000)
                MotorBar(label: "M4", value: wsManager.telemetry?.m4 ?? 1000)
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

    private var safeTestOverlay: some View {
        VStack {
            Spacer()
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                Text("SAFE TEST MODE ACTIVE")
                    .font(.system(size: 14, weight: .black))
            }
            .padding()
            .background(warningColor)
            .foregroundColor(.black)
            .cornerRadius(10)
            .shadow(radius: 10)
            .padding(.bottom, 50)
        }
        .transition(.move(edge: .bottom))
    }

    private var isSafeTestActive: Bool {
        abs(motionManager.pitch) > 45 || abs(motionManager.roll) > 45
    }

    private var batteryColor: Color {
        guard let voltage = wsManager.telemetry?.voltage else { return .gray }
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
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(x: 0, y: 0.5, z: 2.0)
        let lookAtConstraint = SCNLookAtConstraint(target: scene.rootNode)
        cameraNode.constraints = [lookAtConstraint]
        scene.rootNode.addChildNode(cameraNode)

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
        if let data = wsManager.telemetry {
            let degToRad: Float = .pi / 180.0
            let roll  = CGFloat(data.roll  * degToRad)
            let pitch = CGFloat(data.pitch * degToRad)
            let yaw   = CGFloat(data.yaw   * degToRad)

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
