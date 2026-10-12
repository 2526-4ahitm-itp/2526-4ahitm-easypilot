import XCTest

/// Smoke test: the app launches and all three tabs are reachable.
/// No drone is needed — without an ESP32 the app simply stays offline.
final class EasyPilotIOSUITests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testAllTabsAreReachable() throws {
        let app = XCUIApplication()
        app.launch()

        for tab in ["Dashboard", "Simulator", "Algorithms"] {
            let button = app.tabBars.buttons[tab]
            XCTAssertTrue(button.waitForExistence(timeout: 5), "Tab \(tab) missing")
            button.tap()
        }
    }
}
