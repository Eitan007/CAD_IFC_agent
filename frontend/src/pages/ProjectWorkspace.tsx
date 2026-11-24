import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useEffect, useMemo, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { enqueueProcess, getPipelineStatus } from "../api/client";
import type { PipelineStatus } from "../api/types";
import { CADViewer } from "../components/CADViewer";
import { ConversationPanel } from "../components/ConversationPanel";
import { WorkspaceComposer } from "../components/WorkspaceComposer";
import { useBackgroundUpload } from "../hooks/useBackgroundUpload";
import { useConversationStore } from "../stores/conversationStore";
import { useProjectSessionStore } from "../stores/projectSessionStore";
import { motionPresets } from "../utils/motion";
import { IconArrowLeft } from "../components/WorkspaceIcons";

export function ProjectWorkspace() {
  const { projectId } = useParams();
  const pid = projectId ?? "";
  const loadConversation = useConversationStore((s) => s.loadConversation);

  const localModel = useProjectSessionStore((s) => s.localModelFiles[pid]);
  const hasLocalModel = !!localModel;
  const uploadPhase = useProjectSessionStore((s) => s.uploadPhase[pid]);
  const uploadError = useProjectSessionStore((s) => s.uploadError[pid]);

  useBackgroundUpload(pid);

  const enqueueAttempts = useRef(0);

  useEffect(() => {
    if (pid) loadConversation(pid);
    enqueueAttempts.current = 0;
  }, [pid, loadConversation]);

  const statusQueryEnabled = !!pid && (!hasLocalModel || uploadPhase === "done");

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

  const processMutation = useMutation(
    useMemo(
      () => ({
        mutationFn: () => enqueueProcess(pid),
        onSuccess: () => statusQuery.refetch(),
      }),
      [pid, statusQuery],
    ),
  );

  useEffect(() => {
    if (hasLocalModel) return;
    const st = statusQuery.data?.status as PipelineStatus | undefined;
    if (st !== "idle" && st !== "received") return;
    if (processMutation.isPending) return;
    if (enqueueAttempts.current >= 5) return;
    enqueueAttempts.current += 1;
    processMutation.mutate();
  }, [hasLocalModel, pid, statusQuery.data?.status, processMutation]);

  const pipelineStatus = statusQuery.data?.status as PipelineStatus | undefined;
  const chatEnabled =
    statusQuery.data?.graph_ready === true ||
    statusQuery.data?.status === "graph_ready" ||
    statusQuery.data?.status === "completed";

  if (!pid) {
    return (
      <div className="ws-root">
        <p className="muted" style={{ padding: "2rem" }}>Missing project id.</p>
      </div>
    );
  }

  return (
    <motion.div className="ws-root" {...motionPresets.contentSwap}>
      {/* <WorkspaceSidebar
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
      /> */}

      {/* Full-page CAD canvas */}
      <section className="ws-viewer-card">
        <CADViewer
          projectId={pid}
          sourceFormat={localModel?.name.split(".").pop() ?? statusQuery.data?.source_format}
          previewStatus={statusQuery.data?.preview_status}
          previewError={statusQuery.data?.preview_error}
        />
      </section>

      <Link
        to="/"
        className="ws-back-link"
        aria-label="Back to sample selection and upload"
      >
        <IconArrowLeft />
        <span>Projects</span>
      </Link>

      {/* Hamburger menu button - top left */}
      {/* <motion.button
        type="button"
        className="ws-menu-btn"
        whileTap={softPress}
        onClick={() => setSidebarOpen((o) => !o)}
        aria-label="Toggle project sidebar"
        aria-expanded={sidebarOpen}
      >
        <IconMenu />
      </motion.button> */}

      {/* Side chat panel - left side */}
      <ConversationPanel />

      {/* Centered input bar - top center */}
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
      />
    </motion.div>
  );
}
