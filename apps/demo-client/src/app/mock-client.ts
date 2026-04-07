import type {
  AssistantTextMessage,
  AudioChunkPayload,
  ServerMessage,
  SessionSnapshot,
  VideoFramePayload,
} from "./types";

export class MockClient {
  async fetchSnapshot(sessionId: string): Promise<SessionSnapshot> {
    return {
      session_id: sessionId,
      dialog_id: sessionId,
      conversation: {
        dialog_id: sessionId,
        speaker_owner: "fast",
        attention_owner: "fast",
        foreground_task_id: null,
        background_task_ids: [],
        interrupt_epoch: 0,
      },
      tasks: [],
    };
  }

  connect(_sessionId: string, onMessage: (message: ServerMessage) => void): { close: () => void } {
    this.onMessage = onMessage;
    return {
      close: () => {
        this.onMessage = null;
      },
    };
  }

  async sendTurn(sessionId: string, text: string): Promise<void> {
    this.onMessage?.({
      type: "assistant_text",
      sessionId,
      messageId: `mock:${Date.now()}`,
      payload: {
        text: `mock reply: ${text}`,
        source: "fast",
      },
    } satisfies AssistantTextMessage);
  }

  async sendAudioChunk(_sessionId: string, _payload: AudioChunkPayload): Promise<void> {}

  async sendVideoFrame(_sessionId: string, _payload: VideoFramePayload): Promise<void> {}

  private onMessage: ((message: ServerMessage) => void) | null = null;
}
