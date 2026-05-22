import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { enqueueProcess, getPipelineStatus, getProcessedModel } from "../api/client";
import type { PipelineStatus } from "../api/types";
import { CADViewer } from "../components/CADViewer";
import { ConversationPanel } from "../components/ConversationPanel";
import { WorkspaceComposer, type ComposerMode } from "../components/WorkspaceComposer";
import { WorkspaceSidebar } from "../components/WorkspaceSidebar";
import { IconMenu } from "../components/WorkspaceIcons";
import { useBackgroundUpload } from "../hooks/useBackgroundUpload";
import { useConversationStore } from "../stores/conversationStore";
import { useProjectSessionStore } from "../stores/projectSessionStore";

export function ProjectWorkspace() {
  const { projectId } = useParams();
  const pid = projectId ?? "";
  const resetConversation = useConversationStore((s) => s.resetConversation);

  const hasLocalIfc = !!useProjectSessionStore((s) => s.localIfcBuffers[pid]);
  const uploadPhase = useProjectSessionStore((s) => s.uploadPhase[pid]);
  const uploadProgress = useProjectSessionStore((s) => s.uploadProgress[pid] ?? 0);
  const uploadError = useProjectSessionStore((s) => s.uploadError[pid]);

  useBackgroundUpload(pid);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [composerMode, setComposerMode] = useState<ComposerMode>("text");

  const enqueueAttempts = useRef(0);

  useEffect(() => {
    resetConversation();
    enqueueAttempts.current = 0;
    setComposerMode("text");
    setSidebarOpen(false);
  }, [pid, resetConversation]);

  const statusQueryEnabled = !!pid && (!hasLocalIfc || uploadPhase === "done");

  const statusQuery = useQuery({
    queryKey: ["pipeline-status", pid],
    queryFn: () => getPipelineStatus(pid),
    enabled: statusQueryEnabled,
    refetchInterval: (q) => {
      const d = q.state.data;
      const s = d?.status as PipelineStatus | undefined;
      if (s === "queued" || s === "processing") return 1200;
      if (d?.graph_ready && !d?.json_ready) return 2000;
      return false;
    },
  });

  const processMutation = useMutation({
    mutationFn: () => enqueueProcess(pid),
    onSuccess: () => statusQuery.refetch(),
  });

  useEffect(() => {
    if (hasLocalIfc) return;
    const st = statusQuery.data?.status as PipelineStatus | undefined;
    if (st !== "idle" && st !== "received") return;
    if (processMutation.isPending) return;
    if (enqueueAttempts.current >= 5) return;
    enqueueAttempts.current += 1;
    processMutation.mutate();
  }, [hasLocalIfc, pid, uploadPhase, statusQuery.data?.status, processMutation]);

  const modelQuery = useQuery({
    queryKey: ["processed-model", pid],
    queryFn: () => getProcessedModel(pid),
    enabled: !!pid && statusQuery.data?.json_ready === true,
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
  const chatEnabled =
    statusQuery.data?.graph_ready === true ||
    statusQuery.data?.status === "graph_ready" ||
    statusQuery.data?.status === "completed";
  const filtersReady = statusQuery.data?.json_ready === true && !!modelQuery.data;

  const uploadLabel =
    uploadPhase === "uploading"
      ? `Syncing ${uploadProgress}%`
      : uploadPhase === "done"
        ? "Synced"
        : uploadPhase === "error"
          ? "Sync failed"
          : hasLocalIfc
            ? "Local preview"
            : null;

  if (!pid) {
    return (
      <div className="ws-root">
        <p className="muted" style={{ padding: "2rem" }}>Missing project id.</p>
      </div>
    );
  }

  return (
    <div className="ws-root">
      <header className="ws-header">
        <button
          type="button"
          className="ws-menu-btn"
          onClick={() => setSidebarOpen((o) => !o)}
          aria-label="Toggle project sidebar"
          aria-expanded={sidebarOpen}
        >
          <IconMenu />
        </button>
        <h1 className="ws-title">WORK SPACE</h1>
        {uploadLabel && (
          <span
            className={`ws-upload-badge ${uploadPhase === "error" ? "ws-upload-badge-error" : ""}`}
            title={uploadError ?? undefined}
          >
            {uploadLabel}
          </span>
        )}
      </header>

      <WorkspaceSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        projectId={pid}
        pipelineStatus={pipelineStatus}
        pipelineError={
          uploadError ??
          statusQuery.data?.error ??
          statusQuery.error?.message ??
          processMutation.error?.message
        }
        elementCount={statusQuery.data?.element_count ?? modelQuery.data?.element_count}
        storeys={storeys}
        types={types}
        filtersReady={filtersReady}
      />

      <div className="ws-body">
        <div className="ws-stage">
          <section className="ws-viewer-card">
            <CADViewer projectId={pid} />
          </section>
          <ConversationPanel />
        </div>

        <WorkspaceComposer
          projectId={pid}
          chatEnabled={chatEnabled}
          pipelineStatus={pipelineStatus}
          pipelineError={
            uploadError ??
            statusQuery.data?.error ??
            statusQuery.error?.message ??
            processMutation.error?.message
          }
          mode={composerMode}
          onModeChange={setComposerMode}
        />
      </div>
    </div>
  );
}
