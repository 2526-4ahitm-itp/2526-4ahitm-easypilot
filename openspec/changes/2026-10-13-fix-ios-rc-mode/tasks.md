## 1. Flight mode

- [ ] 1.1 [GAP] Add `case rc = "RC"` to `FlightMode`
- [ ] 1.2 [GAP] Change `rcModeIsCurrentlyReportedAsIdle` to `rcModeIsReportedAsRC`

## 2. Commands

- [ ] 2.1 [GAP] Add `startRC(kPRoll:kPPitch:)` and `rc(thr:pit:rol:yaw:)` to `DroneCommand` with the existing wire format
- [ ] 2.2 [GAP] Payload tests for both, including the dot decimal separator
- [ ] 2.3 [GAP] Use them in `SimulatorView` instead of string literals

## 3. UI

- [ ] 3.1 [GAP] Algorithms tab: STOP button for every mode except IDLE

## 4. Close

- [ ] 4.1 [SPEC] Run the iOS tests on CI, update status markers, archive the change
