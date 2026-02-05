import Foundation
import Network
import Combine

class UDPReceiver: ObservableObject {
    @Published var receivedMessage: String = "Warte auf Daten..."

    // Attitude (in Radians)
    @Published var roll: Double = 0.0
    @Published var pitch: Double = 0.0
    @Published var yaw: Double = 0.0

    // Motor Data (1000 - 2000)
    @Published var m1: Int = 1000
    @Published var m4: Int = 1000

    var listener: NWListener?
    let port: NWEndpoint.Port = 5000

    init() {
        startListening()
    }

    func startListening() {
        do {
            let parameters = NWParameters.udp
            parameters.allowLocalEndpointReuse = true

            listener = try NWListener(using: parameters, on: port)

            listener?.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    print("UDP Listener bereit auf Port \(self.port)")
                case .failed(let error):
                    print("UDP Listener Fehler: \(error)")
                case .cancelled:
                    print("UDP Listener beendet")
                default:
                    break
                }
            }

            listener?.newConnectionHandler = { connection in
                connection.start(queue: .main)
                self.receive(on: connection)
            }

            listener?.start(queue: .main)
        } catch {
            print("Konnte Listener nicht starten: \(error)")
        }
    }

    func receive(on connection: NWConnection) {
        connection.receiveMessage { (data, context, isComplete, error) in
            if let data = data, let message = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self.receivedMessage = message
                    self.parseJSON(message)
                }
            }

            if error == nil {
                self.receive(on: connection)
            }
        }
    }

    func parseJSON(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8) else { return }

        struct TelemetryData: Codable {
            let roll: Double?
            let pitch: Double?
            let yaw: Double?
            let m1: Int?
            let m4: Int?
        }

        do {
            let decoded = try JSONDecoder().decode(TelemetryData.self, from: data)
            if let r = decoded.roll { self.roll = r }
            if let p = decoded.pitch { self.pitch = p }
            if let y = decoded.yaw { self.yaw = y }
            if let m1Val = decoded.m1 { self.m1 = m1Val }
            if let m4Val = decoded.m4 { self.m4 = m4Val }
        } catch {
            print("JSON Decode Error: \(error)")
        }
    }
}
