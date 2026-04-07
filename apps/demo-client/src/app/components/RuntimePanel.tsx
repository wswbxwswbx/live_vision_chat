import type {
  CheckpointRecord,
  ConversationState,
  SessionTaskSnapshot,
  TaskEventRecord,
} from "../types";

export function RuntimePanel(props: {
  conversation: ConversationState | null;
  tasks: SessionTaskSnapshot[];
  recentTaskEvents: TaskEventRecord[];
  lastCheckpoint: CheckpointRecord | null;
}) {
  return (
    <section className="panel runtime-panel">
      <div className="panel-header">
        <h2>Runtime</h2>
      </div>
      <div className="runtime-section">
        <h3>Conversation</h3>
        <pre>{JSON.stringify(props.conversation, null, 2)}</pre>
      </div>
      <div className="runtime-section">
        <h3>Tasks</h3>
        <pre>{JSON.stringify(props.tasks, null, 2)}</pre>
      </div>
      <div className="runtime-section">
        <h3>Recent task events</h3>
        <pre>{JSON.stringify(props.recentTaskEvents, null, 2)}</pre>
      </div>
      <div className="runtime-section">
        <h3>Checkpoint</h3>
        <pre>{JSON.stringify(props.lastCheckpoint, null, 2)}</pre>
      </div>
    </section>
  );
}
