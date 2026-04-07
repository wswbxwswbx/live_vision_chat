# Demo Client Debug Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-local `apps/demo-client` that validates the Python gateway and runtime through a lightweight but realistic browser client. The client should support text chat, continuous audio chunk upload, low-frame-rate video upload, browser TTS playback, and runtime state visualization without pretending to be the final product client.

**Architecture:** Keep the Python gateway as the single live backend. Add a React + Vite demo client that speaks to the gateway over HTTP + WebSocket. Use structured media messages with `base64` payloads during the debug phase, but explicitly preserve formal product goals in the docs: final product clients stay app-native, media transport later graduates away from this debug transport, and runtime-facing streaming semantics must remain stable.

**Tech Stack:** React, Vite, TypeScript, browser Media APIs, WebSocket, pytest, Vitest

---

## File Structure

- Create: `apps/demo-client/package.json`
- Create: `apps/demo-client/tsconfig.json`
- Create: `apps/demo-client/vite.config.ts`
- Create: `apps/demo-client/index.html`
- Create: `apps/demo-client/src/main.tsx`
- Create: `apps/demo-client/src/app/App.tsx`
- Create: `apps/demo-client/src/app/app.css`
- Create: `apps/demo-client/src/app/types.ts`
- Create: `apps/demo-client/src/app/session-store.ts`
- Create: `apps/demo-client/src/app/session-controller.ts`
- Create: `apps/demo-client/src/app/mock-client.ts`
- Create: `apps/demo-client/src/lib/gateway-client.ts`
- Create: `apps/demo-client/src/lib/media/audio-stream.ts`
- Create: `apps/demo-client/src/lib/media/video-stream.ts`
- Create: `apps/demo-client/src/lib/media/tts.ts`
- Create: `apps/demo-client/src/app/components/ChatPanel.tsx`
- Create: `apps/demo-client/src/app/components/MediaPanel.tsx`
- Create: `apps/demo-client/src/app/components/RuntimePanel.tsx`
- Create: `apps/demo-client/src/app/components/StatusBar.tsx`
- Create: `apps/demo-client/src/app/session-store.test.ts`
- Create: `apps/demo-client/src/app/session-controller.test.ts`
- Create: `apps/demo-client/src/lib/gateway-client.test.ts`
- Update: `packages/protocol/src/protocol/messages.py`
- Update: `packages/protocol/tests/test_messages.py`
- Update: `apps/gateway/ws.py`
- Update: `apps/gateway/tests/test_ws_session.py`
- Update: `README.md`

---

## Task 1: Capture the Demo Client Contract

**Files:**
- Update: `packages/protocol/src/protocol/messages.py`
- Update: `packages/protocol/tests/test_messages.py`

- [ ] Add protocol models for `assistant_text`, `audio_chunk`, and `video_frame`
- [ ] Keep payloads structured and debuggable, including metadata fields for timestamps and sequence counters
- [ ] Preserve the distinction between debug transport compromise and formal product target in inline comments only where necessary
- [ ] Verify protocol tests pass

## Task 2: Extend the Python Gateway for Demo Client Streaming Messages

**Files:**
- Update: `apps/gateway/ws.py`
- Update: `apps/gateway/tests/test_ws_session.py`

- [ ] Accept `audio_chunk` and `video_frame` messages on the session websocket
- [ ] Return a minimal `assistant_text` event for text turns so the client can drive chat + browser TTS
- [ ] Keep gateway behavior thin; do not implement media intelligence in the gateway
- [ ] Verify gateway websocket tests pass

## Task 3: Scaffold the Demo Client App

**Files:**
- Create: `apps/demo-client/package.json`
- Create: `apps/demo-client/tsconfig.json`
- Create: `apps/demo-client/vite.config.ts`
- Create: `apps/demo-client/index.html`
- Create: `apps/demo-client/src/main.tsx`
- Create: `apps/demo-client/src/app/App.tsx`
- Create: `apps/demo-client/src/app/app.css`

- [ ] Scaffold a Vite React app inside `apps/demo-client`
- [ ] Build the three-column layout plus top status bar
- [ ] Keep styling intentional but lightweight; this is a debug client, not product UI

## Task 4: Build the Demo Client State Model

**Files:**
- Create: `apps/demo-client/src/app/types.ts`
- Create: `apps/demo-client/src/app/session-store.ts`
- Create: `apps/demo-client/src/app/session-controller.ts`
- Create: `apps/demo-client/src/app/mock-client.ts`
- Create: `apps/demo-client/src/app/session-store.test.ts`
- Create: `apps/demo-client/src/app/session-controller.test.ts`

- [ ] Track connection state, chat messages, conversation, tasks, task events, checkpoints, and latest media summaries
- [ ] Bootstrap state from the snapshot endpoint before opening live websocket updates
- [ ] Support a very small mock mode without duplicating full runtime behavior
- [ ] Verify store/controller tests pass

## Task 5: Add Gateway Client and Media Helpers

**Files:**
- Create: `apps/demo-client/src/lib/gateway-client.ts`
- Create: `apps/demo-client/src/lib/media/audio-stream.ts`
- Create: `apps/demo-client/src/lib/media/video-stream.ts`
- Create: `apps/demo-client/src/lib/media/tts.ts`
- Create: `apps/demo-client/src/lib/gateway-client.test.ts`

- [ ] Add a browser client for snapshot fetch + websocket lifecycle
- [ ] Implement continuous microphone chunking over websocket
- [ ] Implement low-frame-rate camera capture over websocket
- [ ] Implement browser TTS using `speechSynthesis`
- [ ] Verify targeted frontend tests pass

## Task 6: Build the Demo Panels

**Files:**
- Create: `apps/demo-client/src/app/components/ChatPanel.tsx`
- Create: `apps/demo-client/src/app/components/MediaPanel.tsx`
- Create: `apps/demo-client/src/app/components/RuntimePanel.tsx`
- Create: `apps/demo-client/src/app/components/StatusBar.tsx`
- Update: `apps/demo-client/src/app/App.tsx`

- [ ] Render chat, media preview/status, and runtime state in the agreed layout
- [ ] Show conversation, tasks, recent task events, checkpoints, and recent media summaries
- [ ] Avoid waveform or volume-bar work in this phase

## Task 7: Update README and Verify the Debug Flow

**Files:**
- Update: `README.md`

- [ ] Document the debug-stage transport compromise vs. the formal product target
- [ ] Add local run instructions for gateway + demo client
- [ ] Run protocol, gateway, and demo client tests
- [ ] Perform a local smoke check for `health`, `snapshot`, websocket text turn, and basic media capture boot
