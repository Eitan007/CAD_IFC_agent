export type PipelineStatus =
  | "idle"
  | "received"
  | "queued"
  | "processing"
  | "graph_ready"
  | "completed"
  | "failed";

export type PipelineStatusPayload = {
  status: PipelineStatus;
  project_id: string;
  element_count?: number | null;
  error?: string | null;
  graph_ready?: boolean;
  json_ready?: boolean;
  source_format?: string | null;
  preview_status?: string | null;
  preview_error?: string | null;
  checks?: DeterministicCheck[];
};

export type DeterministicCheck = { name: string; passed: boolean; detail: string };

export type MonitoringSummary = {
  agent_runs: number;
  failed_runs: number;
  error_rate: number;
  average_duration_ms: number;
  tool_calls: number;
  formats: Record<string, number>;
  recent_runs: Array<{ trace_id?: string; query: string; source_format: string; duration_ms: number; status: string; tool_calls: number }>;
};

export type SampleEvaluation = {
  cases: Array<{ name: string; score: number; passed: boolean; checks: Array<{ name: string; passed: boolean }> }>;
  average_score: number;
};

export type BuildingModelJson = {
  project_id: string;
  element_count: number;
  elements: Array<{
    id: string;
    type: string;
    name?: string | null;
    storey?: string | null;
  }>;
};

export type ChatReference = {
  kind: string;
  detail?: string | null;
};

export type ChatResponsePayload = {
  answer: string;
  explanation: string;
  references: ChatReference[];
  tool_calls: unknown[];
  iterations: number;
  warning?: string | null;
};
