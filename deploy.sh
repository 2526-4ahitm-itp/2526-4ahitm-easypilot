#!/bin/bash
# deploy.sh — build EasyPilotIOS and install to iPhone via USB.
# Usage:
#   ./deploy.sh            # uses hardcoded device UDID below
#   ./deploy.sh <UDID>     # override with a different device UDID

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$PROJECT_ROOT/EasyPilotIOS/EasyPilotIOS.xcodeproj"
SCHEME="EasyPilotIOS"
BUILD_DIR="$PROJECT_ROOT/build"
APP_PATH="$BUILD_DIR/Build/Products/Debug-iphoneos/EasyPilotIOS.app"

DEVICE_UDID="${1:-00008110-001578C00252801E}"
DEVELOPMENT_TEAM="47D26QX4MF"

echo "[deploy] Building $SCHEME for device $DEVICE_UDID..."

DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild build \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -destination "id=$DEVICE_UDID" \
  -derivedDataPath "$BUILD_DIR" \
  DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM"

echo "[deploy] Installing $APP_PATH..."
ios-deploy --bundle "$APP_PATH"

echo "[deploy] Done!"
