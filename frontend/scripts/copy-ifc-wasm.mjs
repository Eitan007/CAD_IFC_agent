import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const pub = path.join(root, "public", "web-ifc");

try {
  // web-ifc-three pins its own nested web-ifc; bundled JS must match those WASM/worker files.
  const nestedWasm = path.join(root, "node_modules", "web-ifc-three", "node_modules", "web-ifc");
  const topWasm = path.join(root, "node_modules", "web-ifc");
  const wasmPkg = fs.existsSync(nestedWasm) ? nestedWasm : topWasm;
  if (!fs.existsSync(wasmPkg)) {
    console.warn("[copy-ifc-wasm] web-ifc not installed yet — skipping.");
    process.exit(0);
  }
  fs.mkdirSync(pub, { recursive: true });
  for (const name of fs.readdirSync(wasmPkg)) {
    const extWasm = name.endsWith(".wasm");
    const extWorker = name.endsWith(".worker.js");
    if (!extWasm && !extWorker) continue;
    fs.copyFileSync(path.join(wasmPkg, name), path.join(pub, name));
  }
  console.log(`[copy-ifc-wasm] WASM + worker scripts copied from ${path.relative(root, wasmPkg)} → public/web-ifc/`);
} catch (err) {
  console.warn("[copy-ifc-wasm]", err);
}
