import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useCallback, useState } from "react";
import { uploadIfc } from "../api/client";

export function UploadPage() {
  const navigate = useNavigate();
  const [drag, setDrag] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => uploadIfc(file),
    onSuccess: (data) => {
      navigate(`/project/${encodeURIComponent(data.project_id)}`, { replace: true });
    },
  });

  const onFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;

      setLocalError(null);

      if (!file.name.toLowerCase().endsWith(".ifc")) {
        setLocalError("Only .ifc files are supported.");
        return;
      }

      mutation.mutate(file);
    },
    [mutation],
  );

  return (
    <div className="upload-shell">
      <div className="glass-panel upload-card">
        <div style={{ fontSize: "1.35rem", fontWeight: 800 }}>CAD / IFC workspace</div>
        <p className="muted" style={{ marginTop: "0.35rem", lineHeight: 1.55 }}>
          Upload a building IFC model. You’ll land in a split workspace with an interactive viewer and an LLM chat
          wired to your processed graph.
        </p>

        <div
          className={`dropzone ${drag ? "drag" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            onFiles(e.dataTransfer.files);
          }}
        >
          <div style={{ fontWeight: 700 }}>Drop a .ifc file here</div>
          <div className="muted" style={{ marginTop: "0.35rem" }}>
            Max ~500 MB • Files upload to{" "}
            <code style={{ color: "var(--accent-hover)" }}>/api/projects/upload</code>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <label className="btn-primary" style={{ display: "inline-block" }}>
              Choose file
              <input type="file" accept=".ifc" style={{ display: "none" }} onChange={(e) => onFiles(e.target.files)} />
            </label>
          </div>

          {mutation.isPending && <div className="muted" style={{ marginTop: "0.85rem" }}>Uploading…</div>}
          {localError && (
            <div style={{ marginTop: "0.85rem", color: "#ffb4b4" }}>
              {localError}
            </div>
          )}
          {mutation.isError && (
            <div style={{ marginTop: "0.85rem", color: "#ffb4b4" }}>
              {(mutation.error as Error).message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
