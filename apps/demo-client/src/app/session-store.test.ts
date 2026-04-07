import { describe, expect, test } from "vitest";

import { SessionStore } from "./session-store";

describe("SessionStore", () => {
  test("applies snapshots into runtime state", () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");

    store.applySnapshot({
      session_id: "s1",
      dialog_id: "d1",
      conversation: {
        dialog_id: "d1",
        speaker_owner: "fast",
        attention_owner: "slow",
        foreground_task_id: null,
        background_task_ids: ["t1"],
        interrupt_epoch: 1,
      },
      tasks: [
        {
          task: { task_id: "t1", status: "running", summary: "demo" },
          checkpoint: { task_id: "t1", state: "midway" },
          events: [{ task_id: "t1", event_kind: "accepted", summary: "accepted" }],
          tool_calls: [],
        },
      ],
    });

    const state = store.getState();
    expect(state.snapshotLoaded).toBe(true);
    expect(state.conversation?.attention_owner).toBe("slow");
    expect(state.tasks).toHaveLength(1);
    expect(state.lastCheckpoint?.state).toBe("midway");
  });

  test("records outgoing and assistant chat messages", () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");

    store.recordOutgoingTurn("user-1", "hello");
    store.applyAssistantText({
      type: "assistant_text",
      sessionId: "s1",
      messageId: "assistant-1",
      payload: {
        text: "reply",
        source: "fast",
      },
    });

    expect(store.getState().chatMessages.map((message) => message.text)).toEqual([
      "hello",
      "reply",
    ]);
  });
});
