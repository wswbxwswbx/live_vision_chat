# Python Runtime Baseline Summary (Historical)

**Date:** 2026-04-07  
**Status:** Historical baseline before M2
**Scope:** Repository checkpoint for the pre-M2 Python-first server skeleton

---

This document is retained as a historical checkpoint only.

It no longer describes the current shipped codebase.

Use these documents instead when continuing development:

- current architecture direction:
  - `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
- shipped M2 runtime behavior:
  - `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md`
- current implementation status and next milestone:
  - `docs/superpowers/status/2026-04-08-m2-runtime-status.md`

What this historical baseline established:

- Python-first package split for `gateway / protocol / runtime_store / runtime_core / execution / memory`
- repository-local demo client for integration debugging
- initial gateway, snapshot, websocket, and runtime-observability skeleton

What changed after this baseline:

- M2 made the Fast/Slow runtime minimally real
- reminder execution and `waiting_user / handoff_resume` are now implemented
- the demo client can now resume reminder tasks

Do not use this file as the current implementation guide.
