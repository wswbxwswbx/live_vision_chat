import { GatewayClient } from "../lib/gateway-client";
import { AudioStream } from "../lib/media/audio-stream";
import { BrowserTts } from "../lib/media/tts";
import { VideoStream } from "../lib/media/video-stream";
import { MockClient } from "./mock-client";
import { SessionStore } from "./session-store";
import type { AudioChunkPayload, ServerMessage, VideoFramePayload } from "./types";

type CloseHandle = { close: () => void } | null;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export class SessionController {
  private liveClient: GatewayClient;
  private mockClient = new MockClient();
  private audioStream = new AudioStream();
  private videoStream = new VideoStream();
  private tts = new BrowserTts();
  private connection: CloseHandle = null;

  constructor(private readonly store: SessionStore) {
    this.liveClient = new GatewayClient(store.getState().gatewayUrl);
    this.tts.subscribe((speaking) => {
      this.store.setTtsSpeaking(speaking);
    });
  }

  async connect(): Promise<void> {
    const state = this.store.getState();
    if (state.mode === "mock") {
      this.connection = this.mockClient.connect(state.sessionId, (message) => {
        void this.handleServerMessage(message);
      });
      this.store.setConnectionStatus("mock");
      this.store.applySnapshot(await this.mockClient.fetchSnapshot(state.sessionId));
      return;
    }

    this.liveClient = new GatewayClient(state.gatewayUrl);
    this.store.setConnectionStatus("connecting");
    const snapshot = await this.liveClient.fetchSnapshot(state.sessionId);
    if (snapshot !== null) {
      this.store.applySnapshot(snapshot);
    }
    this.connection = this.liveClient.connect(state.sessionId, {
      onOpen: () => this.store.setConnectionStatus("connected"),
      onClose: () => this.store.setConnectionStatus("disconnected"),
      onError: (error) => this.store.setConnectionStatus("error", error),
      onMessage: (message) => {
        void this.handleServerMessage(message);
      },
    });
  }

  disconnect(): void {
    this.connection?.close();
    this.connection = null;
    this.audioStream.stop();
    this.videoStream.stop();
    this.tts.stop();
    if (this.store.getState().mode !== "mock") {
      this.store.setConnectionStatus("disconnected");
    }
    this.store.setMicrophoneEnabled(false);
    this.store.setCameraEnabled(false);
  }

  async sendTurn(text: string): Promise<void> {
    const state = this.store.getState();
    const messageId = `user:${Date.now()}`;
    this.store.recordOutgoingTurn(messageId, text);
    if (state.mode === "mock") {
      await this.mockClient.sendTurn(state.sessionId, text);
      return;
    }

    if (state.pendingResumeTaskId !== null) {
      this.liveClient.sendHandoffResume(state.sessionId, state.pendingResumeTaskId, text);
      return;
    }

    this.liveClient.sendTurn(state.sessionId, text);
  }

  async setMicrophoneEnabled(enabled: boolean): Promise<void> {
    if (!enabled) {
      this.audioStream.stop();
      this.store.setMicrophoneEnabled(false);
      return;
    }

    await this.audioStream.start(async (payload) => {
      this.handleAudioChunk(payload);
    });
    this.store.setMicrophoneEnabled(true);
  }

  async setCameraEnabled(enabled: boolean, onStream?: (stream: MediaStream | null) => void): Promise<void> {
    if (!enabled) {
      this.videoStream.stop();
      this.store.setCameraEnabled(false);
      onStream?.(null);
      return;
    }

    const stream = await this.videoStream.start(async (payload) => {
      this.handleVideoFrame(payload);
    });
    this.store.setCameraEnabled(true);
    onStream?.(stream);
  }

  setMode(mode: "live" | "mock"): void {
    this.disconnect();
    this.store.setMode(mode);
  }

  setGatewayUrl(gatewayUrl: string): void {
    this.store.setGatewayUrl(gatewayUrl);
  }

  setSessionId(sessionId: string): void {
    this.store.setSessionId(sessionId);
  }

  setTtsEnabled(ttsEnabled: boolean): void {
    this.store.setTtsEnabled(ttsEnabled);
    if (!ttsEnabled) {
      this.tts.stop();
    }
  }

  private async handleServerMessage(message: ServerMessage): Promise<void> {
    if (message.type === "assistant_text") {
      this.store.applyAssistantText(message);
      if (this.store.getState().ttsEnabled) {
        this.tts.speak(message.payload.text);
      }
      try {
        await this.refreshSnapshot();
      } catch (error) {
        this.store.setConnectionStatus("error", getErrorMessage(error));
      }
      return;
    }

    if (message.type === "task_event") {
      this.store.applyTaskEvent(message);
      try {
        await this.refreshSnapshot();
      } catch (error) {
        this.store.setConnectionStatus("error", getErrorMessage(error));
      }
    }
  }

  private async refreshSnapshot(): Promise<void> {
    const state = this.store.getState();
    if (state.mode !== "live") {
      return;
    }

    const snapshot = await this.liveClient.fetchSnapshot(state.sessionId);
    if (snapshot !== null) {
      this.store.applySnapshot(snapshot);
    }
  }

  private async handleAudioChunk(payload: AudioChunkPayload): Promise<void> {
    this.store.recordAudioChunk({
      sequence: payload.sequence,
      timestampMs: payload.timestampMs,
      mimeType: payload.mimeType,
      sizeBytes: payload.data.length,
    });

    const state = this.store.getState();
    if (state.mode === "mock") {
      await this.mockClient.sendAudioChunk(state.sessionId, payload);
      return;
    }

    this.liveClient.sendAudioChunk(state.sessionId, payload);
  }

  private async handleVideoFrame(payload: VideoFramePayload): Promise<void> {
    this.store.recordVideoFrame({
      sequence: payload.sequence,
      timestampMs: payload.timestampMs,
      mimeType: payload.mimeType,
      sizeBytes: payload.data.length,
    });

    const state = this.store.getState();
    if (state.mode === "mock") {
      await this.mockClient.sendVideoFrame(state.sessionId, payload);
      return;
    }

    this.liveClient.sendVideoFrame(state.sessionId, payload);
  }
}
