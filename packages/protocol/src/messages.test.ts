import { describe, expect, it } from "vitest";
import {
  type ClientMessage,
  type ServerMessage,
  parseClientMessage,
  parseServerMessage,
} from "./messages";

describe("protocol messages", () => {
  it("parses a valid turn message", () => {
    const message: ClientMessage = {
      type: "turn",
      sessionId: "session_001",
      messageId: "msg_001",
      payload: {
        text: "帮我设个闹钟",
      },
    };

    expect(parseClientMessage(message)).toEqual(message);
  });

  it("parses a valid tool_call server message", () => {
    const message: ServerMessage = {
      type: "tool_call",
      sessionId: "session_001",
      messageId: "msg_002",
      payload: {
        callId: "call_001",
        taskId: "task_001",
        toolName: "camera_capture",
        params: {},
      },
    };

    expect(parseServerMessage(message)).toEqual(message);
  });

  it("rejects malformed call ids", () => {
    expect(() =>
      parseServerMessage({
        type: "tool_call",
        sessionId: "session_001",
        messageId: "msg_003",
        payload: {
          callId: "bad id",
          taskId: "task_001",
          toolName: "camera_capture",
          params: {},
        },
      }),
    ).toThrow(/callId/i);
  });

  it("rejects invalid tool call state values", () => {
    expect(() =>
      parseServerMessage({
        type: "tool_progress",
        sessionId: "session_001",
        messageId: "msg_004",
        payload: {
          callId: "call_001",
          state: "done",
          status: "capturing",
        },
      }),
    ).toThrow(/state/i);
  });
});
