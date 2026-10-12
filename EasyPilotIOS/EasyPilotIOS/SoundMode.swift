import Foundation

/// Tilt → PWM math for Sound Mode, kept out of the view so it can be unit-tested.
enum SoundMode {
    /// Tilt (degrees) above which the app sends an emergency STOP.
    static let emergencyTiltDegrees = 60.0
    /// Tilt (degrees) at which the motors reach `maxPWM`.
    static let fullScaleTiltDegrees = 45.0

    /// Combined tilt of the phone in degrees, clamped to 90.
    static func tiltAngle(pitch: Double, roll: Double) -> Double {
        min(sqrt(pitch * pitch + roll * roll), 90)
    }

    /// PWM for a tilt: 1000 when level, `maxPWM` at 45° and beyond.
    static func pwm(forTilt tilt: Double, maxPWM: Double) -> Int {
        1000 + Int((min(tilt, fullScaleTiltDegrees) / fullScaleTiltDegrees) * (maxPWM - 1000))
    }

    static func isEmergency(tilt: Double) -> Bool {
        tilt > emergencyTiltDegrees
    }
}
