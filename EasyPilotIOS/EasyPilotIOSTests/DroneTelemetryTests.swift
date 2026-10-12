import Foundation
import Testing
@testable import EasyPilotIOS

struct DroneTelemetryTests {

    private func decode(_ json: String) throws -> DroneTelemetry {
        try JSONDecoder().decode(DroneTelemetry.self, from: Data(json.utf8))
    }

    @Test func decodesFullFirmwarePacket() throws {
        let t = try decode(#"""
        {"roll":1.5,"pitch":-2.0,"yaw":90.0,"m1":1000,"m2":1010,"m3":1020,"m4":1030,
         "voltage":16.8,"batteryPercentage":100,"armed":true,"mode":"BALANCE","fc":true}
        """#)
        #expect(t.roll == 1.5)
        #expect(t.pitch == -2.0)
        #expect(t.m4 == 1030)
        #expect(t.armed == true)
        #expect(t.mode == "BALANCE")
        #expect(t.fc == true)
    }

    @Test func decodesMinimalTelemetry() throws {
        let t = try decode(#"{"roll":0,"pitch":0,"yaw":0}"#)
        #expect(t.m1 == nil)
        #expect(t.voltage == nil)
        #expect(t.armed == nil)
        #expect(t.mode == nil)
        #expect(t.fc == nil)
    }

    @Test func rejectsPacketWithoutAttitude() {
        #expect(throws: DecodingError.self) {
            try decode(#"{"m1":1000}"#)
        }
    }

    @Test func ignoresUnknownFields() throws {
        let t = try decode(#"{"roll":0,"pitch":0,"yaw":0,"newField":42}"#)
        #expect(t.roll == 0)
    }
}
