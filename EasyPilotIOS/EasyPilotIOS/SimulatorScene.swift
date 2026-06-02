import SwiftUI
import SceneKit

enum SimCamera { case fpv, chase }

/// UIViewRepresentable that owns the full 3D simulator world.
/// The Coordinator is the SCNSceneRendererDelegate and drives physics + propeller animation.
struct SimulatorScene: UIViewRepresentable {

    let sim: DroneSimulator
    var activeCamera: SimCamera

    func makeUIView(context: Context) -> SCNView {
        let v = SCNView()
        v.scene             = context.coordinator.scene
        v.delegate          = context.coordinator
        v.isPlaying         = true
        v.allowsCameraControl = false
        v.showsStatistics   = false
        v.antialiasingMode  = .multisampling2X
        v.backgroundColor   = UIColor(red: 0.49, green: 0.77, blue: 0.93, alpha: 1)
        context.coordinator.scnView = v
        context.coordinator.applyCamera(activeCamera)
        return v
    }

    func updateUIView(_ uiView: SCNView, context: Context) {
        context.coordinator.applyCamera(activeCamera)
    }

    func makeCoordinator() -> Coordinator { Coordinator(sim: sim) }

    // MARK: - Coordinator

    class Coordinator: NSObject, SCNSceneRendererDelegate {

        let sim: DroneSimulator
        let scene = SCNScene()
        weak var scnView: SCNView?

        // Scene nodes
        let droneNode  = SCNNode()
        let chaseCam   = SCNNode()
        let fpvCam     = SCNNode()
        var props:      [SCNNode] = []   // Prop_1 … Prop_4, indexed 0-3
        var shadowNode  = SCNNode()
        var altLineNode = SCNNode()

        // Prop spin: M1 CW, M2 CCW, M3 CCW, M4 CW (Betaflight X layout)
        private let propDirs: [CGFloat] = [1, -1, -1, 1]

        // Render-loop state
        private var lastRenderTime: TimeInterval = 0
        private var syncAccum: Float = 0
        private let syncInterval: Float = 1.0 / 20   // sync @Published at 20 Hz

        init(sim: DroneSimulator) {
            self.sim = sim
            super.init()
            buildScene()
        }

        // MARK: - Scene construction

        private func buildScene() {
            setupLighting()
            setupGround()
            setupLandmarks()
            setupShadowAndLine()
            setupGates()
            setupDrone()
            setupChaseCamera()
        }

        private func setupLighting() {
            let amb = SCNLight()
            amb.type = .ambient
            amb.intensity = 550
            let ambNode = SCNNode(); ambNode.light = amb
            scene.rootNode.addChildNode(ambNode)

            let sun = SCNLight()
            sun.type = .directional
            sun.intensity = 900
            sun.castsShadow = false
            let sunNode = SCNNode(); sunNode.light = sun
            sunNode.eulerAngles = SCNVector3(-0.7, 0.5, 0)
            scene.rootNode.addChildNode(sunNode)
        }

        private func setupGround() {
            // SCNFloor = infinite plane at y = 0; no reflections for performance
            let floor = SCNFloor()
            floor.reflectivity = 0
            let mat = SCNMaterial()
            mat.diffuse.contents  = UIColor(red: 0.20, green: 0.48, blue: 0.20, alpha: 1)
            mat.roughness.contents = NSNumber(value: 1.0)
            floor.materials = [mat]
            scene.rootNode.addChildNode(SCNNode(geometry: floor))

            // Subtle horizon fog to sell depth without overdraw
            scene.fogColor        = UIColor(red: 0.49, green: 0.77, blue: 0.93, alpha: 1)
            scene.fogStartDistance = 60
            scene.fogEndDistance   = 180
        }

        // MARK: - Landmarks

        private func setupLandmarks() {
            addHomePad()
            addCardinalTower(x:   0, z: -20, color: UIColor(red: 0.20, green: 0.85, blue: 0.40, alpha: 1), label: "N")
            addCardinalTower(x:   0, z:  20, color: UIColor(red: 0.25, green: 0.60, blue: 1.00, alpha: 1), label: "S")
            addCardinalTower(x:  20, z:   0, color: UIColor(red: 1.00, green: 0.25, blue: 0.25, alpha: 1), label: "E")
            addCardinalTower(x: -20, z:   0, color: UIColor(red: 1.00, green: 0.70, blue: 0.10, alpha: 1), label: "W")
            addDistanceRing(radius: 10)
            addDistanceRing(radius: 20)
            addTrees()
        }

        private func addHomePad() {
            // Orange launch disc
            let disc = SCNCylinder(radius: 1.4, height: 0.03)
            let discMat = SCNMaterial()
            discMat.diffuse.contents = UIColor(red: 1.0, green: 0.50, blue: 0.0, alpha: 1)
            disc.materials = [discMat]
            let discNode = SCNNode(geometry: disc)
            discNode.position = SCNVector3(0, 0.015, 0)
            scene.rootNode.addChildNode(discNode)

            // White H marking — two uprights + crossbar
            func slab(w: CGFloat, d: CGFloat, dx: Float, dz: Float) -> SCNNode {
                let g = SCNBox(width: w, height: 0.04, length: d, chamferRadius: 0)
                g.firstMaterial?.diffuse.contents = UIColor.white
                let n = SCNNode(geometry: g)
                n.position = SCNVector3(dx, 0.04, dz)
                return n
            }
            scene.rootNode.addChildNode(slab(w: 0.14, d: 0.80, dx: -0.32, dz: 0))
            scene.rootNode.addChildNode(slab(w: 0.14, d: 0.80, dx:  0.32, dz: 0))
            scene.rootNode.addChildNode(slab(w: 0.66, d: 0.14, dx:  0.00, dz: 0))
        }

        private func addCardinalTower(x: Float, z: Float, color: UIColor, label: String) {
            // White pole
            let pole = SCNCylinder(radius: 0.06, height: 4.0)
            pole.firstMaterial?.diffuse.contents = UIColor(white: 0.9, alpha: 1)
            let poleNode = SCNNode(geometry: pole)
            poleNode.position = SCNVector3(x, 2.0, z)
            scene.rootNode.addChildNode(poleNode)

            // Colored band near top
            let band = SCNCylinder(radius: 0.07, height: 0.55)
            band.firstMaterial?.diffuse.contents = color
            let bandNode = SCNNode(geometry: band)
            bandNode.position = SCNVector3(x, 3.6, z)
            scene.rootNode.addChildNode(bandNode)

            // Ball finial
            let ball = SCNSphere(radius: 0.18)
            ball.firstMaterial?.diffuse.contents = color
            ball.firstMaterial?.emission.contents = color.withAlphaComponent(0.3)
            let ballNode = SCNNode(geometry: ball)
            ballNode.position = SCNVector3(x, 4.22, z)
            scene.rootNode.addChildNode(ballNode)
        }

        private func addDistanceRing(radius: CGFloat) {
            // Flat torus lying on the ground
            let ring = SCNTorus(ringRadius: radius, pipeRadius: 0.05)
            let mat = SCNMaterial()
            mat.diffuse.contents = UIColor(white: 1.0, alpha: 0.22)
            ring.materials = [mat]
            let ringNode = SCNNode(geometry: ring)
            ringNode.position = SCNVector3(0, 0.05, 0)
            scene.rootNode.addChildNode(ringNode)
        }

        private func addTrees() {
            // Fixed positions to avoid random — enough variety to read depth
            let pts: [(Float, Float, Float)] = [
                ( 8, -13, 2.6), (-11, -15, 3.1), ( 16,  -9, 2.3), (-16, -11, 3.4),
                (13,   9, 2.8), ( -9,  13, 2.1), ( 19,  16, 3.0), (-19,   8, 2.5),
                ( 7, -21, 2.9), (-13,  21, 2.2), ( 24,  -4, 3.3), (-23,  11, 2.7),
                (14, -28, 2.4), ( -5,  28, 3.2)
            ]
            for (x, z, h) in pts { addTree(x: x, z: z, height: h) }
        }

        private func addTree(x: Float, z: Float, height: Float) {
            let trunkH = height * 0.38
            let trunk = SCNCylinder(radius: 0.10, height: CGFloat(trunkH))
            trunk.firstMaterial?.diffuse.contents = UIColor(red: 0.34, green: 0.21, blue: 0.09, alpha: 1)
            let trunkNode = SCNNode(geometry: trunk)
            trunkNode.position = SCNVector3(x, trunkH * 0.5, z)
            scene.rootNode.addChildNode(trunkNode)

            let foliageH = height * 0.75
            let foliage = SCNCone(topRadius: 0, bottomRadius: CGFloat(height * 0.32), height: CGFloat(foliageH))
            foliage.firstMaterial?.diffuse.contents = UIColor(red: 0.11, green: 0.42, blue: 0.13, alpha: 1)
            let foliageNode = SCNNode(geometry: foliage)
            foliageNode.position = SCNVector3(x, trunkH + foliageH * 0.5, z)
            scene.rootNode.addChildNode(foliageNode)
        }

        // MARK: - Shadow + altitude line

        private func setupShadowAndLine() {
            let shadowGeo = SCNCylinder(radius: 0.6, height: 0.001)
            let shadowMat = SCNMaterial()
            shadowMat.diffuse.contents  = UIColor(white: 0, alpha: 0.45)
            shadowMat.lightingModel     = .constant
            shadowGeo.materials         = [shadowMat]
            shadowNode = SCNNode(geometry: shadowGeo)
            shadowNode.position = SCNVector3(0, 0.012, 0)
            scene.rootNode.addChildNode(shadowNode)

            let lineGeo = SCNCylinder(radius: 0.012, height: 1.0)
            let lineMat = SCNMaterial()
            lineMat.diffuse.contents = UIColor(white: 1, alpha: 0.30)
            lineMat.lightingModel    = .constant
            lineGeo.materials        = [lineMat]
            altLineNode = SCNNode(geometry: lineGeo)
            altLineNode.isHidden = true
            scene.rootNode.addChildNode(altLineNode)
        }

        // MARK: - Racing gates

        private func setupGates() {
            // Four gates roughly on the 17 m radius, alternating colors + yaw
            let configs: [(x: Float, z: Float, h: Float, ry: Float, orange: Bool)] = [
                ( 17,  0,  2.0, 0,            true),
                (-17,  0,  1.8, 0,            false),
                (  0, 17,  2.2, .pi / 2,      false),
                (  0,-17,  1.6, .pi / 2,      true),
            ]
            for c in configs { addGate(x: c.x, z: c.z, height: c.h, rotY: c.ry, orange: c.orange) }
        }

        private func addGate(x: Float, z: Float, height: Float, rotY: Float, orange: Bool) {
            let color: UIColor = orange
                ? UIColor(red: 1.0, green: 0.40, blue: 0.0, alpha: 1)
                : UIColor(white: 0.92, alpha: 1)
            let w: Float   = 2.4
            let postR: CGFloat = 0.08

            let gateNode = SCNNode()
            gateNode.position    = SCNVector3(x, 0, z)
            gateNode.eulerAngles = SCNVector3(0, rotY, 0)

            func post(_ xOff: Float) -> SCNNode {
                let g = SCNCylinder(radius: postR, height: CGFloat(height))
                g.firstMaterial?.diffuse.contents = color
                let n = SCNNode(geometry: g)
                n.position = SCNVector3(xOff, height * 0.5, 0)
                return n
            }

            let topBar = SCNBox(width: CGFloat(w + 0.16), height: 0.12, length: postR * 2, chamferRadius: 0)
            topBar.firstMaterial?.diffuse.contents = color
            let topNode = SCNNode(geometry: topBar)
            topNode.position = SCNVector3(0, height, 0)

            gateNode.addChildNode(post(-w / 2))
            gateNode.addChildNode(post( w / 2))
            gateNode.addChildNode(topNode)
            scene.rootNode.addChildNode(gateNode)
        }

        private func setupDrone() {
            // Load USDZ model
            if let url = Bundle.main.url(forResource: "drohne-compressed", withExtension: "usdz"),
               let loaded = try? SCNScene(url: url, options: nil) {

                let model = loaded.rootNode.clone()
                // Scale: model is ~1.66 units wide at scale 1; 0.2 → ~33cm (realistic 5" quad)
                model.scale = SCNVector3(0.2, 0.2, 0.2)
                droneNode.addChildNode(model)

                // Grab propeller nodes and start a stopped spin action on each
                let names = ["Prop_1", "Prop_2", "Prop_3", "Prop_4"]
                for (i, name) in names.enumerated() {
                    guard let node = model.childNode(withName: name, recursively: true) else { continue }
                    props.append(node)
                    // One full rotation in 1 s; speed multiplier set each frame
                    let spin = SCNAction.repeatForever(
                        SCNAction.rotateBy(x: 0, y: propDirs[i] * .pi * 2, z: 0, duration: 1.0)
                    )
                    node.runAction(spin, forKey: "spin")
                    node.action(forKey: "spin")?.speed = 0   // start stopped
                }
            }

            // FPV camera — child of droneNode, so it inherits all transforms
            fpvCam.camera               = SCNCamera()
            fpvCam.camera!.fieldOfView  = 110        // wide-angle FPV
            fpvCam.camera!.zNear        = 0.01
            fpvCam.camera!.zFar         = 300
            fpvCam.position             = SCNVector3(0, 0.04, -0.15)   // front + slightly up
            fpvCam.eulerAngles          = SCNVector3(0.26, 0, 0)        // 15° up tilt
            droneNode.addChildNode(fpvCam)

            droneNode.position = SCNVector3(0, DroneSimulator.groundLevel, 0)
            scene.rootNode.addChildNode(droneNode)
        }

        private func setupChaseCamera() {
            chaseCam.camera               = SCNCamera()
            chaseCam.camera!.fieldOfView  = 72
            chaseCam.camera!.zNear        = 0.1
            chaseCam.camera!.zFar         = 300
            chaseCam.position             = SCNVector3(0, 1.5, 3.5)

            // Look-at constraint keeps camera pointing at drone regardless of position
            let look = SCNLookAtConstraint(target: droneNode)
            look.isGimbalLockEnabled = true
            chaseCam.constraints = [look]

            scene.rootNode.addChildNode(chaseCam)
        }

        // MARK: - Camera switching

        func applyCamera(_ cam: SimCamera) {
            scnView?.pointOfView = cam == .fpv ? fpvCam : chaseCam
        }

        // MARK: - SCNSceneRendererDelegate

        func renderer(_ renderer: SCNSceneRenderer, updateAtTime time: TimeInterval) {
            let dt: Float
            if lastRenderTime == 0 {
                dt = 1.0 / 60.0
            } else {
                dt = Float(min(time - lastRenderTime, 0.05))   // cap at 50 ms
            }
            lastRenderTime = time

            // Physics update (render thread)
            sim.tick(dt: dt)

            // Snapshot internal state (avoiding repeated property access in closures)
            let pos   = sim._pos
            let roll  = Float(sim._roll)
            let pitch = Float(sim._pitch)
            let yaw   = Float(sim._yaw)
            let motors = [sim.mFil1, sim.mFil2, sim.mFil3, sim.mFil4]

            // --- Drone node transform ---
            droneNode.position    = SCNVector3(pos.x, pos.y, pos.z)
            // eulerAngles order in SceneKit: X (pitch), Y (yaw), Z (roll)
            droneNode.eulerAngles = SCNVector3(
                 pitch * .pi / 180,
                -yaw   * .pi / 180,
                -roll  * .pi / 180
            )

            // --- Ground shadow + altitude line ---
            let alt = max(0, pos.y - DroneSimulator.groundLevel)
            shadowNode.position = SCNVector3(pos.x, 0.012, pos.z)
            let shadowScale = CGFloat(max(0.15, 1.0 - alt * 0.06))
            shadowNode.scale   = SCNVector3(shadowScale, 1, shadowScale)
            shadowNode.opacity = CGFloat(max(0, 0.55 - alt * 0.035))

            if alt > 0.12 {
                altLineNode.isHidden = false
                altLineNode.position = SCNVector3(pos.x, DroneSimulator.groundLevel + alt * 0.5, pos.z)
                altLineNode.scale    = SCNVector3(1, alt, 1)
            } else {
                altLineNode.isHidden = true
            }

            // --- Propeller spin speed (action speed = rev/s) ---
            for (i, node) in props.enumerated() {
                let t = Float(max(0.0, motors[i] - 1000.0)) / 1000.0   // 0…1
                node.action(forKey: "spin")?.speed = CGFloat(t * 25)  // up to 25 rev/s
            }

            // --- Chase camera: lerp behind + above drone based on yaw ---
            let theta   = Float(-yaw) * .pi / 180   // matches droneNode rotation
            let behind: Float = 2.0
            let above:  Float = 0.9
            let tx = pos.x + sin(theta) * behind
            let ty = pos.y + above
            let tz = pos.z + cos(theta) * behind
            let lf: Float = min(1.0, dt * 3.5)   // lag factor, feels like inertia
            let cp = chaseCam.position
            chaseCam.position = SCNVector3(
                cp.x + (tx - cp.x) * lf,
                cp.y + (ty - cp.y) * lf,
                cp.z + (tz - cp.z) * lf
            )

            // --- Sync @Published to SwiftUI at 20 Hz ---
            syncAccum += dt
            if syncAccum >= syncInterval {
                syncAccum = 0
                DispatchQueue.main.async { [weak self] in
                    self?.sim.syncPublished()
                }
            }
        }
    }
}
