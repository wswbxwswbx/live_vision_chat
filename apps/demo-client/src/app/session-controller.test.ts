import { describe, expect, test, vi } from "vitest";

import { SessionController } from "./session-controller";
import { SessionStore } from "./session-store";

describe("SessionController", () => {
  test("mock mode bootstraps snapshot and mock connection state", async () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");
    const controller = new SessionController(store);

    controller.setMode("mock");
    await controller.connect();

    const state = store.getState();
    expect(state.connectionStatus).toBe("mock");
    expect(state.snapshotLoaded).toBe(true);
    expect(state.conversation?.dialog_id).toBe("s1");
  });

  test("routes waiting reminder follow-up through handoff_resume", async () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");
    const controller = new SessionController(store);
    const sendTurn = vi.fn();
    const sendHandoffResume = vi.fn();

    store.applySnapshot({
      session_id: "s1",
      dialog_id: "d1",
      conversation: {
        dialog_id: "d1",
        speaker_owner: "fast",
        attention_owner: "slow",
        foreground_task_id: null,
        background_task_ids: ["task-1"],
        interrupt_epoch: 1,
      },
      tasks: [
        {
          task: {
            task_id: "task-1",
            status: "waiting_user",
            summary: "When should I remind you?",
            payload: {
              task_type: "create_reminder",
              title: "Pay rent",
              raw_user_input: "Remind me to pay rent",
              scheduled_at_text: null,
            },
          },
          checkpoint: {
            task_id: "task-1",
            state: "waiting_user",
            payload: {
              task_type: "create_reminder",
              title: "Pay rent",
              raw_user_input: "Remind me to pay rent",
              scheduled_at_text: null,
              missing_field: "scheduled_at",
            },
          },
          events: [],
          tool_calls: [],
        },
      ],
    });

    (
      controller as unknown as {
        liveClient: {
          sendTurn: (sessionId: string, text: string) => void;
          sendHandoffResume: (sessionId: string, taskId: string, text: string) => void;
        };
      }
    ).liveClient = {
      sendTurn,
      sendHandoffResume,
    };

    await controller.sendTurn("tomorrow at 9am");

    expect(sendHandoffResume).toHaveBeenCalledWith("s1", "task-1", "tomorrow at 9am");
    expect(sendTurn).not.toHaveBeenCalled();
  });

  test("refreshes snapshot after assistant text", async () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");
    const controller = new SessionController(store);
    const fetchSnapshot = vi.fn().mockResolvedValue({
      session_id: "s1",
      dialog_id: "d1",
      conversation: {
        dialog_id: "d1",
        speaker_owner: "fast",
        attention_owner: "slow",
        foreground_task_id: null,
        background_task_ids: ["task-1"],
        interrupt_epoch: 1,
      },
      tasks: [
        {
          task: {
            task_id: "task-1",
            status: "waiting_user",
            summary: "When should I remind you?",
            payload: {
              task_type: "create_reminder",
              title: "Pay rent",
              raw_user_input: "Remind me to pay rent",
              scheduled_at_text: null,
            },
          },
          checkpoint: {
            task_id: "task-1",
            state: "waiting_user",
            payload: {
              task_type: "create_reminder",
              title: "Pay rent",
              raw_user_input: "Remind me to pay rent",
              scheduled_at_text: null,
              missing_field: "scheduled_at",
            },
          },
          events: [],
          tool_calls: [],
        },
      ],
    });

    (
      controller as unknown as {
        liveClient: {
          fetchSnapshot: (sessionId: string) => Promise<unknown>;
        };
      }
    ).liveClient = {
      fetchSnapshot,
    };

    await (controller as unknown as {
      handleServerMessage: (message: {
        type: "assistant_text";
        sessionId: string;
        messageId: string;
        payload: { text: string; source: "slow" };
      }) => Promise<void>;
    }).handleServerMessage({
      type: "assistant_text",
      sessionId: "s1",
      messageId: "assistant-1",
      payload: {
        text: "When should I remind you?",
        source: "slow",
      },
    });

    expect(fetchSnapshot).toHaveBeenCalledWith("s1");
    expect(store.getState().pendingResumeTaskId).toBe("task-1");
    expect(store.getState().chatMessages.at(-1)?.text).toBe("When should I remind you?");
  });

  test("captures snapshot refresh failures after assistant text", async () => {
    const store = new SessionStore("http://127.0.0.1:3000", "s1");
    const controller = new SessionController(store);
    const fetchSnapshot = vi.fn().mockRejectedValue(new Error("snapshot request failed: 500"));

    (
      controller as unknown as {
        liveClient: {
          fetchSnapshot: (sessionId: string) => Promise<unknown>;
        };
      }
    ).liveClient = {
      fetchSnapshot,
    };

    await expect(
      (controller as unknown as {
        handleServerMessage: (message: {
          type: "assistant_text";
          sessionId: string;
          messageId: string;
          payload: { text: string; source: "system" };
        }) => Promise<void>;
      }).handleServerMessage({
        type: "assistant_text",
        sessionId: "s1",
        messageId: "assistant-1",
        payload: {
          text: "task task-1 is not waiting for user input",
          source: "system",
        },
      }),
    ).resolves.toBeUndefined();

    expect(fetchSnapshot).toHaveBeenCalledWith("s1");
    expect(store.getState().connectionStatus).toBe("error");
    expect(store.getState().connectionError).toBe("snapshot request failed: 500");
    expect(store.getState().chatMessages.at(-1)?.text).toBe(
      "task task-1 is not waiting for user input",
    );
  });
});
