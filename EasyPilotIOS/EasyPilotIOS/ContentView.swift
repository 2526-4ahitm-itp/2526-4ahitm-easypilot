import SwiftUI

struct ContentView: View {
    @StateObject private var wsManager = WebSocketManager()

    var body: some View {
        TabView {
            DashboardView(wsManager: wsManager)
                .tabItem {
                    Label("Dashboard", systemImage: "gauge.with.dots.needle.bottom.50percent")
                }

            ControlView(wsManager: wsManager)
                .tabItem {
                    Label("Control", systemImage: "slider.horizontal.3")
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
