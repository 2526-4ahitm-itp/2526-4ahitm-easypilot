import SwiftUI

struct SimulatorView: View {

    @ObservedObject var wsManager: WebSocketManager

    @StateObject private var sim            = DroneSimulator()
    @StateObject private var profileManager = ProfileManager()

    @State private var leftX:  Double = 0
    @State private var leftY:  Double = 0
    @State private var rightX: Double = 0
    @State private var rightY: Double = 0

    @State private var leftTouching:  Bool = false
    @State private var rightTouching: Bool = false

    // General settings
    @State private var expo: Double = 0.35
    @State private var activeCamera: SimCamera = .chase
    @State private var showExpoSlider    = false
    @State private var isLiveMode        = false
    @State private var showLiveHint      = false   // "not connected" hint
    @State private var showThrottleHint  = false
    @State private var rcTimer: Timer?

    /// Landscape only — top telemetry/mode/settings pill is collapsed by default.
    @State private var showLandscapeChip: Bool = false
    /// Optional: animate joystick thumbs to mirror autopilot demand on release.
    @State private var autopilotSticks: Bool = true

    // Flight mode + balance config
    @State private var flightMode:       SimFlightMode = .rate
    @State private var kPRoll:           Double = 10.0
    @State private var kPPitch:          Double = 10.0
    @State private var maxBalanceAngle:  Double = 30.0
    @State private var showBalanceCfg    = false
    @State private var showProfilePicker = false
    @State private var ratePreset:   String = "SPORT"
    @State private var rollHistory:  [Double] = Array(repeating: 0, count: 60)
    @State private var pitchHistory: [Double] = Array(repeating: 0, count: 60)

    @Environment(\.verticalSizeClass) private var verticalSizeClass

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .bottom) {
            SimulatorScene(sim: sim, activeCamera: activeCamera)
                .ignoresSafeArea()

            // Top overlay
            VStack {
                topBar
                    .padding(.top, 14)
                    .padding(.horizontal, 14)

                if verticalSizeClass == .regular {
                    // Portrait only — landscape's top chip replaces these.
                    HStack(alignment: .top) {
                        miniHorizon
                            .padding(.leading, 14)
                            .padding(.top, 6)
                        Spacer()
                        AttitudeSparkline(rollHistory: rollHistory, pitchHistory: pitchHistory)
                            .frame(width: 130, height: 52)
                            .background(.ultraThinMaterial)
                            .cornerRadius(10)
                            .padding(.trailing, 14)
                            .padding(.top, 6)
                    }
                } else {
                    // Landscape: collapsed by default with a small pop-out chevron
                    HStack(alignment: .top) {
                        landscapeChipToggle
                            .padding(.leading, 14)
                            .padding(.top, 8)
                        Spacer()
                        if showLandscapeChip {
                            landscapeTopChip
                                .padding(.top, 8)
                                .padding(.trailing, 14)
                                .transition(.move(edge: .top).combined(with: .opacity))
                        }
                    }
                }

                Spacer()
            }

            // Bottom panel — one cohesive frosted slab
            if verticalSizeClass == .regular {
                portraitBottomPanel
            } else {
                landscapeOverlay
            }
        }
        .onChange(of: leftX)  { _ in pushInputs() }
        .onChange(of: leftY)  { _ in pushInputs() }
        .onChange(of: rightX) { _ in pushInputs() }
        .onChange(of: rightY) { _ in pushInputs() }
        .onChange(of: leftTouching)  { _ in pushTouchState() }
        .onChange(of: rightTouching) { _ in pushTouchState() }
        .onChange(of: expo)   { v in sim.expo = v }
        .onChange(of: flightMode)      { v in sim.flightMode = v }
        .onChange(of: kPRoll)          { v in sim.kPRoll = v }
        .onChange(of: kPPitch)         { v in sim.kPPitch = v }
        .onChange(of: maxBalanceAngle) { v in sim.maxBalanceAngle = v }
        .onReceive(sim.$simRoll)  { v in rollHistory.append(v);  if rollHistory.count  > 60 { rollHistory.removeFirst()  } }
        .onReceive(sim.$simPitch) { v in pitchHistory.append(v); if pitchHistory.count > 60 { pitchHistory.removeFirst() } }
        .onDisappear { stopRCTimer(); sim.disarm() }
        .overlay {
            if sim.isCrashed {
                ZStack {
                    Color.red.opacity(0.28).ignoresSafeArea()
                    VStack(spacing: 24) {
                        Text("CRASHED")
                            .font(.system(size: 42, weight: .black, design: .monospaced))
                            .foregroundColor(.white)
                            .tracking(4)
                            .shadow(color: .black.opacity(0.5), radius: 8)
                        Button { sim.respawn() } label: {
                            Text("RESPAWN")
                                .font(.system(size: 15, weight: .black, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(.black)
                                .padding(.horizontal, 28).padding(.vertical, 12)
                                .background(Color.white)
                                .cornerRadius(10)
                        }
                    }
                }
                .transition(.opacity)
            }
        }
        .overlay(alignment: .top) {
            if showLiveHint {
                toast("Not connected to drone", .warning).padding(.top, 80)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
            if showThrottleHint {
                toast("Lower throttle before arming", .danger).padding(.top, 80)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        // Profile picker sheet
        .confirmationDialog("Load Balance Profile", isPresented: $showProfilePicker, titleVisibility: .visible) {
            let balanceProfiles = profileManager.profiles.filter { $0.mode == "BALANCE" }
            if balanceProfiles.isEmpty {
                Button("No BALANCE profiles saved", role: .cancel) {}
            } else {
                ForEach(balanceProfiles) { profile in
                    Button("\(profile.name)  (kP Roll \(String(format: "%.1f", profile.kPRoll)), Pitch \(String(format: "%.1f", profile.kPPitch)))") {
                        kPRoll  = profile.kPRoll
                        kPPitch = profile.kPPitch
                    }
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("kP values will be copied into the simulator")
        }
    }

    // MARK: - Top bar

    private var topBar: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Circle()
                    .fill(sim.isArmed ? EasyPilotTheme.danger : Color.white.opacity(0.3))
                    .frame(width: 8, height: 8)
                Text(sim.isArmed ? "ARMED" : "DISARMED")
                    .font(.system(size: 11, weight: .black, design: .monospaced))
                    .foregroundColor(sim.isArmed ? EasyPilotTheme.danger : Color.white.opacity(0.45))
                    .tracking(2)
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(.ultraThinMaterial).cornerRadius(8)

            Spacer()

            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    activeCamera = activeCamera == .chase ? .fpv : .chase
                }
            } label: {
                Image(systemName: activeCamera == .fpv ? "video.fill" : "video")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 34, height: 34)
                    .background(.ultraThinMaterial).cornerRadius(8)
            }

            // SIM / LIVE
            HStack(spacing: 0) {
                modeSegment("SIM",  active: !isLiveMode, onTap: {
                    if isLiveMode { enterSimMode() }
                })
                modeSegment("LIVE", active:  isLiveMode, onTap: {
                    if wsManager.isConnected { enterLiveMode() }
                    else { flash($showLiveHint) }
                })
            }
            .background(.ultraThinMaterial).cornerRadius(8)
        }
    }

    private func modeSegment(_ label: String, active: Bool, onTap: (() -> Void)? = nil) -> some View {
        Text(label)
            .font(.system(size: 10, weight: .black, design: .monospaced))
            .tracking(1.5)
            .foregroundColor(active ? .black : .white.opacity(0.18))
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(active ? EasyPilotTheme.accent : Color.clear)
            .cornerRadius(7)
            .onTapGesture { onTap?() }
    }

    // MARK: - Mini horizon

    private var miniHorizon: some View {
        VStack(spacing: 3) {
            HorizonIndicator(pitch: sim.simPitch, roll: sim.simRoll)
                .frame(width: 62, height: 62)
                .clipShape(Circle())
                .overlay(Circle().stroke(Color.white.opacity(0.18), lineWidth: 1))
            Text(rollLabel)
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundColor(.white.opacity(0.5))
        }
        .padding(7)
        .background(.ultraThinMaterial).cornerRadius(12)
    }

    private var rollLabel: String {
        let r = sim.simRoll
        if abs(r) < 1 { return "LEVEL" }
        return String(format: "%.0f°%@", abs(r), r < 0 ? "L" : "R")
    }

    // MARK: - Portrait bottom panel

    private var portraitBottomPanel: some View {
        VStack(spacing: 0) {
            // ── Telemetry row ──────────────────────────────────────────────
            HStack(spacing: 0) {
                telCell("ROL", String(format: "%+.0f°", sim.simRoll))
                divider
                telCell("PCH", String(format: "%+.0f°", sim.simPitch))
                divider
                telCell("YAW", String(format: "%+.0f°", sim.simYaw))
                Spacer()
                divider
                telCell("ALT", String(format: "%.1fm", sim.altitude))
                divider
                telCell("SPD", String(format: "%.1f", sim.speedH))
                divider
                // Expo / RATE settings button
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        if flightMode == .rate {
                            showExpoSlider.toggle()
                            showBalanceCfg = false
                        } else {
                            showBalanceCfg.toggle()
                            showExpoSlider = false
                        }
                    }
                } label: {
                    VStack(spacing: 1) {
                        Image(systemName: "slider.horizontal.3")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(EasyPilotTheme.accent)
                        Text(flightMode == .rate ? "EXPO" : "kP")
                            .font(.system(size: 8, weight: .black, design: .monospaced))
                            .foregroundColor(EasyPilotTheme.accent.opacity(0.7))
                            .tracking(1)
                    }
                    .padding(.horizontal, 12)
                }
            }
            .frame(height: 44)
            .background(Color.white.opacity(0.04))

            separator

            // ── Flight mode selector ───────────────────────────────────────
            HStack(spacing: 6) {
                Text("MODE")
                    .font(.system(size: 9, weight: .black, design: .monospaced))
                    .foregroundColor(.white.opacity(0.35))
                    .tracking(1.5)

                HStack(spacing: 2) {
                    ForEach(SimFlightMode.allCases, id: \.self) { mode in
                        Button {
                            withAnimation(.easeInOut(duration: 0.18)) {
                                flightMode = mode
                                showExpoSlider = false
                                showBalanceCfg = false
                            }
                        } label: {
                            Text(mode.rawValue)
                                .font(.system(size: 10, weight: .black, design: .monospaced))
                                .tracking(1.2)
                                .foregroundColor(flightMode == mode ? .black : .white.opacity(0.45))
                                .padding(.horizontal, 11).padding(.vertical, 5)
                                .background(flightMode == mode ? EasyPilotTheme.accent : Color.white.opacity(0.06))
                                .cornerRadius(6)
                        }
                    }
                }
                .padding(2)
                .background(Color.white.opacity(0.05))
                .cornerRadius(8)

                if flightMode == .balance {
                    Spacer()
                    Text("Self-levelling · stick sets target angle")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(.white.opacity(0.3))
                }

                Spacer()
            }
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(Color.white.opacity(0.03))

            // ── Rate config (RATE mode) ───────────────────────────────────
            if showExpoSlider { rateConfigPanel }

            // ── Balance config (BALANCE mode) ─────────────────────────────
            if showBalanceCfg { balanceConfigPanel }

            separator

            // ── Joysticks + arm ────────────────────────────────────────────
            HStack(alignment: .center, spacing: 0) {
                VirtualJoystick(label: "THR / YAW",
                                lockY: true, expo: expo,
                                centerX: $leftX, centerY: $leftY,
                                isTouching: $leftTouching,
                                autopilotEnabled: autopilotSticks,
                                autopilotX: 0,
                                autopilotY: sim.autopilotLeftY,
                                stabilizationActive: !leftTouching)
                    .padding(.leading, 16)

                Spacer()
                armButton
                Spacer()

                VirtualJoystick(label: "PCH / ROL",
                                lockY: false, expo: expo,
                                centerX: $rightX, centerY: $rightY,
                                isTouching: $rightTouching,
                                autopilotEnabled: autopilotSticks,
                                autopilotX: sim.autopilotRightX,
                                autopilotY: sim.autopilotRightY,
                                stabilizationActive: !rightTouching && (flightMode == .balance || flightMode == .poshold))
                    .padding(.trailing, 16)
            }
            .padding(.top, 10).padding(.bottom, 16)
        }
        .background(.ultraThinMaterial)
    }

    // MARK: - Landscape overlay (floating UI, full-screen 3D scene)

    private var landscapeOverlay: some View {
        ZStack {
            // Bottom row: corner-anchored joysticks + centered arm button
            VStack {
                Spacer()
                HStack(alignment: .bottom, spacing: 0) {
                    floatingJoystick(label: "THR / YAW", lockY: true,
                                     centerX: $leftX, centerY: $leftY,
                                     isTouching: $leftTouching,
                                     autopilotX: 0,
                                     autopilotY: sim.autopilotLeftY,
                                     stabilizationActive: !leftTouching)
                        .padding(.leading, 22)
                        .padding(.bottom, 18)

                    Spacer()

                    landscapeArmButton
                        .padding(.bottom, 24)

                    Spacer()

                    floatingJoystick(label: "PCH / ROL", lockY: false,
                                     centerX: $rightX, centerY: $rightY,
                                     isTouching: $rightTouching,
                                     autopilotX: sim.autopilotRightX,
                                     autopilotY: sim.autopilotRightY,
                                     stabilizationActive: !rightTouching && (flightMode == .balance || flightMode == .poshold))
                        .padding(.trailing, 22)
                        .padding(.bottom, 18)
                }
            }

            // Right-edge slide-out drawer for settings
            if showExpoSlider || showBalanceCfg {
                HStack {
                    Spacer()
                    landscapeSettingsDrawer
                        .frame(width: 320)
                        .background(.ultraThinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        .padding(.trailing, 10)
                        .padding(.vertical, 70)
                        .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
        }
    }

    private var landscapeChipToggle: some View {
        Button {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                showLandscapeChip.toggle()
            }
        } label: {
            Image(systemName: showLandscapeChip ? "chevron.up" : "chevron.down")
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(.white.opacity(0.7))
                .frame(width: 30, height: 30)
                .background(.ultraThinMaterial)
                .clipShape(Circle())
        }
    }

    private var landscapeTopChip: some View {
        HStack(spacing: 8) {
            // Compact numeric telemetry strip
            HStack(spacing: 0) {
                telCell("ROL", String(format: "%+.0f°", sim.simRoll))
                divider
                telCell("PCH", String(format: "%+.0f°", sim.simPitch))
                divider
                telCell("YAW", String(format: "%+.0f°", sim.simYaw))
                divider
                telCell("ALT", String(format: "%.1fm", sim.altitude))
                divider
                telCell("SPD", String(format: "%.1f", sim.speedH))
            }
            .padding(.vertical, 4)
            .background(.ultraThinMaterial)
            .clipShape(Capsule())

            // Mode selector
            HStack(spacing: 2) {
                ForEach(SimFlightMode.allCases, id: \.self) { mode in
                    Button {
                        withAnimation(.easeInOut(duration: 0.18)) {
                            flightMode = mode
                            showExpoSlider = false
                            showBalanceCfg = false
                        }
                    } label: {
                        Text(mode.rawValue)
                            .font(.system(size: 9, weight: .black, design: .monospaced))
                            .tracking(1.2)
                            .foregroundColor(flightMode == mode ? .black : .white.opacity(0.55))
                            .padding(.horizontal, 9).padding(.vertical, 5)
                            .background(flightMode == mode ? EasyPilotTheme.accent : Color.clear)
                            .cornerRadius(6)
                    }
                }
            }
            .padding(3)
            .background(.ultraThinMaterial)
            .clipShape(Capsule())

            // Settings toggle
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if flightMode == .rate {
                        showExpoSlider.toggle()
                        showBalanceCfg = false
                    } else {
                        showBalanceCfg.toggle()
                        showExpoSlider = false
                    }
                }
            } label: {
                Image(systemName: "slider.horizontal.3")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(EasyPilotTheme.accent)
                    .frame(width: 34, height: 34)
                    .background(.ultraThinMaterial)
                    .clipShape(Circle())
            }
        }
    }

    private var landscapeSettingsDrawer: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(flightMode == .rate ? "RATE / EXPO" : "BALANCE kP")
                    .font(.system(size: 11, weight: .black, design: .monospaced))
                    .tracking(1.5)
                    .foregroundColor(.white.opacity(0.55))
                Spacer()
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showExpoSlider = false
                        showBalanceCfg = false
                    }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(.white.opacity(0.5))
                        .frame(width: 24, height: 24)
                }
            }
            .padding(.horizontal, 14).padding(.top, 12).padding(.bottom, 8)

            if flightMode == .rate { rateConfigPanel }
            else                   { balanceConfigPanel }

            Divider().background(Color.white.opacity(0.08))
                .padding(.horizontal, 14).padding(.top, 6)

            Toggle(isOn: $autopilotSticks) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("AUTOPILOT STICKS")
                        .font(.system(size: 10, weight: .black, design: .monospaced))
                        .tracking(1.3)
                        .foregroundColor(.white.opacity(0.7))
                    Text("Mirror auto-level demand on release")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(.white.opacity(0.35))
                }
            }
            .tint(EasyPilotTheme.accent)
            .padding(.horizontal, 14).padding(.vertical, 10)

            Spacer()
        }
    }

    private func floatingJoystick(label: String, lockY: Bool,
                                  centerX: Binding<Double>, centerY: Binding<Double>,
                                  isTouching: Binding<Bool>,
                                  autopilotX: Double, autopilotY: Double,
                                  stabilizationActive: Bool) -> some View {
        VirtualJoystick(label: label, lockY: lockY, expo: expo,
                        centerX: centerX, centerY: centerY,
                        isTouching: isTouching,
                        autopilotEnabled: autopilotSticks,
                        autopilotX: autopilotX,
                        autopilotY: autopilotY,
                        stabilizationActive: stabilizationActive)
            .padding(10)
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
    }

    private var landscapeArmButton: some View {
        Button {
            if sim.isArmed {
                if isLiveMode { wsManager.sendCommand("{\"cmd\":\"DISARM\"}") }
                sim.disarm(); leftY = 0; pushInputs(); stopRCTimer()
            } else if max(0, -leftY) > 0.05 {
                flash($showThrottleHint)
            } else {
                if isLiveMode {
                    let kPRStr = String(format: "%.1f", kPRoll)
                    let kPPStr = String(format: "%.1f", kPPitch)
                    wsManager.sendCommand("{\"cmd\":\"ARM\"}")
                    wsManager.sendCommand("{\"cmd\":\"START_RC\",\"kPRoll\":\(kPRStr),\"kPPitch\":\(kPPStr)}")
                    startRCTimer()
                }
                sim.arm()
            }
        } label: {
            ZStack {
                Circle()
                    .fill(sim.isArmed ? EasyPilotTheme.danger : EasyPilotTheme.success)
                    .frame(width: 56, height: 56)
                    .shadow(color: (sim.isArmed ? EasyPilotTheme.danger : EasyPilotTheme.success).opacity(0.5),
                            radius: 10)
                VStack(spacing: 2) {
                    Image(systemName: sim.isArmed ? "stop.fill" : "play.fill")
                        .font(.system(size: 14, weight: .bold))
                    Text(sim.isArmed ? "DISARM" : "ARM")
                        .font(.system(size: 7, weight: .black, design: .monospaced))
                        .tracking(1.2)
                }
                .foregroundColor(.white)
            }
        }
    }

    // MARK: - Shared config panels

    private var rateConfigPanel: some View {
        VStack(spacing: 8) {
            HStack(spacing: 4) {
                Text("RATE")
                    .font(.system(size: 9, weight: .black, design: .monospaced))
                    .foregroundColor(.white.opacity(0.35))
                    .tracking(1.5)
                    .padding(.trailing, 4)
                ratePresetBtn("BEGINNER", rate: 180)
                ratePresetBtn("SPORT",    rate: 360)
                ratePresetBtn("PRO",      rate: 720)
                Spacer()
                let rateMap: [String: Int] = ["BEGINNER": 180, "SPORT": 360, "PRO": 720]
                Text("\(rateMap[ratePreset] ?? 360)°/s")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(EasyPilotTheme.accent.opacity(0.8))
            }
            HStack(spacing: 10) {
                Text("LINEAR")
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundColor(.white.opacity(0.3))
                Slider(value: $expo, in: 0...0.9).tint(EasyPilotTheme.accent)
                Text("EXPO \(Int(expo * 100))%")
                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                    .foregroundColor(EasyPilotTheme.accent)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .background(Color.white.opacity(0.04))
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    private var balanceConfigPanel: some View {
        VStack(spacing: 10) {
            LabeledSlider(label: "kP Roll",  unit: "", value: $kPRoll,
                          range: 1...20, step: 0.5, format: "%.1f")
            LabeledSlider(label: "kP Pitch", unit: "", value: $kPPitch,
                          range: 1...20, step: 0.5, format: "%.1f")
            LabeledSlider(label: "Max Angle", unit: "°", value: $maxBalanceAngle,
                          range: 10...60, step: 5)

            HStack {
                Button {
                    withAnimation { showProfilePicker = true }
                } label: {
                    Label("From saved profile", systemImage: "doc.badge.arrow.up")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(EasyPilotTheme.accent)
                }
                Spacer()
                Button {
                    kPRoll = 10.0; kPPitch = 10.0; maxBalanceAngle = 30.0
                } label: {
                    Text("Reset")
                        .font(.system(size: 12))
                        .foregroundColor(.white.opacity(0.4))
                }
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(Color.white.opacity(0.04))
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    // MARK: - Arm button

    private var armButton: some View {
        Button {
            if sim.isArmed {
                if isLiveMode { wsManager.sendCommand("{\"cmd\":\"DISARM\"}") }
                sim.disarm(); leftY = 0; pushInputs(); stopRCTimer()
            } else if max(0, -leftY) > 0.05 {
                flash($showThrottleHint)
            } else {
                if isLiveMode {
                    let kPRStr = String(format: "%.1f", kPRoll)
                    let kPPStr = String(format: "%.1f", kPPitch)
                    wsManager.sendCommand("{\"cmd\":\"ARM\"}")
                    wsManager.sendCommand("{\"cmd\":\"START_RC\",\"kPRoll\":\(kPRStr),\"kPPitch\":\(kPPStr)}")
                    startRCTimer()
                }
                sim.arm()
            }
        } label: {
            ZStack {
                Circle()
                    .fill(sim.isArmed ? EasyPilotTheme.danger : EasyPilotTheme.success)
                    .frame(width: 64, height: 64)
                    .shadow(color: (sim.isArmed ? EasyPilotTheme.danger : EasyPilotTheme.success).opacity(0.5),
                            radius: 12)
                VStack(spacing: 3) {
                    Image(systemName: sim.isArmed ? "stop.fill" : "play.fill")
                        .font(.system(size: 16, weight: .bold))
                    Text(sim.isArmed ? "DISARM" : "ARM")
                        .font(.system(size: 8, weight: .black, design: .monospaced))
                        .tracking(1.5)
                }
                .foregroundColor(.white)
            }
        }
    }

    // MARK: - Shared sub-views

    private var separator: some View {
        Rectangle().fill(Color.white.opacity(0.10)).frame(height: 0.5)
    }

    private var divider: some View {
        Rectangle().fill(Color.white.opacity(0.08))
            .frame(width: 0.5).padding(.vertical, 8)
    }

    private func telCell(_ label: String, _ value: String) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.system(size: 8, weight: .black, design: .monospaced))
                .foregroundColor(.white.opacity(0.38)).tracking(1.2)
            Text(value)
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(.white)
        }
        .padding(.horizontal, 11)
    }

    // MARK: - Helpers

    // MARK: - Live mode helpers

    private func enterLiveMode() {
        if sim.isArmed { sim.disarm() }
        isLiveMode = true
    }

    private func enterSimMode() {
        stopRCTimer()
        if sim.isArmed {
            wsManager.sendCommand("{\"cmd\":\"DISARM\"}")
            sim.disarm()
        }
        isLiveMode = false
    }

    private func startRCTimer() {
        rcTimer?.invalidate()
        rcTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [self] _ in
            sendRCPacket()
        }
    }

    private func stopRCTimer() {
        rcTimer?.invalidate()
        rcTimer = nil
    }

    private func sendRCPacket() {
        guard isLiveMode, sim.isArmed, wsManager.isConnected else { return }
        let thr = 1000 + Int(sim.throttle * 600)
        let pit = sim.pitch * maxBalanceAngle   // target pitch angle (°)
        let rol = sim.roll  * maxBalanceAngle   // target roll angle (°)
        let yaw = sim.yaw   * 80                // yaw PWM offset
        let cmd = String(format: "{\"cmd\":\"RC\",\"thr\":%d,\"pit\":%.1f,\"rol\":%.1f,\"yaw\":%.1f}",
                         thr, pit, rol, yaw)
        wsManager.sendCommand(cmd)
    }

    private func ratePresetBtn(_ label: String, rate: Double) -> some View {
        Button {
            ratePreset       = label
            sim.maxRollRate  = rate
            sim.maxPitchRate = rate
        } label: {
            Text(label)
                .font(.system(size: 9, weight: .black, design: .monospaced))
                .tracking(0.8)
                .foregroundColor(ratePreset == label ? .black : .white.opacity(0.45))
                .padding(.horizontal, 8).padding(.vertical, 5)
                .background(ratePreset == label ? EasyPilotTheme.accent : Color.white.opacity(0.06))
                .cornerRadius(6)
        }
    }

    private func pushInputs() {
        sim.yaw      =  leftX
        sim.throttle =  max(0, -leftY)
        sim.pitch    = -rightY
        sim.roll     =  rightX
    }

    private func pushTouchState() {
        sim.leftStickTouched  = leftTouching
        sim.rightStickTouched = rightTouching
    }

    private func flash(_ flag: Binding<Bool>) {
        withAnimation { flag.wrappedValue = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            withAnimation { flag.wrappedValue = false }
        }
    }

    private enum ToastStyle { case warning, danger }

    private func toast(_ text: String, _ style: ToastStyle) -> some View {
        Text(text)
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(style == .warning ? EasyPilotTheme.warning : EasyPilotTheme.danger)
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(.ultraThinMaterial).cornerRadius(10)
    }
}

// MARK: - Sparkline

private struct AttitudeSparkline: View {
    let rollHistory:  [Double]
    let pitchHistory: [Double]

    var body: some View {
        Canvas { ctx, size in
            let w   = size.width
            let h   = size.height
            let mid = h / 2
            // ±80° fills half the height
            let scale = (h / 2) / 80.0

            var zeroPath = Path()
            zeroPath.move(to:    CGPoint(x: 0, y: mid))
            zeroPath.addLine(to: CGPoint(x: w, y: mid))
            ctx.stroke(zeroPath, with: .color(.white.opacity(0.15)), lineWidth: 0.5)

            if rollHistory.count > 1 {
                var rPath = Path()
                for (i, v) in rollHistory.enumerated() {
                    let pt = CGPoint(x: w * CGFloat(i) / CGFloat(rollHistory.count - 1),
                                     y: mid - CGFloat(v) * scale)
                    i == 0 ? rPath.move(to: pt) : rPath.addLine(to: pt)
                }
                ctx.stroke(rPath, with: .color(EasyPilotTheme.accent), lineWidth: 1.5)
            }

            if pitchHistory.count > 1 {
                var pPath = Path()
                for (i, v) in pitchHistory.enumerated() {
                    let pt = CGPoint(x: w * CGFloat(i) / CGFloat(pitchHistory.count - 1),
                                     y: mid - CGFloat(v) * scale)
                    i == 0 ? pPath.move(to: pt) : pPath.addLine(to: pt)
                }
                ctx.stroke(pPath, with: .color(EasyPilotTheme.success), lineWidth: 1.5)
            }
        }
        .padding(6)
    }
}
