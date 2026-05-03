export type PipelineStatus =
  | "idle"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export type PipelineStatusPayload = {
  status: PipelineStatus;
  project_id: string;
  element_count?: number | null;
  error?: string | null;
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
