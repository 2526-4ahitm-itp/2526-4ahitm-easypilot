import Foundation

/// The drone's flight mode. Raw values match the ESP32 firmware strings exactly,
/// so a `FlightMode` round-trips cleanly through telemetry JSON and saved profiles.
enum FlightMode: String, CaseIterable, Codable {
    case idle    = "IDLE"
    case balance = "BALANCE"
    case manual  = "MANUAL"
    case sound   = "SOUND"

    /// Parses a raw telemetry/profile string, defaulting to `.idle` for anything
    /// unrecognised.
    init(rawOrIdle raw: String?) {
        self = raw.flatMap(FlightMode.init(rawValue:)) ?? .idle
    }
}
