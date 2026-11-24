import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { IFCLoader } from "web-ifc-three/IFCLoader";
import { fetchGlbBuffer, fetchIfcBuffer } from "../api/client";
import { useProjectSessionStore } from "../stores/projectSessionStore";
import { useUiStore } from "../stores/uiStore";
import { entranceTransition, softItem } from "../utils/motion";

const WASM_PATH = `${import.meta.env.BASE_URL}wasm/`;

// --- TWEAKABLE CAMERA SETTINGS ---
// Tweak these coordinate values (multipliers based on the model's size) 
// to get the desired starting camera position.
const CAMERA_START_X = 1.4;
const CAMERA_START_Y = 0.4;
const CAMERA_START_Z = 1.4;

// ---------------------------------

function extractExpressId(hit: THREE.Intersection): string | null {
  const mesh = hit.object as THREE.Mesh & { modelID?: number };
  const faceIndex = hit.faceIndex;
  if (mesh.modelID != null && faceIndex != null && mesh.geometry) {
    const geo = mesh.geometry as THREE.BufferGeometry & {
      attributes: { expressID?: THREE.BufferAttribute };
    };
    const exp = geo.attributes.expressID;
    if (exp) {
      const id = exp.getX(faceIndex);
      if (id) return String(id);
    }
  }

  let obj: THREE.Object3D | null = hit.object;
  while (obj) {
    const name = obj.name?.trim();
    if (name && /^\d+$/.test(name)) return name;
    const tagged = obj as THREE.Object3D & { expressID?: number };
    if (typeof tagged.expressID === "number") return String(tagged.expressID);
    obj = obj.parent;
  }
  return null;
}

function fitCameraToModel(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  root: THREE.Object3D,
) {
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z) || 10;

  root.position.sub(center); // Center the model
  
  controls.target.set(0, 0, 0);
  camera.position.set(radius * CAMERA_START_X, radius * CAMERA_START_Y, radius * CAMERA_START_Z);
  camera.near = Math.max(0.01, radius / 500);
  camera.far = radius * 500;
  camera.updateProjectionMatrix();
  controls.update();
}

type CADViewerProps = {
  projectId: string;
  sourceFormat?: string | null;
  previewStatus?: string | null;
  previewError?: string | null;
};

export function CADViewer({ projectId, sourceFormat, previewStatus, previewError }: CADViewerProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const setSelectedElementId = useUiStore((s) => s.setSelectedElementId);
  const localBuffer = useProjectSessionStore((s) => s.localIfcBuffers[projectId]);
  const isIfc = !sourceFormat || sourceFormat.replace(/^\./, "").toLowerCase() === "ifc";

  const [phase, setPhase] = useState<"idle" | "waiting" | "loading" | "ready" | "error">("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [loadPct, setLoadPct] = useState(0);

  useEffect(() => {
    const stepPreviewReady = previewStatus === "ready";
    if (!isIfc && !stepPreviewReady) {
      setSelectedElementId(null);
      setPhase(previewStatus === "failed" ? "error" : "waiting");
      setErrorText(previewStatus === "failed" ? previewError ?? "We could not make a 3D preview from this STEP/STP file." : null);
      return undefined;
    }

    setPhase("idle");
    setErrorText(null);

    const mount = mountRef.current;
    if (!mount) return undefined;

    let cancelled = false;
    let raf = 0;
    let renderer: THREE.WebGLRenderer | null = null;
    let controls: OrbitControls | null = null;
    let modelRoot: THREE.Object3D | null = null;
    let ifcLoader: IFCLoader | null = null;
    let ifcModelId: number | null = null;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x030a18);

    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 5000);
    camera.position.set(18, 14, 22);

    scene.add(new THREE.HemisphereLight(0xbfdcff, 0x223354, 1.05));
    const dir = new THREE.DirectionalLight(0xffffff, 1.05);
    dir.position.set(40, 80, 30);
    scene.add(dir);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const resize = () => {
      if (!renderer || !mount) return;
      const w = mount.clientWidth || 1;
      const h = mount.clientHeight || 1;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };

    const pick = (ev: PointerEvent) => {
      if (!renderer || cancelled || !modelRoot) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObject(modelRoot, true);
      if (!hits.length) {
        setSelectedElementId(null);
        return;
      }
      const id = extractExpressId(hits[0]!);
      setSelectedElementId(id);
    };

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1;
    mount.replaceChildren(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(mount);

    const loop = () => {
      if (cancelled || !renderer || !controls) return;
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };

    let ticker: ReturnType<typeof setInterval> | undefined;

    const loadModel = async () => {
      setPhase("loading");
      setLoadPct(0);
      setErrorText(null);

      let simulatedPct = 0;
      ticker = setInterval(() => {
        if (cancelled) {
          clearInterval(ticker);
          return;
        }
        simulatedPct = Math.min(simulatedPct + (92 - simulatedPct) * 0.07, 92);
        setLoadPct(Math.round(simulatedPct));
      }, 280);

      if (isIfc) {
        let buffer = localBuffer;
        if (!buffer) {
          buffer = await fetchIfcBuffer(projectId);
        }
        if (cancelled) return;

        ifcLoader = new IFCLoader();
        await ifcLoader.ifcManager.setWasmPath(WASM_PATH);
        await ifcLoader.ifcManager.applyWebIfcConfig({
          USE_FAST_BOOLS: true,
          COORDINATE_TO_ORIGIN: true,
        });
        if (cancelled) return;

        const model = await ifcLoader.parse(buffer.slice(0));
        ifcModelId = model.modelID;
        modelRoot = model;
        scene.add(model);
      } else {
        const buffer = await fetchGlbBuffer(projectId);
        if (cancelled) return;
        const loader = new GLTFLoader();
        const gltf = await new Promise<{ scene: THREE.Group }>((resolve, reject) => {
          loader.parse(buffer, "", resolve, reject);
        });
        if (cancelled) return;
        modelRoot = gltf.scene;
        scene.add(gltf.scene);
      }

      clearInterval(ticker);
      ticker = undefined;

      fitCameraToModel(camera, controls!, modelRoot);

      renderer!.domElement.style.cursor = "pointer";
      renderer!.domElement.addEventListener("pointerdown", pick);

      setLoadPct(100);
      loop();
      setPhase("ready");
    };

    // Let the workspace slide in before loading a large model.
    const timer = setTimeout(() => {
      if (!cancelled) {
        void loadModel().catch((err) => {
          if (ticker) clearInterval(ticker);
          if (!cancelled) {
            setPhase("error");
            setErrorText(err instanceof Error ? err.message : String(err));
          }
        });
      }
    }, 950);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (ticker) clearInterval(ticker);
      cancelAnimationFrame(raf);
      ro.disconnect();
      try {
        renderer?.domElement.removeEventListener("pointerdown", pick);
      } catch {
        /* noop */
      }
      if (ifcLoader && ifcModelId != null) {
        try {
          ifcLoader.ifcManager.close(ifcModelId);
        } catch {
          /* noop */
        }
      }
      controls?.dispose();
      renderer?.dispose();
      mount.replaceChildren();
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        mesh.geometry?.dispose();
        const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (!mat) return;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else mat.dispose();
      });
    };
  }, [projectId, localBuffer, setSelectedElementId, isIfc, previewStatus, previewError]);

  return (
    <div className="viewer-pane" style={{ position: "relative", height: "100%" }}>
      <div ref={mountRef} className="viewer-frame" />

      <AnimatePresence>
        {phase === "loading" && (
          <>
            <motion.div className="viewer-shimmer" aria-hidden="true" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={entranceTransition} />
            <motion.div className="viewer-overlay" initial="hidden" animate="show" exit="exit" variants={softItem} transition={entranceTransition}>
              <div className="viewer-overlay-inner">
                <div className="viewer-progress-label">{loadPct}%</div>
                <div className="viewer-progress-track">
                  <div className="viewer-progress-fill" style={{ width: `${loadPct}%` }} />
                </div>
                <div className="muted" style={{ textAlign: "center", fontSize: "0.8rem", marginTop: "0.4rem" }}>
                  {isIfc ? (localBuffer ? "Loading local IFC…" : "Loading IFC model…") : "Loading STEP/STP preview…"}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {phase === "waiting" && (
          <motion.div className="viewer-overlay" initial="hidden" animate="show" exit="exit" variants={softItem} transition={entranceTransition}>
            <div className="viewer-overlay-inner muted">
              Making a 3D preview for your STEP/STP file…
              <div style={{ marginTop: "0.35rem", color: "#fcfefe", fontSize: "0.85rem" }}>
                Think of it like packing a CAD model into a lighter box the browser can open.
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {phase === "error" && (
          <motion.div className="viewer-overlay" initial="hidden" animate="show" exit="exit" variants={softItem} transition={entranceTransition}>
            <div className="viewer-overlay-inner muted">
              Viewer could not load this model.
              <div style={{ marginTop: "0.35rem", color: "#fcfefe", fontSize: "0.85rem" }}>{errorText}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
