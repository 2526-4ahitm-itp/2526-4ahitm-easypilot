import Foundation
import Network
import Combine

/// Manages the UDP connection to receive telemetry data from the drone.
class UDPListener: ObservableObject {
    private var listener: NWListener?
    
    /// The latest telemetry data received from the drone.
    /// Published to update the UI automatically.
    @Published var telemetry: DroneTelemetry?
    
    /// Starts listening for UDP packets on port 5000.
    func startListening() {
        do {
            // Create a listener for UDP on port 5000
            let parameters = NWParameters.udp
            let port = NWEndpoint.Port(integerLiteral: 5000)
            
            listener = try NWListener(using: parameters, on: port)
            
            listener?.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    print("UDP Listener ready and listening on port 5000")
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
