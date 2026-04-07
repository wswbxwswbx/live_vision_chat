import { describe, expect, test } from "vitest";

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
});
