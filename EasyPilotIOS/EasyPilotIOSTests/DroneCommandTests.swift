import Foundation
import Testing
@testable import EasyPilotIOS

/// Pins the exact wire format the ESP32 firmware (main.cpp) parses.
struct DroneCommandTests {

    @Test func simpleCommands() {
        #expect(DroneCommand.arm.payload == #"{"cmd":"ARM"}"#)
        #expect(DroneCommand.disarm.payload == #"{"cmd":"DISARM"}"#)
        #expect(DroneCommand.stop.payload == #"{"cmd":"STOP"}"#)
    }

    @Test func safeTestIsPlainText() {
        #expect(DroneCommand.safeTest.payload == "SAFE_TEST")
    }

    @Test func startBalance() {
        let cmd = DroneCommand.startBalance(baseThrottle: 1200, kPRoll: 10, kPPitch: 12.5)
        #expect(cmd.payload == #"{"cmd":"START_BALANCE","baseThrottle":1200,"kPRoll":10.00,"kPPitch":12.50}"#)
    }

    @Test func balancePayloadUsesDotDecimalSeparator() {
        // ArduinoJson only understands '.', regardless of the phone's region.
        let payload = DroneCommand.startBalance(baseThrottle: 1100, kPRoll: 1.5, kPPitch: 0.25).payload
        #expect(payload.contains("1.50"))
        #expect(!payload.contains("1,50"))
    }

    @Test func startManual() {
        let cmd = DroneCommand.startManual(roll: 1.5, pitch: -2, yaw: 0,
                                           m1: 1000, m2: 1100, m3: 1200, m4: 1300,
                                           voltage: 16.8, batteryPercentage: 100)
        #expect(cmd.payload == #"{"cmd":"START_MANUAL","roll":1.50,"pitch":-2.00,"yaw":0.00,"m1":1000,"m2":1100,"m3":1200,"m4":1300,"voltage":16.80,"batteryPercentage":100}"#)
    }

    @Test func updateManualHasNoCmdKey() {
        let cmd = DroneCommand.updateManual(roll: 0, pitch: 0, yaw: 0,
                                            m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                                            voltage: 16.8, batteryPercentage: 100)
        #expect(!cmd.payload.contains("\"cmd\""))
        #expect(cmd.payload.hasPrefix(#"{"roll":0.00"#))
    }

    @Test func soundCommands() {
        #expect(DroneCommand.startSound(maxPWM: 1400).payload == #"{"cmd":"START_SOUND","maxPWM":1400}"#)
        #expect(DroneCommand.tiltSound(pwm: 1234).payload == #"{"cmd":"TILT_SOUND","pwm":1234}"#)
    }

    @Test(arguments: [
        DroneCommand.arm, .disarm, .stop,
        .startBalance(baseThrottle: 1200, kPRoll: 10, kPPitch: 10),
        .startManual(roll: 0, pitch: 0, yaw: 0, m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                     voltage: 16.8, batteryPercentage: 100),
        .updateManual(roll: 0, pitch: 0, yaw: 0, m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                      voltage: 16.8, batteryPercentage: 100),
        .startSound(maxPWM: 1400), .tiltSound(pwm: 1200),
    ])
    func jsonCommandsAreValidJSON(_ cmd: DroneCommand) throws {
        let object = try JSONSerialization.jsonObject(with: Data(cmd.payload.utf8))
        #expect(object is [String: Any])
    }
}
