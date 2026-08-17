import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { getPipelineStatus, getProcessedModel, enqueueProcess } from "../api/client";
import type { PipelineStatus } from "../api/types";
import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { useUiStore } from "../stores/uiStore";
import { useProjectSessionStore } from "../stores/projectSessionStore";

export function SidebarManager() {
  const { projectId } = useParams();
  const pid = projectId ?? "";
  
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen);

  const hasLocalIfc = !!useProjectSessionStore((s) => s.localIfcBuffers[pid]);
  const uploadPhase = useProjectSessionStore((s) => s.uploadPhase[pid]);
  const uploadError = useProjectSessionStore((s) => s.uploadError[pid]);

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

  const enqueueAttempts = useRef(0);
  const processMutation = useMutation({
    mutationFn: () => enqueueProcess(pid),
    onSuccess: () => statusQuery.refetch(),
  });

  useEffect(() => {
    if (!pid || hasLocalIfc) return;
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
  const filtersReady = statusQuery.data?.json_ready === true && !!modelQuery.data;

  if (!pid) return null;

  return (
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
  );
}
