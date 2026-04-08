import { useEffect, useState } from "react";

import { ChatPanel } from "./components/ChatPanel";
import { MediaPanel } from "./components/MediaPanel";
import { RuntimePanel } from "./components/RuntimePanel";
import { StatusBar } from "./components/StatusBar";
import "./app.css";
import { SessionController } from "./session-controller";
import { SessionStore } from "./session-store";
import type { DemoClientState } from "./types";

const DEFAULT_GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://127.0.0.1:3000";
const DEFAULT_SESSION_ID = import.meta.env.VITE_SESSION_ID ?? "session_demo_client";

export function App() {
  const [store] = useState(
    () => new SessionStore(DEFAULT_GATEWAY_URL, DEFAULT_SESSION_ID),
  );
  const [controller] = useState(() => new SessionController(store));
  const [state, setState] = useState<DemoClientState>(store.getState());
  const [draft, setDraft] = useState("");

  useEffect(() => store.subscribe(() => setState(store.getState())), [store]);
  useEffect(() => {
    void controller.connect();
    return () => {
      controller.disconnect();
    };
  }, [controller]);

  return (
    <main className="app-shell">
      <StatusBar
        gatewayUrl={state.gatewayUrl}
        sessionId={state.sessionId}
        connectionStatus={state.connectionStatus}
        microphoneEnabled={state.microphoneEnabled}
        cameraEnabled={state.cameraEnabled}
        ttsEnabled={state.ttsEnabled}
        ttsSpeaking={state.ttsSpeaking}
        mode={state.mode}
        onModeChange={(mode) => {
          controller.setMode(mode);
          void controller.connect();
        }}
        onGatewayUrlChange={(gatewayUrl) => controller.setGatewayUrl(gatewayUrl)}
        onSessionIdChange={(sessionId) => controller.setSessionId(sessionId)}
      />
      <div className="content-grid">
        <ChatPanel
          messages={state.chatMessages}
          draft={draft}
          pendingResumeTaskId={state.pendingResumeTaskId}
          pendingResumeTitle={state.pendingResumeTitle}
          onDraftChange={setDraft}
          onSend={() => {
            if (draft.trim().length === 0) {
              return;
            }
            void controller.sendTurn(draft.trim());
            setDraft("");
          }}
        />
        <MediaPanel
          microphoneEnabled={state.microphoneEnabled}
          cameraEnabled={state.cameraEnabled}
          lastAudioChunk={state.lastAudioChunk}
          lastVideoFrame={state.lastVideoFrame}
          onToggleMicrophone={(enabled) => {
            void controller.setMicrophoneEnabled(enabled);
          }}
          onToggleCamera={(enabled, attach) => {
            void controller.setCameraEnabled(enabled, attach);
          }}
        />
        <RuntimePanel
          conversation={state.conversation}
          tasks={state.tasks}
          recentTaskEvents={state.recentTaskEvents}
          lastCheckpoint={state.lastCheckpoint}
          pendingResumeTaskId={state.pendingResumeTaskId}
          pendingResumeTitle={state.pendingResumeTitle}
        />
      </div>
    </main>
  );
}
