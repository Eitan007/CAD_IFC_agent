import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget =
  process.env.BIM_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // COOP/COEP makes crossOriginIsolated true → web-ifc picks pthread/WASM-mt build,
    // which needs document.currentScript / mainScriptUrlOrBlob — broken under Vite ESM (undefined → worker Blob URL crash).
    // Single-thread web-ifc works without isolation headers.
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
