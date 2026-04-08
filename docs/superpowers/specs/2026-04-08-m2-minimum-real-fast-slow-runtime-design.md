# M2 Minimum Real Fast/Slow Runtime Design

**Date:** 2026-04-08  
**Status:** Implemented
**Scope:** M2 milestone for making the current Python-first Fast/Slow runtime minimally real before starting streaming-loop work

---

## 0. Implementation Status

This spec now describes shipped runtime behavior in the Python mainline.

M2 is implemented with:

- direct Fast replies for non-reminder turns
- reminder handoff through `RuntimeFacade`
- Slow reminder completion and `waiting_user`
- `handoff_resume` recovery for missing reminder time
- in-memory reminder execution records
- demo-client reminder resume support
- session-bound `handoff_resume` validation and recoverable invalid-resume replies

Current follow-up direction is:

- keep M2 stable
- start `M3: Streaming Ingress + First AccumulationLoop`

## 1. Goal

M2 exists to turn the current runtime skeleton into a minimally real Fast/Slow system.

The milestone is complete when the system can run one real background task chain end to end:

`user turn -> Fast decision -> handoff -> Slow task -> execution -> task_event/checkpoint -> optional waiting_user -> handoff_resume -> completed`

The first and only real task capability in M2 is:

- `create_reminder`

This milestone is about validating runtime behavior, not about building a broad task catalog.

---

## 2. Why M2 Came Before Streaming

At design time, current code already had:

- Python-first gateway
- protocol and shared runtime store
- demo client with text, audio uplink, video uplink, and runtime panels
- `FastRuntime / SlowRuntime / TaskRuntime / RuntimeFacade` skeletons

At design time, current code did **not** yet have:

- a real Fast decision path
- a real Slow one-shot task runner
- a real Fast-to-Slow handoff path
- a real execution path through `packages/execution`
- `waiting_user / handoff_resume` behavior

That is why the next milestone could not start from streaming work.

If streaming input is routed now, it only lands in an incomplete runtime shell.

The resulting order was:

1. M2: Minimum Real Fast/Slow Runtime
2. M3: Streaming Ingress + First AccumulationLoop

This ordering matches the current code reality and the architecture intent from the main design spec.

---

## 3. Scope

### 3.1 Included

- minimally real `FastRuntime`
- minimally real `SlowRuntime`
- minimally real `TaskRuntime`
- real Fast-to-Slow handoff
- real `handoff_resume`
- one real execution path through `packages/execution`
- in-memory reminder registry
- task event and checkpoint visibility through snapshot and demo client

### 3.2 Excluded

- `StreamingLoop`
- `AccumulationLoop / MonitoringLoop / GuidanceLoop`
- true ASR
- true visual reasoning
- external reminder/calendar integration
- advanced time normalization
- long-term memory integration

---

## 4. Capability Chosen for M2

M2 uses one real task type:

- `create_reminder`

Why this task:

- it is clearly background-executable
- it naturally exercises Fast triage and Slow completion
- it naturally exercises `waiting_user`
- it fits a clean execution interface
- it is easy to observe in runtime state and demo UI

Rejected alternatives:

- generic summarization: too weak as a task-runtime proof
- broad todo management: too open-ended for a first milestone
- schedule/calendar integration: too much external-system pressure too early

---

## 5. Runtime Behavior

### 5.1 Fast Runtime

`FastRuntime` remains thin.

Responsibilities:

- receive `turn`
- classify whether the turn should stay in Fast or hand off to Slow
- directly reply for non-reminder requests
- create a slow task for reminder requests
- send an immediate foreground acknowledgment for reminder requests

Non-responsibilities:

- creating reminders directly
- long task lifecycle
- long task recovery
- execution-layer logic

The first implementation uses a thin classifier interface with a rule-based implementation.

This keeps the decision point abstract without prematurely requiring a model-backed classifier.

### 5.2 Slow Runtime

`SlowRuntime` becomes the owner of the first real one-shot task flow.

Responsibilities:

- accept the reminder task
- transition through lifecycle states
- decide whether the task can complete or must wait for user input
- call the reminder execution path
- write task events and checkpoints
- emit assistant-visible completion or clarification text

### 5.3 Task Runtime

`TaskRuntime` becomes the lifecycle helper for reminder tasks.

It must support at least:

- accept
- mark running
- mark waiting_user
- mark completed
- mark failed

It remains the owner of task lifecycle state, not the gateway and not the execution layer.

### 5.4 Runtime Facade

`RuntimeFacade` remains the only runtime entrypoint used by the gateway.

It must route:

- `turn`
- `handoff_resume`

It must not expose internal Fast/Slow objects to gateway code.

---

## 6. Reminder Task Flow

### 6.1 Direct Fast Reply

For non-reminder requests:

1. user sends `turn`
2. Fast classifies request as non-reminder
3. Fast returns a foreground response
4. no slow task is created

### 6.2 Fast Handoff

For reminder requests:

1. user sends `turn`
2. Fast classifies request as `create_reminder`
3. Fast creates a slow task in runtime state
4. Fast returns immediate acknowledgment text
5. Slow takes ownership of the task

### 6.3 Slow Completes Directly

If reminder intent is sufficiently complete:

1. Slow extracts reminder fields
2. Slow calls execution
3. execution creates reminder result
4. Slow writes completion state
5. Slow emits:
   - `task_event`
   - assistant completion text

### 6.4 Slow Enters `waiting_user`

If reminder subject is clear but time is missing or uncertain:

1. Slow extracts reminder title
2. Slow determines `scheduled_at` is missing or unresolved
3. task enters `waiting_user`
4. checkpoint is written
5. Slow emits:
   - `task_event`
   - assistant clarification text asking for time

### 6.5 `handoff_resume`

When the user responds to the clarification:

1. client sends `handoff_resume`
2. `RuntimeFacade` routes it to the matching slow task
3. Slow restores task context from checkpoint
4. Slow treats the new user text as time completion only
5. execution creates reminder result
6. task transitions to `completed`
7. Slow emits:
   - `task_event`
   - assistant completion text

`handoff_resume` in M2 is explicitly scoped to filling the missing reminder time.

It does not reopen title extraction or re-interpret the whole task.

---

## 7. Data Model

### 7.1 Reminder Result

The first reminder result model should include:

- `id`
- `title`
- `scheduled_at_text`
- `scheduled_at_iso` optional
- `status`
- `source_session_id`
- `task_id`
- `raw_user_input`
- `created_at`

### 7.2 Time Strategy

M2 should not block on strong time parsing.

Recommended strategy:

- always preserve `scheduled_at_text`
- populate `scheduled_at_iso` only when parsing is straightforward
- if time is missing or too unclear, use `waiting_user`

This keeps M2 focused on runtime behavior rather than early natural-language time parsing complexity.

### 7.3 Checkpoint Payload

At minimum, reminder checkpoints must hold:

- `task_type = create_reminder`
- `title`
- `raw_user_input`
- current `scheduled_at_text` if any
- `missing_field = scheduled_at`

Checkpoint restore should be narrow and explicit.

---

## 8. State Machine

### 8.1 Fast Result Types

Fast only needs two outcomes:

- `reply`
- `handoff`

This keeps Fast thin and avoids leaking task-lifecycle responsibilities into foreground logic.

### 8.2 Reminder Task States

M2 reminder tasks should use:

- `accepted`
- `running`
- `waiting_user`
- `completed`
- `failed`

Valid transitions:

- `accepted -> running`
- `running -> completed`
- `running -> waiting_user`
- `running -> failed`
- `waiting_user -> running`
- `waiting_user -> failed`

Not part of M2:

- `cancelled`
- `paused`
- `superseded`

### 8.3 `waiting_user` Definition

In M2, `waiting_user` means exactly one thing:

- reminder subject is known
- reminder time is missing or unresolved
- the task cannot continue without a user-supplied time

This state must not be overloaded for unrelated failure or ambiguity modes.

---

## 9. Execution Layer

M2 should make `packages/execution` real through one narrow interface.

### 9.1 New Interface

Introduce a reminder service interface, for example:

- `create_reminder(...) -> ReminderRecord`

### 9.2 First Implementation

Provide an in-memory reminder registry implementation.

This implementation is not the final product target. It exists to validate:

- runtime-to-execution integration
- result persistence at execution scope
- clean replacement of the implementation later

### 9.3 Boundary Rule

Execution returns structured reminder results.

Execution must not:

- emit user-facing assistant text
- mutate conversation state
- handle task routing

That work stays in runtime orchestration.

---

## 10. Protocol and Client Behavior

### 10.1 Protocol

M2 should reuse existing protocol shapes where possible.

Key rule:

- do not create a reminder-specific resume message

Use:

- `turn`
- `handoff_resume`
- `assistant_text`
- `task_event`

### 10.2 Demo Client

The demo client should remain an observability/debug tool.

For M2 it must be able to show:

- direct Fast replies
- reminder handoff acknowledgment
- `waiting_user`
- completion
- reminder-related task events

The chat input should also serve as the recovery path for `handoff_resume`.

---

## 11. Acceptance Criteria Now Shipped

The items below are now part of the current implementation baseline.

M2 is accepted only if all of the following are true.

### 11.1 Fast Direct Reply

For a non-reminder request:

- Fast replies directly
- no slow task is created

### 11.2 Reminder Handoff

For a reminder request:

- Fast classifies it as reminder
- a slow task is created
- Fast returns immediate acknowledgment
- Slow takes ownership

### 11.3 Direct Slow Completion

For a reminder request with complete reminder information:

- Slow completes the task
- execution returns a reminder result
- task reaches `completed`
- user sees assistant completion text

### 11.4 `waiting_user / handoff_resume`

For a reminder request without sufficient time information:

- Slow enters `waiting_user`
- checkpoint is written
- user receives a clarification question
- `handoff_resume` continues the same task
- task then completes successfully

### 11.5 Execution Visibility

Reminder results can be inspected in the in-memory reminder registry.

### 11.6 Demo Client Visibility

The demo client can show:

- task creation
- task waiting state
- task completion
- assistant completion text

---

## 12. Non-Goals

M2 does not attempt to solve:

- production-grade reminder integration
- streaming loop orchestration
- long-term memory persistence
- rich time understanding
- full tool-call lifecycle generalization

Those remain follow-up milestones.

---

## 13. Next Step After M2

After M2:

1. keep the shipped M2 reminder path stable
2. write the M3 streaming-ingress plan on top of the current runtime baseline
3. only then extend into the first real `AccumulationLoop`
