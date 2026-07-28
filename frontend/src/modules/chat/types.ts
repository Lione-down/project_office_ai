export interface ChatModel {
  model_id: string;
  model_code: string;
  display_name: string;
  capabilities: Record<string, unknown>;
  is_recommended: boolean;
  status: string;
}

export interface ChatThread {
  thread_id: string;
  user_id: string;
  title: string;
  default_model_id: string;
  model_code: string;
  mode: "chat" | "ppt";
  status: string;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
}

export type ChatMessageStatus =
  | "pending"
  | "streaming"
  | "succeeded"
  | "cancelled_partial"
  | "failed"
  | "provider_uncertain";

export interface ChatMessage {
  message_id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  status: ChatMessageStatus;
  parent_message_id: string | null;
  supersedes_message_id: string | null;
  branch_root_id: string;
  run_id: string | null;
  model_code: string | null;
  created_at: string;
  finalized_at: string | null;
}

export interface ChatThreadDetail extends ChatThread {
  messages: ChatMessage[];
}

export interface ChatRunRequest {
  content?: string;
  model_id: string;
  parent_message_id?: string;
  supersedes_message_id?: string;
  regenerate_from_message_id?: string;
  thinking_enabled?: boolean;
  context_asset_ids?: string[];
}

export type ChatSseEventName =
  | "run.started"
  | "message.delta"
  | "message.snapshot"
  | "run.completed"
  | "run.cancelled_partial"
  | "run.failed"
  | "run.provider_uncertain";

export interface ChatSseEvent {
  schema_version: "chat-sse.v1";
  event: ChatSseEventName;
  run_id: string;
  thread_id: string;
  sequence: number;
  occurred_at: string;
  trace_id: string;
  payload: Record<string, unknown>;
}
