import Foundation
import Network
import Combine

/// Manages the UDP connection to receive telemetry data from the drone.
class UDPListener: ObservableObject {
    private var listener: NWListener?
    private var pingTimer: Timer?
    private var timeoutTimer: Timer?
    private var broadcastConnection: NWConnection?
    
    /// The latest telemetry data received from the drone.
    @Published var telemetry: DroneTelemetry?

    /// Whether the app is currently receiving data.
    @Published var isConnected: Bool = false

    /// The local IP of the ESP32, extracted from the `esp32_ip` field in telemetry JSON.
    @Published var esp32IP: String?
    
    /// Starts listening for UDP packets on port 4242.
    func startListening() {
        guard listener == nil else { return }
        
        do {
            let parameters = NWParameters.udp
            parameters.allowLocalEndpointReuse = true
            let port = NWEndpoint.Port(integerLiteral: 4242)
            
            listener = try NWListener(using: parameters, on: port)
            
            listener?.stateUpdateHandler = { [weak self] state in
                guard let self = self else { return }
                switch state {
                case .ready:
                    print("UDP Listener ready and listening on port 4242")
                    self.startPinging()
                case .failed(let error):
                    print("UDP Listener failed with error: \(error)")
                    self.isConnected = false
                case .cancelled:
                    print("UDP Listener cancelled")
                    self.isConnected = false
                default:
                    break
                }
            }
            
            listener?.newConnectionHandler = { [weak self] newConnection in
                guard let self = self else { return }
                newConnection.start(queue: .main)
                self.receive(on: newConnection)
            }
            
            listener?.start(queue: .main)
            
        } catch {
            print("Could not start UDP listener: \(error)")
        }
    }
    
    private func startPinging() {
        let endpoint = NWEndpoint.hostPort(host: "255.255.255.255", port: 4242)
        let parameters = NWParameters.udp
        broadcastConnection = NWConnection(to: endpoint, using: parameters)
        broadcastConnection?.start(queue: .main)
        
        pingTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            let message = "PING".data(using: .utf8)!
            self.broadcastConnection?.send(content: message, completion: .idempotent)
        }
    }
    
    private func receive(on connection: NWConnection) {
        connection.receiveMessage { [weak self] (data, context, isComplete, error) in
            guard let self = self else { return }
            
            if let data = data {
                // print("Received data size: \(data.count)")
                self.decodeData(data)
            }
            
            if error == nil {
                self.receive(on: connection)
            } else {
                print("Error receiving data: \(String(describing: error))")
                DispatchQueue.main.async {
                    self.isConnected = false
                }
            }
        }
    }
    
    private func decodeData(_ data: Data) {
        if let stringData = String(data: data, encoding: .utf8), stringData == "PING" {
            return
        }
        
        do {
            let decoder = JSONDecoder()
            let newData = try decoder.decode(DroneTelemetry.self, from: data)
            
            DispatchQueue.main.async {
                self.telemetry = newData
                self.isConnected = true
                if let ip = newData.esp32IP, !ip.isEmpty {
                    self.esp32IP = ip
                }
                self.resetTimeout()
            }
        } catch {
            print("JSON Decoding Error: \(error)")
            if let stringData = String(data: data, encoding: .utf8) {
                print("Raw data received: \(stringData)")
            }
        }
    }
    
    private func resetTimeout() {
        timeoutTimer?.invalidate()
        timeoutTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: false) { [weak self] _ in
            DispatchQueue.main.async {
                self?.isConnected = false
            }
        }
    }
}
