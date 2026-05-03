import type {
  BuildingModelJson,
  ChatResponsePayload,
  PipelineStatusPayload,
} from "./types";

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
  const res = await fetch("/api/projects/upload", { method: "POST", body });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function enqueueProcess(projectId: string): Promise<{ status: string }> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/process`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getPipelineStatus(projectId: string): Promise<PipelineStatusPayload> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/status`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getProcessedModel(projectId: string): Promise<BuildingModelJson> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/model`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function sendChat(
  projectId: string,
  body: { message: string; selected_element?: string | null },
): Promise<ChatResponsePayload> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export function ifcAssetUrl(projectId: string): string {
  return `/api/projects/${encodeURIComponent(projectId)}/ifc`;
}
