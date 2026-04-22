import Foundation
import Network

/// Single entry point for all drone communication.
///
/// Discovery:  listens for a UDP beacon "EASYPILOT:<IP>" on port 4242.
/// Data path:  connects WebSocket to ws://ESP32_IP:81.
///   - Inbound:  telemetry JSON pushed by the ESP32 at 10 Hz.
///   - Outbound: text command strings (e.g. "SAFE_TEST").
class WebSocketManager: ObservableObject {

    @Published var telemetry: DroneTelemetry?
    @Published var isConnected: Bool = false
    @Published var esp32IP: String?

    // MARK: - Constants
    private static let beaconPort: NWEndpoint.Port = 4242
    private static let wsPort                      = 81
    private static let timeoutInterval: TimeInterval  = 3.0
    private static let pingInterval: TimeInterval     = 5.0
    private static let safeTestDebounce: TimeInterval = 2.0

    // MARK: - Private state
    private var beaconListener: NWListener?
    private var webSocketTask: URLSessionWebSocketTask?
    private var timeoutTimer: Timer?
    private var pingTimer: Timer?
    private var lastSafeTestTime: Date = .distantPast

    // MARK: - Lifecycle

    func start() {
        startBeaconListener()
    }

    func stop() {
        beaconListener?.cancel()
        beaconListener = nil
        disconnect()
    }

    // MARK: - Commands

    /// Sends "SAFE_TEST" to the ESP32 (debounced: at most once every 2 s).
    func sendSafeTest() {
        let now = Date()
        guard now.timeIntervalSince(lastSafeTestTime) >= Self.safeTestDebounce else { return }
        lastSafeTestTime = now
        sendCommand("SAFE_TEST")
    }

    func sendCommand(_ command: String) {
        guard isConnected else { return }
        webSocketTask?.send(.string(command)) { error in
            if let error = error {
                print("[WS] Send error: \(error.localizedDescription)")
            }
        }
        print("[WS] Sent: \(command)")
    }

    // MARK: - UDP Beacon Discovery

    private func startBeaconListener() {
        guard beaconListener == nil else { return }
        do {
            let params = NWParameters.udp
            params.allowLocalEndpointReuse = true
            beaconListener = try NWListener(using: params, on: Self.beaconPort)
            beaconListener?.newConnectionHandler = { [weak self] conn in
                conn.start(queue: .main)
                self?.receiveBeacon(on: conn)
            }
            beaconListener?.start(queue: .main)
            print("[Beacon] Listening on port \(Self.beaconPort)")
        } catch {
            print("[Beacon] Failed to start listener: \(error)")
        }
    }

    private func receiveBeacon(on conn: NWConnection) {
        conn.receiveMessage { [weak self] data, _, _, error in
            guard let self = self else { return }
            if let data = data,
               let text = String(data: data, encoding: .utf8),
               text.hasPrefix("EASYPILOT:") {
                let ip = String(text.dropFirst("EASYPILOT:".count))
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                if !ip.isEmpty && ip != self.esp32IP {
                    print("[Beacon] ESP32 discovered at \(ip)")
                    DispatchQueue.main.async {
                        self.esp32IP = ip
                        self.connectWebSocket(to: ip)
                    }
                }
            }
            if error == nil { self.receiveBeacon(on: conn) }
        }
    }

    // MARK: - WebSocket

    private func connectWebSocket(to ip: String) {
        disconnect()
        guard let url = URL(string: "ws://\(ip):\(Self.wsPort)") else { return }
        print("[WS] Connecting to \(url)")
        webSocketTask = URLSession.shared.webSocketTask(with: url)
        webSocketTask?.resume()
        receiveMessage()
        startPing()
    }

    private func disconnect() {
        pingTimer?.invalidate()
        timeoutTimer?.invalidate()
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }
            switch result {
            case .success(let message):
                let text: String?
                switch message {
                case .string(let s): text = s
                case .data(let d):   text = String(data: d, encoding: .utf8)
                @unknown default:    text = nil
                }
                if let text = text { self.decodeJSON(text) }
                self.receiveMessage()

            case .failure(let error):
                print("[WS] Receive error: \(error.localizedDescription)")
                DispatchQueue.main.async { self.isConnected = false }
            }
        }
    }

    private func decodeJSON(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let decoded = try JSONDecoder().decode(DroneTelemetry.self, from: data)
            DispatchQueue.main.async {
                self.telemetry = decoded
                self.isConnected = true
                self.resetTimeout()
            }
        } catch {
            print("[WS] JSON decode error: \(error)")
        }
    }

    private func startPing() {
        pingTimer = Timer.scheduledTimer(withTimeInterval: Self.pingInterval, repeats: true) { [weak self] _ in
            self?.webSocketTask?.sendPing { error in
                if let error = error {
                    print("[WS] Ping failed: \(error.localizedDescription)")
                    DispatchQueue.main.async { self?.isConnected = false }
                }
            }
        }
    }

    private func resetTimeout() {
        timeoutTimer?.invalidate()
        timeoutTimer = Timer.scheduledTimer(withTimeInterval: Self.timeoutInterval, repeats: false) { [weak self] _ in
            DispatchQueue.main.async { self?.isConnected = false }
        }
    }
}
