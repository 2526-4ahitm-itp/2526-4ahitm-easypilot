import Foundation

/// Represents the telemetry data received from the drone.
/// This struct is `Codable` to allow easy decoding from the JSON sent by the ESP32.
struct DroneTelemetry: Codable {
    let roll: Float
    let pitch: Float
    let yaw: Float
    let m1: Int?
    let m4: Int?
}
