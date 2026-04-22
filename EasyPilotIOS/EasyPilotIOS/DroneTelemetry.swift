import Foundation

/// Represents the telemetry data received from the drone.
/// This struct is `Codable` to allow easy decoding from the JSON sent by the ESP32.
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
    /// The local IP address of the ESP32, included in every telemetry packet.
    /// Used by ConnectionManager to determine if local direct UDP commands are possible.
    let esp32IP: String?

    enum CodingKeys: String, CodingKey {
        case roll, pitch, yaw, m1, m2, m3, m4, voltage, batteryPercentage
        case esp32IP = "esp32_ip"
    }
}
