import Foundation

/// A saved set of control parameters, including flight mode and its specific config.
struct ControlProfile: Codable, Identifiable, Equatable {
    var id: UUID
    var name: String

    // Flight mode: "IDLE" | "BALANCE" | "MANUAL"
    var mode: String

    // ── BALANCE mode config ──────────────────────────────────────
    /// Base throttle all four motors start from before P-corrections (PWM).
    var baseThrottle: Double
    /// Proportional gain for roll correction.
    var kPRoll: Double
    /// Proportional gain for pitch correction.
    var kPPitch: Double

    // ── MANUAL mode config (mirrors ESP32 telemetry JSON fields) ─
    var roll:  Double
    var pitch: Double
    var yaw:   Double
    var m1: Double
    var m2: Double
    var m3: Double
    var m4: Double
    var voltage:           Double
    var batteryPercentage: Double

    init(id: UUID = UUID(), name: String,
         mode: String = "IDLE",
         baseThrottle: Double = 1200, kPRoll: Double = 10.0, kPPitch: Double = 10.0,
         roll: Double = 0, pitch: Double = 0, yaw: Double = 0,
         m1: Double = 1000, m2: Double = 1000, m3: Double = 1000, m4: Double = 1000,
         voltage: Double = 16.8, batteryPercentage: Double = 100) {
        self.id   = id;   self.name = name;  self.mode = mode
        self.baseThrottle = baseThrottle
        self.kPRoll = kPRoll;  self.kPPitch = kPPitch
        self.roll = roll; self.pitch = pitch; self.yaw = yaw
        self.m1 = m1; self.m2 = m2; self.m3 = m3; self.m4 = m4
        self.voltage = voltage; self.batteryPercentage = batteryPercentage
    }

    // MARK: - Commands

    /// Command to start BALANCE mode on the ESP32.
    var startBalance: DroneCommand {
        .startBalance(baseThrottle: Int(baseThrottle), kPRoll: kPRoll, kPPitch: kPPitch)
    }

    /// Command to start MANUAL mode with the current slider values.
    var startManual: DroneCommand {
        .startManual(roll: roll, pitch: pitch, yaw: yaw,
                     m1: Int(m1), m2: Int(m2), m3: Int(m3), m4: Int(m4),
                     voltage: voltage, batteryPercentage: Int(batteryPercentage))
    }

    /// Command to re-send manual values mid-flight.
    var updateManual: DroneCommand {
        .updateManual(roll: roll, pitch: pitch, yaw: yaw,
                      m1: Int(m1), m2: Int(m2), m3: Int(m3), m4: Int(m4),
                      voltage: voltage, batteryPercentage: Int(batteryPercentage))
    }
}
