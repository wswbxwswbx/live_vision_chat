# Post-M2 Runtime Status

**Date:** 2026-04-08  
**Status:** Current implementation baseline  
**Scope:** Shipped Python-first runtime state after the M2 reminder milestone

---

## 1. What Is Shipped Now

The current Python mainline now includes one minimally real Fast/Slow task flow:

- direct Fast replies for non-reminder turns
- Fast reminder triage into `create_reminder`
- Slow reminder execution through the in-memory execution layer
- `waiting_user -> handoff_resume -> completed` reminder recovery
- runtime snapshot visibility for reminder task state, checkpoint, and task events
- demo-client support for resuming reminder tasks from the chat box
- session-bound `handoff_resume` validation and graceful invalid-resume handling

The first and only real M2 task capability is:

- `create_reminder`

---

## 2. Current Code Reality

### 2.1 Gateway

`apps/gateway` currently provides:

- `GET /health`
- `GET /sessions/:session_id/snapshot`
- websocket session ingress for `turn`, `handoff_resume`, `audio_chunk`, and `video_frame`
- websocket assistant replies for normal runtime responses and recoverable system errors

### 2.2 Runtime Core

`packages/runtime_core` currently provides:

- `FastRuntime` for direct reply vs reminder handoff triage
- `SlowRuntime` for reminder completion and `waiting_user` recovery
- `TaskRuntime` for reminder task lifecycle transitions
- `RuntimeFacade` as the only gateway-facing runtime entrypoint
- session/dialog/task registries and snapshot composition

### 2.3 Execution

`packages/execution` is now partially real:

- reminder execution boundary exists
- in-memory reminder registry exists
- reminder records are created through runtime-owned orchestration

It is still not a production integration layer.

### 2.4 Demo Client

`apps/demo-client` is still a debug and observability tool, not a product client.

It can now show:

- direct Fast replies
- reminder clarification and completion text
- pending reminder resume state
- reminder task/checkpoint/event changes through snapshot refresh

---

## 3. How To Run And Verify

### 3.1 Python

Use a Python 3.11+ environment with the current server dependencies installed.

Start the gateway:

```bash
python -m apps.gateway.dev
```

Run Python verification:

```bash
python -m pytest packages apps/gateway/tests -q
```

Verified at this status point:

- Python tests: `62 passed`

### 3.2 Demo Client

Install demo-client dependencies:

```bash
cd apps/demo-client
corepack pnpm install
```

Run demo-client verification:

```bash
corepack pnpm test
corepack pnpm build
```

Verified at this status point:

- demo-client tests: `8 passed`
- demo-client build: pass

### 3.3 Expected Smoke Checks

The current runtime should be considered healthy if all of the following hold:

- `curl -s http://127.0.0.1:3000/health` returns `{"ok":true}`
- a non-reminder `turn` returns `Fast reply: ...`
- `Remind me to pay rent` yields `When should I remind you?`
- a follow-up `handoff_resume` such as `tomorrow at 9am` completes the same task
- invalid or repeated `handoff_resume` does not cross session boundaries and does not tear down the websocket

---

## 4. Current Limits

These are real gaps, not documentation omissions:

- only `create_reminder` is implemented as a real Slow task
- `audio_chunk / video_frame` are accepted by the gateway but not yet routed into true streaming runtime logic
- `packages/memory` remains a stub boundary
- reminder execution is in-memory only; there is no external calendar/reminder integration
- time understanding is intentionally narrow and text-preserving
- `StreamingLoop / AccumulationLoop / MonitoringLoop / GuidanceLoop` are not yet implemented in Python mainline

---

## 5. Next Milestone

The next milestone should be:

- `M3: Streaming Ingress + First AccumulationLoop`

That work should start from the shipped M2 runtime rather than reopening Fast/Slow ownership boundaries.

Immediate follow-up focus:

1. route `audio_chunk / video_frame` into runtime-observable ingress
2. let `SlowRuntime` own the first real streaming task lifecycle
3. implement the first minimal `AccumulationLoop`
4. keep `RuntimeFacade` as the gateway-facing boundary

---

## 6. Suggested Team Split

- Gateway owner:
  - `apps/gateway`
- Runtime core owner:
  - `packages/runtime_core`
- Runtime store owner:
  - `packages/runtime_store`
- Execution owner:
  - `packages/execution`
- Memory owner:
  - `packages/memory`
- Demo/debug client owner:
  - `apps/demo-client`

---

## 7. Related Docs

- `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
- `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md`
- `docs/superpowers/status/2026-04-07-python-runtime-baseline.md`
