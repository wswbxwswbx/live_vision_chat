export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error"
  | "mock";

export type ClientMode = "live" | "mock";

export type SpeakerOwner = "user" | "fast" | "slow";
export type AttentionOwner = "fast" | "slow";

export interface ConversationState {
  dialog_id: string;
  speaker_owner: SpeakerOwner;
  attention_owner: AttentionOwner;
  foreground_task_id: string | null;
  background_task_ids: string[];
  interrupt_epoch: number;
}

export interface TaskRecord {
  task_id?: string;
  dialog_id?: string;
  status?: string;
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface CheckpointRecord {
  task_id?: string;
  dialog_id?: string;
  state?: string;
  payload?: Record<string, unknown>;
}

export interface TaskEventRecord {
  task_id?: string;
  dialog_id?: string;
  event_kind?: string;
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface ToolCallRecord {
  call_id?: string;
  task_id?: string;
  status?: string;
  tool_name?: string;
  payload?: Record<string, unknown>;
}

export interface SessionTaskSnapshot {
  task: TaskRecord | null;
  checkpoint: CheckpointRecord | null;
  events: TaskEventRecord[];
  tool_calls: ToolCallRecord[];
}

export interface SessionSnapshot {
  session_id: string;
  dialog_id: string;
  conversation: ConversationState;
  tasks: SessionTaskSnapshot[];
}

export interface AssistantTextPayload {
  text: string;
  source: "fast" | "slow" | "system";
}

export interface AssistantTextMessage {
  type: "assistant_text";
  sessionId: string;
  messageId: string;
  payload: AssistantTextPayload;
}

export interface TaskEventMessage {
  type: "task_event";
  sessionId: string;
  messageId: string;
  payload: {
    taskId: string;
    eventKind: string;
    summary: string;
    payload?: Record<string, unknown>;
  };
}

export interface AudioChunkPayload {
  mimeType: string;
  data: string;
  sequence: number;
  timestampMs: number;
  durationMs: number;
  taskId?: string | null;
}

export interface VideoFramePayload {
  mimeType: string;
  data: string;
  sequence: number;
  timestampMs: number;
  width: number;
  height: number;
  taskId?: string | null;
}

export type ServerMessage = AssistantTextMessage | TaskEventMessage;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  source?: "fast" | "slow" | "system";
  timestampMs: number;
}

export interface MediaSummary {
  sequence: number;
  timestampMs: number;
  mimeType: string;
  sizeBytes: number;
}

export interface DemoClientState {
  mode: ClientMode;
  gatewayUrl: string;
  sessionId: string;
  connectionStatus: ConnectionStatus;
  connectionError: string | null;
  microphoneEnabled: boolean;
  cameraEnabled: boolean;
  ttsEnabled: boolean;
  ttsSpeaking: boolean;
  snapshotLoaded: boolean;
  conversation: ConversationState | null;
  tasks: SessionTaskSnapshot[];
  chatMessages: ChatMessage[];
  recentTaskEvents: TaskEventRecord[];
  lastCheckpoint: CheckpointRecord | null;
  pendingResumeTaskId: string | null;
  pendingResumeTitle: string | null;
  lastAudioChunk: MediaSummary | null;
  lastVideoFrame: MediaSummary | null;
}
