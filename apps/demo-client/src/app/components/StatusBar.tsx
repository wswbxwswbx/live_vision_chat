import type { ConnectionStatus } from "../types";

export function StatusBar(props: {
  gatewayUrl: string;
  sessionId: string;
  connectionStatus: ConnectionStatus;
  microphoneEnabled: boolean;
  cameraEnabled: boolean;
  ttsEnabled: boolean;
  ttsSpeaking: boolean;
  mode: "live" | "mock";
  onModeChange: (mode: "live" | "mock") => void;
  onGatewayUrlChange: (gatewayUrl: string) => void;
  onSessionIdChange: (sessionId: string) => void;
}) {
  return (
    <header className="status-bar">
      <div className="status-group">
        <label>
          Gateway
          <input
            value={props.gatewayUrl}
            onChange={(event) => props.onGatewayUrlChange(event.target.value)}
          />
        </label>
        <label>
          Session
          <input
            value={props.sessionId}
            onChange={(event) => props.onSessionIdChange(event.target.value)}
          />
        </label>
      </div>
      <div className="status-group">
        <button
          className={props.mode === "live" ? "status-pill active" : "status-pill"}
          onClick={() => props.onModeChange("live")}
        >
          live
        </button>
        <button
          className={props.mode === "mock" ? "status-pill active" : "status-pill"}
          onClick={() => props.onModeChange("mock")}
        >
          mock
        </button>
      </div>
      <div className="status-group">
        <span className="status-pill">{props.connectionStatus}</span>
        <span className="status-pill">{props.microphoneEnabled ? "mic on" : "mic off"}</span>
        <span className="status-pill">{props.cameraEnabled ? "cam on" : "cam off"}</span>
        <span className="status-pill">
          {props.ttsEnabled ? (props.ttsSpeaking ? "tts speaking" : "tts ready") : "tts off"}
        </span>
      </div>
    </header>
  );
}
