import Foundation

/// Every command the iOS app can send to the ESP32, in one place.
///
/// Centralising the wire format here keeps the exact JSON (and the plain-text
/// `SAFE_TEST`) out of the views, so command strings aren't hand-built — and
/// typo'd — across the UI. The raw payloads match what `main.cpp` parses.
enum DroneCommand {
    case arm
    case disarm
    case stop
    case startBalance(baseThrottle: Int, kPRoll: Double, kPPitch: Double)
    case startManual(roll: Double, pitch: Double, yaw: Double,
                     m1: Int, m2: Int, m3: Int, m4: Int,
                     voltage: Double, batteryPercentage: Int)
    /// Re-sends manual values mid-flight (no `"cmd"` wrapper — matches firmware).
    case updateManual(roll: Double, pitch: Double, yaw: Double,
                      m1: Int, m2: Int, m3: Int, m4: Int,
                      voltage: Double, batteryPercentage: Int)
    case startSound(maxPWM: Int)
    case tiltSound(pwm: Int)
    case safeTest

    /// The exact text payload sent over the WebSocket.
    var payload: String {
        switch self {
        case .arm:    return #"{"cmd":"ARM"}"#
        case .disarm: return #"{"cmd":"DISARM"}"#
        case .stop:   return #"{"cmd":"STOP"}"#

        case let .startBalance(base, kpr, kpp):
            return #"{"cmd":"START_BALANCE","baseThrottle":\#(base),"kPRoll":\#(f(kpr)),"kPPitch":\#(f(kpp))}"#

        case let .startManual(roll, pitch, yaw, m1, m2, m3, m4, v, bat):
            return #"{"cmd":"START_MANUAL","roll":\#(f(roll)),"pitch":\#(f(pitch)),"yaw":\#(f(yaw)),"m1":\#(m1),"m2":\#(m2),"m3":\#(m3),"m4":\#(m4),"voltage":\#(f(v)),"batteryPercentage":\#(bat)}"#

        case let .updateManual(roll, pitch, yaw, m1, m2, m3, m4, v, bat):
            return #"{"roll":\#(f(roll)),"pitch":\#(f(pitch)),"yaw":\#(f(yaw)),"m1":\#(m1),"m2":\#(m2),"m3":\#(m3),"m4":\#(m4),"voltage":\#(f(v)),"batteryPercentage":\#(bat)}"#

        case let .startSound(maxPWM):
            return #"{"cmd":"START_SOUND","maxPWM":\#(maxPWM)}"#

        case let .tiltSound(pwm):
            return #"{"cmd":"TILT_SOUND","pwm":\#(pwm)}"#

        case .safeTest:
            return "SAFE_TEST"
        }
    }

    /// Two-decimal formatting, matching the firmware's expected precision.
    private func f(_ v: Double) -> String { String(format: "%.2f", v) }
}
