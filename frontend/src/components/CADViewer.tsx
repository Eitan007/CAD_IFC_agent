import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { IFCLoader } from "web-ifc-three/IFCLoader";
import { ifcAssetUrl } from "../api/client";
import { useUiStore } from "../stores/uiStore";

/** web-ifc only prefixes `.wasm` with wasmPath; pthread worker URLs use IFC fetch dirname → breaks when IFC is `/api/.../ifc`. */
function makeIfcLocateFile(wasmAssetsRoot: string) {
  return (path: string, prefix: string): string => {
    const name = path.includes("/") ? path.slice(path.lastIndexOf("/") + 1) : path;
    if (name.endsWith(".wasm") || name.endsWith(".worker.js")) {
      return wasmAssetsRoot + name;
    }
    return prefix + path;
  };
}

function extractExpressId(hit: THREE.Intersection): string | null {
  const mesh = hit.object as THREE.Mesh;
  const geo = mesh.geometry as THREE.BufferGeometry & { expressID?: number };
  if (typeof geo?.expressID === "number") return String(geo.expressID);

  let obj: THREE.Object3D | null = hit.object;
  while (obj) {
    const tagged = obj as unknown as { expressID?: number };
    if (typeof tagged.expressID === "number") return String(tagged.expressID);
    obj = obj.parent;
  }
  return null;
}

export function CADViewer({ projectId }: { projectId: string }) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const setSelectedElementId = useUiStore((s) => s.setSelectedElementId);

  const [phase, setPhase] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [loadPct, setLoadPct] = useState(0);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    let cancelled = false;
    let raf = 0;
    let renderer: THREE.WebGLRenderer | null = null;
    let controls: OrbitControls | null = null;
    let loader: IFCLoader | null = null;
    let ifcRoot: THREE.Object3D | null = null;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x031536);

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
      if (!renderer || cancelled || !ifcRoot) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(ifcRoot.children, true);
      if (!hits.length) {
        setSelectedElementId(null);
        return;
      }
      const id = extractExpressId(hits[0]!);
      setSelectedElementId(id);
    };

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    // three r149 uses outputEncoding + sRGBEncoding (outputColorSpace / SRGBColorSpace arrived in r152)
    (renderer as unknown as { outputEncoding: number }).outputEncoding =
      (THREE as unknown as { sRGBEncoding: number }).sRGBEncoding;
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

    void (async () => {
      try {
        setPhase("loading");
        setLoadPct(0);
        setErrorText(null);

        loader = new IFCLoader();
        const base =
          import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
        const wasmAssetsRoot = `${window.location.origin}${base}web-ifc/`;
        await loader.ifcManager.setWasmPath(`${base}web-ifc/`);

        const api = loader.ifcManager.ifcAPI;
        if (!api.wasmModule) {
          await (
            api.Init as unknown as (locate?: (path: string, prefix: string) => string) => Promise<void>
          )(makeIfcLocateFile(wasmAssetsRoot));
        }

        // Simulate smooth progress since web-ifc doesn't expose byte-level progress
        let simulatedPct = 0;
        const ticker = setInterval(() => {
          if (cancelled) { clearInterval(ticker); return; }
          simulatedPct = Math.min(simulatedPct + (95 - simulatedPct) * 0.06, 94);
          setLoadPct(Math.round(simulatedPct));
        }, 300);

        const model = await new Promise<THREE.Object3D>((resolve, reject) =>
          (loader as unknown as { load: (url: string, onLoad: (m: THREE.Object3D) => void, onProgress: unknown, onError: (e: unknown) => void) => void })
            .load(ifcAssetUrl(projectId), resolve, undefined, reject)
        );
        clearInterval(ticker);
        if (cancelled) return;

        setLoadPct(100);
        ifcRoot = model;

        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const radius = Math.max(size.x, size.y, size.z) || 10;

        controls!.target.copy(center);
        camera.position.copy(center.clone().add(new THREE.Vector3(radius * 1.4, radius * 1.1, radius * 1.4)));
        camera.near = Math.max(0.01, radius / 500);
        camera.far = radius * 500;
        camera.updateProjectionMatrix();

        scene.add(model);

        renderer!.domElement.style.cursor = "pointer";
        renderer!.domElement.addEventListener("pointerdown", pick);

        loop();
        setPhase("ready");
      } catch (err) {
        if (!cancelled) {
          setPhase("error");
          setErrorText(err instanceof Error ? err.message : String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      ro.disconnect();

      try {
        renderer?.domElement.removeEventListener("pointerdown", pick);
      } catch {
        /* noop */
      }

      controls?.dispose();

      try {
        const mgr = loader?.ifcManager as unknown as { dispose?: () => void } | undefined;
        mgr?.dispose?.();
      } catch {
        /* noop */
      }

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
  }, [projectId, setSelectedElementId]);

  return (
    <div className="glass-panel viewer-pane" style={{ position: "relative", height: "100%" }}>
      <div ref={mountRef} className="viewer-frame" />

      {phase === "loading" && (
        <>
          {/* Shimmer sweep across the whole viewer */}
          <div className="viewer-shimmer" aria-hidden="true" />
          {/* Percentage badge */}
          <div className="viewer-overlay">
            <div className="viewer-overlay-inner">
              <div className="viewer-progress-label">{loadPct}%</div>
              <div className="viewer-progress-track">
                <div className="viewer-progress-fill" style={{ width: `${loadPct}%` }} />
              </div>
              <div className="muted" style={{ textAlign: "center", fontSize: "0.8rem", marginTop: "0.4rem" }}>
                Parsing IFC geometry…
              </div>
            </div>
          </div>
        </>
      )}

      {phase === "error" && (
        <div className="viewer-overlay">
          <div className="viewer-overlay-inner muted">
            Viewer could not render this IFC in-browser (file size or WASM mismatch).
            <div style={{ marginTop: "0.35rem", color: "#fcfefe", fontSize: "0.85rem" }}>
              {errorText}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
