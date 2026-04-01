# AGENTS.md

## Project Context

This repository is for a live, multimodal assistant focused on:

- real-time voice interaction
- background task execution
- physical-world observation and guidance

The current architecture direction is:

- `Fast Agent` for live dialog and immediate user-facing responses
- `Slow Agent` for background execution and streaming tasks
- `Runtime Store` for conversation/task/checkpoint state
- `Long-term Memory` for cross-session user/project/reference knowledge

## Streaming Loop Taxonomy

Streaming tasks are currently organized around three primitives:

- `AccumulationLoop`
- `MonitoringLoop`
- `GuidanceLoop`

Complex physical-world tasks may switch loop mode during a single task lifecycle.

## Reference Code Policy

The project may use local reference codebases for study, but they should not be committed wholesale by default.

- avoid committing `reference/` trees unless explicitly requested
- preserve only curated design conclusions in this repo

## Documentation

Primary design doc:

- `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
