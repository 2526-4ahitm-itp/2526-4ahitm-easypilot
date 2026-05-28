import SwiftUI

struct ContentView: View {
    @StateObject private var wsManager = WebSocketManager()

    var body: some View {
        TabView {
            DashboardView(wsManager: wsManager)
                .tabItem {
                    Label("Dashboard", systemImage: "gauge.with.dots.needle.bottom.50percent")
                }

            SimulatorView(wsManager: wsManager)
                .tabItem {
                    Label("Simulator", systemImage: "gamecontroller.fill")
                }

            ControlView(wsManager: wsManager)
                .tabItem {
                    Label("Algorithms", systemImage: "slider.horizontal.3")
                }
        }
        .tint(EasyPilotTheme.accent)
        .onAppear { wsManager.start() }
        .onDisappear { wsManager.stop() }
    }
}

#Preview {
    ContentView()
}
