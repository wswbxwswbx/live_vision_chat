import type {
  AssistantTextMessage,
  ChatMessage,
  CheckpointRecord,
  ConnectionStatus,
  DemoClientState,
  MediaSummary,
  SessionSnapshot,
  TaskEventMessage,
  TaskEventRecord,
} from "./types";

type Listener = () => void;

function taskEventFromMessage(message: TaskEventMessage): TaskEventRecord {
  return {
    task_id: message.payload.taskId,
    dialog_id: undefined,
    event_kind: message.payload.eventKind,
    summary: message.payload.summary,
    payload: message.payload.payload,
  };
}

function createUserMessage(id: string, text: string): ChatMessage {
  return {
    id,
    role: "user",
    text,
    timestampMs: Date.now(),
  };
}

function createAssistantMessage(message: AssistantTextMessage): ChatMessage {
  return {
    id: message.messageId,
    role: "assistant",
    text: message.payload.text,
    source: message.payload.source,
    timestampMs: Date.now(),
  };
}

export class SessionStore {
  private state: DemoClientState;
  private listeners = new Set<Listener>();

  constructor(initialGatewayUrl: string, initialSessionId: string) {
    this.state = {
      mode: "live",
      gatewayUrl: initialGatewayUrl,
      sessionId: initialSessionId,
      connectionStatus: "disconnected",
      connectionError: null,
      microphoneEnabled: false,
      cameraEnabled: false,
      ttsEnabled: true,
      ttsSpeaking: false,
      snapshotLoaded: false,
      conversation: null,
      tasks: [],
      chatMessages: [],
      recentTaskEvents: [],
      lastCheckpoint: null,
      lastAudioChunk: null,
      lastVideoFrame: null,
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getState(): DemoClientState {
    return this.state;
  }

  setMode(mode: DemoClientState["mode"]): void {
    this.patch({
      mode,
      connectionStatus: mode === "mock" ? "mock" : "disconnected",
      connectionError: null,
    });
  }

  setConnectionStatus(connectionStatus: ConnectionStatus, connectionError: string | null = null): void {
    this.patch({ connectionStatus, connectionError });
  }

  setGatewayUrl(gatewayUrl: string): void {
    this.patch({ gatewayUrl });
  }

  setSessionId(sessionId: string): void {
    this.patch({ sessionId });
  }

  setMicrophoneEnabled(microphoneEnabled: boolean): void {
    this.patch({ microphoneEnabled });
  }

  setCameraEnabled(cameraEnabled: boolean): void {
    this.patch({ cameraEnabled });
  }

  setTtsEnabled(ttsEnabled: boolean): void {
    this.patch({ ttsEnabled });
  }

  setTtsSpeaking(ttsSpeaking: boolean): void {
    this.patch({ ttsSpeaking });
  }

  recordOutgoingTurn(messageId: string, text: string): void {
    this.patch({
      chatMessages: [...this.state.chatMessages, createUserMessage(messageId, text)],
    });
  }

  applySnapshot(snapshot: SessionSnapshot): void {
    const taskEvents = snapshot.tasks.flatMap((entry) => entry.events).slice(-8).reverse();
    const lastCheckpoint = [...snapshot.tasks]
      .reverse()
      .map((entry) => entry.checkpoint)
      .find((checkpoint): checkpoint is CheckpointRecord => checkpoint !== null) ?? null;

    this.patch({
      snapshotLoaded: true,
      conversation: snapshot.conversation,
      tasks: snapshot.tasks,
      recentTaskEvents: taskEvents,
      lastCheckpoint,
    });
  }

  applyAssistantText(message: AssistantTextMessage): void {
    this.patch({
      chatMessages: [...this.state.chatMessages, createAssistantMessage(message)],
    });
  }

  applyTaskEvent(message: TaskEventMessage): void {
    const event = taskEventFromMessage(message);
    this.patch({
      recentTaskEvents: [event, ...this.state.recentTaskEvents].slice(0, 10),
    });
  }

  recordAudioChunk(summary: MediaSummary): void {
    this.patch({ lastAudioChunk: summary });
  }

  recordVideoFrame(summary: MediaSummary): void {
    this.patch({ lastVideoFrame: summary });
  }

  patch(partial: Partial<DemoClientState>): void {
    this.state = {
      ...this.state,
      ...partial,
    };
    this.emit();
  }

  private emit(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}
