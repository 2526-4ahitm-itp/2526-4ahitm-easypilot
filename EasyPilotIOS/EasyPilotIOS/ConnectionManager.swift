import Foundation
import Combine

/// Manages the choice between local and remote (Ngrok) connections.
class ConnectionManager: ObservableObject {
    @Published var useLocal: Bool = true
    @Published var localIP: String = "192.168.1.100" // Should be configurable or discovered
    @Published var ngrokURL: String = "7d8f-2001-871-22e-db71-4993-da01-cfcb-644e.ngrok-free.app"
    
    /// The current active websocket or UDP target.
    var currentTarget: String {
        return useLocal ? localIP : ngrokURL
    }
    
    /// Checks if the ESP32 is reachable on the local network.
    func probeLocalConnection() {
        // Simple ping or port check logic could go here.
        // For now, we allow the user to toggle or we use a timeout.
    }
}
