---
title: EasyPilot
layout: hextra-home
---

<div class="hx:mt-6 hx:mb-6">
{{< hextra/hero-headline >}}
  Drohnen fliegen,&nbsp;<br class="hx:sm:block hx:hidden" />auch wenn die Drohne nicht fliegt
{{< /hextra/hero-headline >}}
</div>

<div class="hx:mb-12">
{{< hextra/hero-subtitle >}}
  EasyPilot verbindet eine FPV-Drohne mit einer iOS-App und baut seit Phase 2&nbsp;<br class="hx:sm:block hx:hidden" />eine Drohnensimulation mit Physik-Engine. Diplomarbeit 4AHITM, HTL Leonding.
{{< /hextra/hero-subtitle >}}
</div>

<div class="hx:mb-6">
    <span class="hx:mr-2">{{< hextra/hero-button text="Projektstand" link="slides/projektstand" >}}</span>
    <span class="hx:mr-2">{{< hextra/hero-button text="Dokumentation" link="docs" >}}</span>
    {{< hextra/hero-button text="Phase 2: Simulation" link="docs/explanation/phase-2" style="background-color: #64748b;" >}}
</div>

<div class="hx:mt-6"></div>

{{< hextra/feature-grid >}}
  {{< hextra/feature-card
    title="Drohne & Firmware"
    subtitle="ESP32-C3 als Companion am Betaflight-Flight-Controller: MSP über UART, WebSocket und UDP-Beacon im WLAN, fünf Flugmodi mit Watchdogs."
    link="docs/explanation/kommunikation"
  >}}
  {{< hextra/feature-card
    title="iOS-App"
    subtitle="Live-Telemetrie mit 3D-Modell, Algorithmen-Tuning mit Profilen und ein Simulator mit virtuellen Joysticks und POSHOLD."
    link="docs/explanation/ios-app"
  >}}
  {{< hextra/feature-card
    title="Simulation (Phase 2)"
    subtitle="Hover-Autopilot auf dem FPV-Simulator Liftoff als Prototyp, Web-Simulator mit Physik-Engine für die LeoCloud in Arbeit."
    link="docs/explanation/phase-2"
  >}}
{{< /hextra/feature-grid >}}
