import Foundation

/// Represents the telemetry data received from the drone via WebSocket.
struct DroneTelemetry: Codable {
    let roll: Float
    let pitch: Float
    let yaw: Float
    let m1: Int?
    let m2: Int?
    let m3: Int?
    let m4: Int?
    let voltage: Float?
    let batteryPercentage: Int?
    /// Whether the drone is armed (motors can spin).
    let armed: Bool?
    /// Current flight mode: "IDLE", "BALANCE", or "MANUAL".
    let mode: String?
}
