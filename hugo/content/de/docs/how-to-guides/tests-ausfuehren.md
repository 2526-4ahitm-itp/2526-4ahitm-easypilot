---
title: Tests ausführen
weight: 7
---

{{< tabs >}}
  {{< tab name="iOS" >}}
```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination 'platform=iOS Simulator,name=iPhone 17'
```
Gerätenamen mit `xcrun simctl list devices available` nachsehen.
  {{< /tab >}}
  {{< tab name="Backend" >}}
```bash
cd webinterface/backend && ./mvnw test
```
  {{< /tab >}}
  {{< tab name="Frontend" >}}
```bash
cd webinterface/frontend && npm ci && npm run lint && npm run build
```
  {{< /tab >}}
  {{< tab name="Liftoff-Hover" >}}
```bash
cd simulator/liftoff-hover && python -m unittest -v test_hover.py
```
  {{< /tab >}}
  {{< tab name="Autopilot" >}}
```bash
cd simulator && python -m unittest discover -s autopilot/tests -t . -v
```
  {{< /tab >}}
  {{< tab name="OpenSpec" >}}
```bash
npx @fission-ai/openspec validate --all
```
  {{< /tab >}}
{{< /tabs >}}

Alle laufen auch automatisch in GitHub Actions, siehe [CI/CD](../../explanation/ci-cd).
