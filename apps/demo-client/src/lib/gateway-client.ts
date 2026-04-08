import type {
  AudioChunkPayload,
  ServerMessage,
  SessionSnapshot,
  VideoFramePayload,
} from "../app/types";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export function buildWsUrl(gatewayUrl: string, sessionId: string): string {
  const normalized = trimTrailingSlash(gatewayUrl);
  const url = new URL(normalized);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/sessions/${sessionId}`;
  return url.toString();
}

export class GatewayClient {
  private websocket: WebSocket | null = null;

  constructor(private readonly gatewayUrl: string) {}

  async fetchSnapshot(sessionId: string): Promise<SessionSnapshot | null> {
    const response = await fetch(
      `${trimTrailingSlash(this.gatewayUrl)}/sessions/${sessionId}/snapshot`,
    );
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new Error(`snapshot request failed: ${response.status}`);
    }
    return (await response.json()) as SessionSnapshot;
  }

  connect(
    sessionId: string,
    handlers: {
      onOpen: () => void;
      onClose: () => void;
      onError: (error: string) => void;
      onMessage: (message: ServerMessage) => void;
    },
  ): { close: () => void } {
    const websocket = new WebSocket(buildWsUrl(this.gatewayUrl, sessionId));
    this.websocket = websocket;

    websocket.addEventListener("open", handlers.onOpen);
    websocket.addEventListener("close", handlers.onClose);
    websocket.addEventListener("error", () => handlers.onError("websocket error"));
    websocket.addEventListener("message", (event) => {
      const parsed = JSON.parse(String(event.data)) as ServerMessage;
      handlers.onMessage(parsed);
    });

    return {
      close: () => {
        websocket.close();
        if (this.websocket === websocket) {
          this.websocket = null;
        }
      },
    };
  }

  sendTurn(sessionId: string, text: string): void {
    this.send({
      type: "turn",
      sessionId,
      messageId: `turn:${Date.now()}`,
      payload: { text },
    });
  }

  sendHandoffResume(sessionId: string, taskId: string, text: string): void {
    this.send({
      type: "handoff_resume",
      sessionId,
      messageId: `resume:${Date.now()}`,
      payload: { taskId, text },
    });
  }

  sendAudioChunk(sessionId: string, payload: AudioChunkPayload): void {
    this.send({
      type: "audio_chunk",
      sessionId,
      messageId: `audio:${payload.sequence}`,
      payload,
    });
  }

  sendVideoFrame(sessionId: string, payload: VideoFramePayload): void {
    this.send({
      type: "video_frame",
      sessionId,
      messageId: `video:${payload.sequence}`,
      payload,
    });
  }

  private send(message: object): void {
    if (this.websocket?.readyState !== WebSocket.OPEN) {
      throw new Error("websocket is not connected");
    }

    this.websocket.send(JSON.stringify(message));
  }
}
