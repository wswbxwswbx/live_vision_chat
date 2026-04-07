import type { ChatMessage } from "../types";

export function ChatPanel(props: {
  messages: ChatMessage[];
  draft: string;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
}) {
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
        <textarea
          value={props.draft}
          onChange={(event) => props.onDraftChange(event.target.value)}
          placeholder="Send a turn to the Python gateway"
        />
        <button onClick={props.onSend}>Send turn</button>
      </div>
    </section>
  );
}
