import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { enqueueProcess, getPipelineStatus, getProcessedModel } from "../api/client";
import type { PipelineStatus } from "../api/types";
import { CADViewer } from "../components/CADViewer";
import { ChatPanel } from "../components/ChatPanel";
import { StatusBar } from "../components/StatusBar";
import { useUiStore } from "../stores/uiStore";

const VIEWER_MIN_PCT = 20;
const CHAT_MIN_PCT = 18;

export function ProjectWorkspace() {
  const { projectId } = useParams();
  const pid = projectId ?? "";

  const storeyFilter = useUiStore((s) => s.storeyFilter);
  const typeFilter = useUiStore((s) => s.typeFilter);
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const setStoreyFilter = useUiStore((s) => s.setStoreyFilter);
  const setTypeFilter = useUiStore((s) => s.setTypeFilter);

  // ── Resizable split ──────────────────────────────────────────────────────
  const [viewerPct, setViewerPct] = useState(68);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      const clamped = Math.min(Math.max(pct, VIEWER_MIN_PCT), 100 - CHAT_MIN_PCT);
      setViewerPct(clamped);
    };
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  // ── Pipeline / model queries ─────────────────────────────────────────────
  const enqueueAttempts = useRef(0);

  const statusQuery = useQuery({
    queryKey: ["pipeline-status", pid],
    queryFn: () => getPipelineStatus(pid),
    enabled: !!pid,
    refetchInterval: (q) => {
      const s = q.state.data?.status as PipelineStatus | undefined;
      return s === "queued" || s === "processing" ? 1200 : false;
    },
  });

  const processMutation = useMutation({
    mutationFn: () => enqueueProcess(pid),
    onSuccess: () => statusQuery.refetch(),
  });

  useEffect(() => {
    enqueueAttempts.current = 0;
  }, [pid]);

  useEffect(() => {
    const st = statusQuery.data?.status as PipelineStatus | undefined;
    if (st !== "idle") return;
    if (processMutation.isPending) return;
    if (enqueueAttempts.current >= 5) return;
    enqueueAttempts.current += 1;
    processMutation.mutate();
  }, [pid, statusQuery.data?.status, processMutation]);

  const modelQuery = useQuery({
    queryKey: ["processed-model", pid],
    queryFn: () => getProcessedModel(pid),
    enabled: !!pid && statusQuery.data?.status === "completed",
  });

  const storeys = useMemo(() => {
    const els = modelQuery.data?.elements ?? [];
    const set = new Set<string>();
    for (const e of els) {
      const st = e.storey?.trim();
      if (st) set.add(st);
    }
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [modelQuery.data?.elements]);

  const types = useMemo(() => {
    const els = modelQuery.data?.elements ?? [];
    const set = new Set<string>();
    for (const e of els) set.add(e.type);
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [modelQuery.data?.elements]);

  const pipelineStatus = statusQuery.data?.status as PipelineStatus | undefined;
  const chatEnabled = pipelineStatus === "completed";

  if (!pid) {
    return (
      <div className="upload-shell">
        <div className="glass-panel upload-card muted">Missing project id.</div>
      </div>
    );
  }

  return (
    <div className="workspace">
      <header className="workspace-header">
        <div style={{ display: "flex", gap: "0.65rem", alignItems: "baseline" }}>
          <Link to="/" style={{ color: "var(--accent-hover)", textDecoration: "none", fontWeight: 800 }}>
            ← Upload
          </Link>
          <div style={{ fontWeight: 800 }}>Project workspace</div>
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Route <code>/project/{pid.slice(0, 10)}…</code>
          </span>
        </div>
        <div className="muted" style={{ fontSize: "0.82rem" }}>
          Viewer streams IFC • Pipeline writes graph • Chat hits{" "}
          <code style={{ color: "var(--accent-hover)" }}>/api/projects/…/chat</code>
        </div>
      </header>

      <main className="workspace-main" ref={containerRef}>
        {/* ── Viewer column (filters + 3D) ── */}
        <section
          className="viewer-column"
          style={{ width: `${viewerPct}%` }}
        >
          <div className="glass-panel filters-row">
            <span className="muted" style={{ fontSize: "0.82rem", marginRight: "0.35rem" }}>
              Filters
            </span>
            <select
              value={storeyFilter}
              disabled={!modelQuery.data}
              onChange={(e) => setStoreyFilter(e.target.value)}
              aria-label="Filter by storey"
            >
              <option value="">All storeys</option>
              {storeys.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select
              value={typeFilter}
              disabled={!modelQuery.data}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by component type"
            >
              <option value="">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            {!modelQuery.data && pipelineStatus !== "completed" && (
              <span className="muted" style={{ fontSize: "0.78rem" }}>
                Filters activate after metadata loads.
              </span>
            )}
          </div>

          <CADViewer projectId={pid} />
        </section>

        {/* ── Drag divider ── */}
        <div
          className="panel-divider"
          onMouseDown={onDividerMouseDown}
          title="Drag to resize"
          aria-hidden="true"
        />

        {/* ── Chat column ── */}
        <section
          className="chat-column"
          style={{ width: `${100 - viewerPct}%` }}
        >
          <ChatPanel projectId={pid} chatEnabled={chatEnabled} />
        </section>
      </main>

      <StatusBar
        projectId={pid}
        status={pipelineStatus}
        error={statusQuery.data?.error ?? statusQuery.error?.message ?? processMutation.error?.message}
        elementCount={statusQuery.data?.element_count ?? modelQuery.data?.element_count}
        selectedElementId={selectedElementId}
      />
    </div>
  );
}
