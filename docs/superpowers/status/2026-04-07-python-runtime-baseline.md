# Python Runtime Baseline Summary

**Date:** 2026-04-07  
**Status:** Baseline Ready  
**Scope:** Python-first server backbone + repository-local demo client for integration debugging

---

## 1. What Is Done

This worktree establishes the first stable Python-first baseline for the project.

Completed:

- Python-first runtime backbone
- shared runtime state skeleton
- thin FastAPI gateway
- repository-local browser demo client for integration debugging
- protocol support for text turn plus debug-stage media uplink
- local debug flow documentation

Validated capabilities:

- `GET /health`
- `GET /sessions/:session_id/snapshot`
- websocket session connection
- `turn -> assistant_text`
- browser text chat UI
- browser `speechSynthesis` TTS
- continuous microphone chunk upload
- low-frame-rate camera frame upload
- runtime state visualization for `conversation / tasks / task_events / checkpoint`

---

## 2. Fixed Architecture Decisions

These decisions should now be treated as baseline constraints, not open design questions.

- Formal mainline is Python-first
- `reference/claude-code` remains the primary architecture reference
- `claw-code-main` and `cc-mini-main` are implementation references only
- Server modules stay split as:
  - `apps/gateway`
  - `packages/protocol`
  - `packages/runtime_store`
  - `packages/runtime_core`
  - `packages/execution`
  - `packages/memory`
- `RuntimeFacade` is the gateway-facing runtime entrypoint
- shared runtime state is the truth source for runtime-observable state
- `apps/demo-client` is an integration/debug tool, not a formal product client
- debug-stage media transport is:
  - `WebSocket + structured messages + base64 payload`
- formal product target remains:
  - app-native clients
  - cleaner separation between control-plane traffic and production media transport

---

## 3. Current Code Layout

### 3.1 Gateway

Path: [apps/gateway](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/gateway)

Responsibilities:

- HTTP ingress
- websocket session ingress
- CORS for local demo development
- snapshot API exposure
- delegating runtime work to `RuntimeFacade`

Key files:

- [app.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/gateway/app.py)
- [http.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/gateway/http.py)
- [ws.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/gateway/ws.py)
- [dev.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/gateway/dev.py)

### 3.2 Protocol

Path: [packages/protocol](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/protocol)

Responsibilities:

- client/server message schema
- strict message parsing
- current debug-stage media message definitions

Current important message types:

- `turn`
- `assistant_text`
- `audio_chunk`
- `video_frame`
- task/tool related runtime messages

Key file:

- [messages.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/protocol/src/protocol/messages.py)

### 3.3 Runtime Store

Path: [packages/runtime_store](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_store)

Responsibilities:

- shared runtime truth source
- `conversation`
- `task`
- `checkpoint`
- `task_event`
- `tool_call`

Key files:

- [models.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_store/src/runtime_store/models.py)
- [memory_store.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_store/src/runtime_store/memory_store.py)

### 3.4 Runtime Core

Path: [packages/runtime_core](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core)

Responsibilities:

- Fast/Slow runtime skeletons
- task lifecycle helper
- session/dialog/task binding
- session snapshot composition
- gateway-facing runtime facade

Key files:

- [fast_runtime.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core/src/runtime_core/fast_runtime.py)
- [slow_runtime.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core/src/runtime_core/slow_runtime.py)
- [task_runtime.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core/src/runtime_core/task_runtime.py)
- [runtime_facade.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core/src/runtime_core/runtime_facade.py)
- [session_snapshot.py](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/runtime_core/src/runtime_core/session_snapshot.py)

### 3.5 Execution and Memory

Paths:

- [packages/execution](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/execution)
- [packages/memory](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/packages/memory)

Current state:

- both are intentionally stubs
- boundaries are fixed
- real execution and long-term memory behavior still need implementation

### 3.6 Demo Client

Path: [apps/demo-client](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client)

Responsibilities:

- gateway/runtime integration debugging
- text turn testing
- browser TTS
- microphone chunk uplink
- camera frame uplink
- runtime state visualization
- `live / mock` mode switch

Key files:

- [App.tsx](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client/src/app/App.tsx)
- [session-controller.ts](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client/src/app/session-controller.ts)
- [gateway-client.ts](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client/src/lib/gateway-client.ts)
- [audio-stream.ts](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client/src/lib/media/audio-stream.ts)
- [video-stream.ts](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/apps/demo-client/src/lib/media/video-stream.ts)

---

## 4. What Counts As Working Today

The baseline should be considered healthy if all of the following hold:

- gateway starts with `python -m apps.gateway.dev`
- `curl -s http://127.0.0.1:3000/health` returns `{"ok":true}`
- demo client reaches `connected`
- sending a text turn yields `assistant_text`
- microphone capture updates `Last audio chunk`
- camera capture updates `Last video frame`
- runtime panel shows `conversation` after the first turn

---

## 5. Verification Status

Verified at baseline:

- `python -m pytest packages apps/gateway/tests -q`
  - result: `43 passed`
- `corepack pnpm test` in `apps/demo-client`
  - result: `5 passed`
- `corepack pnpm build` in `apps/demo-client`
  - result: pass
- local smoke checks
  - `/health` pass
  - websocket `turn -> assistant_text` pass

---

## 6. Known Gaps

These are expected and do not invalidate the baseline.

- `FastRuntime` is still a skeleton
- `SlowRuntime` and `TaskRuntime` are still minimal
- `audio_chunk / video_frame` are accepted by gateway but not yet routed into true streaming runtime logic
- `execution` is still a stub
- `memory` is still a stub
- `StreamingLoop / MonitoringLoop / GuidanceLoop` are not yet implemented in Python mainline
- `packages/protocol` still contains a small amount of legacy TypeScript-era material that should be cleaned later

---

## 7. Next Work

Next work should follow the design spec rather than inventing a new direction.

### 7.1 Immediate Next Steps

1. Route `audio_chunk / video_frame` into runtime-observable state
2. Add the first minimal streaming input consumption path
3. Let `SlowRuntime` own the first real streaming task lifecycle
4. Implement the first minimal `AccumulationLoop`

### 7.2 After That

1. Replace execution stubs with a real execution layer
2. Replace memory stubs with a real long-term memory layer
3. Expose richer runtime events to the demo client
4. Implement `MonitoringLoop`
5. Implement `GuidanceLoop`

### 7.3 What Should Not Be Reopened Right Now

- Python-first vs. TypeScript-first
- gateway/runtime/store/execution/memory package split
- demo client vs. formal app-client separation
- debug-stage media transport compromise

Those are already baseline decisions.

---

## 8. Suggested Team Split

The current baseline is ready for parallel work.

- Gateway owner
  - `apps/gateway`
  - protocol ingress and session handling
- Runtime core owner
  - `packages/runtime_core`
  - Fast/Slow/TaskRuntime and loop lifecycles
- Runtime store owner
  - `packages/runtime_store`
  - state invariants and query/snapshot behavior
- Execution owner
  - `packages/execution`
  - tool execution and workers
- Memory owner
  - `packages/memory`
  - long-term memory behavior
- Demo/debug client owner
  - `apps/demo-client`
  - debug UX and runtime observability

---

## 9. Related Docs

- [Architecture Spec](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md)
- [Python-First Runtime Rebuild Plan](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/docs/superpowers/plans/2026-04-07-python-first-runtime-rebuild.md)
- [Demo Client Debug Loop Plan](/Users/chengqinglin/Documents/live_vision_chat/.worktrees/reuse-first-runtime/docs/superpowers/plans/2026-04-07-demo-client-debug-loop.md)
