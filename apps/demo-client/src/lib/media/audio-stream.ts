import type { AudioChunkPayload } from "../../app/types";

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("failed to read audio blob"));
        return;
      }
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(reader.error ?? new Error("failed to read audio blob"));
    reader.readAsDataURL(blob);
  });
}

export class AudioStream {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private sequence = 0;

  async start(
    onChunk: (payload: AudioChunkPayload) => void | Promise<void>,
    sliceMs = 250,
  ): Promise<void> {
    if (this.recorder !== null) {
      return;
    }

    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    this.recorder = new MediaRecorder(this.stream, {
      mimeType: "audio/webm;codecs=opus",
    });

    this.recorder.addEventListener("dataavailable", async (event) => {
      if (event.data.size === 0) {
        return;
      }
      this.sequence += 1;
      await onChunk({
        mimeType: event.data.type || "audio/webm;codecs=opus",
        data: await blobToBase64(event.data),
        sequence: this.sequence,
        timestampMs: Date.now(),
        durationMs: sliceMs,
      });
    });

    this.recorder.start(sliceMs);
  }

  stop(): void {
    this.recorder?.stop();
    this.recorder = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }
}
