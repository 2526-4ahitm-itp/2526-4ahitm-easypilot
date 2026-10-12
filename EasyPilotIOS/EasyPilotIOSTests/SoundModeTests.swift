import Testing
@testable import EasyPilotIOS

struct SoundModeTests {

    @Test func tiltCombinesPitchAndRoll() {
        #expect(SoundMode.tiltAngle(pitch: 3, roll: 4) == 5)
        #expect(SoundMode.tiltAngle(pitch: -3, roll: -4) == 5)
    }

    @Test func tiltIsClampedTo90() {
        #expect(SoundMode.tiltAngle(pitch: 100, roll: 100) == 90)
    }

    @Test func levelPhoneIsSilent() {
        #expect(SoundMode.pwm(forTilt: 0, maxPWM: 1400) == 1000)
    }

    @Test func pwmScalesLinearlyUpTo45Degrees() {
        #expect(SoundMode.pwm(forTilt: 22.5, maxPWM: 1400) == 1200)
        #expect(SoundMode.pwm(forTilt: 45, maxPWM: 1400) == 1400)
    }

    @Test func pwmStaysAtMaxAbove45Degrees() {
        #expect(SoundMode.pwm(forTilt: 80, maxPWM: 1400) == 1400)
        #expect(SoundMode.pwm(forTilt: 90, maxPWM: 1050) == 1050)
    }

    @Test func emergencyStartsAbove60Degrees() {
        #expect(!SoundMode.isEmergency(tilt: 60))
        #expect(SoundMode.isEmergency(tilt: 60.1))
    }
}
