import type {
  BuildingModelJson,
  ChatResponsePayload,
  PipelineStatusPayload,
} from "./types";

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
): Promise<ChatResponsePayload> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...EXTRA_HEADERS },
    body: JSON.stringify(body),
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
