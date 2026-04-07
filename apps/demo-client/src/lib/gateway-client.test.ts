import { describe, expect, test, vi } from "vitest";

import { GatewayClient, buildWsUrl } from "./gateway-client";

describe("gateway-client", () => {
  test("builds websocket urls from gateway urls", () => {
    expect(buildWsUrl("http://127.0.0.1:3000", "s1")).toBe(
      "ws://127.0.0.1:3000/sessions/s1",
    );
  });

  test("returns null for missing snapshots", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 404,
      ok: false,
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = new GatewayClient("http://127.0.0.1:3000");
    await expect(client.fetchSnapshot("missing")).resolves.toBeNull();
  });
});
