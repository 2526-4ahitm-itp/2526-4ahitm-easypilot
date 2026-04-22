import SwiftUI

// MARK: - Theme

enum EasyPilotTheme {
    static let background  = Color(red: 0.04, green: 0.06, blue: 0.12)
    static let cardFill    = Color(red: 0.08, green: 0.11, blue: 0.20)
    static let accent      = Color(red: 0.16, green: 0.47, blue: 1.00)  // #2979FF
    static let success     = Color(red: 0.20, green: 0.85, blue: 0.50)
    static let warning     = Color(red: 1.00, green: 0.60, blue: 0.00)
    static let danger      = Color(red: 1.00, green: 0.27, blue: 0.27)
}

// MARK: - Glass Card

struct GlassCard: ViewModifier {
    var cornerRadius: CGFloat = 20
    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .fill(EasyPilotTheme.cardFill)
                    .overlay(
                        RoundedRectangle(cornerRadius: cornerRadius)
                            .stroke(
                                LinearGradient(
                                    colors: [EasyPilotTheme.accent.opacity(0.35),
                                             Color.white.opacity(0.04)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ),
                                lineWidth: 1
                            )
                    )
            )
    }
}

extension View {
    func glassCard(cornerRadius: CGFloat = 20) -> some View {
        modifier(GlassCard(cornerRadius: cornerRadius))
    }
}

// MARK: - Section Header

struct SectionHeader: View {
    let title: String
    init(_ title: String) { self.title = title }
    var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 11, weight: .black, design: .monospaced))
                .foregroundColor(EasyPilotTheme.accent.opacity(0.8))
                .tracking(2)
            Rectangle()
                .fill(EasyPilotTheme.accent.opacity(0.2))
                .frame(height: 1)
        }
    }
}

// MARK: - Pulsing Dot

struct PulsingDot: View {
    let color: Color
    @State private var pulsing = false

    var body: some View {
        ZStack {
            Circle()
                .fill(color.opacity(0.25))
                .frame(width: 18, height: 18)
                .scaleEffect(pulsing ? 1.6 : 1.0)
                .opacity(pulsing ? 0 : 1)
                .animation(.easeOut(duration: 1.4).repeatForever(autoreverses: false),
                           value: pulsing)
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
        }
        .onAppear { pulsing = true }
    }
}

// MARK: - Horizon Attitude Indicator

struct HorizonIndicator: View {
    let pitch: Double
    let roll: Double

    var body: some View {
        ZStack {
            // Sky
            Circle()
                .fill(Color(red: 0.08, green: 0.22, blue: 0.50))

            // Ground — clips to circle, tilts with roll, offsets with pitch
            GeometryReader { geo in
                let h = geo.size.height
                let pitchOffset = CGFloat(pitch / 90.0) * h * 0.45
                Rectangle()
                    .fill(Color(red: 0.28, green: 0.18, blue: 0.08))
                    .frame(width: geo.size.width * 3, height: h)
                    .offset(x: -geo.size.width, y: h * 0.5 + pitchOffset)
                    .rotationEffect(.degrees(-roll),
                                    anchor: UnitPoint(x: 0.5,
                                                      y: (h * 0.5 + pitchOffset) / h))
            }
            .clipShape(Circle())

            // Horizon line (rotates with roll, shifts with pitch)
            Rectangle()
                .fill(Color.white.opacity(0.9))
                .frame(height: 1.5)
                .padding(.horizontal, 6)
                .offset(y: CGFloat(pitch / 90.0) * 36)
                .rotationEffect(.degrees(-roll))

            // Fixed aircraft reference (yellow crosshair)
            HStack(spacing: 10) {
                Rectangle().fill(Color.yellow).frame(width: 16, height: 2)
                Rectangle().fill(Color.yellow).frame(width: 16, height: 2)
            }
            Circle().fill(Color.yellow).frame(width: 4, height: 4)

            // Border
            Circle().stroke(Color.white.opacity(0.25), lineWidth: 1.5)
        }
        .frame(width: 80, height: 80)
        .clipShape(Circle())
    }
}

// MARK: - Telemetry Card

struct TelemetryCard: View {
    let title: String
    let value: String
    let icon: String
    var color: Color = EasyPilotTheme.accent

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: icon)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(color)
                Spacer()
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.system(size: 22, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                    .minimumScaleFactor(0.7)
                    .lineLimit(1)
                Text(title)
                    .font(.system(size: 9, weight: .black))
                    .foregroundColor(.gray)
                    .tracking(1.5)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(cornerRadius: 16)
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 3)
                .fill(color)
                .frame(width: 3)
                .padding(.vertical, 10)
                .padding(.leading, 0)
                .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }
}

// MARK: - Motor Bar

struct MotorBar: View {
    let label: String
    let value: Int

    private let minPWM = 1000
    private let maxPWM = 2000

    private var barColor: Color {
        let t = Double(max(minPWM, min(maxPWM, value)) - minPWM) / Double(maxPWM - minPWM)
        if t < 0.30 { return EasyPilotTheme.success }
        if t < 0.65 { return EasyPilotTheme.warning }
        return EasyPilotTheme.danger
    }

    private var percentage: CGFloat {
        CGFloat(max(0, min(1, Double(value - minPWM) / Double(maxPWM - minPWM))))
    }

    var body: some View {
        VStack(spacing: 6) {
            GeometryReader { geo in
                ZStack(alignment: .bottom) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.06))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(LinearGradient(
                            colors: [barColor.opacity(0.5), barColor],
                            startPoint: .bottom, endPoint: .top
                        ))
                        .frame(height: geo.size.height * percentage)
                        .animation(.easeOut(duration: 0.15), value: value)
                }
            }
            .frame(width: 14, height: 80)

            Text(label)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.gray)
            Text("\(value)")
                .font(.system(size: 8, design: .monospaced))
                .foregroundColor(.white.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Labeled Slider (used in ControlView)

struct LabeledSlider: View {
    let label: String
    let unit: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    var format: String = "%.0f"

    var body: some View {
        VStack(spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(label)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.white)
                Spacer()
                Text(String(format: format, value))
                    .font(.system(size: 15, weight: .bold, design: .monospaced))
                    .foregroundColor(EasyPilotTheme.accent)
                + Text(" \(unit)")
                    .font(.system(size: 11))
                    .foregroundColor(.gray)
            }
            Slider(value: $value, in: range, step: step)
                .tint(EasyPilotTheme.accent)
        }
        .padding(.vertical, 4)
    }
}
