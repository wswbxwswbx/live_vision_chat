# Talker 实现计划

**日期**：2026-04-02  
**范围**：本仓库仅实现 Talker（Fast Agent）  
**技术栈**：Python + asyncio + FastAPI + Anthropic SDK

---

## 开始前需要拍板的技术决策

在写第一行代码前，以下 4 个决策必须确定，否则中途改动代价很高：

| 决策 | 推荐方案 | 备注 |
|------|---------|------|
| **WebSocket 框架** | FastAPI + websockets | 顺带解决 lifespan、健康检查 |
| **TTS 服务商** | ~~先 benchmark 再定~~ **暂用 Mock，优先级降低** | 主流程跑通后再对接真实 TTS；候选：阿里云 TTS |
| **Fast↔Slow 队列** | `asyncio.Queue` 封装为 `SlowInbox` 接口 | Demo 单进程；分布式时换 Redis，一文件改动 |
| **LLM 模型** | 阿里云百炼（Qwen），环境变量 `ALI_API_FOR_SEEK` | 兼容 OpenAI SDK 接口，base_url 指向阿里云百炼 |

---

## 阶段计划

### Phase 1 · 骨架与核心数据结构
**目标**：可运行的服务，接受 WebSocket 连接，路由消息，维护 Session 状态，所有处理器为 stub。无 LLM 调用。

**交付物**：
```
talker/
  main.py          # FastAPI app + WebSocket endpoint
  session.py       # SessionState + SessionManager
  router.py        # ProtocolRouter
  handlers.py      # 所有 handler（stub）
  models.py        # 所有消息的 Pydantic model
  interfaces.py    # ABCs: SlowInbox / RuntimeStore / MemoryIndex / TTSService
  stubs/           # 内存实现的各接口 stub
```

**完成标准**：
- SessionState 所有状态转换有单测覆盖
- 两个不同 `dialog_id` 的消息能创建两个独立 session
- 30 分钟无活动的 session 自动清理

---

### Phase 2 · TTS 队列
**目标**：完整的优先级调度、per-dialog 隔离、流式分片发送逻辑。TTS 服务仍用 Mock（返回固定音频）。

**完成标准**：
- high/normal/low 优先级按序出队
- 两个 dialog 的 TTS 互不干扰
- `clear_pending` 打断后 `seq` 和 `is_end` 正确
- 客户端收到连续 `seq=0,1,2...` 且最后 `is_end=true`

⚠️ **实现注意**：`_play_next` 是 async 递归调用，用 `asyncio.create_task`；`is_playing` 标记必须在 `enqueue` 里设为 `True` 再 `create_task`，否则有竞态。

---

### Phase 3 · LLM Engine + Prompt 构建
**目标**：真实 LLM 调用，两轮工具调用 loop，`_build_prompt`（system + 记忆 + history + user）。

**完成标准**：
- 普通问答全流程跑通，回复进入 TTS 队列
- history 超 20 轮后只传最近 20 轮（assert captured prompt）
- fast tool 调用正常执行并回填 LLM 第二轮
- `interrupt_epoch` 变化时丢弃进行中的 LLM 响应

⚠️ **重要 Bug（设计文档需修正）**：`session.lock` 不能持有到 LLM 调用期间（LLM 耗时 2-5s，此间同一 session 的 `turn` 消息全堵死）。正确做法：加锁读出状态 → 释放锁 → LLM 调用 → 加锁写回结果。**Phase 3 开始前先修设计文档。**

**测试策略**：用 `pytest-recording`（VCR cassette）录制真实 LLM 响应，CI 中回放，不消耗 API 额度。

---

### Phase 4 · Handoff + 参数收集状态机
**目标**：完整的 `collect_params` / `_handle_param_answer` 流程，`on_task_event` 全部 event_kind，handoff 超时检查，任务取消/查询。

**完成标准**：
- 完整闹钟设置流程：LLM 返回 slow tool → 追问 2 次 → handoff 发出
- handoff 后 Talker **零播报**，直到收到 `accepted` 事件
- `completed` 事件在对话间隙播报，`active_task_ids` 清空后 `attention_owner` 恢复 `fast`
- 用户说"算了"中途取消参数收集，状态机正确重置
- 30s 无 `accepted` 回应触发超时通知

⚠️ **最容易出 Bug 的地方**：`collecting_params` 状态下收到新 `stop_speech` 的分支逻辑，以及多任务并发时 `active_task_ids` 的增删。

---

### Phase 5 · 真实 TTS + 流式优化
**目标**：接入真实 TTS 服务商，实现句子边界流式（LLM 边生成边 TTS，不等完整响应）。

**完成标准**：
- 用户输入到第一个 TTS 音频分片：< 600ms（LLM 首 token ~300ms + TTS 首分片 ~200ms）
- 用户打断时 LLM stream 正确取消，TTS 队列正确清空
- 无 asyncio task 泄漏（`asyncio.all_tasks()` 不增长）

---

### Phase 6 · 集成测试 + 加固
**目标**：Demo 可用的稳定性，结构化日志，并发测试，错误路径全覆盖。

**完成标准**：
- 5 个并发 session 各跑 10 轮对话，无状态串扰
- 断线重连后 `active_task_ids` 和 `attention_owner` 从 checkpoint 正确恢复
- 所有错误路径（LLM 超时/限流、TTS 失败、Slow 无响应）有对应兜底播报
- `docker compose up` 启动，健康检查 200

---

## 依赖关系

```
Phase 1
  ├── Phase 2 (TTS)
  └── Phase 3 (LLM)  ← Phase 1 完成后可与 Phase 2 并行
        └── Phase 4 (Handoff)
              └── Phase 5 (Real TTS)
                    └── Phase 6 (Hardening)
```

---

## 主要风险

| 风险 | 概率 | 应对 |
|------|------|------|
| TTS 服务商不支持真正流式合成 | 中 | Phase 1 期间先跑 benchmark，选定再开发 |
| `session.lock` 持有 LLM 调用导致消息堆积 | 高（设计文档 bug） | Phase 3 前修设计文档，lock 只包裹状态读写 |
| `_find_gap_and_speak` 语义模糊 | 中 | 先实现最简版：`speaker_owner != "user"` 即播；后续按实际效果调整 |
| Slow Agent 未实现，Phase 4 难测试 | 高 | `SlowInbox` 是 asyncio.Queue，测试里跑一个 coroutine 模拟 Slow 回 `accepted` |

---

## 推荐文件结构

```
live_vision_chat/
  talker/
    main.py
    config.py
    session.py
    router.py
    handlers.py
    models.py
    interfaces.py
    llm_engine.py
    prompt.py
    manifest.py
    tts_queue.py
    tts_service.py
    handoff.py
    param_collector.py
    tools/
    stubs/
  tests/
    unit/
    integration/
    e2e/
  pyproject.toml
  Dockerfile
```
