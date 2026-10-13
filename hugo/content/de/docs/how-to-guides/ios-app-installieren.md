---
title: iOS-App installieren
weight: 2
---

Voraussetzung: Mac mit Xcode 26, iPhone per USB, [`ios-deploy`](https://github.com/ios-control/ios-deploy)
(`brew install ios-deploy`), Apple-Entwicklerteam.

{{% steps %}}

### Geräte-ID herausfinden

```bash
xcrun xctrace list devices
```

### Bauen und installieren

```bash
./deploy.sh <DEVICE_UDID>
```

Das Skript baut mit `xcodebuild` (Team `47D26QX4MF`) und installiert mit `ios-deploy`.
Ohne Argument nimmt es das iPhone des Teams.

### Starten

Beim ersten Start fragt iOS nach **Lokales Netzwerk**: erlauben, sonst kommt der Beacon nicht an.
Im selben WLAN wie der ESP32 verbindet sich die App von selbst. Sonst im Dashboard die IP eingeben.

{{% /steps %}}

## Nur im Simulator

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild build \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination 'platform=iOS Simulator,name=iPhone 17'
```

Im iOS-Simulator kommen UDP-Broadcasts oft nicht an. Für die Drohne ein echtes Gerät nehmen.
