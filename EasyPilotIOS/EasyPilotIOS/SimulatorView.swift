import SwiftUI

struct SimulatorView: View {

    // MARK: - State

    @StateObject private var sim = DroneSimulator()

    // Joystick raw inputs (expo-applied, written into sim each frame)
    @State private var leftX:  Double = 0   // yaw
    @State private var leftY:  Double = 0   // throttle (non-centering, inverted: up = 1)
    @State private var rightX: Double = 0   // roll
    @State private var rightY: Double = 0   // pitch

    @State private var expo: Double = 0.35
    @State private var showExpoSlider = false
    @State private var showLiveHint   = false
    @State private var liveToggle     = false   // always snaps back

    // MARK: - Body

    var body: some View {
        ZStack {
            EasyPilotTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                header
                    .padding(.horizontal)
                    .padding(.top, 16)
                    .padding(.bottom, 12)

                Divider().background(Color.white.opacity(0.08))

                telemetryStrip
                    .padding(.horizontal)
                    .padding(.vertical, 14)

                Divider().background(Color.white.opacity(0.08))

                Spacer()

                joystickArea

                Spacer()

                armBar
                    .padding(.horizontal)
                    .padding(.bottom, 24)
            }
        }
        .onChange(of: leftX)  { _ in pushInputs() }
        .onChange(of: leftY)  { _ in pushInputs() }
        .onChange(of: rightX) { _ in pushInputs() }
        .onChange(of: rightY) { _ in pushInputs() }
        .onChange(of: expo)   { v in sim.expo = v }
        .onChange(of: liveToggle) { on in
            if on {
                liveToggle = false
                withAnimation { showLiveHint = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                    withAnimation { showLiveHint = false }
                }
            }
        }
        .onDisappear { sim.disarm() }
        .overlay(alignment: .top) {
            if showLiveHint {
                Text("Live control available in Sprint 5")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(EasyPilotTheme.warning)
                    .padding(.horizontal, 16).padding(.vertical, 8)
                    .background(EasyPilotTheme.cardFill)
                    .cornerRadius(10)
                    .padding(.top, 60)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 3) {
                Text("Simulator")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
                Text(sim.isArmed ? "ARMED · RATE MODE" : "DISARMED")
                    .font(.system(size: 11, weight: .black, design: .monospaced))
                    .foregroundColor(sim.isArmed ? EasyPilotTheme.danger : Color.white.opacity(0.35))
                    .tracking(2)
            }
            Spacer()
            modePill
        }
    }

    private var modePill: some View {
        HStack(spacing: 0) {
            pillSegment(label: "SIM", active: true)
            pillSegment(label: "LIVE", active: false, disabled: true)
        }
        .background(EasyPilotTheme.cardFill)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10)
                    .stroke(EasyPilotTheme.accent.opacity(0.2), lineWidth: 1))
    }

    private func pillSegment(label: String, active: Bool, disabled: Bool = false) -> some View {
        Text(label)
            .font(.system(size: 11, weight: .black, design: .monospaced))
            .tracking(1.5)
            .foregroundColor(active ? .black : (disabled ? Color.white.opacity(0.2) : .white))
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(active ? EasyPilotTheme.accent : Color.clear)
            .cornerRadius(8)
            .onTapGesture { if disabled { liveToggle = true } }
    }

    // MARK: - Telemetry strip

    private var telemetryStrip: some View {
        VStack(spacing: 12) {
            HStack(spacing: 16) {
                HorizonIndicator(pitch: sim.simPitch, roll: sim.simRoll)
                    .frame(width: 90, height: 90)
                    .clipShape(Circle())

                VStack(spacing: 6) {
                    attitudeRow(label: "ROLL",  value: sim.simRoll)
                    attitudeRow(label: "PITCH", value: sim.simPitch)
                    attitudeRow(label: "YAW",   value: sim.simYaw)
                }

                Spacer()

                throttleIndicator
            }

            motorBarsRow
        }
        .padding(14)
        .glassCard()
    }

    private func attitudeRow(label: String, value: Double) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(size: 9, weight: .black, design: .monospaced))
                .foregroundColor(EasyPilotTheme.accent.opacity(0.7))
                .frame(width: 36, alignment: .leading)
                .tracking(1)
            Text(String(format: "%+.1f°", value))
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(.white)
        }
    }

    private var throttleIndicator: some View {
        VStack(spacing: 4) {
            Text("THR")
                .font(.system(size: 9, weight: .black, design: .monospaced))
                .foregroundColor(EasyPilotTheme.accent.opacity(0.7))
                .tracking(1)
            GeometryReader { geo in
                ZStack(alignment: .bottom) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.08))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(throttleColor)
                        .frame(height: geo.size.height * CGFloat(max(0, -leftY)))
                }
            }
            .frame(width: 16, height: 60)
            Text(String(format: "%d%%", Int(max(0, -leftY) * 100)))
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundColor(.white.opacity(0.5))
        }
    }

    private var throttleColor: Color {
        let t = max(0, -leftY)
        if t < 0.4 { return EasyPilotTheme.success }
        if t < 0.75 { return EasyPilotTheme.warning }
        return EasyPilotTheme.danger
    }

    private var motorBarsRow: some View {
        HStack(spacing: 10) {
            ForEach(Array([("M1", sim.m1), ("M2", sim.m2), ("M3", sim.m3), ("M4", sim.m4)].enumerated()), id: \.offset) { _, pair in
                motorBar(label: pair.0, pwm: pair.1)
            }
        }
    }

    private func motorBar(label: String, pwm: Int) -> some View {
        let fraction = CGFloat(pwm - 1000) / 1000.0
        return VStack(spacing: 4) {
            GeometryReader { geo in
                ZStack(alignment: .bottom) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.08))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(EasyPilotTheme.accent.opacity(0.8))
                        .frame(height: geo.size.height * fraction)
                }
            }
            .frame(height: 40)
            Text(label)
                .font(.system(size: 9, weight: .black, design: .monospaced))
                .foregroundColor(Color.white.opacity(0.4))
            Text("\(pwm)")
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundColor(.white.opacity(0.6))
        }
    }

    // MARK: - Joystick area

    private var joystickArea: some View {
        VStack(spacing: 16) {
            // Expo row
            HStack(spacing: 10) {
                Button {
                    withAnimation { showExpoSlider.toggle() }
                } label: {
                    Label("EXPO \(Int(expo * 100))%",
                          systemImage: "slider.horizontal.below.square.filled.and.square")
                        .font(.system(size: 11, weight: .black, design: .monospaced))
                        .foregroundColor(EasyPilotTheme.accent.opacity(0.8))
                        .tracking(1)
                }
                if showExpoSlider {
                    Slider(value: $expo, in: 0...0.9)
                        .tint(EasyPilotTheme.accent)
                        .frame(maxWidth: 160)
                }
            }

            // Sticks
            HStack {
                // Left stick: Throttle (Y, lock) + Yaw (X)
                VStack(spacing: 6) {
                    VirtualJoystick(label: "THROTTLE / YAW",
                                    lockY: true,
                                    expo: expo,
                                    centerX: $leftX,
                                    centerY: $leftY)
                    stickReadout(x: leftX, y: leftY, xLabel: "YAW", yLabel: "THR")
                }

                Spacer()

                // Right stick: Pitch (Y) + Roll (X)
                VStack(spacing: 6) {
                    VirtualJoystick(label: "PITCH / ROLL",
                                    lockY: false,
                                    expo: expo,
                                    centerX: $rightX,
                                    centerY: $rightY)
                    stickReadout(x: rightX, y: rightY, xLabel: "ROL", yLabel: "PCH")
                }
            }
            .padding(.horizontal, 32)

            Text("MODE 2 · RATE")
                .font(.system(size: 9, weight: .black, design: .monospaced))
                .foregroundColor(Color.white.opacity(0.2))
                .tracking(2)
        }
    }

    private func stickReadout(x: Double, y: Double, xLabel: String, yLabel: String) -> some View {
        HStack(spacing: 12) {
            Text("\(xLabel) \(String(format: "%+.2f", x))")
            Text("\(yLabel) \(String(format: "%+.2f", y))")
        }
        .font(.system(size: 9, weight: .semibold, design: .monospaced))
        .foregroundColor(Color.white.opacity(0.25))
    }

    // MARK: - Arm bar

    private var armBar: some View {
        HStack {
            if sim.isArmed {
                Button {
                    sim.disarm()
                    leftY = 0  // reset throttle display
                } label: {
                    Label("Disarm Simulator", systemImage: "stop.fill")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(EasyPilotTheme.danger)
                        .cornerRadius(14)
                }
            } else {
                Button { sim.arm() } label: {
                    Label("Arm Simulator", systemImage: "play.fill")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(EasyPilotTheme.success)
                        .cornerRadius(14)
                }
            }
        }
    }

    // MARK: - Input sync

    private func pushInputs() {
        sim.yaw      =  leftX
        sim.throttle =  max(0, -leftY)   // stick up (negative Y) = throttle up
        sim.pitch    = -rightY            // stick up = nose up (DroneSimulator negates internally)
        sim.roll     =  rightX
    }
}
