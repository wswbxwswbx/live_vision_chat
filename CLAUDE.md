# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This project is in the **design phase**. The repository contains architecture documentation but no implementation yet. No build system, test framework, or runtime dependencies exist as of April 2026.

## Key Documentation

- `README.md` — Project overview
- `AGENTS.md` — High-level agent taxonomy
- `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md` — **Primary architecture spec** (2800+ lines, Chinese). This is the source of truth for all design decisions.
- `docs/superpowers/specs/talker 模型设计.md` — Detailed Fast Agent (Talker) design

## Architecture

### Two-Agent System

The system splits responsibilities between a **Fast Agent (Talker)** and a **Slow Agent**:

| | Fast Agent | Slow Agent |
|---|---|---|
| Purpose | Real-time voice dialog (100–300ms) | Async multi-step task execution |
| Input | `turn` messages from client (audio/text/video) | `handoff` messages from Fast Agent |
| Output | TTS audio stream + task events | `task_event` callbacks to Fast Agent |
| Tool calls | Max 2 planning rounds (text_search, image_search) | Unlimited; multi-step planning |
| Loop style | Synchronous (blocking per turn) | Event-driven with checkpointing |

### Handoff Flow

```
User turn → Fast Agent → simple? → respond directly via TTS
                       → complex? → collect params → send handoff → Slow Agent
                                                                        ↓
                                                               checkpoint each step
                                                                        ↓
                                                               task_event (completed/progress/failed)
                                                                        ↓
Fast Agent finds gap → announces result via TTS
```

### Slow Agent Loop Types

Three `StreamingLoop` primitives for persistent tasks:
- **AccumulationLoop** — progressively compresses inputs (e.g., meeting minutes)
- **MonitoringLoop** — detects conditions and fires alerts (e.g., presence detection)
- **GuidanceLoop** — issues instruction → observes video feedback → decides next step (e.g., repair guidance)

Plus **OneShotLoop** for single-execution tasks (e.g., set alarm).

### State Persistence

Two layers:
- **Runtime Store** (current session): `tasks/{task_id}.json`, `checkpoints/{task_id}.json`, `conversation/{dialog_id}.json`
- **Long-term Memory** (cross-session): `long_term_memory/{user,feedback,project,reference,skills}/` with an `INDEX.md`

Checkpoints enable crash recovery — Slow Agent resumes `RUNNING`/`WAITING_USER` tasks on startup.

### Client Protocol (WebSocket)

Client → Cloud:
```json
{"type": "turn", "dialog_id": "...", "audio": "base64", "transcript": "...", "timestamp": 0}
```

Cloud → Client:
```json
{"type": "tts", "dialog_id": "...", "data": "base64-audio", "seq": 0, "is_end": false}
```

Fast ↔ Slow communication is in-process (in-memory queue or mailbox files), not over WebSocket.

### TTS Queue

Priority-based scheduler: `interrupt` (high) > `queue` (normal) > `silent`. Slow Agent sets `speak_policy` per `task_event` to control announcement timing. Decoupled `execution_state` and `delivery_state` prevent audio collision.

### Skill System

Two layers:
1. **System Skills** — Python classes with `name`, `description`, `params`, and `execute()`
2. **User-Defined Skills** — Markdown files auto-discovered from `long_term_memory/skills/`, executable without restart

Fast Agent receives a JSON manifest at startup listing `fast_tools` (directly callable) and `slow_tools` (require handoff).

### Python Sandbox (for Slow Agent code execution)

Three-layer security: static AST import checking → safe helper injection (`http_get`, `read_memory`, `write_file`, etc.) → bash sandbox with resource limits (128MB RAM, 30s timeout, no subprocess, restricted file paths).
