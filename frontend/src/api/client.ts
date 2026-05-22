import type {
  BuildingModelJson,
  ChatResponsePayload,
  PipelineStatusPayload,
} from "./types";
import { gzipCompress } from "../utils/gzip";

// In dev: VITE_API_URL is unset → relative paths hit the Vite proxy → localhost:8000
// On Vercel: set VITE_API_URL=https://xxxx.ngrok-free.app in Vercel env vars
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

// Skips the ngrok browser-warning interstitial when API_BASE points at a tunnel
const EXTRA_HEADERS: Record<string, string> = API_BASE
  ? { "ngrok-skip-browser-warning": "true" }
  : {};

async function readError(res: Response): Promise<string> {
  try {
    const text = await res.text();
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") return j.detail;
      return text || res.statusText;
    } catch {
      return text || res.statusText;
    }
  } catch {
    return res.statusText;
  }
}

export async function uploadIfc(file: File): Promise<{ project_id: string }> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE}/api/projects/upload`, {
    method: "POST",
    headers: { ...EXTRA_HEADERS },
    body,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

/** Gzip upload to a pre-assigned project id (local preview + background sync). */
export async function uploadIfcProject(
  projectId: string,
  file: File,
  opts?: { onProgress?: (percent: number) => void },
): Promise<{ project_id: string }> {
  const raw = await file.arrayBuffer();
  const gz = await gzipCompress(raw);
  const useGzip = gz.byteLength < raw.byteLength;

  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/upload`;
  const body: BodyInit = useGzip ? gz : raw;
  const headers: Record<string, string> = {
    ...EXTRA_HEADERS,
    "Content-Type": "application/octet-stream",
    "X-Filename": file.name || "model.ifc",
  };
  if (useGzip) headers["Content-Encoding"] = "gzip";

  if (!opts?.onProgress) {
    const res = await fetch(url, { method: "PUT", headers, body });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as { project_id: string });
        } catch {
          resolve({ project_id: projectId });
        }
        return;
      }
      reject(new Error(xhr.responseText || xhr.statusText));
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.open("PUT", url);
    for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v);
    xhr.send(body);
  });
}

export async function enqueueProcess(projectId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/process`, {
    method: "POST",
    headers: { ...EXTRA_HEADERS },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getPipelineStatus(projectId: string): Promise<PipelineStatusPayload> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/status`, {
    headers: { ...EXTRA_HEADERS },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getProcessedModel(projectId: string): Promise<BuildingModelJson> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/model`, {
    headers: { ...EXTRA_HEADERS },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function sendChat(
  projectId: string,
  body: { message: string; selected_element?: string | null },
  signal?: AbortSignal,
): Promise<ChatResponsePayload> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...EXTRA_HEADERS },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchIfcBuffer(projectId: string): Promise<ArrayBuffer> {
  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/ifc`;
  const res = await fetch(url, { headers: { ...EXTRA_HEADERS } });
  if (!res.ok) throw new Error(`IFC fetch failed: ${res.status} ${res.statusText}`);
  return res.arrayBuffer();
}

/** @deprecated Viewer uses IFC directly; GLB may still be generated in background. */
export async function fetchGlbBuffer(projectId: string): Promise<ArrayBuffer> {
  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/glb`;
  const res = await fetch(url, { headers: { ...EXTRA_HEADERS } });
  if (!res.ok) throw new Error(`GLB fetch failed: ${res.status} ${res.statusText}`);
  return res.arrayBuffer();
}

export type VoiceTokenPayload = {
  token: string;
  url: string;
  room_name: string;
};

export async function getVoiceToken(projectId: string): Promise<VoiceTokenPayload> {
  const res = await fetch(
    `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/voice/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...EXTRA_HEADERS },
    },
  );
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
