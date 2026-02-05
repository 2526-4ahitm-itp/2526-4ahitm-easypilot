//
//  ContentView.swift
//  EasyPilotIOSApp
//
//  Created by Eder Simon on 29.01.26.
//

import SwiftUI

struct ContentView: View {
    @StateObject var udpReceiver = UDPReceiver()

    var body: some View {
        VStack(spacing: 20) {
            Text("ESP32 Live Daten")
                .font(.largeTitle)
                .bold()

            Text("Empfangen:")
                .font(.headline)
            Text(udpReceiver.receivedMessage)
                .font(.caption)
                .foregroundColor(.gray)
                .multilineTextAlignment(.center)
                .padding()

            Divider()

            HStack {
                VStack {
                    Text("X")
                        .bold()
                    Text(String(format: "%.2f", udpReceiver.x))
                }
                .frame(maxWidth: .infinity)

                VStack {
                    Text("Y")
                        .bold()
                    Text(String(format: "%.2f", udpReceiver.y))
                }
                .frame(maxWidth: .infinity)

                VStack {
                    Text("Z")
                        .bold()
                    Text(String(format: "%.2f", udpReceiver.z))
                }
                .frame(maxWidth: .infinity)
            }
            .font(.title2)
            .padding()

            // Visualisierung (optional)
            ZStack {
                Circle()
                    .stroke(Color.gray.opacity(0.3), lineWidth: 2)
                    .frame(width: 200, height: 200)

                // Ein kleiner Punkt, der sich basierend auf X und Y bewegt
                Circle()
                    .fill(Color.blue)
                    .frame(width: 20, height: 20)
                    .offset(x: CGFloat(udpReceiver.x * 100), y: CGFloat(udpReceiver.y * 100))
                    .animation(.spring(), value: udpReceiver.x)
                    .animation(.spring(), value: udpReceiver.y)
            }

            Spacer()
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
