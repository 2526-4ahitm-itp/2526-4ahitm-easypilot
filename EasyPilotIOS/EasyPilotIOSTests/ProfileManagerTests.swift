import Foundation
import Testing
@testable import EasyPilotIOS

struct ProfileManagerTests {

    /// Isolated defaults per test, so tests never touch real app data.
    private func freshDefaults() -> UserDefaults {
        let suite = "ProfileManagerTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
        return defaults
    }

    @Test func savedProfileSurvivesRestart() {
        let defaults = freshDefaults()
        let profile = ControlProfile(name: "Hover", mode: "BALANCE", baseThrottle: 1300)
        ProfileManager(defaults: defaults).save(profile)

        #expect(ProfileManager(defaults: defaults).profiles == [profile])
    }

    @Test func savingSameIdReplacesInsteadOfDuplicating() {
        let manager = ProfileManager(defaults: freshDefaults())
        var profile = ControlProfile(name: "A")
        manager.save(profile)
        profile.kPRoll = 20
        manager.save(profile)

        #expect(manager.profiles.count == 1)
        #expect(manager.profiles.first?.kPRoll == 20)
    }

    @Test func renameAndDeletePersist() {
        let defaults = freshDefaults()
        let manager = ProfileManager(defaults: defaults)
        let a = ControlProfile(name: "A")
        let b = ControlProfile(name: "B")
        manager.save(a); manager.save(b)

        manager.rename(a, to: "Renamed")
        manager.delete(b)

        #expect(ProfileManager(defaults: defaults).profiles.map(\.name) == ["Renamed"])
    }

    @Test func corruptStoredDataStartsEmpty() {
        let defaults = freshDefaults()
        defaults.set(Data("not json".utf8), forKey: "easypilot.controlProfiles")
        #expect(ProfileManager(defaults: defaults).profiles.isEmpty)
    }
}
