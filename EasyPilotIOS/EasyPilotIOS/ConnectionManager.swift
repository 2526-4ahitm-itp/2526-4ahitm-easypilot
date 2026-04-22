import Foundation
import Darwin

/// Manages hybrid connectivity: direct local UDP vs. remote Ngrok relay.
/// Call `updateESP32IP(_:)` whenever UDPListener receives a new esp32_ip from telemetry.
class ConnectionManager: ObservableObject {

    /// True when the ESP32 is on the same /24 subnet as the iPhone (local direct mode).
    @Published var isLocal: Bool = false

    /// The confirmed local IP of the ESP32, used as the command target.
    @Published var esp32IP: String?

    /// Called by DashboardView whenever udpListener.esp32IP changes.
    func updateESP32IP(_ ip: String) {
        guard esp32IP != ip else { return }
        esp32IP = ip
        isLocal = isOnSameSubnet(ip)
    }

    // MARK: - Private

    /// Compares the first three octets of the ESP32 IP against the iPhone's WiFi IP.
    /// Assumes a /24 subnet, which covers all typical home/school networks.
    private func isOnSameSubnet(_ esp32IP: String) -> Bool {
        guard let deviceIP = wifiIPAddress() else { return false }
        let esp32Parts  = esp32IP.split(separator: ".").map(String.init)
        let deviceParts = deviceIP.split(separator: ".").map(String.init)
        guard esp32Parts.count == 4, deviceParts.count == 4 else { return false }
        return esp32Parts[0] == deviceParts[0]
            && esp32Parts[1] == deviceParts[1]
            && esp32Parts[2] == deviceParts[2]
    }

    /// Returns the IPv4 address of the en0 (WiFi) interface, or nil if not connected.
    private func wifiIPAddress() -> String? {
        var address: String?
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0 else { return nil }
        defer { freeifaddrs(ifaddr) }
        var ptr = ifaddr
        while ptr != nil {
            let iface = ptr!.pointee
            if iface.ifa_addr.pointee.sa_family == UInt8(AF_INET),
               String(cString: iface.ifa_name) == "en0" {
                var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                getnameinfo(
                    iface.ifa_addr,
                    socklen_t(iface.ifa_addr.pointee.sa_len),
                    &hostname, socklen_t(hostname.count),
                    nil, 0,
                    NI_NUMERICHOST
                )
                address = String(cString: hostname)
            }
            ptr = iface.ifa_next
        }
        return address
    }
}
