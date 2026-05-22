import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProjectSessionStore } from "../stores/projectSessionStore";

function UploadIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 16V4m0 0l-4 4m4-4l4 4M4 20h16"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function UploadPage() {
  const navigate = useNavigate();
  const setLocalIfc = useProjectSessionStore((s) => s.setLocalIfc);
  const [drag, setDrag] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);

  const onFiles = useCallback(
    async (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;

      setLocalError(null);

      if (!file.name.toLowerCase().endsWith(".ifc")) {
        setLocalError("Only .ifc files are supported.");
        return;
      }

      setOpening(true);
      try {
        const projectId = crypto.randomUUID();
        await setLocalIfc(projectId, file);
        navigate(`/project/${encodeURIComponent(projectId)}`, { replace: true });
      } catch (err) {
        setLocalError(err instanceof Error ? err.message : String(err));
        setOpening(false);
      }
    },
    [navigate, setLocalIfc],
  );

  const busy = opening;

  return (
    <div className="upload-page">
      <label
        className={`glass-card upload-glass-card ${drag ? "upload-glass-card--drag" : ""} ${busy ? "upload-glass-card--busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) void onFiles(e.dataTransfer.files);
        }}
      >
        <input
          type="file"
          accept=".ifc"
          className="upload-glass-card-input"
          disabled={busy}
          onChange={(e) => void onFiles(e.target.files)}
        />

        <div className="upload-glass-card-header">
          <span className="upload-glass-card-badge">
            <UploadIcon />
          </span>
          <span className="upload-glass-card-label">Upload Files</span>
        </div>

        <h1 className="upload-glass-card-title">
          {busy ? "Opening workspace…" : "Drag and drop your IFC file here, or click to browse."}
        </h1>

        <p className="upload-glass-card-hint muted">
          Building models only • .ifc • max ~500 MB • preview starts instantly, syncs in background
        </p>

        <div className="upload-glass-card-actions">
          <span className="upload-action-btn" role="presentation">
            <UploadIcon />
            <span>{busy ? "Opening…" : "Choose file"}</span>
          </span>
        </div>

        {localError && <p className="upload-glass-card-error">{localError}</p>}

        <div className="glass-card-dots" aria-hidden="true" />
      </label>
    </div>
  );
}
