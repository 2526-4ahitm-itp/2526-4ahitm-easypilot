import Foundation
import Network
import Combine

class UDPReceiver: ObservableObject {
    @Published var receivedMessage: String = "Warte auf Daten..."
    @Published var x: Double = 0.0
    @Published var y: Double = 0.0
    @Published var z: Double = 0.0

    var listener: NWListener?
    let port: NWEndpoint.Port = 5000

    init() {
        startListening()
    }

    func startListening() {
        do {
            let parameters = NWParameters.udp
            parameters.allowLocalEndpointReuse = true

            // Optional: Wenn Broadcast empfangen werden soll, muss das ggf. konfiguriert werden.
            // Standard UDP Listener sollte aber auf 0.0.0.0 lauschen.

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
                // Weiterhin auf dieser "Verbindung" lauschen
                self.receive(on: connection)
            } else {
                print("Empfangsfehler: \(String(describing: error))")
            }
        }
    }

    func parseJSON(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8) else { return }

        struct GyroData: Codable {
            let x: Double
            let y: Double
            let z: Double
        }

        do {
            let decoded = try JSONDecoder().decode(GyroData.self, from: data)
            self.x = decoded.x
            self.y = decoded.y
            self.z = decoded.z
        } catch {
            print("JSON Decode Error: \(error)")
        }
    }
}
