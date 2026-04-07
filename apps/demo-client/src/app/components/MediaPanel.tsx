import { useEffect, useRef } from "react";

import type { MediaSummary } from "../types";

export function MediaPanel(props: {
  microphoneEnabled: boolean;
  cameraEnabled: boolean;
  lastAudioChunk: MediaSummary | null;
  lastVideoFrame: MediaSummary | null;
  onToggleMicrophone: (enabled: boolean) => void;
  onToggleCamera: (enabled: boolean, attach: (stream: MediaStream | null) => void) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    return () => {
      const video = videoRef.current;
      if (video !== null) {
        video.srcObject = null;
      }
    };
  }, []);

  return (
    <section className="panel media-panel">
      <div className="panel-header">
        <h2>Media</h2>
      </div>
      <div className="media-controls">
        <button onClick={() => props.onToggleMicrophone(!props.microphoneEnabled)}>
          {props.microphoneEnabled ? "Stop mic" : "Start mic"}
        </button>
        <button
          onClick={() =>
            props.onToggleCamera(!props.cameraEnabled, (stream) => {
              if (videoRef.current !== null) {
                videoRef.current.srcObject = stream;
              }
            })
          }
        >
          {props.cameraEnabled ? "Stop camera" : "Start camera"}
        </button>
      </div>
      <video ref={videoRef} className="camera-preview" autoPlay muted playsInline />
      <dl className="metric-list">
        <div>
          <dt>Last audio chunk</dt>
          <dd>{formatMediaSummary(props.lastAudioChunk)}</dd>
        </div>
        <div>
          <dt>Last video frame</dt>
          <dd>{formatMediaSummary(props.lastVideoFrame)}</dd>
        </div>
      </dl>
    </section>
  );
}

function formatMediaSummary(summary: MediaSummary | null): string {
  if (summary === null) {
    return "none";
  }
  return `#${summary.sequence} · ${summary.mimeType} · ${summary.sizeBytes} bytes`;
}
