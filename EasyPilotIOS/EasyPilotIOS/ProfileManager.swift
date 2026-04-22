import Foundation

/// Persists named control profiles to UserDefaults.
class ProfileManager: ObservableObject {
    @Published var profiles: [ControlProfile] = []

    private let storageKey = "easypilot.controlProfiles"

    init() { load() }

    // MARK: - CRUD

    func save(_ profile: ControlProfile) {
        if let idx = profiles.firstIndex(where: { $0.id == profile.id }) {
            profiles[idx] = profile
        } else {
            profiles.append(profile)
        }
        persist()
    }

    func delete(_ profile: ControlProfile) {
        profiles.removeAll { $0.id == profile.id }
        persist()
    }

    func rename(_ profile: ControlProfile, to newName: String) {
        guard let idx = profiles.firstIndex(where: { $0.id == profile.id }) else { return }
        profiles[idx].name = newName
        persist()
    }

    // MARK: - Persistence

    private func persist() {
        guard let data = try? JSONEncoder().encode(profiles) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([ControlProfile].self, from: data)
        else { return }
        profiles = decoded
    }
}
