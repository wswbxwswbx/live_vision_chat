import type { VideoFramePayload } from "../../app/types";

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("failed to read video frame"));
        return;
      }
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(reader.error ?? new Error("failed to read video frame"));
    reader.readAsDataURL(blob);
  });
}

export class VideoStream {
  private stream: MediaStream | null = null;
  private intervalId: number | null = null;
  private sequence = 0;
  private readonly canvas = document.createElement("canvas");

  async start(
    onFrame: (payload: VideoFramePayload) => void | Promise<void>,
    options: {
      fps?: number;
      width?: number;
      height?: number;
    } = {},
  ): Promise<MediaStream> {
    if (this.stream !== null) {
      return this.stream;
    }

    const width = options.width ?? 640;
    const height = options.height ?? 360;
    const fps = options.fps ?? 2;

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        width,
        height,
      },
    });

    this.canvas.width = width;
    this.canvas.height = height;

    const [track] = this.stream.getVideoTracks();
    const imageCapture =
      "ImageCapture" in window
        ? (new ImageCapture(track) as unknown as {
            grabFrame: () => Promise<ImageBitmap>;
          })
        : null;

    this.intervalId = window.setInterval(async () => {
      this.sequence += 1;

      if (imageCapture !== null) {
        const bitmap = await imageCapture.grabFrame();
        const context = this.canvas.getContext("2d");
        if (context === null) {
          return;
        }
        context.drawImage(bitmap, 0, 0, width, height);
      }

      const blob = await new Promise<Blob | null>((resolve) => {
        this.canvas.toBlob(resolve, "image/jpeg", 0.72);
      });
      if (blob === null) {
        return;
      }

      await onFrame({
        mimeType: "image/jpeg",
        data: await blobToBase64(blob),
        sequence: this.sequence,
        timestampMs: Date.now(),
        width,
        height,
      });
    }, Math.max(250, Math.round(1000 / fps)));

    return this.stream;
  }

  stop(): void {
    if (this.intervalId !== null) {
      window.clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }
}
