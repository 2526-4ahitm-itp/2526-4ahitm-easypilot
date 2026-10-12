import Testing
@testable import EasyPilotIOS

struct FlightModeTests {

    @Test func parsesFirmwareStrings() {
        #expect(FlightMode(rawOrIdle: "IDLE") == .idle)
        #expect(FlightMode(rawOrIdle: "BALANCE") == .balance)
        #expect(FlightMode(rawOrIdle: "MANUAL") == .manual)
        #expect(FlightMode(rawOrIdle: "SOUND") == .sound)
    }

    @Test func unknownModeFallsBackToIdle() {
        #expect(FlightMode(rawOrIdle: nil) == .idle)
        #expect(FlightMode(rawOrIdle: "") == .idle)
        #expect(FlightMode(rawOrIdle: "balance") == .idle)   // case-sensitive like the firmware
        #expect(FlightMode(rawOrIdle: "foo") == .idle)
    }

    /// Documents the bug fixed in AP7. Flip this test when AP7 lands.
    @Test func rcModeIsCurrentlyReportedAsIdle() {
        #expect(FlightMode(rawOrIdle: "RC") == .idle)
    }

    @Test func rawValuesRoundTrip() {
        for mode in FlightMode.allCases {
            #expect(FlightMode(rawOrIdle: mode.rawValue) == mode)
        }
    }
}
