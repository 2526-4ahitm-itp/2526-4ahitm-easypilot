import SwiftUI

struct SimulatorView: View {

    @StateObject private var sim            = DroneSimulator()
    @StateObject private var profileManager = ProfileManager()

    @State private var leftX:  Double = 0
    @State private var leftY:  Double = 0
    @State private var rightX: Double = 0
    @State private var rightY: Double = 0

    // General settings
    @State private var expo: Double = 0.35
    @State private var activeCamera: SimCamera = .chase
    @State private var showExpoSlider   = false
    @State private var showLiveHint     = false
    @State private var showThrottleHint = false

    // Flight mode + balance config
    @State private var flightMode:       SimFlightMode = .rate
    @State private var kPRoll:           Double = 10.0
    @State private var kPPitch:          Double = 10.0
    @State private var maxBalanceAngle:  Double = 30.0
    @State private var showBalanceCfg    = false
    @State private var showProfilePicker = false

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

                HStack {
                    miniHorizon
                        .padding(.leading, 14)
                        .padding(.top, 6)
                    Spacer()
                }

                Spacer()
            }

            // Bottom panel — one cohesive frosted slab
            bottomPanel
        }
        .onChange(of: leftX)  { _ in pushInputs() }
        .onChange(of: leftY)  { _ in pushInputs() }
        .onChange(of: rightX) { _ in pushInputs() }
        .onChange(of: rightY) { _ in pushInputs() }
        .onChange(of: expo)   { v in sim.expo = v }
        .onChange(of: flightMode)      { v in sim.flightMode = v }
        .onChange(of: kPRoll)          { v in sim.kPRoll = v }
        .onChange(of: kPPitch)         { v in sim.kPPitch = v }
        .onChange(of: maxBalanceAngle) { v in sim.maxBalanceAngle = v }
        .onDisappear { sim.disarm() }
        .overlay(alignment: .top) {
            if showLiveHint {
                toast("Live control — Sprint 5", .warning).padding(.top, 80)
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
                modeSegment("SIM", active: true)
                modeSegment("LIVE", active: false, onTap: { flash($showLiveHint) })
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

    // MARK: - Bottom panel

    private var bottomPanel: some View {
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

            // ── Expo slider (RATE mode) ────────────────────────────────────
            if showExpoSlider {
                HStack(spacing: 10) {
                    Text("LINEAR")
                        .font(.system(size: 8, design: .monospaced))
                        .foregroundColor(.white.opacity(0.3))
                    Slider(value: $expo, in: 0...0.9).tint(EasyPilotTheme.accent)
                    Text("EXPO \(Int(expo * 100))%")
                        .font(.system(size: 8, weight: .bold, design: .monospaced))
                        .foregroundColor(EasyPilotTheme.accent)
                }
                .padding(.horizontal, 16).padding(.vertical, 8)
                .background(Color.white.opacity(0.04))
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            // ── Balance config (BALANCE mode) ─────────────────────────────
            if showBalanceCfg {
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

            separator

            // ── Joysticks + arm ────────────────────────────────────────────
            HStack(alignment: .center, spacing: 0) {
                VirtualJoystick(label: "THR / YAW",
                                lockY: true, expo: expo,
                                centerX: $leftX, centerY: $leftY)
                    .padding(.leading, 16)

                Spacer()
                armButton
                Spacer()

                VirtualJoystick(label: "PCH / ROL",
                                lockY: false, expo: expo,
                                centerX: $rightX, centerY: $rightY)
                    .padding(.trailing, 16)
            }
            .padding(.top, 10).padding(.bottom, 16)
        }
        .background(.ultraThinMaterial)
    }

    // MARK: - Arm button

    private var armButton: some View {
        Button {
            if sim.isArmed {
                sim.disarm(); leftY = 0; pushInputs()
            } else if max(0, -leftY) > 0.05 {
                flash($showThrottleHint)
            } else {
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

    private func pushInputs() {
        sim.yaw      =  leftX
        sim.throttle =  max(0, -leftY)
        sim.pitch    = -rightY
        sim.roll     =  rightX
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
