import Foundation
import Network
import Combine

/// Manages the UDP connection to receive telemetry data from the drone.
class UDPListener: ObservableObject {
    private var listener: NWListener?
    private var pingTimer: Timer?
    private var broadcastConnection: NWConnection?
    
    /// The latest telemetry data received from the drone.
    /// Published to update the UI automatically.
    @Published var telemetry: DroneTelemetry?
    
    /// Starts listening for UDP packets on port 4242.
    func startListening() {
        guard listener == nil else { return }
        
        do {
            // Create a listener for UDP on port 4242
            let parameters = NWParameters.udp
            parameters.allowLocalEndpointReuse = true
            let port = NWEndpoint.Port(integerLiteral: 4242)
            
            listener = try NWListener(using: parameters, on: port)
            
            listener?.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    print("UDP Listener ready and listening on port 4242")
                    self.startPinging()
                case .failed(let error):
                    print("UDP Listener failed with error: \(error)")
                case .cancelled:
                    print("UDP Listener cancelled")
                default:
                    break
                }
            }
            
            listener?.newConnectionHandler = { newConnection in
                newConnection.start(queue: .main)
                self.receive(on: newConnection)
            }
            
            listener?.start(queue: .main)
            
        } catch {
            print("Could not start UDP listener: \(error)")
        }
    }
    
    /// Starts broadcasting a PING message to port 4242 to help the ESP32 discover our IP address.
    private func startPinging() {
        let endpoint = NWEndpoint.hostPort(host: "255.255.255.255", port: 4242)
        let parameters = NWParameters.udp
        broadcastConnection = NWConnection(to: endpoint, using: parameters)
        broadcastConnection?.start(queue: .main)
        
        pingTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            
            if self.telemetry != nil {
                // If we already received data, stop pinging
                self.pingTimer?.invalidate()
                self.pingTimer = nil
                self.broadcastConnection?.cancel()
                self.broadcastConnection = nil
                return
            }
            
            let message = "PING".data(using: .utf8)!
            self.broadcastConnection?.send(content: message, completion: .idempotent)
            print("Sent broadcast PING to ESP32")
        }
    }
    
    /// Recursively receives messages on a connection.
    private func receive(on connection: NWConnection) {
        connection.receiveMessage { (data, context, isComplete, error) in
            if let data = data {
                self.decodeData(data)
            }
            
            if error == nil {
                // Continue listening on this connection
                self.receive(on: connection)
            } else {
                print("Error receiving data: \(String(describing: error))")
            }
        }
    }
    
    /// Decodes the received JSON data into a DroneTelemetry object.
    private func decodeData(_ data: Data) {
        // Ignore our own PING messages
        if let stringData = String(data: data, encoding: .utf8), stringData == "PING" {
            return
        }
        
        do {
            let decoder = JSONDecoder()
            let newData = try decoder.decode(DroneTelemetry.self, from: data)
            
            DispatchQueue.main.async {
                self.telemetry = newData
            }
        } catch {
            print("JSON Decoding Error: \(error)")
            if let stringData = String(data: data, encoding: .utf8) {
                print("Raw data received: \(stringData)")
            }
        }
    }
}
