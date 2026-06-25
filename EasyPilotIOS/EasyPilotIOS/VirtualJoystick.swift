import SwiftUI

/// Circular virtual joystick pad.
///
/// - `centerX` / `centerY`: normalised [-1, 1] output after expo curve.
/// - `lockY`: when true, the Y axis is linear (no expo). The Y axis still
///   springs back to center on release — altitude-hold takes over the
///   throttle when the thumb is released.
/// - `expo`: 0 = linear, 1 = fully cubic. Applied to X always; to Y only
///   when `lockY == false`.
/// - `autopilotX/Y` + `autopilotEnabled`: when enabled and the user isn't
///   touching the pad, the thumb mirrors the autopilot's demand so the
///   pilot can see what the stabilizer is doing.
struct VirtualJoystick: View {
    let label: String
    let lockY: Bool
    let expo: Double

    @Binding var centerX: Double
    @Binding var centerY: Double
    var isTouching: Binding<Bool> = .constant(false)
    var autopilotEnabled: Bool = false
    var autopilotX: Double = 0
    var autopilotY: Double = 0
    /// When true, the thumb is tinted green to signal that the stabilizer
    /// (not the pilot) is in control of this axis pair.
    var stabilizationActive: Bool = false

    // Raw (pre-expo) thumb position
    @State private var rawX: Double = 0
    @State private var rawY: Double = 0

    private let padRadius: CGFloat = 72
    private let thumbRadius: CGFloat = 22

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .stroke(EasyPilotTheme.accent.opacity(0.25), lineWidth: 1.5)
                    .frame(width: padRadius * 2, height: padRadius * 2)

                Circle()
                    .fill(EasyPilotTheme.cardFill)
                    .frame(width: padRadius * 2, height: padRadius * 2)

                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(width: padRadius * 2, height: 1)
                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(width: 1, height: padRadius * 2)

                Circle()
                    .fill(stabilizationActive ? EasyPilotTheme.success : EasyPilotTheme.accent)
                    .frame(width: thumbRadius * 2, height: thumbRadius * 2)
                    .shadow(color: (stabilizationActive ? EasyPilotTheme.success : EasyPilotTheme.accent).opacity(0.5), radius: 8)
                    .animation(.easeInOut(duration: 0.2), value: stabilizationActive)
                    .offset(x: rawX * padRadius, y: rawY * padRadius)
                    .animation(.interactiveSpring(response: 0.15), value: rawX)
                    .animation(.interactiveSpring(response: 0.15), value: rawY)
            }
            .frame(width: padRadius * 2, height: padRadius * 2)
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0, coordinateSpace: .local)
                    .onChanged { value in
                        if !isTouching.wrappedValue { isTouching.wrappedValue = true }
                        let ox = value.location.x - padRadius
                        let oy = value.location.y - padRadius
                        let dist = sqrt(ox * ox + oy * oy)
                        let scale = dist > padRadius ? padRadius / dist : 1.0
                        rawX = Double(ox * scale / padRadius)
                        rawY = Double(oy * scale / padRadius)
                        centerX = applyExpo(rawX)
                        centerY = lockY ? rawY : applyExpo(rawY)
                    }
                    .onEnded { _ in
                        isTouching.wrappedValue = false
                        let targetX = autopilotEnabled ? autopilotX : 0
                        let targetY = autopilotEnabled ? autopilotY : 0
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                            rawX = targetX
                            rawY = targetY
                        }
                        centerX = 0
                        centerY = 0
                    }
            )
            .onChange(of: autopilotX) { v in
                if autopilotEnabled && !isTouching.wrappedValue {
                    withAnimation(.linear(duration: 0.12)) { rawX = v }
                }
            }
            .onChange(of: autopilotY) { v in
                if autopilotEnabled && !isTouching.wrappedValue {
                    withAnimation(.linear(duration: 0.12)) { rawY = v }
                }
            }
            .onChange(of: autopilotEnabled) { on in
                if !on && !isTouching.wrappedValue {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                        rawX = 0; rawY = 0
                    }
                }
            }

            Text(label)
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundColor(Color.white.opacity(0.35))
                .tracking(1.5)
        }
    }

    private func applyExpo(_ v: Double) -> Double {
        v * v * v * expo + v * (1 - expo)
    }
}
