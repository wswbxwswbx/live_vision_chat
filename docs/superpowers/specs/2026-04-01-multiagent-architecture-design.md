# Multi-Agent 语音助手架构设计

**版本**：v2.2
**日期**：2026-04-07
**状态**：设计完成

---

## 一、设计目标与价值

### 1.1 核心理念

实现一个像 **Jarvis** 一样的语音助手：

- **实时对话**：用户说话，助手即时响应（像人在对面）
- **后台任务**：复杂任务后台处理，不阻塞用户继续对话
- **Live Streaming**：音视频流实时进出，助手能感知物理世界

### 1.2 Fast + Slow 的价值

| | 单 Agent | Fast + Slow |
|---|---|---|
| 简单问答（天气、时间） | 延迟 500ms-1s | Fast: 100-300ms |
| 实时语音对话 | 阻塞等待 | Fast: 不阻塞 |
| 复杂任务（会议记录） | 用户必须等 | Slow: 后台执行 |
| 物理世界指导（修车） | 不支持 | Slow: VL反馈驱动 |
| 多任务并发 | 困难 | Fast/Slow 各司其职 |

**精髓**：`Fast` = 用户等得起的（毫秒级响应），`Slow` = 用户等不起的（后台处理）。

### 1.3 Fast Agent 职责

**实时语音对话助手（Jarvis 风格）**：

- 用户说话 → 实时响应，用户在等
- 单轮工具调用（搜天气、查时间、识图）
- 简短多轮对话（闲聊、澄清）
- 在 Slow Agent 工作时，接收用户的其他问题
- **2 轮限制**：用户等 TTS 出来，超过 2 轮（3s+）会感觉卡住

**Fast Agent 不能做的**：
- 超过 2 轮的复杂任务 → handoff 给 Slow
- 需要等待用户执行动作的指导（修车）→ Slow
- 长时间累积上下文（会议记录）→ Slow

### 1.4 Slow Agent 职责

**后台复杂任务执行器**：

- 会议记录：累积 ASR + 关键帧摘要
- 修车指导：VL 观测 + 语音指令闭环
- 用户不等结果，异步执行
- 结果通过 TTS 队列返回

### 1.5 参考架构

- Claude Code（Anthropic）：主参考，决定 Fast/Slow、runtime core、tool orchestration、memory layering 的架构语义
- claw-code-main：Python 工程化参考，借鉴 session、remote、workspace、执行边界的实现方式
- cc-mini-main：Python 最小内核参考，借鉴 engine、session、permission、memory、coordinator 的轻量实现

---

## 二、术语表

### 2.1 Agent 与系统边界

| 术语 | 定义 |
|------|------|
| Fast Agent | 面向 live 对话的前台 agent，负责用户正在等待的响应 |
| Slow Agent | 面向后台任务的 agent，负责长任务、持续感知、长期记忆写入 |
| 端侧 | HarmonyOS 客户端，负责音频/视频采集、播放、工具执行和 UI 展示 |
| 云侧 | 承载 Fast Agent、Slow Agent、Runtime Store、Long-term Memory 的服务端 |

### 2.2 Loop 层级

| 术语 | 定义 |
|------|------|
| SlowLoop | Slow Agent 内部执行任务的总称 |
| OneShotLoop | 一次性任务 loop，规划后执行，完成即结束 |
| StreamingLoop | 持续接收外部输入的 loop，上位抽象 |
| AccumulationLoop | 以累积和压缩状态为主的 streaming primitive |
| MonitoringLoop | 以检测条件是否命中、并在命中时触发事件为主的 streaming primitive |
| GuidanceLoop | 以主动发指令、再根据环境反馈调整下一步为主的 streaming primitive |
| MeetingMinutesLoop | `AccumulationLoop` 的实现，用于会议记录/摘要累积 |
| VisualGuidanceLoop | `GuidanceLoop` 的实现，用于物理世界指导闭环 |
| VisionSensor | `MonitoringLoop / GuidanceLoop` 可复用的观测器，负责按频率读取并分析视频帧 |

### 2.3 任务与事件

| 术语 | 定义 |
|------|------|
| task | 用户目标在系统中的持久化任务对象 |
| run | 某个 task 的一次具体执行实例；一个 task 可因重试或 supersede 派生多个 run |
| handoff | Fast 把任务和上下文交给 Slow 的控制权协议 |
| task_event | Slow 回传给 Fast 的统一事件信封 |
| event_kind | `task_event` 的事件类型，如 `accepted` / `progress` / `need_user_input` / `completed` |
| supersede | 新任务执行替代旧 run，旧 run 不再继续推进 |
| checkpoint | Slow loop 的执行快照，用于暂停、恢复、重试和崩溃恢复 |
| tool_call | 一次具体的工具调用实例，带 `call_id` 和独立生命周期 |
| tool_call_state | 单个工具调用的执行状态，如 `queued / running / paused / waiting_approval / completed / failed / cancelled` |

### 2.4 控制权与状态

| 术语 | 定义 |
|------|------|
| speaker_owner | 当前谁有发言权，通常是 `user / fast / slow` |
| attention_owner | 当前系统主要关注哪个执行体，通常是 `fast / slow` |
| speak_policy | 某个事件是否发声以及如何发声，`interrupt / queue / silent` |
| execution_state | 任务执行态，如 `handoff_pending / running / waiting_user / completed` |
| delivery_state | 任务通知态，如 `silent / pending_announce / announced / deferred` |
| foreground | 当前直接与用户交互的执行体 |
| background | 当前在后台推进但不抢占用户对话的执行体 |

### 2.5 存储边界

| 术语 | 定义 |
|------|------|
| Runtime Store | 保存 conversation state、task registry、checkpoint、task event 索引的运行时存储 |
| Conversation State | 当前 session 的 owner、foreground/background task、interrupt epoch 等会话态 |
| Task Registry | 给 Fast/UI 读取的任务摘要索引，不是执行真相源 |
| Long-term Memory | 跨会话仍有价值的 user / feedback / project / reference 记忆 |
| MemorySystem | Long-term Memory 的检索、写入、清理、过期校验组件 |

### 2.6 感知模式

| 术语 | 定义 |
|------|------|
| Turn-bound | 单轮按需感知，通常是用户提问时带一帧图像或一次短输入 |
| Streaming | 持续感知，端侧持续推流，Slow loop 持续处理 |
| observe | 从环境中读取新信号，例如视频帧、transcript、timer |
| react | 根据观测结果调整下一步行为 |
| aggregate | 持续收集输入并压缩为结构化结果，而不是即时纠错 |

---

## 三、整体架构

```
端侧（HarmonyOS）
  ├─ Audio In / Push-to-talk
  ├─ Audio Out / TTS 播放队列
  ├─ Video Stream / Camera
  ├─ Tool Executor
  └─ Chat UI
          │
          │ WebSocket
          │ turn / handoff_resume / request_to_speak / stop_speech /
          │ tool_result / video_frame
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                            云侧 Runtime                          │
│                                                                  │
│  ┌──────────────────────┐                                        │
│  │ Protocol Router      │                                        │
│  │ - session 绑定       │                                        │
│  │ - 消息分发           │                                        │
│  │ - interrupt 处理     │                                        │
│  └──────────────────────┘                                        │
│             │                                                    │
│      ┌──────┴──────┐                                             │
│      ▼             ▼                                             │
│  ┌──────────────────────┐    handoff / task_event / yield       │
│  │ Fast Agent Runtime   │◄──────────────────────────────────┐    │
│  │ - live dialog loop   │                                   │    │
│  │ - fast tools         │──────────────────────────────┐     │    │
│  │ - handoff policy     │                              │     │    │
│  └──────────────────────┘                              │     │    │
│             │                                          │     │    │
│             │ 读写                                     │     │    │
│             ▼                                          ▼     │    │
│  ┌────────────────────────────────────────────────────────┐   │    │
│  │ Shared Runtime Layer                                  │   │    │
│  │ - Conversation State                                  │   │    │
│  │ - Task Registry                                       │   │    │
│  │ - Checkpoint Store                                    │   │    │
│  │ - Event Dispatcher                                    │   │    │
│  └────────────────────────────────────────────────────────┘   │    │
│             ▲                                          ▲     │    │
│             │ 读                                       │写    │    │
│             │                                          │     │    │
│  ┌────────────────────────────────────────────────────────┐   │    │
│  │ Long-term Memory Layer                               │   │    │
│  │ - user / feedback / project / reference              │   │    │
│  └────────────────────────────────────────────────────────┘   │    │
│                                                                │    │
│  ┌──────────────────────────────────────────────────────────┐  │    │
│  │ Slow Agent Runtime                                      │──┘    │
│  │ - OneShotLoop Runner                                    │       │
│  │ - StreamingLoop Runner                                  │       │
│  │ - VisionSensor                                          │       │
│  │ - Skill Registry                                        │       │
│  │ - Python Executor                                       │       │
│  └──────────────────────────────────────────────────────────┘       │
│                          ▲                                          │
│                          │ video_frame(task_id) / tool_result       │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           └── 端侧按 task_id 绑定视频流和工具结果
```

**运行时说明：**

1. 端侧所有输入先进入 `Protocol Router`，由它按 session 和消息类型路由。
2. `Fast Agent Runtime` 负责 live 对话、即时回复和 handoff 决策。
3. `Slow Agent Runtime` 负责 `OneShotLoop` 和 `StreamingLoop` 两类后台执行。
4. `Shared Runtime Layer` 是运行时真相源，保存 `Conversation State / Task Registry / Checkpoint / Event Dispatcher`。
5. `Long-term Memory Layer` 只保存跨会话仍然有价值的信息，不保存当前运行态。
6. 视频流和端侧工具结果直接按 `task_id` 路由到对应的 `StreamingLoop` 或 Slow 任务实例。
7. Fast 和 Slow 之间不直接共享内部对象，而是通过 `handoff / task_event / yield-resume` 协议协作。

### 3.1 Python-first 实施约束

正式主干采用 **Python-first**，当前 TypeScript 实现只作为架构原型和联调样板，不作为后续正式主线继续扩展。

约束如下：

- 架构语义以 `reference/claude-code` 为主，不以现有 TS 原型或 Python reference 的局部实现细节为主
- `reference/claw-code-main` 和 `reference/cc-mini-main` 只用于借鉴 Python 实现方式，不直接决定系统边界
- 第一阶段部署允许单进程，但代码边界必须按可拆分服务设计
- `gateway`、`runtime_core`、`runtime_store`、`execution`、`memory` 必须是清晰可分工的独立模块
- 任何可恢复、可观测、可协作的运行态，都必须先写入 `Runtime Store`

### 3.2 Python 主干推荐代码分层

```text
apps/
  gateway/              # FastAPI ingress, HTTP/WS, session connection, snapshot API
  debug_client/         # 调试终端，可先用 Web，后续可替换为正式端侧

packages/
  protocol/             # Pydantic 消息 schema
  runtime_store/        # shared memory 真相源
  runtime_core/         # FastRuntime / SlowRuntime / TaskRuntime / RuntimeFacade
  execution/            # tool executor / slow task worker / loop worker
  memory/               # long-term memory retrieval / writeback / pruning
```

分层原则：

- `apps/gateway` 可以使用 `FastAPI + Pydantic + asyncio`
- `packages/runtime_core`、`packages/runtime_store` 保持框架无关，只依赖纯 Python 域模型和接口
- `packages/execution` 负责“怎么执行”，`runtime_core` 负责“做什么”和“状态推进到哪里”
- `packages/memory` 独立于当前 turn/runtime state，不与 `Runtime Store` 混用
- 后续多人协作时，以 package 边界拆分任务，而不是以单文件或单功能点拆分

### 3.3 Python 并发模型

正式主干采用混合并发模型：

- `gateway / session / realtime protocol` 使用 `asyncio`
- `Fast Runtime` 运行在异步主循环中，统一处理 turn、取消、超时和事件路由
- `Slow Runtime` 由 `TaskRuntime` 驱动，其长任务、阻塞 I/O、重 CPU 工具通过 `execution` 层隔离到 worker 进程或独立 runner

这保证：

- 控制面适合实时流式协议
- 执行面不会污染主事件循环
- 第一阶段可单进程部署，后续也能平滑拆成多进程或多服务

---

## 四、快系统（Fast Agent）

### 3.1 职责边界

快系统只做两件事：

1. **对话**：接收用户语音，生成回复，播报 TTS
2. **转发**：自己搞不定的，handoff 给慢系统

快系统**不执行**复杂任务，**不维护**长期记忆，**不写** long-term memory 文件。

### 3.2 能处理的范围

快系统能直接回答或执行的：

- **对话**：闲聊、问答、话题切换
- **text_search**：文本搜索
- **image_search**：图像搜索/识别人脸
- **追问**：收集用户参数（通过 skill schema 知道该问什么）

超出范围的 → handoff。

### 3.3 两轮规划限制

快系统的 LLM 规划受"两轮"限制：

```
用户：左边这个人最近演过什么电影？

快系统内部规划（用户不可见，在等）：
  round 1：
    → 需要先识别人物 → image_search
    → 得到：刘德华

  round 2：
    → 需要查刘德华电影 → text_search
    → 得到：近期作品列表

  → 合并结果，回复用户

如果 round 2 发现还需要第三步：
  → 直接 handoff 给慢系统
```

两轮是**用户不可见的内部规划轮数**，用户干等着。超过两轮还没搞定 → handoff。

### 3.4 LLM Prompt 模板

Fast Agent 的 system prompt 包含三部分：

```python
FAST_AGENT_PROMPT = """
你是一个快速响应的语音助手，负责实时对话交互。

## 你的能力边界

你可以直接调用的工具（fast_tools）：
{fast_tools_json}

需要 handoff 给后台系统的工具（slow_tools）：
{slow_tools_json}

## 规则

1. **两轮规划限制**：你最多有 2 轮内部规划机会（用户看不到）
   - 每次调用工具算一轮
   - 超过 2 轮还没完成 → 立即 handoff

2. **Handoff 决策**：以下情况必须 handoff
   - 需要调用 slow_tools
   - 需要超过 2 轮规划
   - 需要执行复杂任务（多步骤、需要等待、需要写代码）
   - 需要访问或修改长期记忆

3. **参数收集**：对于 slow_tools，如果参数标记了 can_ask_upfront=true
   - 可以提前问用户收集参数
   - 收集完后再 handoff（减少慢系统的追问次数）

4. **过渡话术**：handoff 时给用户一个过渡回复
   - "好的，正在帮你处理"
   - "稍等，我来帮你安排"

## 示例

用户: "帮我设个闹钟"
你: "你想设几点？" (收集 can_ask_upfront 参数)
用户: "8点"
你: "是哪一天？" (继续收集)
用户: "明天"
你: "好的，正在帮你设置" (handoff，不等结果)

用户: "左边这个人是谁？"
你: (round 1) 调用 image_search → 识别出"刘德华"
你: "这是刘德华"

用户: "他最近演过什么电影？"
你: (round 1) 调用 text_search → 查询刘德华近期作品
你: "刘德华最近的作品有..."
"""
```

### 3.5 两轮规划的判断逻辑

**什么算"一轮"？**

```python
class FastAgent:
    async def handle_turn(self, user_input):
        messages = [{"role": "user", "content": user_input}]
        rounds = 0
        
        while rounds < 2:
            response = await self.llm.call(messages, tools=self.manifest)
            
            # 判断：LLM 返回 tool_calls 算一轮
            if response.tool_calls:
                rounds += 1
                
                for tool in response.tool_calls:
                    if tool.name in self.fast_tools:
                        # Fast 工具，直接执行
                        result = await self.execute_tool(tool)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool.id,
                            "content": result
                        })
                    else:
                        # Slow 工具，handoff
                        await self.handoff(tool, messages)
                        return "好的，正在帮你处理"
            else:
                # LLM 返回文本回复，结束
                return response.content
        
        # 超过 2 轮，handoff
        await self.handoff_with_context(messages)
        return "这个需要我仔细处理一下，稍后告诉你结果"
```

**Handoff 决策标准：**

| 场景 | 判断 | 动作 |
|------|------|------|
| LLM 调用 slow_tool | tool.name in slow_tools | 立即 handoff |
| 超过 2 轮 | rounds >= 2 | handoff_with_context |
| LLM 明确说"需要复杂处理" | response.content 包含特定标记 | handoff |
| 用户说"后台帮我..." | intent 分析 | handoff |

### 3.6 参数收集流程（can_ask_upfront）

```python
class FastAgent:
    async def collect_params(self, skill_name: str, user_input: str):
        """收集 can_ask_upfront 参数"""
        skill_schema = self.manifest.get_slow_tool(skill_name)
        collected_params = {}
        
        # 从用户输入中提取已有参数
        extracted = await self.llm.extract_params(user_input, skill_schema)
        collected_params.update(extracted)
        
        # 检查哪些 can_ask_upfront 参数还缺
        missing = []
        for param in skill_schema.params:
            if param.can_ask_upfront and param.name not in collected_params:
                missing.append(param)
        
        # 逐个追问
        for param in missing:
            question = param.question_for_user
            await self.ask_user(question)
            user_answer = await self.wait_for_user_input()
            collected_params[param.name] = user_answer
        
        # 参数齐了，handoff
        await self.handoff({
            "skill": skill_name,
            "params": collected_params,
            "conversation_snapshot": self.messages
        })
```

### 3.7 Handoff 确认与超时机制

**问题**：handoff 消息发出后，Slow Agent 可能丢失（进程崩溃/重启），用户不知道任务没开始。

**解决方案：handoff 不是普通消息，而是控制权协议**

handoff 需要同时解决 4 件事：

1. **任务投递**：Fast 把目标、上下文、参数交给 Slow
2. **控制权转移**：定义当前谁可以说话、谁消费视频流、谁处理用户打断
3. **状态确认**：Slow 必须显式 ack，Fast 才能认为任务进入后台
4. **恢复语义**：用户打断、断线重连、Slow 追问后，系统能恢复到正确 owner

因此 handoff 需要显式区分两个 owner：

- `speaker_owner`: 当前谁有发言权，`user | fast | slow`
- `attention_owner`: 当前谁有主要注意力，`fast | slow`

默认规则：

- 日常 live 对话时：`speaker_owner=fast`, `attention_owner=fast`
- Slow 在后台跑任务时：`speaker_owner=fast`, `attention_owner=slow`
- Slow 需要立即追问用户时：先发 `task_event(need_user_input)`，由 Fast 接管说话
- 用户一开口或按下打断：`speaker_owner` 立即切回 `user/fast`

```python
class SessionControlState:
    speaker_owner = "fast"      # user | fast | slow
    attention_owner = "fast"    # fast | slow

class FastAgent:
    async def handoff(self, msg: HandoffMessage) -> bool:
        """发送 handoff，并把任务挂到后台"""
        task_id = msg.task_id
        runtime_store.update_task(task_id, {
            "execution_state": "handoff_pending",
            "delivery_state": "silent",
            "speaker_owner": "fast",
            "attention_owner": "slow",
        })
        
        sent = await self.slow_inbox.send(msg)
        if not sent:
            runtime_store.update_task(task_id, {
                "execution_state": "failed",
                "delivery_state": "pending_announce",
            })
            return False
        
        asyncio.create_task(self._handoff_timeout_check(task_id, timeout=30))
        return True
    
    async def _handoff_timeout_check(self, task_id, timeout):
        await asyncio.sleep(timeout)
        if runtime_store.get_task(task_id).execution_state == "handoff_pending":
            runtime_store.update_task(task_id, {
                "execution_state": "failed",
                "delivery_state": "pending_announce",
            })
            await self.enqueue_task_event(task_id, "failed", speak_policy="interrupt")

class SlowAgent:
    async def on_handoff(self, msg: HandoffMessage):
        task_id = msg.task_id
        runtime_store.update_task(task_id, {
            "execution_state": "queued",
            "delivery_state": "silent",
            "attention_owner": "slow",
        })
        await self.fast_callbacks.ack_handoff(task_id)
        await self._execute_task(msg)
```

### 3.8 TTS 队列与消息优先级

**问题**：Fast 和 Slow 的 TTS 可能同时到达端侧，导致音频打架。

**解决方案：统一 TTS 队列 + speak policy**

单纯的优先级队列还不够，因为后台任务的消息不一定都应该发声。Slow 返回 Fast 的事件必须额外带上 `speak_policy`：

- `interrupt`：可以打断当前播报
- `queue`：排队等待合适时机播报
- `silent`：只更新 UI / task card，不播报

因此，TTS 队列只负责“怎么播”，不负责“该不该播”。“该不该播”由 Fast 在消费 `task_event` 时决定。

```python
class TTSQueue:
    """Fast/Slow 共享的 TTS 队列，按优先级排序"""
    
    def __init__(self):
        self.queue = []  # [(priority, tts_item), ...]
        self.playing = None
        self.is_playing = False
    
    def enqueue(self, audio: bytes, source: str, priority: str = "normal"):
        """
        priority: "high" (Fast) | "normal" (Fast 普通) | "low" (Slow)
        """
        item = {"audio": audio, "source": source, "priority": priority}
        
        # 插入队列（按优先级排序）
        inserted = False
        for i, (p, _) in enumerate(self.queue):
            if self._priority_value(priority) > self._priority_value(p):
                self.queue.insert(i, (priority, item))
                inserted = True
                break
        if not inserted:
            self.queue.append((priority, item))
        
        # 如果当前没在播放，开始播放
        if not self.is_playing:
            self._play_next()
    
    def _priority_value(self, p: str) -> int:
        return {"high": 3, "normal": 2, "low": 1}[p]
    
    def _play_next(self):
        if not self.queue:
            self.is_playing = False
            return
        
        _, item = self.queue.pop(0)
        self.is_playing = True
        self.playing = item
        
        # 播放完成回调
        self._play_and_wait(item).then(self._on_tts_complete)
    
    def _on_tts_complete(self):
        """播完一个，继续播下一个"""
        self.playing = None
        self._play_next()
    
    def stop_current(self):
        """打断当前播放（Fast 高优先级打断 Slow 低优先级）"""
        if self.playing and self.playing["priority"] == "low":
            # 打断 Slow 的低优先级 TTS
            self._stop_playback()
            self.playing = None
            self._play_next()
    
    def get_queue(self) -> list:
        """返回队列状态（用于调试/UI显示）"""
        return [{"source": src, "priority": p} for p, src in self.queue]
```

**策略说明**：

| 消息类型 | 来源 | speak_policy | 行为 |
|---------|------|--------------|------|
| Fast 实时回复 | Fast | `interrupt` | 打断任何播放 |
| Fast 普通回复 | Fast | `queue` | 队列等待 |
| Slow need_user_input | Slow | `interrupt` | 立即让 Fast 接管发问 |
| Slow task_completed | Slow | `queue` | 找对话间隙播报 |
| Slow progress | Slow | `silent/queue` | 默认不播报，仅更新 UI |
| Slow alert | Slow | `interrupt` | 仅用于高优先级提醒 |

### 3.9 Skill Schema

快系统持有所有 skill 的 schema（但不执行），用于：
- 知道哪些参数是 `can_ask_upfront` 的，直接问用户
- 知道任务是否超出自己的执行能力，决定是否 handoff

```json
{
  "version": "1.0.0",
  "fast_skills": [
    {
      "name": "text_search",
      "description": "搜索文本获取实时信息",
      "can_ask_upfront": []
    },
    {
      "name": "image_search",
      "description": "识别人脸或物体",
      "can_ask_upfront": []
    }
  ],
  "slow_skills": [
    {
      "name": "set_alarm",
      "description": "设置闹钟",
      "can_ask_upfront": ["time", "date"],
      "params": [
        {
          "name": "time",
          "type": "string",
          "required": true,
          "can_ask_upfront": true,
          "question": "你想设几点？",
          "examples": ["9点", "上午10点", "晚上8点半"]
        },
        {
          "name": "date",
          "type": "string",
          "required": true,
          "can_ask_upfront": true,
          "question": "是哪一天？",
          "examples": ["今天", "明天", "周一"]
        },
        {
          "name": "repeat",
          "type": "string",
          "required": false,
          "can_ask_upfront": false
        }
      ]
    }
  ]
}
```

---

## 五、慢系统（Slow Agent）

### 4.1 职责边界

慢系统是真正的 autonomous agent：

1. **执行复杂任务**：多步规划、工具调用、Python 代码执行
2. **维护长期记忆**：用户偏好、事实、项目上下文
3. **生成用户自定义 skill**：对话中学习并扩展能力
4. **后台任务**：用户不等结果，异步执行

慢系统是唯一能写 long-term memory 文件的系统。

### 4.2 Agent Loop 状态机

#### 4.2.1 任务级状态机

任务状态拆成两层：

- `execution_state`：任务本身执行到哪里
- `delivery_state`：这个状态是否需要通知用户、是否已经播报

这样可以避免“任务完成了”和“现在是否应该插播结果”混成一个字段。

```python
class ExecutionState(Enum):
    HANDOFF_PENDING = "handoff_pending"   # Fast 已投递，Slow 未确认
    QUEUED          = "queued"            # Slow 已接受，等待执行
    RUNNING         = "running"           # 执行中
    WAITING_USER    = "waiting_user"      # 等待用户输入
    WAITING_WORLD   = "waiting_world"     # 等待现实世界反馈/VL观察
    PAUSED          = "paused"            # 因打断/恢复策略进入暂停
    COMPLETED       = "completed"         # 正常完成
    FAILED          = "failed"            # 执行失败
    CANCELLED       = "cancelled"         # 用户取消
    SUPERSEDED      = "superseded"        # 被新任务替代

class DeliveryState(Enum):
    SILENT            = "silent"             # 不播报，仅内部状态
    PENDING_ANNOUNCE  = "pending_announce"   # 等待 Fast 找时机播报
    ANNOUNCED         = "announced"          # 已播报/已通知
    DEFERRED          = "deferred"           # 暂不播报，等待更合适时机
```

**VALID_TRANSITIONS 表：**

| execution_state | 允许的下一状态 | 触发条件 |
|----------------|------------------|---------|
| HANDOFF_PENDING | QUEUED / FAILED | Slow ack / handoff 超时 |
| QUEUED | RUNNING / CANCELLED | Slow 开始执行 / 用户取消 |
| RUNNING | WAITING_USER | 需要用户补参 |
| RUNNING | WAITING_WORLD | 等待视频/环境变化 |
| RUNNING | PAUSED | Fast 接管或系统恢复中 |
| RUNNING | COMPLETED / FAILED / CANCELLED / SUPERSEDED | 正常完成 / 异常 / 取消 / 被替代 |
| WAITING_USER | RUNNING / CANCELLED / SUPERSEDED | 用户回答 / 取消 / 改成新任务 |
| WAITING_WORLD | RUNNING / PAUSED / CANCELLED / SUPERSEDED | 新观察到达 / Fast 接管 / 取消 / 替代 |
| PAUSED | RUNNING / CANCELLED / SUPERSEDED | 恢复执行 / 取消 / 替代 |
| FAILED | QUEUED | 重试 |

#### 4.2.1.b 工具调用级状态机

任务级状态机描述的是一个 task/run 的生命周期；双向工具执行还需要一个更细粒度的
`tool_call_state`，否则 `cancel_tool`、迟到的 `tool_result`、重连恢复都会缺少真相源。

```python
class ToolCallState(Enum):
    QUEUED           = "queued"             # 已创建，尚未下发到执行器
    RUNNING          = "running"            # 执行中
    WAITING_APPROVAL = "waiting_approval"   # 等待端侧权限/用户确认
    PAUSED           = "paused"             # 被显式暂停
    COMPLETED        = "completed"          # 正常完成，终态
    FAILED           = "failed"             # 执行失败，终态
    CANCELLED        = "cancelled"          # 被取消，终态
```

**VALID_TRANSITIONS 表：**

| tool_call_state | 允许的下一状态 | 触发条件 |
|----------------|------------------|---------|
| QUEUED | RUNNING / CANCELLED | 下发执行 / 尚未开始前被取消 |
| RUNNING | WAITING_APPROVAL / PAUSED / COMPLETED / FAILED / CANCELLED | 权限确认 / 暂停 / 完成 / 失败 / 取消 |
| WAITING_APPROVAL | RUNNING / FAILED / CANCELLED | 批准继续 / 拒绝 / 取消 |
| PAUSED | RUNNING / CANCELLED | 恢复 / 取消 |

**一致性规则：**

- `COMPLETED / FAILED / CANCELLED` 是工具调用终态
- 到达终态后，后续迟到的 `tool_progress / tool_result / tool_error` 一律丢弃并记日志
- `cancel_tool` 成功提交后，以 `CANCELLED` 为准；除非工具在取消前已经被 Runtime 原子标记为 `COMPLETED`
- `pause_tool / resume_tool` 只允许发给声明支持该能力的工具

#### 4.2.2 Loop 内状态机

```
IDLE → PLANNING → EXECUTING
                  ↓
            USER_INPUT ← 需要用户输入，暂停等回调
                  ↓
            COMPLETE → IDLE
```

**关键机制：**
- 每步执行前写 checkpoint（崩溃可恢复）
- LLM 规划步骤，返回结构化 Step[]
- StreamingToolExecutor 并发执行工具
- 任务状态拆成 `execution_state + delivery_state`

#### 4.2.3 Step 类型

```python
class StepType(Enum):
    SKILL_CALL   = "skill_call"    # 调用 skill
    PYTHON_EXEC  = "python_exec"   # 执行 Python 代码
    USER_INPUT   = "user_input"     # 需要用户输入（任务暂停）
    BRANCH       = "branch"         # 条件分支
    VL_WAIT      = "vl_wait"        # 等待视觉反馈（物理世界 Loop）

@dataclass
class Step:
    step_id: str
    type: StepType
    action: str           # skill 名称或 "python"
    params: dict
    requires_user_input: bool = False
    rollback_on_fail: bool = False
    timeout_seconds: Optional[int] = None   # 单步超时
```

#### 4.2.4 规划生成逻辑

```python
class SlowAgent:
    async def on_handoff(self, handoff_msg: HandoffMessage):
        """收到 handoff，生成执行计划"""
        task_id = handoff_msg.task_id

        # 1. LLM 生成执行计划
        plan = await self._generate_plan(handoff_msg)

        # 2. 保存 checkpoint（初始状态）
        await self._save_checkpoint(task_id, {
            "task_id": task_id,
            "plan": plan,
            "current_step": 0,
            "step_results": [],
            "execution_state": ExecutionState.QUEUED.value,
            "delivery_state": DeliveryState.SILENT.value,
            "handoff": {
                "intent": handoff_msg.intent,
                "video_mode": handoff_msg.video_mode,
            },
            "created_at": utcnow(),
            "updated_at": utcnow(),
        })

        # 3. 启动执行循环（异步）
        asyncio.create_task(self._execute_loop(task_id))

    async def _generate_plan(self, handoff_msg) -> List[Step]:
        """LLM 生成结构化执行步骤"""
        prompt = f"""
你是一个任务规划器。用户意图: {handoff_msg.intent}

可用工具:
{json.dumps(self.skill_registry.list(), ensure_ascii=False)}

请生成执行步骤（JSON 数组格式）：
[
  {{
    "step_id": "step_1",
    "type": "skill_call",
    "action": "check_calendar",
    "params": {{"date": "明天"}},
    "requires_user_input": false,
    "rollback_on_fail": false
  }},
  {{
    "step_id": "step_2",
    "type": "skill_call",
    "action": "set_alarm",
    "params": {{"time": "08:00", "date": "明天"}},
    "requires_user_input": false,
    "rollback_on_fail": true
  }}
]

规则:
1. 每个 step 必须有唯一的 step_id
2. type 可选: skill_call / python_exec / user_input / branch / vl_wait
3. rollback_on_fail=true 表示失败时回滚前面的步骤
4. requires_user_input=true 表示需要暂停等用户输入
5. vl_wait 用于物理世界视觉反馈场景
"""
        response = await self.llm.call(prompt)
        return self._parse_steps(response.content)
```

#### 4.2.5 执行循环（含超时与崩溃恢复）

```python
class SlowAgent:
    async def _execute_loop(self, task_id: str):
        """主执行循环，支持暂停/恢复/崩溃恢复"""
        checkpoint = await self._load_checkpoint(task_id)
        if checkpoint is None:
            return  # 任务已被清理

        plan = checkpoint["plan"]
        current_step = checkpoint["current_step"]

        # ---- 崩溃恢复路径 ----
        # 从上次保存的 step_results 过滤出实际完成的（跳过已失败的）
        executed_ids = {r["step_id"] for r in checkpoint["step_results"]
                        if r.get("result") is not None and r.get("result", {}).get("ok") is not False}
        plan = [s for s in plan if s.step_id in executed_ids or
                all(r["step_id"] != s.step_id for r in checkpoint["step_results"])]
        current_step = len([r for r in checkpoint["step_results"]
                              if r.get("result") is not None and r.get("result", {}).get("ok") is not False])

        checkpoint["execution_state"] = ExecutionState.RUNNING.value
        await self._save_checkpoint(task_id, checkpoint)

        try:
            for i in range(current_step, len(plan)):
                step = plan[i]

                # 单步超时保护
                async def run_step_with_timeout():
                    if step.type == StepType.SKILL_CALL:
                        return await self._execute_skill(step)
                    elif step.type == StepType.PYTHON_EXEC:
                        return await self.python_executor.execute(step.params["code"])
                    elif step.type == StepType.USER_INPUT:
                        await self._pause_for_user_input(task_id, step)
                        return None  # 等 on_resume 恢复后由调用方继续
                    elif step.type == StepType.VL_WAIT:
                        return await self._wait_vl_feedback(task_id, step)
                    else:
                        raise ValueError(f"Unknown step type: {step.type}")

                timeout = step.timeout_seconds
                if timeout:
                    result = await asyncio.wait_for(run_step_with_timeout(),
                                                     timeout=timeout)
                else:
                    result = await run_step_with_timeout()

                if step.type == StepType.USER_INPUT:
                    return  # 暂停，等 on_resume 恢复

                checkpoint["step_results"].append({
                    "step_id": step.step_id,
                    "result": result,
                    "completed_at": utcnow(),
                })
                checkpoint["current_step"] = i + 1
                checkpoint["updated_at"] = utcnow()
                await self._save_checkpoint(task_id, checkpoint)

            await self._on_task_complete(task_id, checkpoint)

        except asyncio.TimeoutError:
            await self._save_checkpoint(task_id, {
                **checkpoint,
                "execution_state": ExecutionState.FAILED.value,
                "delivery_state": DeliveryState.PENDING_ANNOUNCE.value,
                "error": f"Step {plan[current_step].step_id} timeout",
                "updated_at": utcnow(),
            })
            await self._on_task_error(task_id, "step timeout")
        except Exception as e:
            step = plan[current_step]
            if step.rollback_on_fail:
                await self._rollback(task_id, checkpoint)
            await self._save_checkpoint(task_id, {
                **checkpoint,
                "execution_state": ExecutionState.FAILED.value,
                "delivery_state": DeliveryState.PENDING_ANNOUNCE.value,
                "error": str(e),
                "updated_at": utcnow(),
            })
            await self._on_task_error(task_id, str(e))
```

#### 4.2.6 Checkpoint 存储格式

每个任务对应文件：`{runtime_store_root}/checkpoints/{task_id}.json`

```json
{
  "task_id": "alarm_001",
  "plan": [
    {"step_id": "step_1", "type": "skill_call", "action": "check_calendar", ...},
    {"step_id": "step_2", "type": "skill_call", "action": "set_alarm", ...}
  ],
  "current_step": 1,
  "step_results": [
    {"step_id": "step_1", "result": {"ok": true, "available": true}, "completed_at": "..."}
  ],
  "execution_state": "running",
  "delivery_state": "silent",
  "control": {
    "speaker_owner": "fast",
    "attention_owner": "slow"
  },
  "handoff": {
    "intent": "帮我明天8点设个闹钟",
    "video_mode": null
  },
  "created_at": "2026-04-01T10:00:00Z",
  "updated_at": "2026-04-01T10:00:05Z"
}
```

#### 4.2.7 崩溃恢复机制

```python
class SlowAgent:
    async def _restore_from_checkpoints(self) -> List[str]:
        """
        启动时扫描所有 checkpoint 目录，恢复未完成的任务。
        返回恢复的任务 ID 列表。
        """
        restored = []
        for task_dir in list_task_dirs(runtime_store_root):
            checkpoint = await self._load_checkpoint_from_path(task_dir)
            if checkpoint and checkpoint["execution_state"] in (
                ExecutionState.RUNNING.value,
                ExecutionState.WAITING_USER.value,
                ExecutionState.WAITING_WORLD.value,
                ExecutionState.PAUSED.value
            ):
                # 标记为可恢复（避免重复执行）
                await self._save_checkpoint(checkpoint["task_id"], {
                    **checkpoint,
                    "execution_state": ExecutionState.PAUSED.value,
                    "needs_review": True,
                })
                restored.append(checkpoint["task_id"])
        return restored
```

#### 4.2.8 GuidanceLoop 示例（VisualGuidanceLoop）

**场景：** 指导类任务（如修车指导），Slow Agent 下发指令后，需要通过视频流实时观察执行结果来决定下一步。

这里的 `VisualGuidanceLoop` 是 `StreamingLoop` 的一个具体子类，不是和 `StreamingLoop` 并列的概念。

```python
class VisualGuidanceLoop:
    """
    物理世界闭环：LLM 下发指令 → VL 模型监控 → 结果反馈 → 下一个指令
    """

    def __init__(self, vl_model: VLModel, task_id: str):
        self.vl_model = vl_model
        self.task_id = task_id
        self.pending_instruction: Optional[str] = None
        self.vl_frame_interval = 5  # 每 5 秒采样一帧

    async def issue_instruction(self, instruction: str):
        """LLM 下发指令给用户/设备"""
        self.pending_instruction = instruction
        # 指令通过 TTS 播报 + App UI 显示
        await self._notify_user(instruction)
        # VL 监控从此刻开始
        asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """后台 VL 监控循环"""
        instruction = self.pending_instruction
        frame_count = 0

        async for frame in self.video_stream.subscribe(self.task_id):
            frame_count += 1
            if frame_count % self.vl_frame_interval != 0:
                continue  # 降帧采样

            observation = await self.vl_model.analyze(
                frame=frame,
                task=instruction,
            )

            if observation.is_complete:
                # 执行完成，通知 LLM 继续下一步
                await self._notify_agent_complete(self.task_id, observation.result)
                break
            elif observation.needs_adjustment:
                # 需调整，通过 TTS 提示
                await self._notify_user(observation.adjustment_hint)

    # ---- Fast Agent 接管时的处理 ----

    def on_fast_takeover(self):
        """
        Fast Agent 接管语音对话时调用。
        暂停 VL 监控循环，保留 pending_instruction。
        """
        self._paused = True
        logger.info(f"[VGL] Fast takeover, pausing task={self.task_id}")

    def on_fast_done(self):
        """
        Fast Agent 交还控制权时调用。
        恢复 VL 监控（如有 pending_instruction）。
        """
        self._paused = False
        if self.pending_instruction:
            asyncio.create_task(self._monitor_loop())
        logger.info(f"[VGL] Fast done, resuming task={self.task_id}")
```

**Fast 接管时 VL_WAIT 行为：**
- VL 监控暂停，但保留当前 pending_instruction
- Fast 完成对话后，VL 监控恢复（无需重新下发指令）
- Fast 播报不受 VL_WAIT 影响，正常执行（TTS 队列优先级高于 Slow）

#### 4.2.9 Rollback 逻辑

```python
async def _rollback(self, task_id: str, checkpoint: dict):
    """回滚已执行的步骤"""
    for step_result in reversed(checkpoint["step_results"]):
        step_id = step_result["step_id"]
        step = next(s for s in checkpoint["plan"] if s.step_id == step_id)

        # 如果 skill 定义了 rollback 方法，调用
        if step.type == StepType.SKILL_CALL:
            skill = self.skill_registry.get(step.action)
            if hasattr(skill, "rollback"):
                await skill.rollback(step.params, step_result["result"])
```

### 4.3 Skill 两层架构

**第一层：系统 Skill（代码定义，稳定可靠）**

```python
class SetAlarmSkill:
    name = "set_alarm"
    description = "设置闹钟"

    params = [
        {"name": "time", "required": True, "question": "你想设几点？"},
        {"name": "date", "required": True, "question": "是哪一天？"},
        {"name": "repeat", "required": False}
    ]

    async def execute(self, params):
        # 实际执行逻辑
        return {"status": "ok", "message": "闹钟设好了"}
```

**第二层：用户自定义 Skill（markdown 文件）**

```markdown
# my_custom_skill.md

## 描述
用户自定义的 skill

## 参数
- xxx

## 执行
用户定义的执行逻辑
```

慢系统 agent 可以在对话中**生成**新的 skill 文件，立即可用。

### 4.4 Python 执行器

Agent 自己写代码，然后执行。不是用户输入代码，是 agent 生成。

**核心设计：复用 Bash 沙箱**

Python Executor 不独立实现隔离，而是复用 Bash 沙箱的能力：
- 网络白名单 → Bash 沙箱已有
- 文件路径限制 → Bash 沙箱已有
- resource limits（内存、CPU、timeout）→ Bash 沙箱已有
- subprocess 隔离 → Bash 沙箱已有

Python Executor 只需要做 Python 特定的检查和注入。

**架构：**

```python
class PythonExecutor:
    """轻量 Python 执行器，复用 Bash 沙箱能力"""
    
    def __init__(self, bash_sandbox):
        self.bash_sandbox = bash_sandbox  # 复用已有的 Bash 沙箱
    
    async def execute(self, code: str) -> ExecResult:
        # 1. 静态检查（Python 特定）
        if not self._check_imports(code):
            return ExecResult(error="Import not allowed")
        
        # 2. 注入 helpers（Python 特定）
        script = self._inject_helpers(code)
        
        # 3. 写入临时文件
        script_path = f"/tmp/agent_{uuid.uuid4().hex}.py"
        with open(script_path, "w") as f:
            f.write(script)
        
        # 4. 通过 Bash 沙箱执行（复用沙箱能力）
        result = await self.bash_sandbox.execute(
            command=f"python3 {script_path}",
            timeout=30,
        )
        
        # 5. 清理 + 返回
        os.remove(script_path)
        return self._parse_result(result)
```

**Layer 1: 静态 import 检查（白名单）**

```python
# 白名单模块（参考 Claude Code）
ALLOWED_MODULES = {
    # 标准库（安全子集）
    'json', 'math', 'random', 'datetime', 'time',
    're', 'collections', 'itertools', 'functools',
    'typing', 'dataclasses', 'enum', 'uuid',
    'base64', 'hashlib', 'hmac',
    
    # 数据处理
    'pandas', 'numpy',
    
    # 禁止的模块（黑名单，双重保险）
    # 'os', 'sys', 'subprocess', 'socket', 'urllib',
    # 'requests', 'httpx', 'eval', 'exec', 'open',
    # '__import__', 'multiprocessing', 'threading'
}

def _check_imports(code: str) -> bool:
    """检查所有 import 是否在白名单"""
    imported = extract_imports(code)  # AST 解析
    for module in imported:
        if module.split('.')[0] not in ALLOWED_MODULES:
            return False
    return True
```

**Layer 2: helpers 注入**

Agent 代码里不能直接 `import requests`，但可以调用注入的 `http_get()`：

```python
def _inject_helpers(code: str) -> str:
    """在 agent 代码前注入安全 helpers"""
    return f"""
import json
import sys

# 安全 helpers（网络请求会被 Bash 沙箱拦截）
def http_get(url: str) -> dict:
    import urllib.request
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())

def read_memory(key: str) -> dict:
    # 调用宿主机 API（通过环境变量传递 token）
    import urllib.request
    token = os.environ.get("AGENT_TOKEN")
    req = urllib.request.Request(
        f"http://localhost:8000/memory/{{key}}",
        headers={{"Authorization": f"Bearer {{token}}"}}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def write_memory(key: str, value: dict):
    # 同上，POST 到宿主机 API
    ...

def print_result(data):
    print("__RESULT__", json.dumps(data))

# Agent 代码
{code}
"""
```

**Layer 3: Bash 沙箱执行（自动隔离）**

```
Python 进程在 Bash 沙箱内运行：
  → 网络调用 → Bash 沙箱检查域名白名单
  → 文件读写 → Bash 沙箱检查路径（workspace 内）
  → 内存/CPU → Bash 沙箱 resource limits
  → timeout → Bash 沙箱强制 kill
```

**默认限制：**
- timeout: 30s
- max_memory: 128MB（Bash 沙箱 RLIMIT_AS）
- 网络白名单：`["api.github.com", "api.weather.com"]`
- 文件路径：只允许 workspace 目录
- 禁止子进程：Bash 沙箱 RLIMIT_NPROC=0

**Agent 可用的 helpers：**

```python
# 网络请求（域名白名单由 Bash 沙箱控制）
result = http_get("https://api.example.com/...")

# Memory 操作（通过宿主机 API）
memory = read_memory("user_preferences")
write_memory("user_preferences", {"key": "value"})

# Skill 操作
skill_code = read_skill("my_custom_skill")
write_skill("my_custom_skill", "# markdown content")

# 文件操作（限制在 workspace，Bash 沙箱控制）
content = read_file("tasks/result.txt")
write_file("tasks/output.txt", "data")

# 输出（结果被捕获）
print_result({"status": "ok", "data": ...})
```

### 4.5 Long-term Memory 系统

#### 文件结构

```
long_term_memory/
  user/                    ← 用户偏好、角色信息
  feedback/                ← 用户反馈和纠正
  project/                 ← 项目上下文和目标
  reference/               ← 外部系统引用
  skills/                  ← 用户自定义 skill（markdown）
  INDEX.md                 ← 记忆索引
```

#### 每条记忆的格式

```markdown
---
name: {{记忆名称}}
description: {{单行描述 — 决定相关性}}
type: {{user|feedback|project|reference}}
---

{{记忆内容 — feedback/project 格式：rule + **Why:** + **How to apply:**}}
```

#### 四类记忆（参考 Claude Code memoryTypes.ts）

| 类型 | 描述 | 何时保存 |
|------|------|---------|
| `user` | 用户角色、偏好、知识 | 了解用户背景时 |
| `feedback` | 用户反馈和纠正（成功和失败都记） | 用户纠正或确认时 |
| `project` | 项目上下文、目标、正在进行的工作 | 学习到相关上下文时 |
| `reference` | 外部系统引用（Linear、Jira 等） | 了解资源位置时 |

#### 不保存什么（参考 WHAT_NOT_TO_SAVE_SECTION）

- 代码模式、架构、文件路径（可以从代码读取）
- Git 历史（`git log` 是权威）
- 调试解决方案（代码里有）
- MEMORY.md 里已有的内容
- 临时状态、当前对话上下文

#### 记忆可能过时

> Memory records can become stale over time. Before answering based solely on memory, verify current state. If recalled memory conflicts with observation, trust observation — update or remove stale memory.

### 4.6 错误处理和降级策略

**Fast Agent 错误处理：**

```python
class FastAgent:
    async def handle_turn(self, user_input: str):
        try:
            return await self._handle_turn_impl(user_input)
        except LLMTimeoutError:
            # LLM 调用超时
            return "抱歉，我现在响应有点慢，请稍后再试"
        except LLMRateLimitError:
            # 限流，handoff 给 Slow 异步处理
            await self.handoff_async(user_input)
            return "好的，我会帮你处理，稍后告诉你结果"
        except NetworkError:
            # 网络问题
            return "网络连接不稳定，请检查网络后重试"
        except Exception as e:
            logger.error(f"Fast Agent error: {e}")
            return "出了一些问题，请稍后再试"
```

**Slow Agent 错误处理：**

```python
class SlowAgent:
    async def _execute_plan(self, task_id: str, plan: List[Step]):
        try:
            for step in plan:
                result = await self._execute_step(step)
        except SkillExecutionError as e:
            # Skill 执行失败，检查是否需要 rollback
            if step.rollback_on_fail:
                await self._rollback(task_id)
            await self._on_task_error(task_id, str(e))
        except TaskTimeoutError:
            # 任务超时
            await self._on_task_error(task_id, "任务执行超时")
        except OutOfMemoryError:
            # 内存超限
            await self._on_task_error(task_id, "任务占用内存过大")
```

**Python Executor 沙箱逃逸检测：**

```python
class PythonExecutor:
    async def execute(self, code: str) -> ExecResult:
        # 1. 静态 import 检查
        if not self._check_imports(code):
            return ExecResult(error="Import not allowed: dangerous module")
        
        # 2. AST 检查危险模式
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 检查危险调用
                if self._is_dangerous_call(node):
                    return ExecResult(error="Dangerous call detected")
        
        # 3. Bash 沙箱执行（subprocess 自动隔离）
        result = await self.bash_sandbox.execute(
            command=f"python3 {script_path}",
            timeout=30,
        )
        
        # 4. 检查执行结果
        if result.exit_code != 0:
            return ExecResult(error=result.stderr)
        
        # 5. 检查输出是否包含敏感信息
        if self._output_has_secrets(result.stdout):
            return ExecResult(stdout="[output contains sensitive data, redacted]")
        
        return result
    
    def _is_dangerous_call(self, node: ast.Call) -> bool:
        """AST 检查危险调用"""
        dangerous_patterns = [
            ("os", "system"),
            ("os", "popen"),
            ("subprocess", "Popen"),
            ("builtins", "eval"),
            ("builtins", "exec"),
            ("__import__",),
        ]
        if isinstance(node.func, ast.Name):
            name = node.func.id
            return (name,) in dangerous_patterns
        if isinstance(node.func, ast.Attribute):
            obj = node.func.value
            if isinstance(obj, ast.Name):
                return (obj.id, node.func.attr) in dangerous_patterns
        return False
```

**WebSocket 断线重连：**

```python
class WebSocketClient:
    async def connect(self, url: str):
        while True:
            try:
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    self._on_connected()
                    await self._receive_loop()
            except websockets.ConnectionClosed:
                self._on_disconnected()
                await asyncio.sleep(self.retry_interval)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(self.retry_interval)
    
    async def _on_connected(self):
        """重连后的状态恢复"""
        # 1. 恢复 Fast Agent 状态
        await self.fast_agent.resume()
        
        # 2. 检查是否有 running 的 Slow Tasks
        running_tasks = await self.runtime_store.get_running_tasks()
        for task in running_tasks:
            # 从 checkpoint 恢复
            checkpoint = await self.runtime_store.get_checkpoint(task.task_id)
            if checkpoint:
                # 重新注册到 Slow Agent
                await self.slow_agent.resume_from_checkpoint(checkpoint)
        
        # 3. 通知端侧重连成功
        await self.send({"type": "reconnected", "timestamp": time.time()})
```

**降级策略总结：**

| 错误类型 | 降级策略 | 恢复方式 |
|---------|---------|---------|
| LLM 超时 | Fast 直接回复 | 用户重试 |
| LLM 限流 | handoff 给 Slow 异步处理 | 稍后通知用户 |
| 网络断线 | 自动重连 + 状态恢复 | 从 checkpoint 恢复 |
| Skill 执行失败 | rollback + 错误通知 | 用户手动重试 |
| Python Executor 超时 | 超时错误 + 回滚 | 用户手动重试 |
| 内存超限 | 杀掉进程 + 错误通知 | 用户手动重试 |
| 沙箱逃逸 | 拒绝执行 + 错误通知 | 记录审计日志 |

---

## 六、快慢通信机制

### 5.1 Handoff 消息格式

统一的消息信封，未来可平滑迁移到进程间通信（只需把内存队列换成 Mailbox 文件）：

```json
{
  "from": "fast_system",
  "to": "slow_system",
  "type": "handoff",
  "task_id": "alarm_001",
  "intent": "用户要设闹钟，8点，明天",
  "payload": {
    "action": "set_alarm",
    "params": {"time": "08:00", "date": "明天"}
  },
  "conversation_snapshot": [
    {"role": "user", "text": "帮我设个闹钟"},
    {"role": "assistant", "text": "你想设几点？"},
    {"role": "user", "text": "8点，明天"}
  ],
  "timestamp": "2026-04-01T10:00:00Z"
}
```

### 5.2 Handoff / Task Event 类型

| type | 方向 | 说明 |
|------|------|------|
| `handoff` | fast → slow | 快系统投递任务 |
| `task_event` | slow → fast | 慢系统回传统一任务事件 |

`task_event` 统一承载 Slow → Fast 的所有回调，避免 `handoff_back / need_param / progress / error` 四散：

```json
{
  "type": "task_event",
  "task_id": "alarm_001",
  "event_kind": "completed",
  "message": "闹钟设好了，明天8点",
  "speak_policy": "queue",
  "delivery_state": "pending_announce"
}
```

其中 `event_kind` 可选：

- `accepted`
- `started`
- `progress`
- `need_user_input`
- `completed`
- `failed`
- `cancelled`
- `superseded`

### 5.3 完整对话流程

```
用户：帮我设个闹钟
  ↓
快系统 round 1：
  查 skill schema，发现闹钟需要 time 和 date
  → 问：「你想设几点？」
  ↓
用户：8点
  ↓
快系统 round 2：
  time 有了，date 还缺
  → 问：「是哪一天？」
  ↓
用户：明天
  ↓
快系统：
  参数齐了
  → handoff({ intent: "用户要设闹钟，8点，明天" })
  → 过渡话术：「好的，正在帮你处理」
  → 立即返回，不 await
  → 快系统继续接用户下一轮输入
  ↓
慢系统收到：
  → 解析 intent，填充参数
  → 执行 set_alarm skill
  → 完成后 task_event({ event_kind: "completed", message: "闹钟设好了，明天8点", speak_policy: "queue" })
  ↓
快系统收到 task_event：
  → 找对话间隙插入播报
  → 「对了，你让我设的闹钟已经设好了，明天早上8点」
  ↓
继续正常对话
```

### 5.4 中途修改/取消

```
用户：等等，改成9点
  ↓
快系统：
  查 runtime store，发现有个相关任务在跑
  → 过渡话术：「好的，稍等」
  → handoff({ intent: "用户要把闹钟从8点改成9点", task_id: "alarm_001", mode: "supersede" })
  ↓
慢系统收到：
  → 找到 running_task alarm_001
  → 将旧 run 标记为 superseded
  → 新建 run_002 继承上下文并重跑
  → 完成后 task_event(completed)
  ↓
快系统找间隙播报：「闹钟已经改成9点了」
```

---

## 七、Runtime Store 与 Long-term Memory

这里不再把所有共享状态都叫 memory，而是拆成三层：

1. `Conversation State`：当前对话态、当前 owner、当前 speaking 状态
2. `Runtime Store`：任务注册表、checkpoint、任务事件索引
3. `Long-term Memory`：user / feedback / project / reference 四类长期记忆

### 6.1 Runtime Store: 任务注册表

```json
{
  "tasks": {
    "alarm_001": {
      "action": "set_alarm",
      "params": {"time": "09:00", "date": "明天"},
      "execution_state": "running",
      "delivery_state": "silent",
      "speaker_owner": "fast",
      "attention_owner": "slow",
      "handoff_at": "2026-04-01T10:00:00Z",
      "updated_at": "2026-04-01T10:00:05Z",
      "active_run_id": "run_002",
      "supersedes": "run_001"
    }
  }
}
```

### 6.2 Runtime Store: Checkpoint（慢系统写入）

```json
{
  "checkpoints": {
    "alarm_001": {
      "step": 2,
      "plan": ["check_calendar", "set_alarm", "confirm"],
      "step_results": [
        {"step": 1, "action": "check_calendar", "result": "available"},
        {"step": 2, "action": "set_alarm", "result": "pending"}
      ],
      "execution_state": "waiting_user",
      "paused_at": "step_3",
      "control": {
        "speaker_owner": "fast",
        "attention_owner": "slow"
      },
      "pending_user_input": {
        "field": "confirm",
        "question": "闹钟设好了，确认一下，明天9点对吗？"
      }
    }
  }
}
```

### 6.3 Runtime Store: Conversation State

```json
{
  "conversation": {
    "dialog_id": "dialog_001",
    "speaker_owner": "fast",
    "attention_owner": "slow",
    "foreground_task_id": null,
    "background_task_ids": ["alarm_001", "meeting_003"],
    "interrupt_epoch": 12
  }
}
```

### 6.3.b Runtime Store: Tool Call Registry

双向工具协议需要一个轻量的 `tool_call` 注册表，保存“调用级真相”，避免把工具中间态混进 task 摘要，也避免只靠内存里的 `active_calls`。

```json
{
  "tool_calls": {
    "call_001": {
      "task_id": "repair_001",
      "run_id": "run_009",
      "tool_name": "camera_capture",
      "target": "device",
      "state": "waiting_approval",
      "supports_pause": false,
      "supports_resume": false,
      "supports_cancel": true,
      "approval_required": {
        "kind": "device_permission",
        "permission": "camera"
      },
      "last_progress": {
        "status": "awaiting_camera_permission",
        "updated_at": "2026-04-02T10:00:08Z"
      },
      "created_at": "2026-04-02T10:00:05Z",
      "updated_at": "2026-04-02T10:00:08Z"
    }
  }
}
```

**Tool Call Registry 规则：**

- `tool_calls` 是工具调用级真相源，粒度低于 `tasks`、高于端侧执行器内部状态
- `tasks` 只聚合任务摘要，不保存每个 `call_id` 的完整历史
- Slow/Fast Runtime 在发送 `tool_call` 前先写入 `tool_calls`
- 端侧执行器恢复连接后，可以按 `tool_calls` 判断哪些调用仍应继续、取消或忽略
- `tool_calls` 可按终态和 TTL 清理，不进入 Long-term Memory

### 6.4 Long-term Memory

Long-term Memory 只保存未来会话仍然有价值的信息，不保存当前任务运行态。

### 6.5 读写权限

| 模块 | 快系统 | 慢系统 |
|------|--------|--------|
| tasks | 读 | 写 |
| checkpoints | — | 读写 |
| conversation | 读写 | 读写 |
| long_term_memory | 读 | 写 |
| system | 读（部分） | 读写 |

**一致性约束**：

- `checkpoint` 是执行真相源
- `tool_calls` 是工具调用级真相源
- `tasks` 是给 Fast/UI 读取的摘要索引
- Slow 必须先写 checkpoint / tool_calls，再更新 task registry
- Fast 不读取 checkpoint 内部细节，只读 registry / conversation state

---

## 八、Skill Registry 设计

### 7.1 统一工厂模式

参考 Claude Code `buildTool()` 工厂，所有 skill 走同一接口：

```python
SKILL_DEFAULTS = {
    "isEnabled": lambda: True,
    "isConcurrencySafe": lambda input: False,
    "isReadOnly": lambda input: False,
    "isDestructive": lambda input: False,
    "checkPermissions": lambda input: {"behavior": "allow"},
}

def buildSkill(def):
    """统一 skill 工厂"""
    return {**SKILL_DEFAULTS, **def}

# 注册
registry.register(buildSkill({
    "name": "set_alarm",
    "description": "设置闹钟",
    "params": [...],
    "can_ask_upfront": ["time", "date"],
    "async execute(self, params):
        ...
}))

# 生成 manifest
manifest = registry.get_manifest()
# → 注入快系统 prompt，供规划使用
```

### 7.2 Manifest 同步机制

**Manifest 的作用**：告诉 Fast Agent 的 LLM 两件事：
1. 你可以直接调这些工具（fast_tools）
2. 这些工具需要 handoff（slow_tools）

### 7.3 工具执行是双向闭环，不是单向 RPC

这里参考 Claude Code 的一个重要设计点：工具执行不应被理解为
`Agent -> 调工具 -> 返回结果`
的单向调用，而应理解为一个可协商、可中断、可回传状态的执行闭环。

**单向 RPC 心智模型：**

```text
Agent -> tool_call -> Tool Executor -> tool_result -> Agent
```

**双向闭环心智模型：**

```text
Agent -> tool_intent
      -> Runtime / Permission / User / Device 协商
      -> tool_call 执行
      <- progress / approval_request / cancellation / failure / tool_result
Agent 再根据这些反馈继续决策
```

这意味着工具层不是一个“调完等结果”的黑盒，而是 Slow/Fast Runtime 的一部分控制面。

**为什么要这样设计：**

- 用户可能在工具执行中插话或打断
- 某些工具需要端侧权限确认或用户补充参数
- StreamingLoop 中的工具往往不是一次性完成，而是持续产生进度和观测结果
- 某个并行工具失败时，其他工具可能需要被取消，而不是继续消耗资源

**对本项目的落地约束：**

1. `tool_call` 只是执行开始，不代表这次调用一定会自然完成
2. Runtime 可以反向向工具执行流注入控制信号：
   - `tool_approval_required`
   - `tool_approval_response`
   - `cancel_tool`
   - `pause_tool`
   - `resume_tool`
3. 工具执行器可以反向向 Runtime 回报状态，而不只是在结束时回一个最终结果：
   - `tool_progress`
   - `tool_result`
   - `tool_error`
4. Fast Agent 和 Slow Agent 都不应把工具当作纯同步函数，而应把它当作“带状态的任务通道”

**架构结论：**

- Fast Agent 更适合使用“短生命周期、可快速取消”的工具
- Slow Agent 更适合使用“长生命周期、可持续回报进度/观测”的工具
- 端侧执行器需要同时支持执行面和控制面，而不是只有 `execute()`

**Manifest Schema**：

```json
{
  "version": "1.0.0",
  "updated_at": "2026-04-01T10:00:00Z",
  
  "fast_tools": [
    {
      "name": "text_search",
      "description": "搜索文本获取实时信息",
      "capabilities": {
        "supports_progress": false,
        "supports_cancel": true,
        "supports_pause": false,
        "supports_resume": false,
        "may_require_approval": false
      },
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
      }
    },
    {
      "name": "image_search",
      "description": "识别人脸或物体",
      "capabilities": {
        "supports_progress": true,
        "supports_cancel": true,
        "supports_pause": false,
        "supports_resume": false,
        "may_require_approval": false
      },
      "parameters": {
        "type": "object",
        "properties": {
          "image_data": {"type": "string", "description": "base64图片"}
        },
        "required": ["image_data"]
      }
    }
  ],
  
  "slow_tools": [
    {
      "name": "set_alarm",
      "description": "设置闹钟提醒",
      "can_ask_upfront": true,
      "upfront_params": ["time", "date"],
      "capabilities": {
        "supports_progress": true,
        "supports_cancel": true,
        "supports_pause": false,
        "supports_resume": false,
        "may_require_approval": true
      },
      "parameters": {
        "type": "object",
        "properties": {
          "time": {
            "type": "string",
            "description": "时间",
            "question_for_user": "你想设几点？",
            "examples": ["9点", "上午10点", "晚上8点半"]
          },
          "date": {
            "type": "string",
            "description": "日期",
            "question_for_user": "是哪一天？",
            "examples": ["今天", "明天", "周一"]
          },
          "label": {"type": "string", "description": "备注（可选）"}
        },
        "required": ["time", "date"]
      }
    }
  ]
}
```

**同步协议（v1：启动同步）**：

```python
# Slow Agent 启动时生成 manifest
class SkillRegistry:
    def __init__(self, manifest_path: str = "manifest.json"):
        self.skills = {}
        self.manifest_path = manifest_path
        self._load_skills()
        self._generate_manifest()

    def _load_skills(self):
        """扫描 skills/ 目录，注册所有 skill"""
        for skill_file in Path("skills/").glob("*.py"):
            skill = load_skill(skill_file)
            self.skills[skill.name] = skill

    def _generate_manifest(self):
        """生成 manifest.json"""
        manifest = {
            "version": "1.0.0",
            "updated_at": datetime.now().isoformat(),
            "fast_tools": [
                {"name": "text_search", "description": "...", "parameters": {...}},
                {"name": "image_search", "description": "...", "parameters": {...}}
            ],
            "slow_tools": [
                skill.to_manifest_schema() for skill in self.skills.values()
            ]
        }
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

# Fast Agent 启动时读取 manifest
class FastAgent:
    def __init__(self, manifest_path: str = "manifest.json"):
        with open(manifest_path) as f:
            self.manifest = json.load(f)
        self._inject_tools_to_prompt()

    def _inject_tools_to_prompt(self):
        """将 manifest 注入 LLM prompt"""
        self.system_prompt += f"\n\n可用工具��\n{json.dumps(self.manifest, ensure_ascii=False)}"
```

**热更新（v2：未来扩展）**：

```python
# Slow Agent 提供回调机制
class SkillRegistry:
    def __init__(self):
        self._update_callbacks = []

    def subscribe(self, callback):
        self._update_callbacks.append(callback)

    def update_manifest(self):
        """skill 变更时重新生成，通知快系统"""
        self._generate_manifest()
        for callback in self._update_callbacks:
            callback(self.manifest)

# Fast Agent 注册回调
registry.subscribe(lambda m: fast_agent.reload_manifest(m))
```

**设计决策**：
- v1 只做启动同步（skill 变更需重启）
- v2 支持热更新（需处理正在进行的对话的边界情况）
- 优先简化设计，跑通核心流程

---

## 九、端侧改动

### 8.1 端侧职责

端侧不需要知道 Fast/Slow Agent 的存在，对云侧架构完全透明。

端侧只需要做四件事：

```
1. 音频输入    → 麦克风采集，持续推流到云侧
2. 音频输出    → 播放云侧返回的 TTS 流
3. 视频输入    → 摄像头采集，按需/持续推流到云侧
4. 聊天交互    → 实时显示对话、文本输入、工具执行状态
```

### 8.1.1 开发顺序：先 Debug Client，再 HarmonyOS 客户端

为了先把端云链路、协议和 Runtime 状态机跑通，第一阶段不要求先完成原生客户端。
在 Python-first 主干下，Debug Client 可以先用 Web 形态实现，也可以后续补 CLI/桌面调试终端；它是联调工具，不是语言路线的主线。

推荐顺序：

1. **先做 Debug Client（推荐先 Web）**
   - 第一阶段建议运行在浏览器里
   - 提供文本输入、麦克风、摄像头、TTS 播放、消息日志、task/tool_call 状态面板
   - 目标是快速验证 `turn / handoff / task_event / tool_call / tool_result / video_frame`
2. **再做 HarmonyOS 客户端**
   - 在协议已经稳定后，实现正式端侧体验
   - 优先复用云侧协议和 Runtime，不重新设计消息模型

**为什么这样安排：**

- 浏览器调试更快，便于直接观察 WebSocket / WebRTC / DataChannel 消息
- 可以先验证 `Fast Agent / Slow Agent / Runtime Store / Tool Call Registry` 的协作
- 可以先暴露调试视图，直接看到 owner、task、checkpoint、tool_call 状态
- 避免太早陷入原生端权限、打包、安装、设备兼容性问题

**Debug Client 的定位：**

- 它是“协议调试终端”，不是正式产品 UI
- 它的职责是帮助系统联调，不承担最终交互体验设计
- 只要协议和行为一致，浏览器端与 HarmonyOS 端可以共用同一套云侧接口

### 8.1.2 Demo Client 的调试阶段方案与正式目标

仓库内新增的 `apps/demo-client` 应视为联调优先的轻量 Demo Client，而不是正式产品客户端。

当前调试阶段方案：

- 前端技术栈使用 `React + Vite`
- 默认连接 Python `gateway`
- 保留极轻的 `mock mode`，仅用于离线 UI 调整，不模拟完整 Runtime
- 文本输入继续通过 `turn` 走现有控制协议
- 麦克风输入采用持续采集 + 分片上行
- 摄像头输入采用低帧率持续抓帧上行
- 媒体消息先走 `WebSocket + 结构化消息 + base64 payload`
- TTS 第一版先用浏览器 `speechSynthesis`，不要求云侧先回真实音频流

正式目标方案：

- 正式客户端仍然是各个 App，不是仓库内的 Demo Client
- 媒体面和控制面需要分离设计
- 媒体链路后续优先迁移到更适合实时产品的正式传输方案
- Demo 阶段的消息语义必须向正式协议靠拢，避免后续切换时重做 Runtime 事件模型

当前调试阶段允许妥协的部分：

- 媒体传输实现
- TTS 播放实现
- 页面视觉形态

当前调试阶段不应妥协的部分：

- `session_id` 绑定
- streaming 输入的持续性语义
- `conversation / tasks / checkpoints / task_events` 的观测方式
- 后续 `StreamingLoop / MonitoringLoop / GuidanceLoop` 所需的事件时序

**阶段目标：**

- Phase 1：Python Gateway + Debug Client + WebSocket，打通控制协议和最小媒体链路
- Phase 2：在协议稳定后，引入 WebRTC 优化实时音视频
- Phase 3：HarmonyOS 客户端接入同一协议，替换 Debug Client 的端侧能力

### 8.2 端侧架构

```

### 8.2.1 Demo Client 页面结构

`apps/demo-client` 第一版建议采用三栏调试布局：

- 顶栏：连接与媒体状态
  - `gateway` 地址
  - `session_id`
  - `connected / reconnecting / mock`
  - 麦克风状态
  - 摄像头状态
  - TTS 状态
- 左栏：聊天与语音输出
  - 聊天消息流
  - 文本输入与 `turn` 发送
  - assistant 文本回复
  - 浏览器 TTS 播放状态
- 中栏：媒体调试
  - 摄像头预览
  - 视频发送频率
  - 音频分片发送节奏
  - 最近一次媒体上行时间
- 右栏：Runtime 状态
  - `conversation`
  - `tasks`
  - `recent task_events`
  - `checkpoint`
  - 最近 `audio_chunk / video_frame` 摘要

第一版不要求：

- 音量条或波形图
- 原始 JSON 抓包页
- 正式产品化视觉设计
HomePage (UI + 状态)
  │
  ├─ AudioStreamService     → 麦克风采集 → 实时推流到云侧
  │                           云侧可发 stop_speech 中断
  │
  ├─ VideoStreamService      → 摄像头采集 → 按需/持续推流
  │                           按 task_id 绑定推流任务
  │
  ├─ AudioPlaybackService   → 播放云侧 TTS 流
  │                           支持队列（TTS 音频排队播放）
  │
  ├─ WebSocketService       → 统一的消息管道
  │                           收: tts / tool_call / video_frame
  │                           发: turn / handoff_resume / tool_result
  │
  └─ ChatHistoryService     → 维护对话历史
                              同时支持: 用户文本输入 + 后台任务消息插入
```

### 8.3 四个核心能力

**1. 音频推流**

```
麦克风 → PCM流 → [100ms分片] → WebSocket audio_chunk 消息 → 云侧
```

云侧可以发 `stop_speech` 中断采集/推流。

调试阶段约束：

- 必须使用持续分片语义，而不是“录一段再上传”
- 首版可使用结构化消息和 `base64` 包裹 payload
- 后续迁移正式媒体链路时，不改变音频分片在 Runtime 中的事件语义

**2. TTS 播放**

调试阶段允许先不依赖云侧真实音频流。第一版可以由端侧根据 assistant 文本使用浏览器 `speechSynthesis` 播放，确保：

- StreamingLoop 调试时有可听反馈
- 不阻塞 Python 主干的媒体输出协议演进

正式方案仍然是云侧返回真实 TTS 流并由端侧实时播放。届时需要支持队列：

```typescript
class AudioPlaybackService {
  private queue: AudioChunk[] = []
  
  enqueue(chunk: AudioChunk): void {
    this.queue.push(chunk)
    if (!this.isPlaying) {
      this.playNext()
    }
  }
  
  private playNext(): void {
    const chunk = this.queue.shift()
    if (chunk) {
      this.play(chunk).then(() => this.playNext())
    }
  }
}
```

云侧统一发 `tts` 消息（无论是 Fast Agent 还是 Slow Agent），端侧只需要一个播放队列。

**3. 视频推流**

调试阶段：

- 浏览器持续采集摄像头
- 以前台固定低帧率抓帧
- 通过 `video_frame` 消息持续上行

正式方案：

- 延续相同的 `session / task / loop` 绑定语义
- 只替换媒体传输实现，不替换 Runtime 对视频输入的消费方式

两种模式：
- **按需**：`turn` 消息里带一帧 base64 图片
- **持续**：云侧通过 `start_camera_stream` / `stop_camera_stream` 控制

```typescript
// 云侧发 start_camera_stream
{
  "type": "start_camera_stream",
  "task_id": "repair_001",
  "fps": 2
}

// 端侧开始推流
setInterval(() => {
  const frame = captureFrame()
  ws.send({
    type: 'video_frame',
    task_id: 'repair_001',
    data: base64(frame),
    timestamp: Date.now()
  })
}, 500)  // 2fps

// 云侧发 stop_camera_stream
{
  "type": "stop_camera_stream",
  "task_id": "repair_001"
}
```

**4. 聊天页面**

端侧维护对话列表，显示：

```
用户: "帮我设个闹钟"
助手: "你想设几点？"
用户: "8点"
助手: "好的，闹钟已设置，明天早上8点。"

--- (后台任务) ---
[会议助手] 正在记录会议...
[会议助手] 会议内容已保存
```

后台任务消息以特殊样式插入聊天列表。

### 8.4 工具执行

云侧发 `tool_call` 消息，端侧执行后返回结果：

```
云侧 → tool_call { tool: "camera_capture", params: {}, call_id: "xxx" }
端侧 → 执行摄像头拍照
端侧 → 返回 tool_result { call_id: "xxx", result: "base64..." }
```

端侧工具注册表：

```typescript
class ToolExecutor {
  private tools: Map<string, ToolHandler> = new Map()
  
  register(name: string, handler: ToolHandler): void {
    this.tools.set(name, handler)
  }
  
  async execute(name: string, params: object): Promise<string> {
    const handler = this.tools.get(name)
    if (!handler) {
      throw new Error(`Tool not found: ${name}`)
    }
    return await handler(params)
  }
}

// 注册端侧工具
toolExecutor.register('camera_capture', async () => {
  const frame = await cameraService.captureFrame()
  return base64(frame)
})

toolExecutor.register('camera_zoom_in', async () => {
  await cameraService.zoomIn()
  return '{"status": "ok"}'
})
```

### 8.4.1 端侧工具协议应按双向闭环设计

上一节的示例是最简 happy path，但正式协议不应只支持
`tool_call -> tool_result`
这一条直线。

对于摄像头、麦克风、系统设置、通知、定位、文件等端侧工具，云侧和端侧之间应该保留双向控制能力：

- 云侧下发执行请求：`tool_call`
- 端侧回报进度：`tool_progress`
- 端侧请求权限或用户确认：`tool_approval_required`
- 云侧取消执行：`cancel_tool`
- 云侧暂停/恢复执行：`pause_tool / resume_tool`
- 端侧结束并返回：`tool_result / tool_error`

示例：

```text
云侧 -> tool_call(camera_stream_start, call_id=1)
端侧 -> tool_progress(call_id=1, status="opening_camera")
端侧 -> tool_result(call_id=1, result={"stream_id":"cam_001"})

云侧 -> tool_call(camera_capture, call_id=2)
端侧 -> tool_approval_required(call_id=2, permission="camera")
云侧 -> tool_approval_response(call_id=2, approved=true)
端侧 -> tool_result(call_id=2, result={"image":"base64..."})

云侧 -> tool_call(vibrate_device, call_id=3)
用户打断
云侧 -> cancel_tool(call_id=3)
端侧 -> tool_error(call_id=3, error="cancelled")
```

**设计要求：**

- 每个端侧工具调用都必须有 `call_id`
- 工具调用必须支持中间态，而不是只有开始和结束
- 取消必须是显式协议动作，不能只靠连接断开隐式表达
- StreamingLoop 绑定的工具应优先支持 `pause/resume/cancel`
- 端侧工具执行器内部应维护 `active_calls`，而不是只暴露一个无状态 `execute()`
- `pause_tool / resume_tool` 只能发给声明 `supports_pause / supports_resume` 的工具
- 不支持 `pause` 的工具收到暂停请求时，Runtime 必须降级为：
  - 若支持 `cancel`，改发 `cancel_tool`
  - 若也不支持 `cancel`，则把该 task 标记为 `waiting_world` 或 `running`，并禁止新的同类调用重入
- `tool_approval_required / tool_approval_response` 是唯一审批消息命名，不再使用 `approval_required`
- 所有 `tool_progress / tool_result / tool_error` 都必须带 `call_id`

### 8.5 端侧需要关心的所有消息类型

**收到 (云侧 → 端侧)：**

| 消息类型 | 说明 | 处理 |
|---------|------|------|
| `tts` | TTS 音频流 | 加入播放队列 |
| `tool_call` | 工具调用请求 | 执行工具，返回 tool_result |
| `cancel_tool` | 取消指定工具调用 | 尝试取消并回报结果 |
| `pause_tool` | 暂停指定工具调用 | 暂停执行并保留上下文 |
| `resume_tool` | 恢复指定工具调用 | 从暂停点继续 |
| `tool_approval_response` | 对端侧权限/确认请求的答复 | 继续或终止执行 |
| `start_camera_stream` | 开始摄像头推流 | 启动摄像头，按 fps 推流 |
| `stop_camera_stream` | 停止摄像头推流 | 停止推流 |
| `heartbeat` | 心跳保活 | 回复 heartbeat |

**发出 (端侧 → 云侧)：**

| 消息类型 | 说明 | 触发时机 |
|---------|------|---------|
| `turn` | 用户对话 | 用户说话/文本输入 |
| `handoff_resume` | 用户回复追问 | 用户回答后台任务的追问 |
| `tool_result` | 工具执行结果 | 工具执行完成 |
| `tool_progress` | 工具中间进度 | 长调用有阶段变化时 |
| `tool_error` | 工具执行失败或被取消 | 执行失败/取消 |
| `tool_approval_required` | 端侧工具需要权限或确认 | 执行前无法直接继续 |
| `video_frame` | 视频帧 | 摄像头推流中 |
| `stop_speech` | 用户打断 | 用户按下打断按钮 |
| `request_to_speak` | 用户请求说话 | 用户按下说话按钮 |

### 8.6 端侧不需要关心的（云侧内部）

- Fast/Slow Agent 架构
- handoff 机制
- VL 模型反馈
- VisualGuidanceLoop / MeetingMinutesLoop
- manifest 同步
- task_id 的语义（端侧只是透传）

这些对端侧完全透明。

---

## 十、WebSocket 消息格式

### 9.1 端侧 → 云侧

```json
// 普通对话轮次
{
  "type": "turn",
  "dialog_id": "xxx",
  "text": "帮我设个闹钟",
  "audio": "base64...",
  "video_frame": "base64...",
  "timestamp": 1743400000000
}

// handoff 继续（慢系统需要补充参数）
{
  "type": "handoff_resume",
  "task_id": "alarm_001",
  "dialog_id": "xxx",
  "text": "8点，明天",
  "timestamp": 1743400000000
}

// 控制消息
{ "type": "stop_speech", "dialog_id": "xxx", "timestamp": 0 }
{ "type": "request_to_speak", "dialog_id": "xxx", "timestamp": 0 }
{ "type": "local_responding_ended", "dialog_id": "xxx", "reply_id": "xxx", "timestamp": 0 }
```

### 9.2 云侧 → 端侧

```json
// TTS 音频
{
  "type": "tts",
  "dialog_id": "xxx",
  "reply_id": "xxx",
  "data": "base64...",
  "seq": 0,
  "is_end": false,
  "timestamp": 0
}

// 追问（快慢系统通用）
{
  "type": "need_param",
  "task_id": "alarm_001",
  "dialog_id": "xxx",
  "message": "你想设几点？",
  "timestamp": 0
}

// 慢系统完成
{
  "type": "task_done",
  "task_id": "alarm_001",
  "dialog_id": "xxx",
  "message": "闹钟设好了，明天早上8点",
  "timestamp": 0
}

// 慢系统出错
{
  "type": "task_error",
  "task_id": "alarm_001",
  "dialog_id": "xxx",
  "message": "抱歉，闹钟设置失败了，可能需要授权日历权限",
  "timestamp": 0
}

// 心跳
{ "type": "heartbeat", "timestamp": 0 }
```

### 9.3 协议变更对比

| 旧协议 | 新协议 | 说明 |
|--------|--------|------|
| `dialog_state_changed` | **去掉** | 端侧不需要知道内部状态 |
| `responding_started` | **去掉** | 同上 |
| `request_accepted` | **去掉** | 快慢在云侧内部协调 |
| `audio` | 纳入 `turn` | audio + text + video_frame 在一条消息里 |
| 新增 `need_param` | 快慢追问统一格式 | 端侧只知道要追问 |
| 新增 `task_done` | 慢系统结果通知 | 端侧找间隙插入 |
| 新增 `task_error` | 慢系统错误通知 | 端侧播报错误 |

---

## 十一、Loop 架构对比与选型

### 10.1 Claude Code Loop（while + 状态机）

**核心结构：**

```typescript
// query.ts 核心逻辑
while (!shouldStop) {
  const response = await callLLM(messages);
  
  if (response.stop_reason === 'tool_use') {
    for (const toolUse of response.content) {
      const result = await executeTool(toolUse);
      messages.push(result);
    }
  } else {
    break; // 完成
  }
}
```

**优点：**
- ✅ **简单直观** — 代码逻辑清晰，易于理解和调试
- ✅ **同步控制** — 每一步都在主线程控制下，状态可预测
- ✅ **适合单任务** — 一次处理一个用户请求，顺序执行
- ✅ **错误处理简单** — try/catch 包裹整个 loop，统一处理

**缺点：**
- ❌ **阻塞式** — 一个 loop 跑完才能处理下一个请求
- ❌ **资源占用** — 即使空闲也要维持 loop 状态
- ❌ **并发差** — 多用户场景需要多个 loop 实例
- ❌ **不适合长任务** — 用户等待时间长（如订机票、发邮件）

---

### 10.2 OpenClaw Loop（事件驱动）

**核心结构：**

```python
# Gateway 收到消息 → 激活 agent
class Agent:
    async def on_message(self, msg):
        if msg.type == "user_input":
            await self.plan_and_execute(msg)
        elif msg.type == "tool_result":
            await self.continue_execution(msg)
        elif msg.type == "pause":
            self.save_checkpoint()
```

**优点：**
- ✅ **非阻塞** — 收到消息才激活，空闲时不占资源
- ✅ **天然并发** — 多个 agent 实例可以并行处理
- ✅ **适合长任务** — 可以暂停、恢复、后台执行
- ✅ **可扩展** — 容易加入新的事件类型（如定时任务、webhook）

**缺点：**
- ❌ **复杂度高** — 需要消息队列、状态持久化、checkpoint 机制
- ❌ **调试困难** — 异步执行，状态分散在多个地方
- ❌ **状态管理** — 需要显式保存/恢复状态，容易出错
- ❌ **过度设计风险** — 简单任务也要走完整事件流程

---

### 10.3 选型决策：混合方案

| 场景 | 选型 | 理由 |
|------|------|------|
| **快系统（Fast Agent）** | **Claude Code 风格** | 两轮规划，快速响应，不需要暂停/恢复 |
| **慢系统（Slow Agent）** | **OpenClaw 风格** | 长任务、后台执行、需要 checkpoint |

**对比矩阵：**

| 维度 | Claude Code | OpenClaw | 快系统选择 | 慢系统选择 |
|------|------------|---------|-----------|-----------|
| **简单性** | ✅ 更简单 | ❌ 更复杂 | Claude Code | - |
| **并发性** | ❌ 阻塞式 | ✅ 非阻塞 | - | OpenClaw |
| **长任务** | ❌ 不适合 | ✅ 适合 | - | OpenClaw |
| **调试性** | ✅ 易调试 | ❌ 难调试 | Claude Code | - |
| **资源占用** | ❌ 持续占用 | ✅ 按需激活 | - | OpenClaw |

---

### 10.4 混合实现示例

**快系统（同步 loop）：**

```python
class FastAgent:
    async def handle_turn(self, user_input):
        messages = [user_input]
        rounds = 0
        
        while rounds < 2:  # 最多两轮
            response = await self.llm.call(messages)
            
            if response.tool_calls:
                for tool in response.tool_calls:
                    if tool.name in ['text_search', 'image_search']:
                        result = await self.execute_tool(tool)
                        messages.append(result)
                        rounds += 1
                    else:
                        # 需要慢系统，handoff
                        await self.handoff_to_slow(tool, messages)
                        return
            else:
                return response.text
```

**慢系统（事件驱动）：**

```python
class SlowAgent:
    async def on_handoff(self, handoff_msg):
        task_id = handoff_msg.task_id
        
        # 规划
        plan = await self.plan(handoff_msg)
        
        # 逐步执行
        for step in plan:
            if step.type == "skill_call":
                result = await self.execute_skill(step)
            elif step.type == "python_exec":
                result = await self.python_executor.run(step.code)
            elif step.type == "user_input":
                # 暂停，等待用户输入
                self.save_checkpoint(task_id, step)
                await self.callbacks.ask_user(step.question)
                return  # 等待 on_resume
            
            self.update_checkpoint(task_id, step, result)
        
        # 完成
        await self.callbacks.on_event(
            task_id=task_id,
            event_kind="completed",
            result=result
        )
    
    async def on_resume(self, task_id, user_input):
        # 恢复执行
        checkpoint = self.load_checkpoint(task_id)
        # 继续执行...
```

---

## 十二、视频流输入与慢系统 Loop 类型

### 11.1 视频帧的两种使用模式

视频帧进入云侧后，根据任务类型有不同用法：

**Turn-bound（按需感知）**：用户主动提问 + 单帧图像
- 典型场景："这是什么花"、"帮我读一下这个"
- 架构：Fast Agent 的 `image_search` 工具直接调 Qwen VL
- 帧率：按需 1 帧

**Streaming（持续感知）**：摄像头持续推流，Agent 持续观察
- 典型场景：会议记录、修车指导
- 架构：Slow Agent 的 VL 模型作为 loop 观测反馈
- 帧率：按任务类型 1-5fps

两者路由由任务类型决定，不需要在帧层面做复杂路由。

### 11.2 Slow Agent 的 Loop 层级

Slow Agent 的 Loop 应按层级理解，而不是把所有 loop 名称放在同一层：

```
SlowLoop
  ├─ OneShotLoop
  │    - 一次性任务
  │    - 规划 -> 执行 -> 完成
  │
  └─ StreamingLoop
       - 持续接收外部信号
       - observe -> update state -> evaluate trigger -> act / wait
       - 可长期运行，可暂停恢复
       ├─ AccumulationLoop
       │    - 以累积和压缩状态为主
       │    - 例：MeetingMinutesLoop
       │
       ├─ MonitoringLoop
       │    - 以检测条件命中并触发事件为主
       │
       └─ GuidanceLoop
            - 主动指令 + 环境反馈闭环
            - 例：VisualGuidanceLoop
```

也就是说：

- `StreamingLoop` 是上位抽象
- `Accumulation / Monitoring / Guidance` 是三种基础 streaming primitive
- `VisualGuidanceLoop` 是 `GuidanceLoop` 的一个实现
- `MeetingMinutesLoop` 是 `AccumulationLoop` 的一个实现
- 复杂物理世界任务可以在同一生命周期内切换 loop mode，而不要求从开始到结束只属于一种 primitive

#### OneShotLoop（一次性任务）

```
Fast → Slow: handoff { task_id, goal }
  → Slow 执行（规划 → 工具调用 → 输出）
  → Slow → Fast: task_event { event_kind="completed", result }
```

- 例：设闹钟、搜天气、查日历

#### StreamingLoop（持续感知任务）

```
Fast → Slow: handoff { task_id, goal, loop_type="streaming" }
  → Slow 创建具体的 streaming loop 子类
  → 外部信号（视频帧 / transcript / timer）持续进入 loop
  → loop 根据任务类型进入 accumulation / monitoring / guidance mode
  → 主动发 TTS / 等待 / 结束
```

#### StreamingLoop 的三种基础 primitive

```
StreamingLoop
  ├─ AccumulationLoop
  │    - 主职责：持续累积信息，并维护越来越好的状态表示
  │    - 输入：ASR transcript / frame summary / timer
  │    - 输出：阶段性摘要 / 任务产物
  │    - 代表：MeetingMinutesLoop
  │
  ├─ MonitoringLoop
  │    - 主职责：持续判断是否命中条件，并在命中时触发事件
  │    - 输入：视频帧 / 音频事件 / 传感器状态 / timer
  │    - 输出：事件、告警、计数变化、即时通知
  │
  └─ GuidanceLoop
       - 主职责：系统发指令，环境反馈驱动下一步决策
       - 输入：视频帧 / 用户动作 / 环境状态
       - 输出：纠错 / 下一步指令 / 暂停让 Fast 接管
       - 代表：VisualGuidanceLoop
```

#### MeetingMinutesLoop（AccumulationLoop 示例）

```
MeetingMinutesLoop
  → 持续累积 ASR transcript
  → 定期抽取关键帧并生成 frame summary
  → 周期性压缩为结构化 notes
  → 用户触发“总结 / 导出”时聚合输出
```

它的特点是：

- 重点是“持续收集和压缩”
- 不主动指挥用户做动作
- 不依赖逐帧正确/错误反馈

#### MonitoringLoop 示例

```
MonitoringLoop
  → 持续读取视频帧/事件流
  → 判断是否命中预设条件
  → 命中后记录 event / 计数 / 触发提醒
  → 未命中则继续等待
```

典型场景：

- “帮我看看老板来过几次工位”
- “有人靠近设备就提醒我”
- “监控这个区域有没有异常”

它的特点是：

- 重点是“检测是否该触发”
- 每轮 loop 的关键不是压缩内容，而是判断是否要反应
- 可以只记事件不提醒，也可以即时提醒

### 11.3 VisualGuidanceLoop（GuidanceLoop）核心结构

**核心理念**：指令下发 + VL 模型作为 loop 的反馈传感器，形成主动闭环。

```
传统 Agent Loop（确定性反馈）：
  Agent → execute_tool() → 返回值 → Agent 决策

GuidanceLoop（环境反馈）：
  Agent → speak("拧开机油盖") → 用户执行动作
  → VL 模型 observe(frame) → 返回 {status, correctness}
  → Agent 决策下一步
```

```python
class VisualGuidanceLoop:
    """
    GuidanceLoop 的具体实现：视觉指导任务
    驱动源：VL 模型的观测反馈，不是 TTS 完成事件
    """
    
    async def run(self):
        """主 loop：Agent 决策 → 执行 → VL 观测反馈 → 循环"""
        
        while not self.done:
            # 1. Agent 决策下一步
            decision = await self.agent.decide(
                goal=self.goal,
                current_step=self.current_step,
                vl_history=self.vl_observations,
            )
            
            # 2. 执行决策（speak = TTS 工具）
            if decision.action == "speak":
                await self.tts.speak(decision.text)
            elif decision.action == "done":
                await self.tts.speak("任务完成")
                self.done = True
                break
            
            # 3. VL 模型持续观测，直到有确定性反馈
            while True:
                frame = await self.video_source.next_frame()
                observation = await self.vl_model.observe(
                    frame,
                    expected_state=decision.expected_state,
                )
                
                if observation.status == "completed":
                    # 动作完成，loop 前进
                    self.current_step += 1
                    self.vl_observations.append(observation)
                    break
                
                elif observation.status == "wrong":
                    # 动作出错，纠错
                    correction = await self.agent.generate_correction(
                        expected=decision.expected_state,
                        observed=observation,
                    )
                    await self.tts.speak(correction)
                    # 不前进，等待下一帧验证
                
                elif observation.status == "confused":
                    # 用户困惑，主动询问
                    await self.tts.speak("需要我再解释一下吗？")
                    # 触发 Fast Agent 接管点
                    await self._yield_to_fast()
```

**TTS 和 VL 观测是并行的**：TTS 发出去之后，Agent 不等播完就继续监听 VL 反馈，因为用户可能边听边动作。

### 11.4 VisionSensor 设计

`VisionSensor` 是 `MonitoringLoop / GuidanceLoop` 可复用的观测器，不是整个 `StreamingLoop` 的同义词。

**帧率策略**：云端 VL 调用成本高，采用降频监控。

| 方案 | 模型 | 调用频率 | 成本 | 适用场景 |
|------|------|---------|------|---------|
| 大 VL | Qwen-VL-Max | 每帧 | 高 | Turn-bound 精确感知 |
| 小 VL | InternVL3-2B / Qwen2-VL-2B | 每帧 | 中 | Streaming 持续监控 |
| 小 VL + 降频 | 同上 | 每 3-5 帧 | 低 | VisualGuidanceLoop |

```python
class VisionSensor:
    """VL 观测传感器，支持降频控制"""
    
    def __init__(self, model, frame_interval=3):
        self.model = model       # 小 VL 模型
        self.frame_interval = frame_interval
        self._frame_count = 0
    
    async def observe(self, frame, expected_state: str) -> Observation:
        self._frame_count += 1
        
        # 降频：每 N 帧分析一次
        if self._frame_count % self.frame_interval != 0:
            return Observation(status="skip")  # 不做分析
        
        return await self.model.analyze(
            image=frame,
            prompt=f"""
            当前任务目标: {expected_state}
            请判断:
            1. 用户是否完成当前动作? (completed / pending)
            2. 用户动作是否正确? (correct / wrong)
            3. 用户是否看起来困惑? (confused / normal)
            """
        )
```

### 11.5 Fast/Slow 协作机制

**协作原则**：
- Fast Agent 处理用户主动对话（turn-bound）
- Slow Loop 处理后台任务本身的执行
- 两者共享同一个 WebSocket 连接，共享同一个 session

**Fast → Slow 切换（handoff）**：

```python
class SlowAgent:
    async def on_handoff(self, msg: HandoffMessage):
        if msg.loop_type == "streaming":
            loop = self._create_streaming_loop(msg)
            self.active_loops[msg.task_id] = loop
            asyncio.create_task(loop.run())
        else:
            # One-shot 任务，正常执行
            ...
```

**Fast ← Slow 切换（yield）**：

当 `GuidanceLoop` 观测到 `status="confused"` 或用户主动说话时，Slow Loop 暂停：

```python
class VisualGuidanceLoop:
    async def _yield_to_fast(self):
        """VL 检测到用户困惑，暂停 loop，等待 Fast Agent 处理"""
        self.state = "paused"
        # 发信号给 Fast Agent
        await self.callbacks.notify_fast(
            task_id=self.task_id,
            reason="user_needs_assistance",
            context=self.vl_observations[-1]
        )
        # 等待 Fast 处理完恢复
        await self._wait_for_resume()

    async def _wait_for_resume(self):
        event = asyncio.Event()
        self._resume_events.append(event)
        await event.wait()
        self.state = "running"
```

Fast Agent 收到通知后，用户说话 → Fast 处理 → 恢复对应的 `GuidanceLoop`：

```python
# Fast Agent 侧
async def handle_turn(self, msg):
    result = await self.fast_loop.handle(msg)
    
    # 如果 session 有 paused 的 Slow Loop
    if self.session.has_paused_loop():
        paused_loop = self.session.get_paused_loop()
        # Fast 处理完用户请求
        # 恢复 Slow Loop
        paused_loop.resume()
    
    return result
```

**并发多任务**：用户可以同时运行多个 Slow Loop，每个 task_id 独立。

```python
class SlowAgent:
    active_loops: dict[str, StreamingLoop]

# 端侧消息带 task_id
# { "type": "video_frame", "task_id": "meeting_001", "data": "..." }
# → 路由到 SlowAgent.active_loops["meeting_001"].on_frame()
```

### 11.6 端侧摄像头模式

端侧根据任务类型切换摄像头工作模式：

```typescript
// HomePage.ets
type CameraMode = 'off' | 'on_demand' | 'continuous'

// turn-bound: 按需拍照
sendFrame(frame: ImageData) {
  this.wsClient.send({
    type: 'video_frame',
    task_id: null,
    mode: 'on_demand',
    data: base64(frame),
    timestamp: Date.now()
  })
}

// streaming: 持续推流（配合慢任务）
startCameraStream(taskId: string, fps: number = 2) {
  this.cameraMode = 'continuous'
  this.streamingTaskId = taskId
  setInterval(() => {
    const frame = this.captureFrame()
    this.wsClient.send({
      type: 'video_frame',
      task_id: taskId,
      mode: 'continuous',
      data: base64(frame),
      timestamp: Date.now()
    })
  }, 1000 / fps)
}
```

### 11.7 视频流的端云协调

**云侧发起视频流请求：**

```python
class SlowAgent:
    async def _start_video_stream(self, task_id: str, fps: int = 2):
        """通知端侧开始摄像头推流"""
        await self.callbacks.send_to_client({
            "type": "start_camera_stream",
            "task_id": task_id,
            "fps": fps
        })
    
    async def _stop_video_stream(self, task_id: str):
        """通知端侧停止摄像头推流"""
        await self.callbacks.send_to_client({
            "type": "stop_camera_stream",
            "task_id": task_id
        })
```

**视频帧路由逻辑：**

```python
class CloudWebSocketServer:
    """云侧 WebSocket 服务器"""
    
    async def on_video_frame(self, msg: dict):
        """收到端侧视频帧"""
        task_id = msg.get("task_id")
        frame = msg.get("data")
        
        if task_id and task_id in self.slow_agent.active_loops:
            # 有活跃的 Slow Loop 需要视频流
            await self.slow_agent.active_loops[task_id].on_frame(frame)
        elif task_id is None:
            # Turn-bound 模式，单帧感知
            # Fast Agent 处理
            result = await self.fast_agent.process_frame(frame)
            await self.send_tts(result)
        else:
            # task_id 不对应任何活跃 loop，丢弃
            pass
```

**视频流冲突处理：**

多个 Slow Loop 可能同时需要视频流，按优先级处理：

```python
class SlowAgent:
    def __init__(self):
        self.active_loops: dict[str, StreamingLoop] = {}
        self.video_stream_priority: dict[str, int] = {}
    
    def register_loop(self, task_id: str, loop: StreamingLoop, priority: int = 0):
        """注册时指定优先级（数字越大优先级越高）"""
        self.active_loops[task_id] = loop
        self.video_stream_priority[task_id] = priority
    
    async def route_frame(self, frame: bytes):
        """路由到最高优先级的 loop"""
        if not self.active_loops:
            return
        
        # 找到最高优先级
        best_task_id = max(
            self.video_stream_priority,
            key=lambda tid: self.video_stream_priority[tid]
        )
        
        # 只发给最高优先级的 loop
        await self.active_loops[best_task_id].on_frame(frame)
```

**帧丢失/延迟处理：**

```python
class VisionSensor:
    """VL 观测传感器，带帧处理控制"""
    
    def __init__(self, model, frame_interval=3, timeout_seconds=5):
        self.model = model
        self.frame_interval = frame_interval
        self.timeout_seconds = timeout_seconds
        self._last_frame_time = None
        self._last_observation = None
    
    async def observe(self, frame, expected_state: str, frame_timestamp: float) -> Observation:
        # 跳过非分析帧
        if not self._should_analyze():
            return Observation(status="skip")
        
        # 检查帧延迟
        if self._last_frame_time and (frame_timestamp - self._last_frame_time) > self.timeout_seconds:
            # 延迟超过阈值，可能是丢帧或网络问题
            self._last_observation = Observation(status="timeout")
            # 可选：通知 loop
            return Observation(status="timeout")
        
        self._last_frame_time = frame_timestamp
        self._last_observation = await self.model.analyze(frame, expected_state)
        return self._last_observation
```

### 11.8 Long-term Memory 的实际使用场景

**Fast Agent 读取 Long-term Memory：**

```python
class FastAgent:
    async def handle_turn(self, user_input: str):
        # 1. 检索相关记忆
        relevant = await self.memory.search(
            query=user_input,
            types=["user", "feedback", "project"],
            limit=5
        )
        
        # 2. 注入到 prompt
        context = "\n".join([
            f"【记忆: {m.type}】{m.content}"
            for m in relevant
        ])
        
        prompt = f"{self.system_prompt}\n\n相关记忆:\n{context}\n\n用户: {user_input}"
        
        # 3. LLM 调用
        response = await self.llm.call(prompt)
        ...
```

**Slow Agent 写入 Long-term Memory：**

```python
class SlowAgent:
    async def on_task_complete(self, task_id: str, result: dict):
        # 1. 提取值得记忆的内容
        if result.get("type") == "meeting_minutes":
            # 会议纪要 → 写入 project 记忆
            await self.memory.write("project", {
                "name": f"会议记录_{task_id}",
                "description": result.get("summary", "")[:100],
                "content": result.get("summary")
            })
        
        elif result.get("user_feedback"):
            # 用户确认 → 写入 feedback 记忆
            await self.memory.write("feedback", {
                "name": f"用户偏好_{task_id}",
                "description": result.get("user_feedback"),
                "content": result.get("user_feedback")
            })
        
        # 2. 更新任务状态
        await self.runtime_store.update_task(task_id, {
            "execution_state": "completed",
            "delivery_state": "pending_announce",
            "completed_at": datetime.now().isoformat(),
            "result": result
        })
```

**Long-term Memory 检索策略：**

```python
class MemorySystem:
    async def search(
        self,
        query: str,
        types: list[str] = None,
        limit: int = 5,
        threshold: float = 0.7
    ) -> list[Memory]:
        """检索相关记忆"""
        # 1. 如果有 embedding 模型，用向量检索
        if self.embedding_model:
            query_vec = await self.embedding_model.encode(query)
            candidates = await self._vector_search(query_vec, types, limit)
        
        # 2. 否则用关键词检索
        else:
            candidates = await self._keyword_search(query, types, limit)
        
        # 3. 过滤低相关度
        return [c for c in candidates if c.score >= threshold]
    
    async def _vector_search(self, query_vec, types, limit):
        """向量相似度搜索"""
        results = []
        for memory_file in self._list_memory_files(types):
            memory = self._load_memory(memory_file)
            # 简化：直接用标题相似度
            score = self._cosine_similarity(
                query_vec,
                await self.embedding_model.encode(memory.description)
            )
            results.append((score, memory))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
```

**Long-term Memory 过期和清理：**

```python
class MemorySystem:
    async def cleanup_stale(self, max_age_days: int = 90):
        """清理过期的记忆"""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        for memory_file in self._list_memory_files():
            m = self._load_memory(memory_file)
            if m.updated_at < cutoff:
                # 检查是否有最近的引用
                if not await self._is_referenced(memory_file):
                    # 无引用且过期，删除
                    self._delete_memory(memory_file)
    
    async def verify_before_use(self, memory: Memory) -> bool:
        """使用记忆前验证是否过时"""
        # 如果记忆内容和当前观察冲突，以观察为准
        current_state = await self._observe_current_state()
        
        if self._conflicts_with(memory, current_state):
            # 冲突，更新或删除记忆
            await self._update_memory(memory, current_state)
            return False  # 标记为过时
        
        return True  # 可用
```

---

## 十三、参考架构

### 13.1 Claude Code（Anthropic，主参考）

参考路径：`reference/claude-code/`

| 模块 | Claude Code | 本文借鉴 |
|------|------------|---------|
| Query / Runtime Core | `QueryEngine` 会话内执行态中枢 | `RuntimeFacade + FastRuntime + SlowRuntime + TaskRuntime` |
| Tool 接口 | `Tool.ts` buildTool() 工厂 | Skill Registry / Tool Registry 统一接口 |
| Tool Orchestration | 双向工具执行、审批、取消、流式结果 | `tool_call` 状态机与 execution control plane |
| Task 状态 | 任务执行态、权限、回调与恢复语义 | `task / checkpoint / task_event / tool_call` 模型 |
| Memory Layering | 运行态与长期记忆分层 | `Runtime Store + Long-term Memory` 双层设计 |
| Remote Session | session / control plane / 远程事件桥接 | `gateway + protocol + runtime facade` 边界 |

### 13.2 claw-code-main（Python 实现借鉴）

参考路径：`reference/claw-code-main/`

| 模块 | claw-code-main | 本文借鉴 |
|------|---------|---------|
| Session / Remote | Python 版 session、remote、workspace 组织 | `gateway / runtime_core / execution` 的工程边界 |
| 执行隔离 | Python 进程与执行器组织方式 | `execution` 层的 worker/runners 设计 |
| 工程化分层 | Python 包与模块拆分方式 | 多人协作时的 package 切分参考 |

### 13.3 cc-mini-main（Python 最小内核借鉴）

参考路径：`reference/cc-mini-main/`

| 模块 | cc-mini-main | 本文借鉴 |
|------|-------------|---------|
| Engine | `engine.py` tool loop + streaming API loop | Python 版 Fast/Slow 内核的最小事件循环参考 |
| Session | `session.py` 持久化与恢复 | session snapshot / resume 的实现参考 |
| Permission / Tools | `permissions.py`、`tools/` | tool approval 与执行器接口细节 |
| Coordinator | `coordinator.py` worker 协作模式 | 后续 slow execution / multi-worker 设计参考 |
