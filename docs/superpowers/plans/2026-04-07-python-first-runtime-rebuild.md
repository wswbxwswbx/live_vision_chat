# Python-First Runtime Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the project's formal runtime backbone in Python-first form while preserving the current Fast/Slow/shared-memory architecture semantics from the design spec.

**Architecture:** Build a Python monorepo with a thin `FastAPI` gateway, a framework-agnostic runtime core, a shared runtime store, and isolated execution/memory packages. Keep deployment single-process at first, but enforce package boundaries so gateway, runtime, store, execution, and memory can later split across teams or processes without redesign.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, asyncio, pytest, uv or pip, ruff, mypy

---

## File Structure

- Create: `pyproject.toml`
- Create: `apps/gateway/app.py`
- Create: `apps/gateway/ws.py`
- Create: `apps/gateway/http.py`
- Create: `apps/gateway/tests/test_health.py`
- Create: `apps/gateway/tests/test_snapshot_api.py`
- Create: `apps/gateway/tests/test_ws_session.py`
- Create: `packages/protocol/src/protocol/messages.py`
- Create: `packages/protocol/src/protocol/session_envelope.py`
- Create: `packages/protocol/src/protocol/task_events.py`
- Create: `packages/protocol/src/protocol/tool_calls.py`
- Create: `packages/protocol/tests/test_messages.py`
- Create: `packages/runtime_store/src/runtime_store/models.py`
- Create: `packages/runtime_store/src/runtime_store/interfaces.py`
- Create: `packages/runtime_store/src/runtime_store/memory_store.py`
- Create: `packages/runtime_store/tests/test_memory_store.py`
- Create: `packages/runtime_core/src/runtime_core/session_conversation_registry.py`
- Create: `packages/runtime_core/src/runtime_core/session_task_registry.py`
- Create: `packages/runtime_core/src/runtime_core/task_runtime.py`
- Create: `packages/runtime_core/src/runtime_core/fast_runtime.py`
- Create: `packages/runtime_core/src/runtime_core/slow_runtime.py`
- Create: `packages/runtime_core/src/runtime_core/runtime_facade.py`
- Create: `packages/runtime_core/src/runtime_core/session_snapshot.py`
- Create: `packages/runtime_core/tests/test_fast_runtime.py`
- Create: `packages/runtime_core/tests/test_task_runtime.py`
- Create: `packages/runtime_core/tests/test_runtime_facade.py`
- Create: `packages/runtime_core/tests/test_session_snapshot.py`
- Create: `packages/execution/src/execution/tool_executor.py`
- Create: `packages/execution/src/execution/slow_task_runner.py`
- Create: `packages/execution/tests/test_tool_executor.py`
- Create: `packages/execution/tests/test_slow_task_runner.py`
- Create: `packages/memory/src/memory/interfaces.py`
- Create: `packages/memory/src/memory/in_memory_memory_system.py`
- Create: `packages/memory/tests/test_memory_system.py`
- Modify later: `README.md`
- Modify later: `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`

## Task 1: Bootstrap Python Workspace

**Files:**
- Create: `pyproject.toml`
- Create: `packages/protocol/src/protocol/__init__.py`
- Create: `packages/runtime_store/src/runtime_store/__init__.py`
- Create: `packages/runtime_core/src/runtime_core/__init__.py`
- Create: `packages/execution/src/execution/__init__.py`
- Create: `packages/memory/src/memory/__init__.py`

- [ ] **Step 1: Write the failing workspace smoke test**

```python
def test_python_workspace_imports() -> None:
    import protocol  # noqa: F401
    import runtime_store  # noqa: F401
    import runtime_core  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest packages/runtime_core/tests/test_workspace_smoke.py -v`
Expected: FAIL with import errors because packages are not configured.

- [ ] **Step 3: Write minimal workspace configuration**

```toml
[project]
name = "live-vision-chat"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = [
  "packages/protocol/src",
  "packages/runtime_store/src",
  "packages/runtime_core/src",
  "packages/execution/src",
  "packages/memory/src",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest packages/runtime_core/tests/test_workspace_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml packages
git commit -m "chore: bootstrap python workspace"
```

## Task 2: Build Protocol Schemas

**Files:**
- Create: `packages/protocol/src/protocol/messages.py`
- Create: `packages/protocol/src/protocol/session_envelope.py`
- Create: `packages/protocol/src/protocol/task_events.py`
- Create: `packages/protocol/src/protocol/tool_calls.py`
- Create: `packages/protocol/tests/test_messages.py`

- [ ] **Step 1: Write failing protocol tests**

```python
def test_parse_turn_message() -> None:
    payload = {"type": "turn", "sessionId": "s1", "messageId": "m1", "payload": {"text": "hi"}}
    message = parse_client_message(payload)
    assert message.type == "turn"
    assert message.payload.text == "hi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/protocol/tests/test_messages.py -v`
Expected: FAIL because schema modules do not exist.

- [ ] **Step 3: Implement minimal Pydantic protocol models**

```python
class TurnPayload(BaseModel):
    text: str

class TurnMessage(BaseModel):
    type: Literal["turn"]
    sessionId: str
    messageId: str
    payload: TurnPayload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/protocol/tests/test_messages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/protocol pyproject.toml
git commit -m "feat: add python protocol schemas"
```

## Task 3: Build Shared Runtime Store

**Files:**
- Create: `packages/runtime_store/src/runtime_store/models.py`
- Create: `packages/runtime_store/src/runtime_store/interfaces.py`
- Create: `packages/runtime_store/src/runtime_store/memory_store.py`
- Create: `packages/runtime_store/tests/test_memory_store.py`

- [ ] **Step 1: Write failing store tests for ownership and invariants**

```python
def test_slow_cannot_change_speaker_owner() -> None:
    store = InMemoryRuntimeStore()
    store.upsert_conversation("dialog-1", {"dialog_id": "dialog-1", "speaker_owner": "fast"}, actor="system")
    with pytest.raises(ValueError):
        store.upsert_conversation("dialog-1", {"speaker_owner": "slow"}, actor="slow")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/runtime_store/tests/test_memory_store.py -v`
Expected: FAIL because runtime store is not implemented.

- [ ] **Step 3: Implement multi-conversation shared store**

```python
class InMemoryRuntimeStore(RuntimeStore):
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationState] = {}
        self._tasks: dict[str, TaskRecord] = {}
        self._checkpoints: dict[str, CheckpointRecord] = {}
        self._events: dict[str, list[TaskEventRecord]] = {}
        self._tool_calls: dict[str, ToolCallRecord] = {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/runtime_store/tests/test_memory_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/runtime_store pyproject.toml
git commit -m "feat: add python shared runtime store"
```

## Task 4: Build Session Registries and Snapshot Reader

**Files:**
- Create: `packages/runtime_core/src/runtime_core/session_conversation_registry.py`
- Create: `packages/runtime_core/src/runtime_core/session_task_registry.py`
- Create: `packages/runtime_core/src/runtime_core/session_snapshot.py`
- Create: `packages/runtime_core/tests/test_session_snapshot.py`

- [ ] **Step 1: Write failing snapshot tests**

```python
def test_snapshot_collects_conversation_tasks_and_tool_calls() -> None:
    snapshot = reader.get_session_snapshot("session-1")
    assert snapshot.dialog_id == "dialog-1"
    assert len(snapshot.tasks) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/runtime_core/tests/test_session_snapshot.py -v`
Expected: FAIL because registries and snapshot reader do not exist.

- [ ] **Step 3: Implement registries and reader**

```python
class SessionTaskRegistry:
    def bind_task(self, session_id: str, task_id: str) -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/runtime_core/tests/test_session_snapshot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/runtime_core pyproject.toml
git commit -m "feat: add python session snapshot support"
```

## Task 5: Build Fast Runtime Skeleton

**Files:**
- Create: `packages/runtime_core/src/runtime_core/fast_runtime.py`
- Create: `packages/runtime_core/tests/test_fast_runtime.py`

- [ ] **Step 1: Write failing fast runtime tests**

```python
async def test_fast_runtime_initializes_conversation_on_first_turn() -> None:
    result = await runtime.handle_turn(session_id="s1", text="你好")
    assert result.reply_text is not None
    assert store.get_conversation("s1") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/runtime_core/tests/test_fast_runtime.py -v`
Expected: FAIL because fast runtime is not implemented.

- [ ] **Step 3: Implement minimal fast runtime**

```python
class FastRuntime:
    async def handle_turn(self, session_id: str, text: str) -> FastTurnResult:
        self._ensure_conversation(session_id)
        return FastTurnResult(reply_text="stub")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/runtime_core/tests/test_fast_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/runtime_core pyproject.toml
git commit -m "feat: add python fast runtime skeleton"
```

## Task 6: Build Task Runtime and Slow Runtime Skeleton

**Files:**
- Create: `packages/runtime_core/src/runtime_core/task_runtime.py`
- Create: `packages/runtime_core/src/runtime_core/slow_runtime.py`
- Create: `packages/runtime_core/tests/test_task_runtime.py`

- [ ] **Step 1: Write failing task runtime tests**

```python
async def test_accept_attaches_task_to_background_and_sets_attention_slow() -> None:
    await task_runtime.accept(task_id="task-1", dialog_id="dialog-1")
    conversation = store.get_conversation("dialog-1")
    assert conversation.attention_owner == "slow"
    assert "task-1" in conversation.background_task_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/runtime_core/tests/test_task_runtime.py -v`
Expected: FAIL because task runtime is not implemented.

- [ ] **Step 3: Implement minimal task runtime and one-shot slow runtime**

```python
class TaskRuntime:
    async def accept(self, task_id: str, dialog_id: str) -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/runtime_core/tests/test_task_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/runtime_core pyproject.toml
git commit -m "feat: add python slow runtime skeleton"
```

## Task 7: Build Runtime Facade

**Files:**
- Create: `packages/runtime_core/src/runtime_core/runtime_facade.py`
- Create: `packages/runtime_core/tests/test_runtime_facade.py`

- [ ] **Step 1: Write failing facade tests**

```python
async def test_runtime_facade_routes_turn_and_exposes_snapshot() -> None:
    await facade.handle_client_message(turn_message)
    snapshot = facade.get_session_snapshot("s1")
    assert snapshot is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/runtime_core/tests/test_runtime_facade.py -v`
Expected: FAIL because facade is not implemented.

- [ ] **Step 3: Implement minimal facade**

```python
class RuntimeFacade:
    async def handle_client_message(self, message: ClientMessage) -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/runtime_core/tests/test_runtime_facade.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/runtime_core pyproject.toml
git commit -m "feat: add python runtime facade"
```

## Task 8: Build FastAPI Gateway

**Files:**
- Create: `apps/gateway/app.py`
- Create: `apps/gateway/http.py`
- Create: `apps/gateway/ws.py`
- Create: `apps/gateway/tests/test_health.py`
- Create: `apps/gateway/tests/test_snapshot_api.py`
- Create: `apps/gateway/tests/test_ws_session.py`

- [ ] **Step 1: Write failing gateway tests**

```python
def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/gateway/tests -v`
Expected: FAIL because gateway app is not implemented.

- [ ] **Step 3: Implement minimal FastAPI ingress**

```python
app = FastAPI()

@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/gateway/tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/gateway pyproject.toml
git commit -m "feat: add python gateway"
```

## Task 9: Build Execution Layer Stubs

**Files:**
- Create: `packages/execution/src/execution/tool_executor.py`
- Create: `packages/execution/src/execution/slow_task_runner.py`
- Create: `packages/execution/tests/test_tool_executor.py`
- Create: `packages/execution/tests/test_slow_task_runner.py`

- [ ] **Step 1: Write failing execution tests**

```python
async def test_tool_executor_reports_progress_and_completion() -> None:
    result = await executor.execute(tool_call)
    assert result.state == "completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/execution/tests -v`
Expected: FAIL because execution stubs do not exist.

- [ ] **Step 3: Implement minimal inline executors**

```python
class ToolExecutor:
    async def execute(self, tool_call: ToolCallRecord) -> ToolCallRecord:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/execution/tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/execution pyproject.toml
git commit -m "feat: add python execution stubs"
```

## Task 10: Build Long-term Memory Stubs

**Files:**
- Create: `packages/memory/src/memory/interfaces.py`
- Create: `packages/memory/src/memory/in_memory_memory_system.py`
- Create: `packages/memory/tests/test_memory_system.py`

- [ ] **Step 1: Write failing memory tests**

```python
def test_memory_system_stores_and_retrieves_entries() -> None:
    memory.write("user", "likes espresso")
    hits = memory.search("espresso")
    assert len(hits) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/memory/tests/test_memory_system.py -v`
Expected: FAIL because memory system is not implemented.

- [ ] **Step 3: Implement minimal in-memory memory system**

```python
class InMemoryMemorySystem:
    def write(self, namespace: str, content: str) -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest packages/memory/tests/test_memory_system.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/memory pyproject.toml
git commit -m "feat: add python memory stubs"
```

## Task 11: Run End-to-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the integration smoke test**

```python
def test_gateway_runtime_smoke() -> None:
    response = client.get("/health")
    assert response.status_code == 200
```

- [ ] **Step 2: Run targeted tests to verify gaps**

Run: `pytest packages apps/gateway/tests -v`
Expected: PASS except for any uncovered integration issue.

- [ ] **Step 3: Fix minimal integration issues**

```python
# only patch failing integration glue discovered by smoke tests
```

- [ ] **Step 4: Run full verification**

Run: `pytest -v`
Expected: PASS

Run: `ruff check .`
Expected: PASS

Run: `mypy packages apps`
Expected: PASS or a short documented allowlist if one remains.

- [ ] **Step 5: Commit**

```bash
git add README.md pyproject.toml apps packages
git commit -m "chore: verify python runtime foundation"
```

## Task 12: Document Migration Boundary

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`

- [ ] **Step 1: Write the failing docs checklist**

```text
- README explains Python-first workspace commands
- Spec references the implementation baseline correctly
- TS prototype is clearly labeled as prototype-only
```

- [ ] **Step 2: Review docs against the checklist**

Run: `rg -n "Python-first|prototype|pytest|ruff|mypy" README.md docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
Expected: Identify any missing guidance.

- [ ] **Step 3: Apply minimal doc updates**

```markdown
## Python Workspace

- `pytest -v`
- `ruff check .`
- `mypy packages apps`
```

- [ ] **Step 4: Re-run docs verification**

Run: `rg -n "Python-first|pytest|ruff|mypy" README.md docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
Expected: Matches all checklist items.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md
git commit -m "docs: document python runtime baseline"
```
