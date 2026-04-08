# live_vision_chat

This repository is the single source of truth for the `live_vision_chat` project.

## Scope

- Maintain product/design docs here
- Maintain implementation here going forward
- Keep reference architectures out of Git history unless explicitly curated

## Current Structure

- `docs/superpowers/specs/`
  - architecture and design specs
- `apps/gateway`
  - Python `FastAPI` ingress for health, snapshots, and session websocket endpoints
- `apps/demo-client`
  - React + Vite browser client for gateway/runtime integration debugging
- `packages/protocol`
  - Python protocol schema and parsing helpers
- `packages/runtime_store`
  - Python shared runtime state truth source
- `packages/runtime_core`
  - Python Fast/Slow runtime orchestration, task lifecycle, snapshots, and facade
- `packages/execution`
  - Python execution interfaces plus the first in-memory reminder service
- `packages/memory`
  - Python long-term memory stubs

## M2 Reminder Flow

The current M2 runtime path supports one minimally real Fast/Slow task flow for `create_reminder`.

- `FastRuntime` triages direct replies versus reminder handoff
- `RuntimeFacade` immediately runs the reminder handoff through `SlowRuntime`
- `SlowRuntime` either completes the reminder or enters `waiting_user`
- `handoff_resume` continues the same reminder task when only time input is missing
- reminder results are stored in the in-memory execution registry and reflected in runtime snapshots

## Docs Map

- Long-term architecture direction:
  - `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
- Shipped M2 runtime behavior:
  - `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md`
- Current implementation status and next milestone:
  - `docs/superpowers/status/2026-04-08-m2-runtime-status.md`
- Historical pre-M2 baseline only:
  - `docs/superpowers/status/2026-04-07-python-runtime-baseline.md`

## Reference Policy

Reference codebases are used for inspiration only. They are not the product source of truth.

- Do not commit large upstream reference trees by default
- If a reference excerpt is worth preserving, copy only the minimal curated subset
- Keep repo-owned design decisions in this repository

## Working Agreement

- Use this repository as the main workspace going forward
- Prefer updating docs here rather than under legacy local folders
- Treat `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md` as the long-term architecture source of truth
- Treat `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md` as the current runtime-behavior baseline
- Treat `docs/superpowers/status/2026-04-08-m2-runtime-status.md` as the current shipped-state and next-step summary
- Treat the Python packages as the formal implementation mainline

## Python Setup And Verification

Use a Python 3.11+ environment from the repository root.

Current `pyproject.toml` configures `pytest` import paths, but it does not yet lock server dependencies. Before running the gateway or Python tests, make sure your active environment already includes the packages used by the current server stack, including:

- `fastapi`
- `uvicorn`
- `pydantic`
- `pytest`
- `httpx`

Run targeted or full Python verification from the worktree root:

```bash
python -m pytest packages apps/gateway/tests -q
```

Current Python foundation includes:

- `protocol`
- `runtime_store`
- `runtime_core`
- `gateway`
- `execution`
- `memory`

## Local Debug Flow

Start the Python gateway on port `3000` from the worktree root:

```bash
python -m apps.gateway.dev
```

Install demo-client dependencies:

```bash
cd apps/demo-client
corepack pnpm install
```

Start the demo client:

```bash
corepack pnpm dev
```

Then open the Vite URL in a browser. The demo client will:

- fetch `GET /sessions/:session_id/snapshot`
- open `ws://<host>:3000/sessions/:session_id`
- send `turn`, `handoff_resume`, `audio_chunk`, and `video_frame`
- render chat, conversation, tasks, checkpoints, and recent task events
- reuse the chat box to continue a `waiting_user` reminder task
- play assistant text through browser `speechSynthesis`

## Debug-Stage Media Transport

The browser demo client uses a debug-stage transport compromise:

- media travels over `WebSocket`
- payloads are wrapped in structured messages with `base64` data
- TTS currently uses browser `speechSynthesis`

This is not the formal product target. Final product clients remain app-native, and the long-term architecture still expects a cleaner separation between control-plane traffic and production media transport.
