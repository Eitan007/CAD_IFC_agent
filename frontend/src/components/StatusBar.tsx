import type { PipelineStatus } from "../api/types";

type Props = {
  projectId: string;
  status: PipelineStatus | undefined;
  error?: string | null;
  elementCount?: number | null;
  selectedElementId: string | null;
};

export function StatusBar({ projectId, status, error, elementCount, selectedElementId }: Props) {
  const label = status ?? "…";

  return (
    <footer className="status-bar glass-panel" style={{ borderRadius: 0 }}>
      <span className="pill">
        Project <strong style={{ color: "var(--text)" }}>{projectId.slice(0, 8)}…</strong>
      </span>
      <span className="pill">
        Pipeline <strong style={{ color: "var(--text)" }}>{label}</strong>
      </span>
      {typeof elementCount === "number" && (
        <span className="pill">
          Elements <strong style={{ color: "var(--text)" }}>{elementCount}</strong>
        </span>
      )}
      {selectedElementId && (
        <span className="pill" style={{ borderColor: "color-mix(in srgb, var(--accent) 70%, transparent)" }}>
          Selected IFC express ID{" "}
          <strong style={{ color: "var(--accent-hover)" }}>{selectedElementId}</strong>
        </span>
      )}
      {error && (
        <span className="pill" style={{ borderColor: "#ff7b7b", color: "#ffd7d7" }}>
          {error}
        </span>
      )}
    </footer>
  );
}
