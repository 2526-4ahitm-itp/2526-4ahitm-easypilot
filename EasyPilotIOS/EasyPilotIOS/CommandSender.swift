import Foundation
import Network

/// Sends UDP command packets to the ESP32's command port (4243).
/// All commands are fire-and-forget UDP; no acknowledgement is expected.
class CommandSender {

    static let commandPort: UInt16 = 4243

    private var lastSafeTestTime: Date = .distantPast
    /// Minimum seconds between repeated SAFE_TEST commands to avoid spamming the ESC.
    private let safeTestDebounce: TimeInterval = 2.0

    /// Sends a SAFE_TEST command to the ESP32 if the debounce period has passed.
    /// ESP32 will pulse Motor 1 at 1050 PWM for 500 ms.
    func sendSafeTest(to ip: String) {
        let now = Date()
        guard now.timeIntervalSince(lastSafeTestTime) >= safeTestDebounce else { return }
        lastSafeTestTime = now
        send("SAFE_TEST", to: ip)
    }

    // MARK: - Private

    private func send(_ command: String, to ip: String) {
        guard let port = NWEndpoint.Port(rawValue: CommandSender.commandPort) else { return }
        let connection = NWConnection(
            host: NWEndpoint.Host(ip),
            port: port,
            using: .udp
        )
        connection.start(queue: .global(qos: .userInitiated))
        connection.send(
            content: command.data(using: .utf8),
            completion: .contentProcessed { _ in connection.cancel() }
        )
        print("[CMD] Sent '\(command)' to \(ip):\(CommandSender.commandPort)")
    }
}
