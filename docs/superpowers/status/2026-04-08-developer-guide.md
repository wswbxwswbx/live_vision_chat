# 开发指导

**Date:** 2026-04-08  
**Status:** Current developer onboarding guide  
**Scope:** 帮助团队基于当前 Python-first mainline 快速上手、定位代码边界，并安全扩展后续能力

---

## 1. 这份文档解决什么问题

这份文档不是新的架构 spec，也不是里程碑状态汇报。

它主要解决三件事：

- 新同学进入仓库后，先看什么文档、先读什么代码
- 当前一条请求是怎样穿过 `gateway -> runtime -> store -> client` 的
- 后续要新增能力时，哪些边界可以扩，哪些边界不要破坏

如果你要确认长期方向，先看架构文档。  
如果你要确认当前已经交付了什么，先看状态文档。  
如果你要开始读代码和提交改动，就从这份文档开始。

---

## 2. 建议阅读顺序

推荐按下面顺序进入项目：

1. `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
   先理解长期架构目标，尤其是 `Fast Agent / Slow Agent / Runtime Store / Memory` 的职责划分。
2. `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md`
   再理解当前已经跑通的最小真实链路，也就是 reminder 的 M2 闭环。
3. `docs/superpowers/status/2026-04-08-m2-runtime-status.md`
   再确认当前 shipped reality，而不是按旧假设理解代码。
4. `docs/superpowers/status/2026-04-08-developer-guide.md`
   最后用这份文档对照代码入口、主链路、扩展方式。

如果你只想在 30 分钟内搞清楚仓库：

1. 先看本文件第 3 节到第 6 节
2. 再读 `apps/gateway/ws.py`
3. 再读 `packages/runtime_core/src/runtime_core/runtime_facade.py`
4. 再读 `packages/runtime_core/src/runtime_core/fast_runtime.py`
5. 再读 `packages/runtime_core/src/runtime_core/slow_runtime.py`
6. 最后看 `packages/runtime_store/src/runtime_store/memory_store.py`

---

## 3. 仓库地图

当前仓库可以先按 7 个块理解：

| 目录 | 主要职责 | 什么时候进入这个目录 |
| --- | --- | --- |
| `apps/gateway` | Python `FastAPI` 入口，处理 health、snapshot 和 websocket session ingress | 你在改接入、消息路由、错误处理、服务启动 |
| `apps/demo-client` | React 调试客户端，用来观察 runtime 状态和手动验证流程 | 你在改交互调试、可观测性、前端验证 |
| `packages/protocol` | Python 协议模型和解析 | 你在新增消息类型、调整消息 schema |
| `packages/runtime_store` | Runtime 真相源模型和内存实现 | 你在改状态结构、校验规则、snapshot 依赖字段 |
| `packages/runtime_core` | Fast/Slow 编排、任务生命周期、snapshot 组合、runtime facade | 你在改主业务路径，通常主要在这里 |
| `packages/execution` | 外部执行边界，目前只有 reminder 的内存实现 | 你在改“真正执行动作”而不是编排 |
| `packages/memory` | 长期记忆边界，目前还是 stub | 你在开始做跨 session 记忆时进入 |

一句话概括：

- `gateway` 负责收消息和发消息
- `protocol` 负责消息长什么样
- `runtime_core` 负责决定系统怎么动
- `runtime_store` 负责状态最终长什么样
- `execution` 负责真正副作用
- `demo-client` 负责把这些状态展示出来

---

## 4. 当前已实现范围

当前 mainline 已经实现的是一个最小真实闭环，不是完整产品能力。

### 4.1 已实现

- 普通文本 `turn`
- reminder 意图 triage
- `create_reminder` slow task 创建与执行
- `waiting_user -> handoff_resume -> completed`
- snapshot 中的 conversation/task/checkpoint/task_event 可观测
- demo client 对 reminder 恢复链路的支持

### 4.2 还没实现

- 真正的 streaming runtime
- `AccumulationLoop / MonitoringLoop / GuidanceLoop`
- 长期记忆
- 多个真实 slow task
- 外部 reminder/calendar 集成
- 生产级持久化、恢复、权限与运维闭环

因此你现在应该把仓库理解成：

- 架构主干已经稳定
- M2 的 reminder 用来证明主干是对的
- 后续开发应该沿主干补能力，而不是重开边界

---

## 5. 一条请求是怎么走的

### 5.1 普通 `turn`

普通聊天消息的路径是：

1. `apps/gateway/ws.py` 收到 websocket JSON
2. `packages/protocol/src/protocol/messages.py` 解析为协议消息
3. `packages/runtime_core/src/runtime_core/runtime_facade.py` 接收消息
4. `packages/runtime_core/src/runtime_core/fast_runtime.py` 判断这是 Fast 直接处理
5. runtime 写入 conversation 相关状态
6. gateway 把 `assistant_text` 回给客户端
7. demo client 再拉一次 snapshot 做状态刷新

这条路径不会创建 slow task。

### 5.2 reminder `turn`

当用户说 `Remind me to pay rent` 之类的话时：

1. gateway 收到 `turn`
2. `RuntimeFacade` 调 `FastRuntime`
3. `FastRuntime` 识别为 `create_reminder`
4. `FastRuntime` 创建 task，并通过 session/task registry 绑定到当前 session
5. `RuntimeFacade` 立即把这个 task 交给 `SlowRuntime`
6. `SlowRuntime` 判断信息是否足够
7. 如果时间完整，直接调用 `packages/execution/src/execution/reminder_service.py`
8. `TaskRuntime` 驱动任务进入 `completed`
9. task、checkpoint、task_event 都进入 runtime store
10. gateway 返回 assistant 文本，client 刷新 snapshot

### 5.3 `waiting_user -> handoff_resume`

如果 reminder 缺时间信息：

1. `SlowRuntime` 让 task 进入 `waiting_user`
2. `TaskRuntime` 写 checkpoint 和 task_event
3. assistant 返回类似 `When should I remind you?`
4. demo client 从 snapshot 中识别出一个待恢复 task
5. 用户下一条输入不再走普通 `turn`，而是走 `handoff_resume`
6. `RuntimeFacade` 会先校验 `taskId` 是否属于当前 `sessionId`
7. 校验通过后，`SlowRuntime` 从 checkpoint 恢复上下文
8. task 完成后再刷新 snapshot

这一段是当前 M2 最重要的代码现实。后续新增可恢复的 slow task 时，基本都要参考这一段的模式。

---

## 6. 关键代码地图

如果你想快速读代码，优先看下面这些文件。

| 文件 | 角色 | 你会在什么场景修改它 |
| --- | --- | --- |
| `apps/gateway/app.py` | FastAPI app 装配入口 | 新增路由、中间件、服务装配 |
| `apps/gateway/http.py` | `/health` 与 snapshot HTTP 接口 | 新增只读查询接口 |
| `apps/gateway/ws.py` | websocket ingress、消息解析、错误转发 | 新增消息入口、调整 recoverable error 行为 |
| `packages/protocol/src/protocol/messages.py` | 协议 schema | 新增 `ClientMessage` / `ServerMessage` 类型 |
| `packages/runtime_core/src/runtime_core/runtime_facade.py` | gateway 唯一允许调用的 runtime 入口 | 新增 facade 级消息路由 |
| `packages/runtime_core/src/runtime_core/fast_runtime.py` | Fast triage 与 task 创建 | 新增 Fast 决策、决定是否 handoff |
| `packages/runtime_core/src/runtime_core/slow_runtime.py` | Slow task 执行与恢复 | 新增 slow task 流程、waiting/resume 逻辑 |
| `packages/runtime_core/src/runtime_core/task_runtime.py` | 任务生命周期帮助类 | 新增状态迁移、task_event/checkpoint 规则 |
| `packages/runtime_core/src/runtime_core/session_snapshot.py` | session 视角的 snapshot 组合 | 调整 snapshot 字段或组合规则 |
| `packages/runtime_core/src/runtime_core/session_conversation_registry.py` | `session -> dialog` 映射 | session 级会话归属问题 |
| `packages/runtime_core/src/runtime_core/session_task_registry.py` | `task -> session` 映射 | resume 归属校验、task ownership |
| `packages/runtime_store/src/runtime_store/models.py` | 共享状态模型 | 新增 task payload、checkpoint payload、record 字段 |
| `packages/runtime_store/src/runtime_store/memory_store.py` | 内存态 truth source 和校验 | 新增状态不变量或存储行为 |
| `packages/execution/src/execution/reminder_service.py` | 第一个真实执行边界 | 接 execution、替换内存实现 |
| `apps/demo-client/src/app/session-controller.ts` | client 侧入口控制器 | 改发送逻辑、snapshot 刷新、resume 行为 |
| `apps/demo-client/src/app/session-store.ts` | demo client 本地状态 | 改 runtime 面板显示前的派生状态 |

一个实用阅读顺序是：

1. `apps/gateway/ws.py`
2. `packages/runtime_core/src/runtime_core/runtime_facade.py`
3. `packages/runtime_core/src/runtime_core/fast_runtime.py`
4. `packages/runtime_core/src/runtime_core/slow_runtime.py`
5. `packages/runtime_core/src/runtime_core/task_runtime.py`
6. `packages/runtime_store/src/runtime_store/models.py`
7. `packages/runtime_store/src/runtime_store/memory_store.py`
8. `packages/runtime_core/src/runtime_core/session_snapshot.py`
9. `apps/demo-client/src/app/session-controller.ts`

---

## 7. 关键边界和不变量

后续开发最容易出问题的，不是写不出功能，而是把边界写穿。

下面这些约束默认不要破坏。

### 7.1 `RuntimeFacade` 是 gateway 面向 runtime 的唯一入口

`apps/gateway` 不应该直接调用 `FastRuntime`、`SlowRuntime`、`TaskRuntime`。

原因很简单：

- gateway 负责 ingress，不负责编排
- 编排逻辑集中在 facade，才能保持消息入口清晰
- 后面新增 `audio_chunk / video_frame` 真正路由时，也应该先落到 facade

### 7.2 `runtime_store` 是运行态真相源

不要在 gateway、demo client 或某个 runtime helper 里偷偷维护平行状态。

可以有 registry、snapshot reader、client store 这样的派生视图，但最终真相应以 `runtime_store` 中的 record 为准。

### 7.3 `taskId` 不能脱离 `sessionId` 独立信任

`handoff_resume` 已经证明了这一点。

任何可恢复任务，只要是客户端回传 `taskId`，都必须做 session ownership 校验。当前 reminder 逻辑通过 `SessionTaskRegistry` 保证这一点。

### 7.4 任务生命周期应该由 `TaskRuntime` 收口

不要把 `accepted/running/waiting_user/completed/failed` 的状态迁移散写到多个地方。

否则很快会出现：

- event 没写
- checkpoint 没写
- conversation attention 没同步
- task 状态和 snapshot 展示不一致

### 7.5 `memory_store` 的校验不是装饰品

当前内存实现已经带有几条重要约束，例如：

- `background_task_ids` 不能重复
- `foreground_task_id` 不能同时出现在 background 集合中
- `interrupt_epoch` 不能回退
- `speaker_owner` 只能由 `system` actor 改写

如果你改了状态模型，记得同时判断这些不变量是否仍然成立。

### 7.6 `execution` 负责副作用，不负责 runtime 编排

现在 reminder service 还是内存实现，但边界已经很清楚：

- 是否应该执行、是否该等待用户，由 runtime 决定
- 真正执行创建 reminder 记录，由 execution 决定

后面接真实 calendar/reminder 系统时，也应保持这个边界。

---

## 8. 如何新增一个 Slow Task

后续团队大概率会继续加第二个、第三个 slow task。推荐按下面顺序做。

### 8.1 先决定它属于哪一类

先判断这个能力到底是：

- Fast 直接回复
- 一次性 Slow task
- 可恢复 Slow task
- 真正 streaming task

不要因为“想快点做出来”就把所有东西塞进 `FastRuntime`。

### 8.2 再补状态模型

通常要先看：

- `packages/runtime_store/src/runtime_store/models.py`

你可能要补：

- task payload
- checkpoint payload
- event payload
- snapshot 需要暴露的字段

### 8.3 在 `FastRuntime` 里加 triage 和 task 创建

通常要改：

- `packages/runtime_core/src/runtime_core/fast_runtime.py`

这里负责：

- 识别是否 handoff
- 创建 task
- 给用户一个立即可见的前台反馈
- 如果任务可恢复，确保 session/task 归属被记录

### 8.4 在 `SlowRuntime` 里写真正流程

通常要改：

- `packages/runtime_core/src/runtime_core/slow_runtime.py`
- `packages/runtime_core/src/runtime_core/task_runtime.py`
- `packages/execution/...`

这里负责：

- 如何进入 running
- 什么时候进入 `waiting_user`
- checkpoint 写什么
- 完成后调用哪个 execution adapter
- 失败时如何反馈

### 8.5 如果新增客户端交互，再改 protocol 和 demo client

通常要看：

- `packages/protocol/src/protocol/messages.py`
- `apps/demo-client/src/app/session-controller.ts`
- `apps/demo-client/src/app/session-store.ts`

尤其是：

- 是否需要新的 client message
- 是否需要新的 server message
- snapshot 刷新策略是否要变

### 8.6 最后补测试

至少覆盖：

- runtime_core 单测
- gateway round-trip 测试
- demo client 行为测试

经验上，新的 slow task 最容易漏的是：

- ownership 校验
- 重复 resume
- snapshot 不更新
- task event 和 checkpoint 不一致

---

## 9. 如果要开始做 Streaming M3

M3 不应该推翻 M2，而应该建立在 M2 上。

开始 streaming 工作时，建议牢记四件事：

1. `audio_chunk / video_frame` 可以继续从 gateway 进，但不要绕过 `RuntimeFacade`
2. streaming task 依然应该落到 runtime store 中可观察的状态，而不是只在内存对象里“活着”
3. `AccumulationLoop / MonitoringLoop / GuidanceLoop` 是任务行为模型，不是 HTTP 或 websocket 细节
4. demo client 只是调试工具，不应主导 runtime 边界设计

如果某个 streaming 能力需要长期状态、检查点和恢复，那它本质上仍然是 runtime 问题，不是 transport 问题。

---

## 10. 常见坑

下面这些坑已经可以提前避免：

- 不要在 gateway 里写业务编排，入口代码一旦变厚，后面所有消息类型都会散掉
- 不要绕过 `runtime_store` 直接拼 snapshot，真相源和视图一旦分叉就很难收回来
- 不要把 demo client 的临时交互当成正式协议承诺
- 不要默认客户端传回来的 `taskId` 是可信的，先做 session ownership 校验
- 不要把 execution service 当成“顺手写一点状态”的地方，副作用和编排应该分开
- 不要新增一个字段却不补验证和测试，runtime state 很容易在这种地方悄悄失真

---

## 11. 推荐验证命令

日常开发至少跑下面这些：

```bash
python -m pytest packages apps/gateway/tests -q
```

```bash
cd apps/demo-client
corepack pnpm test
corepack pnpm build
```

如果只改了 runtime reminder 路径，至少跑：

```bash
python -m pytest packages/runtime_core/tests/test_runtime_facade.py apps/gateway/tests/test_ws_session.py -q
```

手工 smoke check 的最小集合：

1. 发普通 `turn`，应返回 `Fast reply: ...`
2. 发 `Remind me to pay rent`，应返回 `When should I remind you?`
3. 再发 `tomorrow at 9am`，应通过 `handoff_resume` 完成同一个 task
4. 重复发一次同样的 resume，不应该把 websocket 打断

---

## 12. 接手第一天建议做什么

如果你今天刚接手这个项目，建议按下面顺序做：

1. 跑一次 Python 测试和 demo-client 测试，确认本地环境是通的
2. 手工走一遍 reminder 流程，确认你理解 `turn -> handoff -> waiting_user -> handoff_resume`
3. 按第 6 节顺序读关键文件
4. 再开始改动自己的任务，不要一上来就改 gateway 或 store schema

这是当前成本最低、误判最少的上手路径。

---

## 13. 相关文档

- `README.md`
- `docs/superpowers/specs/2026-04-01-multiagent-architecture-design.md`
- `docs/superpowers/specs/2026-04-08-m2-minimum-real-fast-slow-runtime-design.md`
- `docs/superpowers/status/2026-04-08-m2-runtime-status.md`
- `docs/superpowers/status/2026-04-07-python-runtime-baseline.md`
