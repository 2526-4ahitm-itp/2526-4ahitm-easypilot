import Foundation
import simd

/// The simulated flight mode, matching what the real ESP32 firmware calls.
enum SimFlightMode: String, CaseIterable {
    case rate    = "RATE"
    case balance = "BALANCE"
}

/// Rate-mode and balance-mode 3D flight simulator driven by SceneKit's render loop.
///
/// Threading model:
///   tick(dt:)       — called on the SceneKit render thread; updates internal `_` vars only
///   syncPublished() — called on the main thread; copies `_` vars → @Published for SwiftUI
class DroneSimulator: ObservableObject {

    // MARK: - Published (SwiftUI, main thread only)

    @Published var simRoll:  Double = 0
    @Published var simPitch: Double = 0
    @Published var simYaw:   Double = 0
    @Published var altitude: Double = 0
    @Published var speedH:   Double = 0
    @Published var m1: Int = 1000
    @Published var m2: Int = 1000
    @Published var m3: Int = 1000
    @Published var m4: Int = 1000
    @Published var isArmed: Bool = false

    // MARK: - Internal physics state (render thread)

    var _roll:  Double = 0
    var _pitch: Double = 0
    var _yaw:   Double = 0
    var _pos:   SIMD3<Float> = SIMD3(0, groundLevel, 0)
    var _vel:   SIMD3<Float> = .zero
    var im1: Int = 1000
    var im2: Int = 1000
    var im3: Int = 1000
    var im4: Int = 1000

    // MARK: - Flight mode + config (written on main thread, read on render thread)

    var flightMode: SimFlightMode = .rate

    // Rate mode
    var maxRollRate:  Double = 360   // °/s at full deflection
    var maxPitchRate: Double = 360
    var maxYawRate:   Double = 200
    var expo:         Double = 0.35

    // Balance mode — mirrors real ESP32 firmware params
    var kPRoll:         Double = 10.0  // same units as ControlProfile.kPRoll
    var kPPitch:        Double = 10.0  // same units as ControlProfile.kPPitch
    var maxBalanceAngle: Double = 30.0 // max target tilt at full stick deflection (°)

    // Converts firmware kP (PWM/°) → simulation (°/s per °):
    // kP=10, error=10° → 35°/s correction → levels from 10° in ~0.3 s
    private let kPScale: Double = 0.35

    // MARK: - Joystick inputs (written on main thread, read on render thread)

    var throttle: Double = 0   // 0…1
    var yaw:      Double = 0   // -1…1
    var pitch:    Double = 0   // -1…1
    var roll:     Double = 0   // -1…1

    // MARK: - Constants

    static let groundLevel: Float = 0.05

    private let gravity:       Float = 9.81
    private let maxThrust:     Float = 22.0
    private let maxHorizAccel: Float = 8.0
    private let drag:          Float = 0.987

    // MARK: - Control

    func arm() {
        DispatchQueue.main.async { self.isArmed = true }
    }

    func disarm() {
        DispatchQueue.main.async { self.isArmed = false }
        resetPhysics()
    }

    // MARK: - Tick (render thread)

    func tick(dt: Float) {
        guard isArmed else {
            im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
            return
        }

        let thr    = Float(throttle)
        let flying = thr > 0.02

        // ── Attitude update ────────────────────────────────────────────────
        switch flightMode {

        case .rate:
            if flying {
                _roll  += roll  * maxRollRate  * Double(dt)
                _pitch -= pitch * maxPitchRate * Double(dt)
                _yaw   += yaw   * maxYawRate   * Double(dt)
            } else {
                let ret = 30.0 * Double(dt)
                _roll  = nudge(_roll,  to: 0, step: ret)
                _pitch = nudge(_pitch, to: 0, step: ret)
            }

        case .balance:
            // Right stick sets a target angle; P-controller drives actual attitude toward it.
            // Mimics the ESP32 BALANCE mode P-controller: correction = kP × error.
            // kPScale converts firmware-unit kP to simulation angular velocity.
            let targetRoll  =  roll  * maxBalanceAngle
            let targetPitch = -pitch * maxBalanceAngle
            let rollError   = targetRoll  - _roll
            let pitchError  = targetPitch - _pitch
            _roll  += rollError  * kPRoll  * kPScale * Double(dt)
            _pitch += pitchError * kPPitch * kPScale * Double(dt)
            // Yaw is always rate-based
            _yaw += yaw * maxYawRate * Double(dt)
        }

        _roll  = max(-80, min(80, _roll))
        _pitch = max(-80, min(80, _pitch))
        if _yaw >  180 { _yaw -= 360 }
        if _yaw < -180 { _yaw += 360 }

        // ── World-space position physics (same for both modes) ─────────────
        let theta = Float(-_yaw) * .pi / 180
        let vertA = thr * maxThrust - gravity
        let pFrac = Float(_pitch / 80.0)
        let rFrac = Float(_roll  / 80.0)
        let fwdA  = pFrac * maxHorizAccel
        let latA  = rFrac * maxHorizAccel

        _vel.x += (-sin(theta) * fwdA + cos(theta) * latA) * dt
        _vel.y +=  vertA * dt
        _vel.z += (-cos(theta) * fwdA - sin(theta) * latA) * dt
        _vel   *= drag
        _pos   += _vel * dt

        if _pos.y < Self.groundLevel {
            _pos.y = Self.groundLevel
            if _vel.y < 0 { _vel.y = 0 }
            _vel.x *= 0.7
            _vel.z *= 0.7
        }

        // ── Motor mixing ───────────────────────────────────────────────────
        let airborne = flying || _pos.y > Self.groundLevel
        if airborne {
            let base = 1000 + Int(throttle * 600)

            switch flightMode {
            case .rate:
                let rD = Int(_roll  * 0.5)
                let pD = Int(_pitch * 0.5)
                im1 = clampPWM(base - rD + pD)
                im2 = clampPWM(base + rD + pD)
                im3 = clampPWM(base - rD - pD)
                im4 = clampPWM(base + rD - pD)

            case .balance:
                // Visualise P-controller corrections like the real firmware does
                let tgtRoll  =  roll  * maxBalanceAngle
                let tgtPitch = -pitch * maxBalanceAngle
                let rCorr = Int((tgtRoll  - _roll)  * kPRoll  * 0.8)
                let pCorr = Int((tgtPitch - _pitch) * kPPitch * 0.8)
                im1 = clampPWM(base - rCorr + pCorr)
                im2 = clampPWM(base + rCorr + pCorr)
                im3 = clampPWM(base - rCorr - pCorr)
                im4 = clampPWM(base + rCorr - pCorr)
            }
        } else {
            im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
        }
    }

    // MARK: - Sync to @Published (main thread)

    func syncPublished() {
        simRoll  = _roll
        simPitch = _pitch
        simYaw   = _yaw
        altitude = Double(max(0, _pos.y - Self.groundLevel))
        speedH   = Double(sqrt(_vel.x * _vel.x + _vel.z * _vel.z))
        m1 = im1; m2 = im2; m3 = im3; m4 = im4
    }

    // MARK: - Private

    private func nudge(_ v: Double, to t: Double, step: Double) -> Double {
        abs(v - t) <= step ? t : v + (v < t ? step : -step)
    }

    private func clampPWM(_ v: Int) -> Int { max(1000, min(2000, v)) }

    private func resetPhysics() {
        _roll = 0; _pitch = 0; _yaw = 0
        _pos  = SIMD3(0, Self.groundLevel, 0)
        _vel  = .zero
        im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
        throttle = 0; yaw = 0; pitch = 0; roll = 0
    }
}
