import SwiftUI

struct ContentView: View {
    @StateObject private var wsManager = WebSocketManager()
    // One shared motion source for the whole app — Apple recommends a single
    // CMMotionManager per process, so Dashboard and Algorithms both read this one.
    @StateObject private var motionManager = MotionManager()

    var body: some View {
        TabView {
            DashboardView(wsManager: wsManager, motionManager: motionManager)
                .tabItem {
                    Label("Dashboard", systemImage: "gauge.with.dots.needle.bottom.50percent")
                }

            SimulatorView(wsManager: wsManager)
                .tabItem {
                    Label("Simulator", systemImage: "gamecontroller.fill")
                }

            ControlView(wsManager: wsManager, motionManager: motionManager)
                .tabItem {
                    Label("Algorithms", systemImage: "slider.horizontal.3")
                }
        }
        .tint(EasyPilotTheme.accent)
        .preferredColorScheme(.dark)
        .onAppear {
            wsManager.start()
            motionManager.startUpdates()
        }
        .onDisappear {
            wsManager.stop()
            motionManager.stopUpdates()
        }
    }
}

#Preview {
    ContentView()
}
