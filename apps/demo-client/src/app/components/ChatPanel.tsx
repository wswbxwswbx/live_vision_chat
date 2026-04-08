import type { ChatMessage } from "../types";

export function ChatPanel(props: {
  messages: ChatMessage[];
  draft: string;
  pendingResumeTaskId: string | null;
  pendingResumeTitle: string | null;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
}) {
  const isWaitingForReminderTime = props.pendingResumeTaskId !== null;
  const placeholder = isWaitingForReminderTime
    ? `Reply with the reminder time${props.pendingResumeTitle ? ` for ${props.pendingResumeTitle}` : ""}`
    : "Send a turn to the Python gateway";
  const buttonLabel = isWaitingForReminderTime ? "Send reminder time" : "Send turn";

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Chat</h2>
      </div>
      <div className="chat-list">
        {props.messages.map((message) => (
          <article key={message.id} className={`chat-message ${message.role}`}>
            <div className="chat-role">{message.role}</div>
            <div>{message.text}</div>
          </article>
        ))}
      </div>
      <div className="chat-input">
        {isWaitingForReminderTime ? (
          <div className="chat-hint">
            Waiting for reminder time on <strong>{props.pendingResumeTaskId}</strong>
            {props.pendingResumeTitle ? ` for ${props.pendingResumeTitle}` : ""}.
          </div>
        ) : null}
        <textarea
          value={props.draft}
          onChange={(event) => props.onDraftChange(event.target.value)}
          placeholder={placeholder}
        />
        <button onClick={props.onSend}>{buttonLabel}</button>
      </div>
    </section>
  );
}
