import Foundation
import Combine

/// Phone-side rate-mode flight simulator.
///
/// Inputs (set by the joystick view):
///   throttle  0…1    (left stick up)
///   yaw      -1…1    (left stick right = positive yaw)
///   pitch    -1…1    (right stick up = negative pitch / nose-down)
///   roll     -1…1    (right stick right = positive roll)
///
/// Outputs (published):
///   simRoll / simPitch / simYaw  — degrees
///   m1…m4                        — PWM 1000–2000
///   isArmed
class DroneSimulator: ObservableObject {

    // MARK: - Published state

    @Published var simRoll:  Double = 0
    @Published var simPitch: Double = 0
    @Published var simYaw:   Double = 0
    @Published var m1: Int = 1000
    @Published var m2: Int = 1000
    @Published var m3: Int = 1000
    @Published var m4: Int = 1000
    @Published var isArmed: Bool = false

    // MARK: - Config (settable from UI)

    var maxRollRate:  Double = 360   // °/s at full deflection
    var maxPitchRate: Double = 360
    var maxYawRate:   Double = 200
    var expo:         Double = 0.35  // passed through from view

    // MARK: - Inputs (written by joystick view)

    var throttle: Double = 0   // 0…1, non-expo
    var yaw:      Double = 0   // -1…1, already expo-applied
    var pitch:    Double = 0   // -1…1, already expo-applied (positive = nose up)
    var roll:     Double = 0   // -1…1, already expo-applied

    // MARK: - Private

    private var ticker: Timer?
    private let dt: Double = 1.0 / 20.0   // 20 Hz

    // MARK: - Control

    func arm() {
        guard !isArmed else { return }
        isArmed = true
        startTicker()
    }

    func disarm() {
        isArmed = false
        stopTicker()
        resetState()
    }

    // MARK: - Ticker

    private func startTicker() {
        ticker = Timer.scheduledTimer(withTimeInterval: dt, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    private func stopTicker() {
        ticker?.invalidate()
        ticker = nil
    }

    private func tick() {
        let flying = isArmed && throttle > 0.05

        if flying {
            // Integrate angular rates
            simRoll  += roll  * maxRollRate  * dt
            simPitch -= pitch * maxPitchRate * dt  // stick up = nose up = negative pitch
            simYaw   += yaw   * maxYawRate   * dt

            // Clamp to avoid gimbal-lock territory
            simRoll  = max(-85, min(85, simRoll))
            simPitch = max(-85, min(85, simPitch))
            // yaw wraps
            if simYaw >  180 { simYaw -= 360 }
            if simYaw < -180 { simYaw += 360 }
        } else {
            // Gravity / level return at 20°/s
            let returnRate = 20.0 * dt
            simRoll  = nudgeToward(simRoll,  target: 0, step: returnRate)
            simPitch = nudgeToward(simPitch, target: 0, step: returnRate)
        }

        updateMotors(flying: flying)
    }

    private func nudgeToward(_ v: Double, target: Double, step: Double) -> Double {
        if abs(v - target) <= step { return target }
        return v + (v < target ? step : -step)
    }

    private func updateMotors(flying: Bool) {
        guard flying else {
            m1 = 1000; m2 = 1000; m3 = 1000; m4 = 1000
            return
        }
        let base = 1000 + Int(throttle * 600)   // 1000…1600
        let rDelta = Int(simRoll  * 0.4)         // ±34 PWM at ±85°
        let pDelta = Int(simPitch * 0.4)

        // Motor layout: M1=FL, M2=FR, M3=RL, M4=RR
        m1 = clampPWM(base - rDelta + pDelta)
        m2 = clampPWM(base + rDelta + pDelta)
        m3 = clampPWM(base - rDelta - pDelta)
        m4 = clampPWM(base + rDelta - pDelta)
    }

    private func clampPWM(_ v: Int) -> Int { max(1000, min(2000, v)) }

    private func resetState() {
        simRoll = 0; simPitch = 0; simYaw = 0
        m1 = 1000; m2 = 1000; m3 = 1000; m4 = 1000
        throttle = 0; yaw = 0; pitch = 0; roll = 0
    }
}
