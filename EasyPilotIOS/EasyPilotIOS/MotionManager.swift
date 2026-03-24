import Foundation
import CoreMotion
import Combine

/// Manages the iPhone's motion sensors (Gyroscope/Accelerometer).
class MotionManager: ObservableObject {
    private let motionManager = CMMotionManager()
    
    /// Current pitch of the iPhone in degrees.
    @Published var pitch: Double = 0.0
    
    /// Current roll of the iPhone in degrees.
    @Published var roll: Double = 0.0
    
    /// Starts updates from the device motion sensors.
    func startUpdates() {
        if motionManager.isDeviceMotionAvailable {
            motionManager.deviceMotionUpdateInterval = 0.1 // 10Hz
            motionManager.startDeviceMotionUpdates(to: .main) { [weak self] (data, error) in
                guard let data = data, error == nil else { return }
                
                // Convert radians to degrees
                let radToDeg = 180.0 / .pi
                self?.pitch = data.attitude.pitch * radToDeg
                self?.roll = data.attitude.roll * radToDeg
                
                // Safety Check: If tilted more than 45 degrees, we could trigger something
                // this is handled in the View or a separate Controller
            }
        }
    }
    
    /// Stops updates to save battery.
    func stopUpdates() {
        motionManager.stopDeviceMotionUpdates()
    }
}
