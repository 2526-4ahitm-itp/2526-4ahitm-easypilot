import SwiftUI

struct ControlView: View {
    @ObservedObject var wsManager: WebSocketManager
    @StateObject private var profileManager  = ProfileManager()
    @StateObject private var motionManager   = MotionManager()   // own instance for sound mode

    @State private var values        = ControlProfile(name: "")
    @State private var selectedMode  = "IDLE"

    // Sound mode
    @State private var soundModeActive = false
    @State private var maxSoundPWM: Double = 1400
    @State private var soundTimer: Timer?

    // Arm hold-to-arm
    @State private var armHoldProgress: CGFloat = 0.0
    @State private var armHoldTimer: Timer?

    // Profile UI
    @State private var selectedProfileID: UUID? = nil
    @State private var showSaveSheet   = false
    @State private var showDeleteAlert = false
    @State private var newProfileName  = ""
    @State private var didSend         = false

    private var isArmed:   Bool   { wsManager.telemetry?.armed ?? false }
    private var droneMode: String { wsManager.telemetry?.mode  ?? "IDLE" }

    // MARK: - Computed (Sound Mode)

    private var currentTiltAngle: Double {
        min(sqrt(pow(motionManager.pitch, 2) + pow(motionManager.roll, 2)), 90)
    }
    private var currentSoundPWM: Int {
        1000 + Int((min(currentTiltAngle, 45.0) / 45.0) * (maxSoundPWM - 1000))
    }

    // MARK: - Body

    var body: some View {
        ZStack {
            EasyPilotTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                headerView
                    .padding(.horizontal).padding(.top, 16).padding(.bottom, 12)

                profileBar
                    .padding(.horizontal).padding(.bottom, 12)

                Divider().background(Color.white.opacity(0.08))

                ScrollView {
                    VStack(spacing: 16) {
                        droneStatusCard
                        armSection
                        if isArmed { modeSection }
                        if isArmed && selectedMode != "IDLE" { modeConfigSection }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 16)
                }

                Divider().background(Color.white.opacity(0.08))

                if isArmed && selectedMode != "IDLE" {
                    bottomBar.padding()
                }
            }
        }
        .sheet(isPresented: $showSaveSheet) { saveSheet }
        .alert("Delete Profile", isPresented: $showDeleteAlert) {
            Button("Delete", role: .destructive) {
                if let id = selectedProfileID,
                   let p  = profileManager.profiles.first(where: { $0.id == id }) {
                    profileManager.delete(p); selectedProfileID = nil
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: { Text("This cannot be undone.") }
        .onChange(of: selectedProfileID) { id in
            if let id, let p = profileManager.profiles.first(where: { $0.id == id }) {
                values = p; selectedMode = p.mode
            }
        }
        .onChange(of: droneMode) { mode in selectedMode = mode }
        .onDisappear {
            // Stop streaming if user switches tab
            if soundModeActive { stopSoundMode() }
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Control")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
                Text(isArmed ? "Drone is armed" : "Drone is disarmed")
                    .font(.system(size: 12))
                    .foregroundColor(isArmed ? EasyPilotTheme.danger : .gray)
            }
            Spacer()
            HStack(spacing: 6) {
                PulsingDot(color: wsManager.isConnected ? EasyPilotTheme.success : EasyPilotTheme.danger)
                Text(wsManager.isConnected ? "LIVE" : "OFFLINE")
                    .font(.system(size: 11, weight: .black, design: .monospaced))
                    .foregroundColor(wsManager.isConnected ? EasyPilotTheme.success : EasyPilotTheme.danger)
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
            .glassCard(cornerRadius: 12)
        }
    }

    // MARK: - Drone Status Card

    private var droneStatusCard: some View {
        HStack(spacing: 0) {
            statusPill("STATE",
                       value: isArmed ? "ARMED" : "DISARMED",
                       color: isArmed ? EasyPilotTheme.danger : .gray)
            Divider().frame(height: 36).background(Color.white.opacity(0.1))
            statusPill("MODE", value: droneMode, color: modeColor(droneMode))
            Divider().frame(height: 36).background(Color.white.opacity(0.1))
            statusPill("CONN",
                       value: wsManager.isConnected ? "OK" : "—",
                       color: wsManager.isConnected ? EasyPilotTheme.success : .gray)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .glassCard()
    }

    private func statusPill(_ label: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 13, weight: .black, design: .monospaced))
                .foregroundColor(color)
            Text(label)
                .font(.system(size: 9, weight: .bold))
                .foregroundColor(.gray).tracking(1.5)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Arm Section

    private var armSection: some View {
        VStack(spacing: 10) {
            if !isArmed {
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 16).fill(Color.white.opacity(0.06))
                    GeometryReader { geo in
                        RoundedRectangle(cornerRadius: 16)
                            .fill(EasyPilotTheme.danger.opacity(0.35))
                            .frame(width: geo.size.width * armHoldProgress)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    HStack {
                        Spacer()
                        HStack(spacing: 10) {
                            Image(systemName: "lock.fill")
                            Text(armHoldProgress > 0 ? "HOLD TO ARM…" : "HOLD TO ARM")
                                .font(.system(size: 15, weight: .black))
                        }
                        .foregroundColor(.gray)
                        Spacer()
                    }
                }
                .frame(height: 58)
                .gesture(DragGesture(minimumDistance: 0)
                    .onChanged { _ in startArmHold() }
                    .onEnded   { _ in cancelArmHold() }
                )
                Text("Hold for 1.5 s to arm")
                    .font(.system(size: 11)).foregroundColor(.gray)
            } else {
                Button {
                    if soundModeActive { stopSoundMode() }
                    wsManager.sendCommand(#"{"cmd":"DISARM"}"#)
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "lock.open.fill")
                        Text("DISARM")
                            .font(.system(size: 15, weight: .black))
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity).padding(.vertical, 16)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(EasyPilotTheme.danger)
                            .shadow(color: EasyPilotTheme.danger.opacity(0.5), radius: 12, y: 4)
                    )
                }
                .disabled(!wsManager.isConnected)
            }
        }
    }

    // MARK: - Mode Selector (2×2 grid for 4 modes)

    private var modeSection: some View {
        VStack(spacing: 10) {
            SectionHeader("FLIGHT MODE")
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(["IDLE", "BALANCE", "MANUAL", "SOUND"], id: \.self) { mode in
                    Button {
                        if soundModeActive && mode != "SOUND" { stopSoundMode() }
                        selectedMode = mode
                        values.mode  = mode
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: modeIcon(mode))
                                .font(.system(size: 11, weight: .bold))
                            Text(mode)
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                        }
                        .foregroundColor(selectedMode == mode ? .black : .white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 10)
                                .fill(selectedMode == mode
                                      ? modeColor(mode)
                                      : Color.white.opacity(0.07))
                        )
                    }
                }
            }
        }
        .padding()
        .glassCard()
    }

    // MARK: - Mode Config

    @ViewBuilder
    private var modeConfigSection: some View {
        switch selectedMode {
        case "BALANCE": balanceConfig
        case "MANUAL":  manualConfig
        case "SOUND":   soundConfig
        default:        EmptyView()
        }
    }

    private var balanceConfig: some View {
        VStack(spacing: 14) {
            SectionHeader("BALANCE CONFIG")
            LabeledSlider(label: "Base Throttle", unit: "PWM",
                          value: $values.baseThrottle, range: 1000...1600, step: 10)
            LabeledSlider(label: "kP Roll",  unit: "",
                          value: $values.kPRoll,  range: 0...50, step: 0.5, format: "%.1f")
            LabeledSlider(label: "kP Pitch", unit: "",
                          value: $values.kPPitch, range: 0...50, step: 0.5, format: "%.1f")
        }
        .padding()
        .glassCard()
    }

    private var manualConfig: some View {
        VStack(spacing: 16) {
            VStack(spacing: 14) {
                SectionHeader("MOTORS")
                LabeledSlider(label: "M1", unit: "PWM", value: $values.m1, range: 1000...2000, step: 1)
                LabeledSlider(label: "M2", unit: "PWM", value: $values.m2, range: 1000...2000, step: 1)
                LabeledSlider(label: "M3", unit: "PWM", value: $values.m3, range: 1000...2000, step: 1)
                LabeledSlider(label: "M4", unit: "PWM", value: $values.m4, range: 1000...2000, step: 1)
            }
            .padding()
            .glassCard()

            VStack(spacing: 14) {
                SectionHeader("ATTITUDE")
                LabeledSlider(label: "Roll",  unit: "°", value: $values.roll,
                              range: -90...90,   step: 0.5, format: "%.1f")
                LabeledSlider(label: "Pitch", unit: "°", value: $values.pitch,
                              range: -90...90,   step: 0.5, format: "%.1f")
                LabeledSlider(label: "Yaw",   unit: "°", value: $values.yaw,
                              range: -180...180, step: 0.5, format: "%.1f")
            }
            .padding()
            .glassCard()
        }
    }

    private var soundConfig: some View {
        VStack(spacing: 16) {
            // Live tilt + PWM readout
            VStack(spacing: 14) {
                SectionHeader("LIVE TILT")

                HorizonIndicator(pitch: motionManager.pitch, roll: motionManager.roll)
                    .frame(width: 110, height: 110)

                HStack(spacing: 32) {
                    VStack(spacing: 4) {
                        Text(String(format: "%.1f°", currentTiltAngle))
                            .font(.system(size: 26, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                        Text("TILT ANGLE")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.gray).tracking(1.5)
                    }
                    VStack(spacing: 4) {
                        Text("\(currentSoundPWM)")
                            .font(.system(size: 26, weight: .bold, design: .monospaced))
                            .foregroundColor(soundModeActive ? soundColor : .gray)
                            .animation(.easeInOut(duration: 0.1), value: currentSoundPWM)
                        Text("MOTOR PWM")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.gray).tracking(1.5)
                    }
                }
            }
            .padding()
            .glassCard()

            // Config
            VStack(spacing: 14) {
                SectionHeader("SOUND CONFIG")
                LabeledSlider(label: "Max PWM (safety cap)", unit: "PWM",
                              value: $maxSoundPWM, range: 1050...1500, step: 10)
                HStack(spacing: 8) {
                    Image(systemName: "info.circle")
                        .font(.system(size: 12))
                        .foregroundColor(.gray)
                    Text("Level = 1000 (silent) · 45° tilt = max PWM · >60° = emergency stop")
                        .font(.system(size: 11))
                        .foregroundColor(.gray)
                }
            }
            .padding()
            .glassCard()
        }
    }

    // MARK: - Bottom Bar

    private var bottomBar: some View {
        HStack(spacing: 12) {
            if droneMode != "IDLE" {
                Button {
                    if soundModeActive { stopSoundMode() }
                    wsManager.sendCommand(#"{"cmd":"STOP"}"#)
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "stop.fill")
                        Text("STOP").font(.system(size: 14, weight: .black))
                    }
                    .foregroundColor(.white).frame(width: 90).padding(.vertical, 16)
                    .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.1)))
                }
            }

            if selectedMode == "SOUND" {
                soundToggleButton
            } else {
                standardStartButton
            }
        }
    }

    private var soundToggleButton: some View {
        Button {
            soundModeActive ? stopSoundMode() : startSoundMode()
        } label: {
            HStack(spacing: 8) {
                if soundModeActive {
                    PulsingDot(color: .white)
                    Text("STREAMING")
                        .font(.system(size: 14, weight: .black))
                } else {
                    Image(systemName: "waveform")
                    Text("START SOUND")
                        .font(.system(size: 14, weight: .black))
                }
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity).padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(soundModeActive ? soundColor : (wsManager.isConnected ? soundColor.opacity(0.6) : Color.gray.opacity(0.4)))
                    .shadow(color: soundColor.opacity(soundModeActive ? 0.6 : 0.2), radius: 10, y: 4)
            )
        }
        .disabled(!wsManager.isConnected)
        .animation(.easeInOut(duration: 0.2), value: soundModeActive)
    }

    private var standardStartButton: some View {
        Button { sendModeCommand() } label: {
            HStack(spacing: 8) {
                Image(systemName: didSend ? "checkmark.circle.fill"
                      : (droneMode == selectedMode ? "arrow.clockwise" : "play.fill"))
                Text(didSend ? "SENT"
                     : (droneMode == selectedMode && droneMode != "IDLE" ? "UPDATE" : "START \(selectedMode)"))
                    .font(.system(size: 14, weight: .black))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity).padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(didSend ? EasyPilotTheme.success
                          : (wsManager.isConnected ? modeColor(selectedMode) : Color.gray.opacity(0.4)))
                    .shadow(color: modeColor(selectedMode).opacity(0.4), radius: 10, y: 4)
            )
        }
        .disabled(!wsManager.isConnected)
        .animation(.easeInOut(duration: 0.2), value: didSend)
    }

    // MARK: - Profile Bar

    private var profileBar: some View {
        HStack(spacing: 10) {
            Menu {
                Button("No profile") { selectedProfileID = nil }
                Divider()
                ForEach(profileManager.profiles) { p in
                    Button(p.name) { selectedProfileID = p.id }
                }
            } label: {
                HStack {
                    Image(systemName: "tray.full").font(.system(size: 13))
                    Text(selectedProfileID.flatMap { id in
                        profileManager.profiles.first { $0.id == id }?.name
                    } ?? "Select Profile")
                    .font(.system(size: 13, weight: .semibold))
                    Image(systemName: "chevron.down").font(.system(size: 10, weight: .bold))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .glassCard(cornerRadius: 12)
            }
            Spacer()
            Button {
                newProfileName = selectedProfileID.flatMap { id in
                    profileManager.profiles.first { $0.id == id }?.name
                } ?? ""
                showSaveSheet = true
            } label: {
                Image(systemName: "square.and.arrow.down")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(EasyPilotTheme.accent)
                    .frame(width: 38, height: 38).glassCard(cornerRadius: 12)
            }
            Button {
                if selectedProfileID != nil { showDeleteAlert = true }
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(selectedProfileID != nil ? EasyPilotTheme.danger : .gray)
                    .frame(width: 38, height: 38).glassCard(cornerRadius: 12)
            }
            .disabled(selectedProfileID == nil)
        }
    }

    // MARK: - Save Sheet

    private var saveSheet: some View {
        NavigationStack {
            Form {
                Section("Profile Name") {
                    TextField("e.g. Balance Test", text: $newProfileName)
                }
            }
            .navigationTitle("Save Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { showSaveSheet = false } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let name = newProfileName.trimmingCharacters(in: .whitespaces)
                        guard !name.isEmpty else { return }
                        var p = values; p.id = selectedProfileID ?? UUID()
                        p.name = name; p.mode = selectedMode
                        profileManager.save(p); selectedProfileID = p.id
                        showSaveSheet = false
                    }
                }
            }
        }
        .presentationDetents([.height(200)])
    }

    // MARK: - Sound Mode Logic

    private func startSoundMode() {
        let cmd = "{\"cmd\":\"START_SOUND\",\"maxPWM\":\(Int(maxSoundPWM))}"
        wsManager.sendCommand(cmd)
        motionManager.startUpdates()
        soundModeActive = true

        soundTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
            // Emergency stop if phone is tilted past 60°
            if self.currentTiltAngle > 60 {
                self.stopSoundMode()
                return
            }
            let cmd = "{\"cmd\":\"TILT_SOUND\",\"pwm\":\(self.currentSoundPWM)}"
            self.wsManager.sendCommand(cmd)
        }
    }

    private func stopSoundMode() {
        soundTimer?.invalidate(); soundTimer = nil
        soundModeActive = false
        motionManager.stopUpdates()
        wsManager.sendCommand(#"{"cmd":"STOP"}"#)
    }

    // MARK: - Arm Hold Logic

    private func startArmHold() {
        guard armHoldTimer == nil else { return }
        armHoldProgress = 0
        let start = Date()
        armHoldTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { timer in
            let elapsed = Date().timeIntervalSince(start)
            self.armHoldProgress = CGFloat(min(elapsed / 1.5, 1.0))
            if elapsed >= 1.5 {
                timer.invalidate(); self.armHoldTimer = nil
                self.armHoldProgress = 0
                self.wsManager.sendCommand(#"{"cmd":"ARM"}"#)
            }
        }
    }

    private func cancelArmHold() {
        armHoldTimer?.invalidate(); armHoldTimer = nil
        withAnimation(.easeOut(duration: 0.2)) { armHoldProgress = 0 }
    }

    // MARK: - Helpers

    private func sendModeCommand() {
        switch selectedMode {
        case "BALANCE": wsManager.sendCommand(values.startBalanceCommand())
        case "MANUAL":  wsManager.sendCommand(values.startManualCommand())
        default: break
        }
        flash()
    }

    private func flash() {
        withAnimation(.spring(response: 0.3)) { didSend = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
            withAnimation { didSend = false }
        }
    }

    private var soundColor: Color { Color(red: 0.65, green: 0.25, blue: 1.0) }

    private func modeColor(_ mode: String) -> Color {
        switch mode {
        case "BALANCE": return EasyPilotTheme.accent
        case "MANUAL":  return EasyPilotTheme.warning
        case "SOUND":   return soundColor
        default:        return .gray
        }
    }

    private func modeIcon(_ mode: String) -> String {
        switch mode {
        case "BALANCE": return "gyroscope"
        case "MANUAL":  return "slider.horizontal.3"
        case "SOUND":   return "waveform"
        default:        return "stop.circle"
        }
    }
}
