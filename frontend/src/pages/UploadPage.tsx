import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useProjectSessionStore } from "../stores/projectSessionStore";
import { entranceTransition, softContainer, softEntrance, softItem, softPress } from "../utils/motion";

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

function SparklesIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3v3m0 12v3M3 12h3m12 0h3m-2.636-6.364l-2.121 2.121m-8.486 8.486l-2.121 2.121m0-12.728l2.121 2.121m8.486 8.486l2.121 2.121"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
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

  const SAMPLE_PROJECT_ID = "sample-basichouse";

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

  const onSelectSample = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setOpening(true);
      navigate(`/project/${encodeURIComponent(SAMPLE_PROJECT_ID)}`, { replace: true });
    },
    [navigate],
  );

  const busy = opening;

  return (
    <div className="upload-page">
      <motion.label
        className={`glass-card upload-glass-card ${drag ? "upload-glass-card--drag" : ""} ${busy ? "upload-glass-card--busy" : ""}`}
        variants={softContainer}
        initial="hidden"
        animate="show"
        whileTap={busy ? undefined : softPress}
        transition={entranceTransition}
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

        <motion.div className="upload-glass-card-header" variants={softItem} transition={entranceTransition}>
          <span className="upload-glass-card-badge">
            <UploadIcon />
          </span>
          <span className="upload-glass-card-label">Upload Files</span>
        </motion.div>

        <motion.h1 className="upload-glass-card-title" variants={softEntrance} transition={entranceTransition}>
          {busy ? "Opening workspace…" : "Drag and drop your IFC file here, or click to browse."}
        </motion.h1>

        <motion.p className="upload-glass-card-hint muted" variants={softItem} transition={entranceTransition}>
          Building models only • .ifc • max ~500 MB • preview starts instantly, syncs in background
        </motion.p>

        <motion.div className="upload-glass-card-actions" variants={softItem} transition={entranceTransition}>
          <span className="upload-action-btn" role="presentation">
            <UploadIcon />
            <span>{busy ? "Opening…" : "Choose file"}</span>
          </span>

          <motion.button
            type="button"
            className="upload-action-btn upload-action-btn--sample"
            disabled={busy}
            whileTap={busy ? undefined : softPress}
            onClick={onSelectSample}
          >
            <SparklesIcon />
            <span>Try Sample Model</span>
          </motion.button>
        </motion.div>

        {localError && (
          <motion.p className="upload-glass-card-error" initial="hidden" animate="show" variants={softItem} transition={entranceTransition}>
            {localError}
          </motion.p>
        )}

        <div className="glass-card-dots" aria-hidden="true" />
      </motion.label>
    </div>
  );
}
