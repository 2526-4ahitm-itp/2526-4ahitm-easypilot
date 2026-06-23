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
    @Published var isArmed:   Bool = false
    @Published var isCrashed: Bool = false

    // Autopilot "demand" values for visualisation — normalised [-1, 1] so the
    // VirtualJoystick can mirror them on its thumb when the user has released
    // the sticks and the "Autopilot sticks" option is enabled.
    @Published var autopilotLeftY:  Double = 0   // throttle correction view (negative = pushed up)
    @Published var autopilotRightX: Double = 0   // roll correction view
    @Published var autopilotRightY: Double = 0   // pitch correction view

    // MARK: - Internal physics state (render thread)

    var _roll:  Double = 0
    var _pitch: Double = 0
    var _yaw:   Double = 0
    var _pos:   SIMD3<Float> = SIMD3(0, groundLevel, 0)
    var _vel:   SIMD3<Float> = .zero

    // Angular velocities (°/s) — used by rate mode inertia model
    var _rollRate:  Double = 0
    var _pitchRate: Double = 0
    var _yawRate:   Double = 0

    // Target motor PWM (from mixing)
    var im1: Int = 1000
    var im2: Int = 1000
    var im3: Int = 1000
    var im4: Int = 1000

    // Filtered motor PWM (low-pass, drives prop animation and @Published m1-m4)
    var mFil1: Double = 1000
    var mFil2: Double = 1000
    var mFil3: Double = 1000
    var mFil4: Double = 1000

    private var crashLatch: Bool = false

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

    // Rate mode angular physics
    private let rateResponse:  Double = 14.0  // how fast actual rate follows stick command
    private let angularDrag:   Double = 0.40  // aerodynamic damping on rotation (fraction/s)
    private let motorFilterTC: Double = 10.0  // motor low-pass: 1/TC = time constant ~100 ms

    // MARK: - Joystick inputs (written on main thread, read on render thread)

    var throttle: Double = 0   // 0…1
    var yaw:      Double = 0   // -1…1
    var pitch:    Double = 0   // -1…1
    var roll:     Double = 0   // -1…1

    /// True while the LEFT stick (throttle/yaw) is being touched.
    /// When false, altitude-hold takes over the throttle and yaw rate decays.
    var leftStickTouched:  Bool = false
    /// True while the RIGHT stick (pitch/roll) is being touched.
    /// When false, attitude auto-levels per the active flight mode.
    var rightStickTouched: Bool = false

    /// True while at least one stick is touched — kept for legacy callers.
    var sticksTouched: Bool { leftStickTouched || rightStickTouched }

    // Altitude-hold state. The last-known hover throttle that produced ~zero
    // vertical velocity, used as the baseline when the left stick is released.
    private var holdThrottle: Float = 0.45   // ~mass/maxThrust at startup

    // MARK: - Constants

    static let groundLevel: Float = 0.05

    private let gravity:   Float = 9.81
    private let maxThrust: Float = 22.0
    private let drag:      Float = 0.987   // per-frame factor tuned for 60 fps

    // MARK: - Control

    func arm() {
        DispatchQueue.main.async { self.isArmed = true }
    }

    func disarm() {
        crashLatch = false
        DispatchQueue.main.async { self.isArmed = false; self.isCrashed = false }
        resetPhysics()
    }

    // MARK: - Tick (render thread)

    func tick(dt: Float) {
        guard isArmed else {
            im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
            // Filter still runs so propellers spin down smoothly after disarm / crash
            let αD = min(1.0, motorFilterTC * Double(dt))
            mFil1 += (1000.0 - mFil1) * αD
            mFil2 += (1000.0 - mFil2) * αD
            mFil3 += (1000.0 - mFil3) * αD
            mFil4 += (1000.0 - mFil4) * αD
            return
        }

        // ── Effective throttle (altitude-hold when left stick released) ────
        let userThrottle = Float(throttle)
        let effectiveThrottle: Float
        if leftStickTouched {
            effectiveThrottle = userThrottle
            // Track current throttle as the baseline for altitude-hold.
            if userThrottle > 0.05 { holdThrottle = userThrottle }
        } else {
            // Hover-hold: nudge throttle to drive _vel.y toward 0
            let velYCorrection = -_vel.y * 0.025
            effectiveThrottle = max(0, min(1, holdThrottle + velYCorrection))
        }
        let flying = effectiveThrottle > 0.02

        // ── Attitude update ────────────────────────────────────────────────
        // Pitch/roll stabilise when the RIGHT stick is released; yaw responds
        // to LEFT stick (yaw axis) and decays naturally when released.
        if flying && rightStickTouched {
            integrateRatePhysics(dt: dt)
        } else if !flying {
            // Ground: snap level, zero all rates
            _rollRate = 0; _pitchRate = 0; _yawRate = 0
            let ret = 30.0 * Double(dt)
            _roll  = nudge(_roll,  to: 0, step: ret)
            _pitch = nudge(_pitch, to: 0, step: ret)
        } else {
            // Flying, right stick released → auto-level pitch/roll
            _rollRate = 0; _pitchRate = 0
            switch flightMode {
            case .rate:
                let ret = 30.0 * Double(dt)
                _roll  = nudge(_roll,  to: 0, step: ret)
                _pitch = nudge(_pitch, to: 0, step: ret)
            case .balance:
                _roll  += (0 - _roll)  * kPRoll  * kPScale * Double(dt)
                _pitch += (0 - _pitch) * kPPitch * kPScale * Double(dt)
            }
            // Yaw still responds to left stick if it's held
            if leftStickTouched {
                let drag = 1.0 - angularDrag * Double(dt)
                _yawRate *= drag
                let cmdYaw = yaw * maxYawRate
                let dt2 = min(1.0, rateResponse * Double(dt))
                _yawRate += (cmdYaw - _yawRate) * dt2
                _yaw     += _yawRate * Double(dt)
            } else {
                let drag = 1.0 - angularDrag * Double(dt)
                _yawRate *= drag
                _yaw += _yawRate * Double(dt)
            }
        }

        _roll  = max(-80, min(80, _roll))
        _pitch = max(-80, min(80, _pitch))
        if _yaw >  180 { _yaw -= 360 }
        if _yaw < -180 { _yaw += 360 }

        // ── World-space position physics (thrust-vector based) ─────────────
        let theta    = Float(-_yaw) * .pi / 180
        let velYPre  = _vel.y   // capture before this frame's acceleration

        // Decompose thrust by attitude so tilt reduces vertical lift
        // and horizontal acceleration scales with throttle.
        let pitchRad = Float(-_pitch) * .pi / 180   // + when nose-down
        let rollRad  = Float(_roll)  * .pi / 180    // + when right-wing-down
        let thrust   = effectiveThrottle * maxThrust

        let vertThrust = thrust * cos(pitchRad) * cos(rollRad)
        let fwdThrust  = thrust * sin(pitchRad)       // forward component
        let latThrust  = thrust * sin(rollRad)        // rightward component

        let vertA = vertThrust - gravity

        _vel.x += (-sin(theta) * fwdThrust + cos(theta) * latThrust) * dt
        _vel.y +=  vertA * dt
        _vel.z += (-cos(theta) * fwdThrust - sin(theta) * latThrust) * dt

        // Frame-rate independent drag (preserves 60 fps feel)
        let dragFactor = pow(drag, dt * 60.0)
        _vel *= dragFactor
        _pos += _vel * dt

        if _pos.y < Self.groundLevel {
            _pos.y = Self.groundLevel
            if !crashLatch {
                if velYPre < -4.0 {
                    triggerCrash(); return
                }
                if flightMode == .rate && (abs(_roll) > 72 || abs(_pitch) > 72) {
                    triggerCrash(); return
                }
            }
            if _vel.y < 0 { _vel.y = 0 }
            _vel.x *= 0.7
            _vel.z *= 0.7
        }

        // ── Motor mixing ───────────────────────────────────────────────────
        let airborne = flying || _pos.y > Self.groundLevel
        if airborne {
            let base = 1000 + Int(Double(effectiveThrottle) * 600)

            if flightMode == .balance && !rightStickTouched {
                // Visualise P-controller corrections like the real firmware does
                let rCorr = Int((0 - _roll)  * kPRoll  * 0.8)
                let pCorr = Int((0 - _pitch) * kPPitch * 0.8)
                im1 = clampPWM(base - rCorr + pCorr)
                im2 = clampPWM(base + rCorr + pCorr)
                im3 = clampPWM(base - rCorr - pCorr)
                im4 = clampPWM(base + rCorr - pCorr)
            } else {
                let rD = Int(_roll  * 0.5)
                let pD = Int(_pitch * 0.5)
                im1 = clampPWM(base - rD + pD)
                im2 = clampPWM(base + rD + pD)
                im3 = clampPWM(base - rD - pD)
                im4 = clampPWM(base + rD - pD)
            }
        } else {
            im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
        }

        // ── Motor output filtering (brushless spin-up/down lag) ────────────────
        let α = min(1.0, motorFilterTC * Double(dt))
        mFil1 += (Double(im1) - mFil1) * α
        mFil2 += (Double(im2) - mFil2) * α
        mFil3 += (Double(im3) - mFil3) * α
        mFil4 += (Double(im4) - mFil4) * α
    }

    // MARK: - Shared rate physics

    private func integrateRatePhysics(dt: Float) {
        // Aerodynamic drag attenuates angular velocity every frame
        let drag = 1.0 - angularDrag * Double(dt)
        _rollRate  *= drag
        _pitchRate *= drag
        _yawRate   *= drag
        // Rate controller: actual rate tracks commanded rate with inertia
        let cmdRoll  = roll  * maxRollRate
        let cmdPitch = pitch * maxPitchRate
        let cmdYaw   = yaw   * maxYawRate
        let dt2 = min(1.0, rateResponse * Double(dt))
        _rollRate  += (cmdRoll  - _rollRate)  * dt2
        _pitchRate += (cmdPitch - _pitchRate) * dt2
        _yawRate   += (cmdYaw   - _yawRate)   * dt2
        // Integrate angular velocity → attitude
        _roll  += _rollRate  * Double(dt)
        _pitch -= _pitchRate * Double(dt)  // minus: forward pitch input → nose down
        _yaw   += _yawRate   * Double(dt)
    }

    // MARK: - Sync to @Published (main thread)

    func syncPublished() {
        simRoll  = _roll
        simPitch = _pitch
        simYaw   = _yaw
        altitude = Double(max(0, _pos.y - Self.groundLevel))
        speedH   = Double(sqrt(_vel.x * _vel.x + _vel.z * _vel.z))
        m1 = Int(mFil1); m2 = Int(mFil2); m3 = Int(mFil3); m4 = Int(mFil4)

        // Autopilot demand for stick visualisation. Throttle: signed Y in
        // [-1, 1] where -1 = full up (since SwiftUI Y is inverted on the pad).
        // Mapping the hold throttle in 0…1 to [-1, 1] with 0 throttle = +1.
        let holdY = -((Double(holdThrottle) - 0.5) * 2.0)
        autopilotLeftY  = max(-1, min(1, holdY))
        // Right stick: the angle the autopilot is "asking for" — opposite of
        // current tilt, clamped to ±maxBalanceAngle then normalised.
        let demandRollDeg  = -_roll  * 0.5
        let demandPitchDeg = -_pitch * 0.5
        autopilotRightX = max(-1, min(1,  demandRollDeg  / max(1, maxBalanceAngle)))
        autopilotRightY = max(-1, min(1, -demandPitchDeg / max(1, maxBalanceAngle)))
    }

    // MARK: - Private

    private func nudge(_ v: Double, to t: Double, step: Double) -> Double {
        abs(v - t) <= step ? t : v + (v < t ? step : -step)
    }

    private func clampPWM(_ v: Int) -> Int { max(1000, min(2000, v)) }

    private func triggerCrash() {
        crashLatch = true
        im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
        DispatchQueue.main.async {
            self.isArmed   = false
            self.isCrashed = true
        }
    }

    func respawn() {
        crashLatch = false
        resetPhysics()
        DispatchQueue.main.async { self.isCrashed = false }
    }

    private func resetPhysics() {
        _roll = 0; _pitch = 0; _yaw = 0
        _rollRate = 0; _pitchRate = 0; _yawRate = 0
        _pos  = SIMD3(0, Self.groundLevel, 0)
        _vel  = .zero
        im1 = 1000; im2 = 1000; im3 = 1000; im4 = 1000
        mFil1 = 1000; mFil2 = 1000; mFil3 = 1000; mFil4 = 1000
        throttle = 0; yaw = 0; pitch = 0; roll = 0
    }
}
