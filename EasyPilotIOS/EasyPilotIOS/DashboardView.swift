import SwiftUI
import SceneKit

struct DashboardView: View {
    @ObservedObject var wsManager: WebSocketManager
    @StateObject private var motionManager = MotionManager()
    @State private var droneScene: SCNScene?

    var body: some View {
        ZStack {
            EasyPilotTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                headerView
                    .padding(.horizontal)
                    .padding(.top, 16)
                    .padding(.bottom, 12)

                ScrollView {
                    VStack(spacing: 16) {
                        drone3DCard
                        telemetryGrid
                        iphoneMotionCard
                        motorStatusCard
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 24)
                }
            }

            if isSafeTestActive { safeTestOverlay }
        }
        .onAppear {
            motionManager.startUpdates()
            loadScene()
        }
        .onDisappear {
            motionManager.stopUpdates()
        }
        .onChange(of: isSafeTestActive) { active in
            if active { wsManager.sendSafeTest() }
        }
    }

    // MARK: - Subviews

    private var headerView: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 5) {
                Text("EasyPilot")
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                    .foregroundColor(.white)

                HStack(spacing: 8) {
                    PulsingDot(color: wsManager.isConnected ? EasyPilotTheme.success : EasyPilotTheme.danger)
                    Text(wsManager.isConnected ? "CONNECTED" : "SEARCHING…")
                        .font(.system(size: 11, weight: .black, design: .monospaced))
                        .foregroundColor(wsManager.isConnected
                                         ? EasyPilotTheme.success : EasyPilotTheme.danger)
                    if let ip = wsManager.esp32IP, wsManager.isConnected {
                        Text("· \(ip)")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.gray)
                    }
                }
                // Armed + mode badge
                if wsManager.isConnected {
                    HStack(spacing: 6) {
                        if wsManager.telemetry?.armed == true {
                            Label("ARMED", systemImage: "exclamationmark.triangle.fill")
                                .font(.system(size: 9, weight: .black))
                                .foregroundColor(EasyPilotTheme.danger)
                        }
                        if let mode = wsManager.telemetry?.mode, mode != "IDLE" {
                            Text(mode)
                                .font(.system(size: 9, weight: .black, design: .monospaced))
                                .foregroundColor(EasyPilotTheme.accent)
                        }
                    }
                }
            }

            Spacer()

            if let voltage = wsManager.telemetry?.voltage {
                VStack(alignment: .trailing, spacing: 2) {
                    HStack(spacing: 4) {
                        Image(systemName: batteryIcon(voltage))
                            .foregroundColor(batteryColor(voltage))
                        Text(String(format: "%.1f V", voltage))
                            .font(.system(size: 15, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                    }
                    if let pct = wsManager.telemetry?.batteryPercentage {
                        Text("\(pct)%")
                            .font(.system(size: 10, weight: .semibold, design: .monospaced))
                            .foregroundColor(batteryColor(voltage))
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .glassCard(cornerRadius: 14)
            }
        }
    }

    private var drone3DCard: some View {
        Group {
            if let scene = droneScene {
                SceneView(scene: scene, options: [.autoenablesDefaultLighting, .allowsCameraControl])
                    .frame(height: 280)
                    .onChange(of: wsManager.telemetry?.roll) { _ in
                        updateSceneRotation(scene: scene)
                    }
            } else {
                VStack(spacing: 10) {
                    ProgressView().tint(EasyPilotTheme.accent)
                    Text("Initializing Avionics…")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                .frame(height: 280)
                .frame(maxWidth: .infinity)
            }
        }
        .glassCard(cornerRadius: 24)
    }

    private var telemetryGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            TelemetryCard(title: "ROLL",
                          value: String(format: "%.1f°", wsManager.telemetry?.roll ?? 0),
                          icon: "arrow.left.and.right")
            TelemetryCard(title: "PITCH",
                          value: String(format: "%.1f°", wsManager.telemetry?.pitch ?? 0),
                          icon: "arrow.up.and.down")
            TelemetryCard(title: "YAW",
                          value: String(format: "%.1f°", wsManager.telemetry?.yaw ?? 0),
                          icon: "rotate.right")
            TelemetryCard(title: "BATTERY",
                          value: wsManager.telemetry?.voltage != nil
                              ? String(format: "%.1f V", wsManager.telemetry!.voltage!)
                              : "--.- V",
                          icon: "battery.100",
                          color: wsManager.telemetry?.voltage.map { batteryColor($0) } ?? .gray)
        }
    }

    private var iphoneMotionCard: some View {
        HStack(spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader("IPHONE MOTION")

                HStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(String(format: "%.1f°", motionManager.pitch))
                            .font(.system(size: 20, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                        Text("PITCH")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.gray)
                            .tracking(1.5)
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(String(format: "%.1f°", motionManager.roll))
                            .font(.system(size: 20, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                        Text("ROLL")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.gray)
                            .tracking(1.5)
                    }
                }

                if isSafeTestActive {
                    Text("⚠ SAFE TEST ARMED")
                        .font(.system(size: 10, weight: .black))
                        .foregroundColor(EasyPilotTheme.warning)
                        .transition(.opacity)
                }
            }

            Spacer()

            HorizonIndicator(pitch: motionManager.pitch, roll: motionManager.roll)
        }
        .padding()
        .glassCard()
    }

    private var motorStatusCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader("MOTOR OUTPUT")
            HStack(spacing: 16) {
                MotorBar(label: "M1", value: wsManager.telemetry?.m1 ?? 1000)
                MotorBar(label: "M2", value: wsManager.telemetry?.m2 ?? 1000)
                MotorBar(label: "M3", value: wsManager.telemetry?.m3 ?? 1000)
                MotorBar(label: "M4", value: wsManager.telemetry?.m4 ?? 1000)
            }
        }
        .padding()
        .glassCard()
    }

    private var safeTestOverlay: some View {
        VStack {
            Spacer()
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.black)
                Text("SAFE TEST MODE ACTIVE")
                    .font(.system(size: 13, weight: .black))
                    .foregroundColor(.black)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(EasyPilotTheme.warning)
            .clipShape(Capsule())
            .shadow(color: EasyPilotTheme.warning.opacity(0.5), radius: 16, y: 4)
            .padding(.bottom, 40)
        }
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .animation(.spring(response: 0.4), value: isSafeTestActive)
    }

    // MARK: - Computed helpers

    private var isSafeTestActive: Bool {
        abs(motionManager.pitch) > 45 || abs(motionManager.roll) > 45
    }

    private func batteryColor(_ v: Float) -> Color {
        if v < 14.0 { return EasyPilotTheme.danger }
        if v < 15.0 { return EasyPilotTheme.warning }
        return EasyPilotTheme.success
    }

    private func batteryIcon(_ v: Float) -> String {
        if v < 14.0 { return "battery.25" }
        if v < 15.0 { return "battery.50" }
        return "battery.75"
    }

    // MARK: - Scene management

    private func loadScene() {
        guard droneScene == nil else { return }
        DispatchQueue.global(qos: .userInitiated).async {
            var scene: SCNScene
            if let url = Bundle.main.url(forResource: "drohne-compressed", withExtension: "usdz"),
               let loaded = try? SCNScene(url: url, options: nil) {
                scene = loaded
            } else {
                scene = makeFallbackScene()
            }
            setupSceneCamera(scene)
            DispatchQueue.main.async { self.droneScene = scene }
        }
    }

    private func setupSceneCamera(_ scene: SCNScene) {
        let cam = SCNNode(); cam.camera = SCNCamera()
        cam.position = SCNVector3(0, 0.5, 2.0)
        cam.constraints = [SCNLookAtConstraint(target: scene.rootNode)]
        scene.rootNode.addChildNode(cam)

        let ambient = SCNNode(); ambient.light = SCNLight()
        ambient.light?.type = .ambient; ambient.light?.intensity = 400
        scene.rootNode.addChildNode(ambient)

        let dir = SCNNode(); dir.light = SCNLight()
        dir.light?.type = .directional; dir.light?.intensity = 800
        dir.position = SCNVector3(5, 10, 5)
        dir.eulerAngles = SCNVector3(-Float.pi / 4, Float.pi / 4, 0)
        scene.rootNode.addChildNode(dir)

        scene.background.contents = UIColor.clear
    }

    private func updateSceneRotation(scene: SCNScene) {
        guard let data = wsManager.telemetry else { return }
        let r: Float = .pi / 180.0
        let node = scene.rootNode.childNodes.first { $0.camera == nil && $0.light == nil } ?? scene.rootNode
        SCNTransaction.begin()
        SCNTransaction.animationDuration = 0.1
        node.eulerAngles = SCNVector3(data.pitch * r, data.yaw * r, data.roll * r)
        SCNTransaction.commit()
    }

    private func makeFallbackScene() -> SCNScene {
        let s = SCNScene()
        let box = SCNBox(width: 1, height: 0.1, length: 1, chamferRadius: 0.05)
        box.firstMaterial?.diffuse.contents = UIColor.systemBlue
        s.rootNode.addChildNode(SCNNode(geometry: box))
        return s
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView(wsManager: WebSocketManager())
            .preferredColorScheme(.dark)
    }
}
