import { useEffect, useRef } from "react";
import { enqueueProcess, uploadModelProject } from "../api/client";
import { useProjectSessionStore } from "../stores/projectSessionStore";

/** Gzip upload + enqueue parse after a local session starts. */
export function useBackgroundUpload(projectId: string) {
  const file = useProjectSessionStore((s) => s.localModelFiles[projectId]);
  const uploadPhase = useProjectSessionStore((s) => s.uploadPhase[projectId]);
  const setUploadPhase = useProjectSessionStore((s) => s.setUploadPhase);
  const started = useRef(false);

  useEffect(() => {
    if (!file || !projectId) return;
    if (uploadPhase === "done" || uploadPhase === "uploading") return;
    if (started.current) return;
    started.current = true;

    setUploadPhase(projectId, "uploading", 0, null);

    void (async () => {
      try {
        await uploadModelProject(projectId, file, {
          onProgress: (pct) => setUploadPhase(projectId, "uploading", pct, null),
        });
        setUploadPhase(projectId, "done", 100, null);
        await enqueueProcess(projectId);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setUploadPhase(projectId, "error", 0, msg);
        started.current = false;
      }
    })();
  }, [projectId, file, setUploadPhase, uploadPhase]);
}
