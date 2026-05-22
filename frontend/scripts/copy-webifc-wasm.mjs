import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const srcDir = path.join(root, "node_modules", "web-ifc");
const destDir = path.join(root, "public", "wasm");

const files = ["web-ifc.wasm", "web-ifc-mt.wasm", "web-ifc-mt.worker.js"];

if (!fs.existsSync(srcDir)) {
  console.warn("[copy-webifc-wasm] web-ifc not installed, skipping.");
  process.exit(0);
}

fs.mkdirSync(destDir, { recursive: true });
for (const name of files) {
  const src = path.join(srcDir, name);
  if (!fs.existsSync(src)) {
    console.warn(`[copy-webifc-wasm] missing ${name}`);
    continue;
  }
  fs.copyFileSync(src, path.join(destDir, name));
}
console.log("[copy-webifc-wasm] copied wasm to public/wasm/");
