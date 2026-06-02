import SwiftUI

/// Circular virtual joystick pad.
///
/// - `centerX` / `centerY`: normalised [-1, 1] output after expo curve.
/// - `lockY`: when true the Y axis does NOT spring back on release (throttle behaviour).
/// - `expo`: 0 = linear, 1 = fully cubic. Applied to all axes when expo > 0.
struct VirtualJoystick: View {
    let label: String
    let lockY: Bool
    let expo: Double

    @Binding var centerX: Double
    @Binding var centerY: Double
    @Binding var isActive: Bool

    // Raw (pre-expo) thumb position
    @State private var rawX: Double = 0
    @State private var rawY: Double = 0

    private let padRadius: CGFloat = 72
    private let thumbRadius: CGFloat = 22

    init(label: String,
         lockY: Bool,
         expo: Double,
         centerX: Binding<Double>,
         centerY: Binding<Double>,
         isActive: Binding<Bool> = .constant(false)) {
        self.label = label
        self.lockY = lockY
        self.expo = expo
        self._centerX = centerX
        self._centerY = centerY
        self._isActive = isActive
    }

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                // Outer ring
                Circle()
                    .stroke(EasyPilotTheme.accent.opacity(0.25), lineWidth: 1.5)
                    .frame(width: padRadius * 2, height: padRadius * 2)

                // Background
                Circle()
                    .fill(EasyPilotTheme.cardFill)
                    .frame(width: padRadius * 2, height: padRadius * 2)

                // Crosshair lines
                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(width: padRadius * 2, height: 1)
                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(width: 1, height: padRadius * 2)

                // Thumb
                Circle()
                    .fill(EasyPilotTheme.accent)
                    .frame(width: thumbRadius * 2, height: thumbRadius * 2)
                    .shadow(color: EasyPilotTheme.accent.opacity(0.5), radius: 8)
                    .offset(x: rawX * padRadius, y: rawY * padRadius)
                    .animation(.interactiveSpring(response: 0.15), value: rawX)
                    .animation(.interactiveSpring(response: 0.15), value: rawY)
            }
            .frame(width: padRadius * 2, height: padRadius * 2)
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0, coordinateSpace: .local)
                    .onChanged { value in
                        if !isActive { isActive = true }
                        let ox = value.location.x - padRadius
                        let oy = value.location.y - padRadius
                        let dist = sqrt(ox * ox + oy * oy)
                        let scale = dist > padRadius ? padRadius / dist : 1.0
                        rawX = Double(ox * scale / padRadius)
                        rawY = Double(oy * scale / padRadius)
                        centerX = applyExpo(rawX)
                        centerY = lockY ? rawY : applyExpo(rawY)  // no expo on throttle
                    }
                    .onEnded { _ in
                        isActive = false
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                            rawX = 0
                        }
                        if !lockY {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                                rawY = 0
                            }
                        }
                        centerX = 0
                        if !lockY { centerY = applyExpo(rawY) }
                    }
            )

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
