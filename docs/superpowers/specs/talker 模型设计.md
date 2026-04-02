# Talker 模块设计文档

**版本**：v2.12  
**日期**：2026-04-02  
**状态**：设计中  
**来源**：提取自 `2026-04-01-multiagent-architecture-design.md`

---

## 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| v1.0 | 2026-04-02 | 初始版本（提取自多模态架构设计） |
| v2.0 | 2026-04-02 | 重新定位 Talker 为云侧 Fast Agent，增加 LLM 调用分析 |
| v2.1 | 2026-04-02 | 重写第二章，聚焦 Talker 输入处理 |
| v2.2 | 2026-04-02 | 增加多会话管理、端侧 ASR/VAD、Streaming 推流 |
| v2.3 | 2026-04-02 | 明确 Slow 在云侧，增加并发锁、异常处理、dialog_id 校验 |
| v2.4 | 2026-04-02 | 第三章增加流式 TTS、seq 校验、异常处理 |
| v2.5 | 2026-04-02 | 增加长时任务处理机制、Task Registry 查询、进度通知 |
| v2.6 | 2026-04-02 | 第八/九章增加 WebSocket 消息详解、完整错误处理 |
| v2.7 | 2026-04-02 | 修复 5 个冲突：accepted 播报、VAD 降级、Task Registry 权限、interrupt_epoch、handoff_resume |

---

## 目录

1. [模块定位与职责](#一模块定位与职责)
2. [Talker 输入处理](#二 talker 输入处理)
3. [音频输出处理](#三音频输出处理)
4. [控制权管理](#四控制权管理)
5. [对话 Loop 设计](#五对话 loop 设计)
6. [Handoff 协议](#六 handoff 协议)
7. [Task Event 回调](#七 task-event 回调)
8. [WebSocket 消息格式](#八 websocket 消息格式)
9. [错误处理与降级](#九错误处理与降级)

---

## 一、模块定位与职责

### 1.1 Talker 在整体架构中的位置

```
端侧（HarmonyOS）
  ├─ AudioStreamService   → 音频采集推流（ASR + VAD）
  ├─ AudioPlaybackService → TTS 播放
  ├─ VideoStreamService   → 视频推流
  └─ WebSocketService     → 消息管道
          │
          │ WebSocket (turn / tts / control)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         云侧 Runtime                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TALKER (Fast Agent)                   │  │
│  │  - 实时对话 Loop（LLM 驱动）                             │  │
│  │  - 多会话管理（dialog_id 隔离）                          │  │
│  │  - 两轮规划限制                                          │  │
│  │  - Handoff 决策 (交给 Slow)                              │  │
│  │  - TTS 队列管理 (优先级调度)                             │  │
│  │  - 控制权管理 (speaker_owner / attention_owner)          │  │
│  │  - Long-term Memory 检索                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              │ handoff / task_event             │
│                              │ （云侧内部消息，不经过 WebSocket） │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    SLOW AGENT（云侧）                    │  │
│  │  - OneShotLoop (一次性任务)                              │  │
│  │  - StreamingLoop (持续感知任务)                          │  │
│  │  - Checkpoint 存储                                       │  │
│  │  - Long-term Memory 写入                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Shared Runtime Layer                        │  │
│  │  - Conversation State (控制权状态)                       │  │
│  │  - Task Registry (任务索引)                              │  │
│  │  - Checkpoint Store                                      │  │
│  │  - Memory Index (记忆索引)                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Talker 模块** 是云侧的 **实时对话 Agent**，负责：
- 接收端侧 `turn` 消息（音频/文本/视频帧）
- 调用 LLM 生成对话回复
- 管理 TTS 队列（优先级调度 + 多会话）
- 控制权管理（`speaker_owner` / `attention_owner`）
- Handoff 决策（复杂任务交给 Slow Agent）

### 1.2 与 Slow Agent 的关系（两者都在云侧）

| 组件 | 位置 | 职责 | 与 Talker 的交互 |
|------|------|------|-----------------|
| **Talker** | 云侧 | 实时对话响应（Fast Loop） | 接收 `turn`，调用 LLM，返回 TTS |
| **Slow Agent** | 云侧 | 后台复杂任务执行 | 接收 `handoff`，返回 `task_event` |
| **Shared Runtime** | 云侧 | 运行时状态存储 | Talker/Slow 共享 Conversation State、Task Registry |

**关键设计**：
- ✅ Talker = Fast Loop = 实时对话 Agent
- ✅ Talker 和 Slow **都在云侧**
- ✅ `handoff` 和 `task_event` 是**云侧内部消息**，不经过 WebSocket
- ✅ Talker 调用 LLM 进行对话规划和回复生成
- ✅ Slow Agent 不直接对话，通过 `task_event` 让 Talker 代为播报
- ✅ 只有 TTS 音频通过 WebSocket 发到端侧

**云侧内部通信：**
```python
# Talker → Slow（handoff）
await self.slow_inbox.send({
    "type": "handoff",
    "task_id": "alarm_001",
    "intent": "用户要设闹钟，8 点，明天",
    "payload": {"action": "set_alarm", "params": {...}}
})

# Slow → Talker（task_event）
await self.fast_callbacks.send({
    "type": "task_event",
    "task_id": "alarm_001",
    "event_kind": "completed",
    "message": "闹钟设好了，明天 8 点",
    "speak_policy": "queue"
})
```

### 1.3 核心职责边界

**Talker 负责：**
- ✅ **LLM 调用**：对话回复生成、工具调用规划、参数提取
- ✅ **对话 Loop**：接收 `turn` → LLM → TTS 输出
- ✅ **两轮规划**：最多 2 轮工具调用，超限 handoff
- ✅ **TTS 队列管理**：优先级调度（high/normal/low）+ 多会话
- ✅ **控制权管理**：`speaker_owner` / `attention_owner` 状态机
- ✅ **Handoff 决策**：复杂任务交给 Slow Agent
- ✅ **Task Event 处理**：Slow 任务完成，找间隙播报
- ✅ **Long-term Memory 检索**：注入用户偏好/历史到 Prompt
- ✅ **多会话管理**：`dialog_id` 隔离，并发处理

**Talker 不负责：**
- ❌ 音频采集（端侧 `AudioStreamService`）
- ❌ 音频播放（端侧 `AudioPlaybackService`）
- ❌ 视频流处理（端侧 `VideoStreamService`）
- ❌ 复杂任务执行（Slow Agent）
- ❌ Long-term Memory 写入（Slow Agent）
- ❌ Checkpoint 存储（Slow Agent）

### 1.4 LLM 调用点分析

| 调用点 | 频率 | 输入 | 输出 | 延迟要求 |
|--------|------|------|------|---------|
| **1. 对话回复生成** | 每轮对话必调 | 对话历史 + 用户输入 | 文本回复 或 tool_calls | <300ms（流式首字） |
| **2. 工具调用规划** | 与调用点 1 同时 | 对话历史 + 工具 manifest | tool_calls[] | 同上（同一 LLM 返回） |
| **3. 参数提取** | handoff 前参数收集 | 用户输入 + skill_schema | {param: value, ...} | <200ms |
| **4. 追问问题生成** | 参数收集时（可选） | 缺失参数 + 上下文 | 自然语言追问 | <200ms（可用模板优化） |

**典型对话流程：**
```
用户：帮我设个闹钟
  ↓
Talker LLM 调用 1：追问"你想设几点？"
  ↓
用户：8 点
  ↓
Talker LLM 调用 2：追问"是哪一天？"
  ↓
用户：明天
  ↓
Talker LLM 调用 3：handoff，回复"好的，正在帮你设置"
  ↓
Talker → Slow：handoff
  ↓
Slow 执行完成
  ↓
Talker 播报："闹钟设好了，明天早上 8 点"（无 LLM）
```

---

## 二、Talker 输入处理

### 2.1 输入消息类型

| type | 方向 | 说明 | Talker 处理 |
|------|------|------|------------|
| `turn` | 端→云 | 对话轮次（音频/文本/视频） | 累积，等 `stop_speech` 后处理 |
| `stop_speech` | 端→云 | 用户打断（VAD 检测后） | 停止 TTS，开始处理累积音频 |
| `request_to_speak` | 端→云 | 用户请求说话 | 暂停 TTS，等待输入 |
| `handoff_resume` | 端→云 | Slow 追问的回答 | 恢复 Slow 任务 |

**端侧职责（ASR + VAD）：**
- ✅ ASR：语音转文字（端侧优先）
- ✅ VAD：检测用户说完，发 `stop_speech`
- ✅ Streaming 推流：100ms 分片持续推

**VAD 降级方案：**
1. **端侧 VAD 优先**：端侧检测到静音 → 立即发 `stop_speech`
2. **云侧备用 VAD**：如果端侧超过 5 秒没发 `stop_speech`，云侧分析音频能量
3. **超时强制处理**：如果超过 10 秒还在推流，Talker 强制开始处理

---

### 2.1.1 多会话管理

**Talker 支持多个并发会话**，每个 `dialog_id` 独立状态：

```python
import asyncio

class Talker:
    def __init__(self):
        self.sessions = {}  # dialog_id → SessionState
    
    class SessionState:
        def __init__(self, dialog_id: str):
            self.dialog_id = dialog_id
            self.speaker_owner = "fast"      # user | fast | slow
            self.attention_owner = "fast"    # fast | slow
            self.audio_buffer = []           # 累积的音频分片
            self.vad_state = "silent"        # speaking | silent
            self.interrupt_epoch = 0         # 打断计数
            self.state = "waiting_user"      # waiting_user | responding | handoff_pending | collecting_params
            self.last_activity = time.time() # 最后活动时间
            self.lock = asyncio.Lock()       # 并发锁
            self.active_task_ids: list[str] = []  # 当前所有后台任务 ID（支持并发多任务）
            self.collecting: dict | None = None   # 参数收集上下文（state=collecting_params 时有值）
            self.history: list[dict] = []         # 对话历史（user/assistant 交替，_build_prompt 截取最近 20 轮）
            # collecting = {
            #   "skill": "set_alarm",
            #   "collected": {"time": "8点"},          # 已收集的参数
            #   "missing": [ParamSchema(...), ...]      # 还缺的参数列表（按顺序追问）
            # }
            
            # 会话上下文（明确定义字段）
            self.context = {
                "current_text": "",          # 当前累积的 ASR 文本
                "vision_frame": None,        # 视频帧（turn-bound 模式）
                "vision_mode": None,         # "turn-bound" | "streaming"
                "asr_source": "client",      # "client" | "cloud"
            }
```

**会话生命周期：**
1. **创建**：收到第一个 `turn` 消息时创建
2. **活跃**：用户持续交互
3. **过期**：超过 30 分钟无活动，自动清理

**消息路由（带并发锁）：**
```python
class Talker:
    async def on_message(self, msg: WebSocketMessage):
        dialog_id = msg.dialog_id
        
        # 获取或创建会话
        if dialog_id not in self.sessions:
            self.sessions[dialog_id] = SessionState(dialog_id)
        
        session = self.sessions[dialog_id]
        session.last_activity = time.time()
        
        # 路由到对应处理器（每个处理器内部有锁）
        if msg.type == "turn":
            await self.on_turn(session, msg)
        elif msg.type == "stop_speech":
            await self.on_stop_speech(session, msg)
        elif msg.type == "request_to_speak":
            await self.on_request_to_speak(session, msg)
        elif msg.type == "handoff_resume":
            await self.on_handoff_resume(session, msg)
```

---

### 2.2 `turn` 消息处理（Streaming 推流）

**消息格式：**
```json
{
  "type": "turn",
  "dialog_id": "dialog_001",
  "text": "帮我设个闹钟",           // 端侧 ASR 累积结果
  "audio": "base64...",              // 100ms 分片，原始音频
  "video_frame": "base64...",        // 可选，按需拍照
  "timestamp": 1743400000000
}
```

**端侧 Streaming 推流：**
```
用户说话 3 秒 → 端侧发送 30 个 turn 消息（每 100ms 一个）

t=0ms     → turn(dialog_id="001", audio=chunk_1, text="帮")
t=100ms   → turn(dialog_id="001", audio=chunk_2, text="帮我")
t=200ms   → turn(dialog_id="001", audio=chunk_3, text="帮我设")
...
t=2900ms  → turn(dialog_id="001", audio=chunk_30, text="帮我设个闹钟")
t=3000ms  → stop_speech(dialog_id="001")  ← VAD 检测完成
```

**Talker 累积处理（带并发锁 + dialog_id 校验）：**
```python
class Talker:
    async def on_turn(self, session: SessionState, msg: TurnMessage):
        # ========== 1. 校验 dialog_id ==========
        if session.dialog_id != msg.dialog_id:
            logger.warning(f"dialog_id mismatch: {session.dialog_id} != {msg.dialog_id}")
            return
        
        # ========== 2. 并发锁保护 ==========
        async with session.lock:
            # 3. 累积音频分片
            if msg.audio:
                session.audio_buffer.append(msg.audio)
            
            # 4. 更新 ASR 文本（端侧实时转录）
            if msg.text:
                session.context["current_text"] = msg.text
            
            # 5. 更新视频帧（如果有）
            if msg.video_frame:
                session.context["vision_frame"] = msg.video_frame
                session.context["vision_mode"] = "turn-bound"
            
            # 6. 等待 VAD 完成信号（stop_speech 触发后才处理）
```

**关键设计：**
1. **Streaming 累积**：100ms 分片持续累积
2. **端侧 ASR 实时转录**：`text` 字段是累积结果
3. **VAD 触发处理**：收到 `stop_speech` 才开始 LLM 调用
4. **并发锁**：`asyncio.Lock` 保护会话状态
5. **dialog_id 校验**：防止消息路由错误

---

### 2.2.1 `stop_speech` 触发处理（带异常处理）

```python
class Talker:
    async def on_stop_speech(self, session: SessionState, msg: StopSpeechMessage):
        try:
            # ========== 1. 校验 dialog_id ==========
            if session.dialog_id != msg.dialog_id:
                logger.warning(f"dialog_id mismatch: {session.dialog_id} != {msg.dialog_id}")
                return
            
            # ========== 2. 并发锁保护 ==========
            async with session.lock:
                # 3. 停止当前 TTS（如果正在播报）并清空队列中所有待播内容
                if session.state == "responding":
                    self.tts_generator.stop()
                self.tts_queue.clear_pending(dialog_id=session.dialog_id)
                
                # 4. 获取累积的用户输入
                user_input = session.context.get("current_text", "")
                if not user_input:
                    session.state = "waiting_user"
                    return
                
                # 5. 清理音频缓冲区和视频帧
                session.audio_buffer = []
                session.context["vision_frame"] = None
                session.context["vision_mode"] = None
                
                # 6. 参数收集状态机：如果正在追问参数，把用户回答填入，继续或 handoff
                if session.state == "collecting_params":
                    await self._handle_param_answer(session, user_input)
                    return
                
                # 7. 更新对话状态
                session.speaker_owner = "user"
                session.interrupt_epoch += 1
                
                # 8. 检索 Long-term Memory
                memories = await self.memory.search(query=user_input, limit=5)
                
                # 9. 构建 Prompt（注入记忆 + 对话历史 + 视频帧）
                prompt = self._build_prompt(
                    user_input, memories, session.context, session.history
                )
                
                # 10. 调用 LLM（流式输出）
                session.state = "responding"
                response = await self.llm.call(prompt, tools=self.manifest, stream=True)
                
                # 11. 追加到对话历史（供下轮使用）
                session.history.append({"role": "user", "content": user_input})
                session.history.append({"role": "assistant", "content": response.content})
                
                # 12. TTS 输出
                await self.speak(session, response, priority="normal")
                session.speaker_owner = "fast"
                session.state = "waiting_user"
        
        except LLMError as e:
            logger.error(f"LLM call failed: {e}")
            await self.speak(session, "抱歉，我现在有点问题，请稍后再试", priority="high")
            session.state = "waiting_user"
            session.audio_buffer = []
        
        except TTS Error as e:
            logger.error(f"TTS failed: {e}")
            session.state = "waiting_user"
        
        except Exception as e:
            logger.error(f"Unexpected error in on_stop_speech: {e}")
            session.state = "waiting_user"
            session.audio_buffer = []
```

**异常处理策略：**
| 异常类型 | 处理 | 用户感知 |
|---------|------|---------|
| `LLMError` | 播报错误消息，清空缓冲 | "抱歉，我现在有点问题" |
| `TTSError` | 记录日志，恢复状态 | 无播报，等待下一轮 |
| `Exception` | 记录日志，恢复状态 | 无播报，等待下一轮 |

---

### 2.3 云侧备用 VAD（降级方案）

> ⚠️ **TODO（TODO-015）**：云侧备用 VAD 暂不实现。Demo 阶段依赖端侧 VAD 发送 `stop_speech`，云侧不做兜底。后续如需支持端侧 VAD 失败降级，再实现此方案。

**背景（设计保留）：** 如果端侧 VAD 失败，用户说完后不发 `stop_speech`，云侧可通过音频静音检测兜底触发处理。待实现时参考以下策略：

| 方案 | 延迟 | 准确性 | 适用场景 |
|------|------|--------|---------|
| **端侧 VAD** | 低（~200ms） | 高 | 大多数场景（当前唯一实现） |
| **云侧备用 VAD** | 中（5 秒静音） | 中 | 端侧 VAD 失败降级（TODO） |
| **超时强制** | 高（10 秒） | 低 | 最后保障（TODO） |

---

### 2.4 多会话并发场景

**场景 1：用户同时发起多个对话**
```
用户：（会话 A）帮我查天气
  ↓
Talker 处理会话 A，session_A.state = "responding"
  ↓
用户：（会话 B）设个闹钟
  ↓
Talker 创建 session_B，独立处理
```

**场景 2：Slow 任务中，用户发起新对话**
```
Slow 任务进行中（session_A.attention_owner = "slow"）
  ↓
用户发起新对话（session_B）
  ↓
Talker 正常处理 session_B，不影响 session_A
```

**会话隔离：**
```python
# 每个会话独立状态
session_A.speaker_owner = "fast"
session_B.speaker_owner = "user"

# TTS 队列全局共享，按优先级调度
self.tts_queue.enqueue(text, source="fast", dialog_id="session_A")
self.tts_queue.enqueue(text, source="slow", dialog_id="session_B")
```

---

### 2.5 `stop_speech` 打断处理（带会话 ID）

**消息格式：**
```json
{
  "type": "stop_speech",
  "dialog_id": "dialog_001",
  "timestamp": 1743400000000
}
```

**Talker 处理：**
```python
class Talker:
    async def on_stop_speech(self, session: SessionState, msg: StopSpeechMessage):
        # 1. 停止当前 TTS（本会话）
        if session.state == "responding":
            self.tts_generator.stop()
        
        # 2. 清空 TTS 队列（本会话所有待播内容，high 优先级除外）
        self.tts_queue.clear_pending(dialog_id=session.dialog_id)
        
        # 3. 更新对话状态
        session.interrupt_epoch += 1
        session.speaker_owner = "user"
        
        # 4. 处理累积的音频
        if session.audio_buffer:
            await self._process_accumulated_audio(session)
        else:
            session.state = "waiting_user"
        
        # 5. 通知端侧确认
        await self.ws.send({
            "type": "stop_confirmed",
            "dialog_id": session.dialog_id
        })
```

**关键设计：**
- ✅ 打断路由到对应 `dialog_id` 会话
- ✅ 只清空该会话的低优先级消息
- ✅ `interrupt_epoch` 按会话独立计数

---

### 2.6 `request_to_speak` 请求说话（带会话 ID）

**消息格式：**
```json
{
  "type": "request_to_speak",
  "dialog_id": "dialog_001",
  "timestamp": 1743400000000
}
```

**Talker 处理：**
```python
class Talker:
    async def on_request_to_speak(self, session: SessionState, msg: RequestToSpeakMessage):
        await self.tts_queue.pause(dialog_id=session.dialog_id)
        session.speaker_owner = "user"
        session.state = "waiting_user"
```

**典型场景（Push-to-Talk）：**
```
用户按住说话按钮
    ↓
端侧：request_to_speak(dialog_id="001") → Talker
    ↓
Talker：暂停 session_001 的 TTS，speaker_owner=user
    ↓
端侧：开始推流（持续 turn 消息）
    ↓
用户松开按钮
    ↓
端侧：stop_speech(dialog_id="001") → Talker
    ↓
Talker：处理 session_001 累积音频，生成回复
```

---

### 2.7 `handoff_resume` 处理（带会话 ID）

**消息格式：**
```json
{
  "type": "handoff_resume",
  "task_id": "alarm_001",
  "dialog_id": "dialog_001",
  "text": "8 点，明天",
  "timestamp": 1743400000000
}
```

**Talker 处理：**
```python
class Talker:
    async def on_handoff_resume(self, session: SessionState, msg: HandoffResumeMessage):
        task = self.runtime_store.get_task(msg.task_id)
        if not task:
            return
        
        await self.slow_inbox.send({
            "type": "task_resume",
            "task_id": msg.task_id,
            "user_input": msg.text
        })
        
        session.attention_owner = "slow"
```

---

### 2.8 会话过期清理

**清理策略：**
```python
class Talker:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = 30 * 60  # 30 分钟无活动过期
    
    async def cleanup_expired_sessions(self):
        """定时清理过期会话（每 5 分钟执行一次）"""
        now = time.time()
        expired = []
        
        for dialog_id, session in self.sessions.items():
            if now - session.last_activity > self.session_timeout:
                expired.append(dialog_id)
        
        for dialog_id in expired:
            self.tts_queue.stop_session(dialog_id)
            del self.sessions[dialog_id]
            logger.info(f"Session expired: {dialog_id}")
```

**触发清理的时机：**
1. 定时清理（每 5 分钟）
2. 会话数超过阈值（如 1000 个）
3. 用户主动断开连接（WebSocket close）

---

### 2.9 时序图

**场景 1：Streaming 推流 → Talker 响应**
```
端侧                              Talker（云侧）
  │                                  │
  │─turn(text="帮", audio=chunk1)──>│ 累积音频和文本
  │─turn(text="帮我", audio=chunk2)>│ 更新 current_text
  │─turn(text="帮我设", audio=chunk3)>│ 继续累积
  │   ...                            │
  │─stop_speech(dialog_id="001")───>│ VAD 完成，开始处理
  │                                  │ 检索 Memory，调用 LLM
  │<─tts(audio 分片)─────────────────│ 流式 TTS 输出
```

**场景 2：多会话并发**
```
会话 A（查天气）会话 B（设闹钟）     Talker
      │              │                │
      │─turn───────>│                │ 创建 session_A
      │              │                │ 处理会话 A
      │              │─turn────────>│ 创建 session_B
      │              │                │ 处理会话 B（独立）
      │<─tts────────│                │ 播报会话 A
      │              │<─tts──────────│ 播报会话 B（找间隙）
```

**场景 3：用户打断（带会话 ID）**
```
端侧                              Talker（云侧）
  │                                  │
  │─turn(dialog_id="001")─────────>│ 处理会话 001，生成 TTS
  │<─tts────────────────────────────│ 开始播报
  │                                  │
  │─stop_speech(dialog_id="001")──>│ 停止会话 001 的 TTS
  │                                  │ 清空 001 的低优先级队列
  │<─stop_confirmed─────────────────│ 确认
  │                                  │
  │─turn(dialog_id="001")─────────>│ 处理新输入
  │<─tts────────────────────────────│ 生成回复
```

---

## 三、音频输出处理

### 3.1 云侧 TTS 队列（多会话支持 + 流式 TTS）

```python
class TTSQueue:
    def __init__(self, sessions: dict):
        self.queue = []  # [(priority, tts_item), ...]
        self.playing = {}  # dialog_id → tts_item
        self.is_playing = {}  # dialog_id → bool
        self.sessions = sessions  # 引用 Talker 的 sessions，用于状态校验
    
    def enqueue(self, text: str, source: str, priority: str = "normal", dialog_id: str = None):
        # ========== 1. 会话状态校验 ==========
        if dialog_id and dialog_id not in self.sessions:
            logger.warning(f"Session {dialog_id} not found, dropping TTS")
            return
        
        session = self.sessions.get(dialog_id)
        if session and getattr(session, 'state', None) == "expired":
            logger.warning(f"Session {dialog_id} expired, dropping TTS")
            return
        
        # ========== 2. 构建 TTS 任务 ==========
        item = {
            "text": text,
            "source": source,
            "priority": priority,
            "dialog_id": dialog_id,
            "generated_at": time.time()
        }
        
        # ========== 3. 按优先级插入队列 ==========
        inserted = False
        for i, (p, _) in enumerate(self.queue):
            if self._priority_value(priority) > self._priority_value(p):
                self.queue.insert(i, (priority, item))
                inserted = True
                break
        if not inserted:
            self.queue.append((priority, item))
        
        # ========== 4. 启动播放 ==========
        if not self.is_playing.get(dialog_id, False):
            asyncio.create_task(self._play_next(dialog_id))
    
    def _priority_value(self, p: str) -> int:
        return {"high": 3, "normal": 2, "low": 1}[p]
    
    async def _play_next(self, dialog_id: str):
        if not self.queue:
            self.is_playing[dialog_id] = False
            return
        
        # 找到下一个属于该会话或全局的消息
        for i, (p, item) in enumerate(self.queue):
            if item.get("dialog_id") == dialog_id or item.get("dialog_id") is None:
                self.queue.pop(i)
                self.is_playing[dialog_id] = True
                self.playing[dialog_id] = item
                
                try:
                    # ========== 5. 调用 TTS 服务（流式） ==========
                    audio_chunks = await self.tts_service.synthesize_streaming(
                        item["text"],
                        chunk_duration=200  # 每 200ms 一个分片
                    )
                    
                    # ========== 6. 流式分片发送 ==========
                    for seq, chunk in enumerate(audio_chunks):
                        # 检查会话是否还在播放
                        if not self.is_playing.get(dialog_id):
                            break
                        
                        await self.ws.send({
                            "type": "tts",
                            "dialog_id": dialog_id,
                            "data": base64Encode(chunk),
                            "seq": seq,
                            "is_end": (seq == len(audio_chunks) - 1)
                        })
                    
                    self.playing[dialog_id] = None
                    asyncio.create_task(self._play_next(dialog_id))
                    return
                
                except TTSError as e:
                    logger.error(f"TTS failed for dialog {dialog_id}: {e}")
                    # 跳过失败消息，继续播下一个
                    self.playing[dialog_id] = None
                    asyncio.create_task(self._play_next(dialog_id))
                    return
                
                except Exception as e:
                    logger.error(f"Unexpected TTS error for dialog {dialog_id}: {e}")
                    self.playing[dialog_id] = None
                    asyncio.create_task(self._play_next(dialog_id))
                    return
        
        self.is_playing[dialog_id] = False
    
    def clear_low_priority(self, dialog_id: str = None):
        """清空指定会话或全局的低优先级消息"""
        if dialog_id:
            self.queue = [(p, item) for p, item in self.queue 
                         if item.get("dialog_id") != dialog_id or p != "low"]
        else:
            self.queue = [(p, item) for p, item in self.queue if p != "low"]
    
    def clear_pending(self, dialog_id: str):
        """用户打断时调用：清空该会话队列中所有非 high 优先级的待播消息。
        high 优先级（如系统警告）保留，其余全部丢弃。"""
        self.queue = [(p, item) for p, item in self.queue
                      if item.get("dialog_id") != dialog_id or p == "high"]
    
    def stop_session(self, dialog_id: str):
        """会话过期或断开时调用，停止该会话的所有 TTS"""
        self.is_playing[dialog_id] = False
        self.playing.pop(dialog_id, None)
        # 清空该会话的队列
        self.queue = [(p, item) for p, item in self.queue if item.get("dialog_id") != dialog_id]
```

**关键设计：**
- ✅ TTS 队列在**云侧 Talker**
- ✅ 队列存储**文本**，播放时调用 TTS 服务
- ✅ **多会话支持**：每个 `dialog_id` 独立播放状态
- ✅ **流式 TTS**：200ms 分片发送，降低首字延迟
- ✅ **会话状态校验**：enqueue 前检查会话是否存在/过期
- ✅ **异常处理**：TTS 失败跳过当前消息，继续播下一个

---

### 3.2 优先级策略（多会话 + 流式 TTS）

| 优先级 | 来源 | 典型场景 | speak_policy | 会话范围 |
|--------|------|---------|-------------|---------|
| `high` | Talker | 用户打断后的响应、追问 | `interrupt` | 本会话 |
| `normal` | Talker | 普通问答、闲聊 | `queue` | 本会话 |
| `low` | Slow Agent | 后台任务完成通知 | `queue` / `silent` | 本会话 |

**流式 TTS 延迟优化：**
```
传统 TTS（一次性生成）：
  TTS 服务 → 生成完整音频（500ms） → 发送 → 端侧播放
  首字延迟：500ms+

流式 TTS（分片生成）：
  TTS 服务 → 生成 chunk_1（200ms） → 发送 → 端侧播放
            → 生成 chunk_2（200ms） → 发送 → 端侧继续播
  首字延迟：200ms
```

**多会话隔离：**
- 会话 A 的 `high` 优先级只打断会话 A 的 `low` 优先级
- 会话 B 不受会话 A 的影响

---

### 3.3 `speak_policy` 类型（多会话）

```python
class SpeakPolicy(Enum):
    INTERRUPT = "interrupt"  # 打断本会话的当前播放
    QUEUE     = "queue"      # 在本会话队列等待
    SILENT    = "silent"     # 不播报，仅更新 UI
```

| speak_policy | 消息类型 | 来源 | 行为 |
|-------------|---------|------|------|
| `interrupt` | Fast 实时回复 | Talker | 打断**本会话**任何播放 |
| `interrupt` | Slow `need_user_input` | Slow | 立即让 Talker 接管发问（本会话） |
| `queue` | Fast 普通回复 | Talker | 在**本会话**队列等待 |
| `queue` | Slow `task_completed` | Slow | 找**本会话**对话间隙播报 |
| `silent` | Slow `progress` | Slow | 仅更新 UI（不播报） |

---

### 3.4 端侧播放队列（多会话缓冲 + 异常处理）

```typescript
// AudioPlaybackService.ets（端侧）
class AudioPlaybackService {
  private queues = new Map<string, AudioChunk[]>()  // dialog_id → 队列
  private playing = new Map<string, boolean>()       // dialog_id → 播放状态
  private expectedSeq = new Map<string, number>()    // dialog_id → 期望的 seq
  
  enqueue(chunk: AudioChunk, dialog_id: string): void {
    if (!this.queues.has(dialog_id)) {
      this.queues.set(dialog_id, [])
      this.expectedSeq.set(dialog_id, 0)
    }
    this.queues.get(dialog_id)!.push(chunk)
    
    if (!this.playing.get(dialog_id)) {
      this.playNext(dialog_id)
    }
  }
  
  private async playNext(dialog_id: string): Promise<void> {
    const queue = this.queues.get(dialog_id)
    if (!queue || queue.length === 0) {
      this.playing.set(dialog_id, false)
      this.expectedSeq.set(dialog_id, 0)
      return
    }
    
    this.playing.set(dialog_id, true)
    const chunk = queue.shift()!
    
    try {
      await this.play(chunk, dialog_id)
      this.playNext(dialog_id)
    } catch (error) {
      console.error(`Playback failed for ${dialog_id}:`, error)
      // 跳过失败 chunk，继续播下一个
      this.playNext(dialog_id)
    }
  }
  
  private async play(chunk: AudioChunk, dialog_id: string): Promise<void> {
    try {
      // 1. 解码音频数据
      const audioData = base64Decode(chunk.data)
      
      // 2. 检查 seq 是否连续（可选，用于检测丢包）
      const expected = this.expectedSeq.get(dialog_id) || 0
      if (chunk.seq !== expected) {
        console.warn(`Seq mismatch for ${dialog_id}: expected ${expected}, got ${chunk.seq}`)
        // 不中断播放，继续
      }
      this.expectedSeq.set(dialog_id, expected + 1)
      
      // 3. 播放音频
      await this.audioPlayer.play(audioData)
      
      // 4. 如果是最后一个分片，重置状态
      if (chunk.is_end) {
        this.expectedSeq.set(dialog_id, 0)
      }
    
    } catch (error) {
      console.error(`Play failed for ${dialog_id}:`, error)
      throw error  // 向上抛出，由 playNext 处理
    }
  }
  
  stop(dialog_id: string): void {
    const queue = this.queues.get(dialog_id)
    if (queue) queue.length = 0
    this.playing.set(dialog_id, false)
    this.expectedSeq.set(dialog_id, 0)
  }
  
  pause(dialog_id: string): void {
    this.playing.set(dialog_id, false)
  }
  
  resume(dialog_id: string): void {
    if (!this.playing.get(dialog_id)) {
      this.playNext(dialog_id)
    }
  }
}
```

**关键设计：**
- ✅ **多会话隔离**：每个 `dialog_id` 独立队列和播放状态
- ✅ **异常处理**：播放失败跳过当前 chunk，继续播下一个
- ✅ **seq 校验**：检测丢包（可选，不中断播放）
- ✅ **is_end 重置**：最后一个分片重置 `expectedSeq`

---

### 3.5 云侧 TTS 队列 vs 端侧播放队列

| 维度 | 云侧 TTS 队列 | 端侧播放队列 |
|------|------------|-------------|
| **位置** | Talker（云侧） | AudioPlaybackService（端侧） |
| **存储内容** | 文本（待 TTS） | 音频分片（已 TTS） |
| **职责** | 优先级调度 + 多会话管理 + 流式 TTS | 缓冲 + 多会话播放 + seq 校验 |
| **隔离** | 按 `dialog_id` 隔离 | 按 `dialog_id` 隔离 |
| **异常处理** | TTS 失败跳过当前消息 | 播放失败跳过当前 chunk |
| **流式支持** | 200ms 分片发送 | 按 seq 顺序播放 |

---

### 3.6 流式 TTS 完整流程

```
云侧 TTS 队列                          端侧播放队列
     │                                      │
     │ 1. 调用 TTS 服务（流式）              │
     │    → 生成 chunk_1 (200ms)            │
     │                                      │
     │ 2. 发送 tts(seq=0, is_end=false)    │
     │──────────────────────────────────>  │ 3. 入队
     │                                      │
     │ 4. 生成 chunk_2 (200ms)              │
     │                                      │
     │ 5. 发送 tts(seq=1, is_end=false)    │
     │──────────────────────────────────>  │ 6. 入队
     │                                      │
     │ ...                                  │
     │                                      │
     │ 7. 生成 chunk_N (200ms)              │
     │                                      │
     │ 8. 发送 tts(seq=N-1, is_end=true)   │
     │──────────────────────────────────>  │ 9. 入队
     │                                      │
     │                                      │ 10. 播放 chunk_0
     │                                      │ 11. seq 校验 (0==0) ✓
     │                                      │ 12. 播放 chunk_1
     │                                      │ 13. seq 校验 (1==1) ✓
     │                                      │ ...
     │                                      │ 14. 播放 chunk_N-1
     │                                      │ 15. is_end=true → 重置 seq
```

**延迟优化：**
- **首字延迟**：200ms（第一个分片生成完成即可播放）
- **传统 TTS**：500ms+（需要等完整音频生成）
- **优化效果**：首字延迟降低 60%+

---

## 四、控制权管理

### 4.1 `speaker_owner` / `attention_owner` 机制

**双 Owner 设计目的：** 支持 Fast 对话和 Slow 后台任务并发

```python
class SessionState:
    speaker_owner = "fast"      # user | fast | slow（谁可以发 TTS）
    attention_owner = "fast"    # fast | slow（谁在后台执行）
    interrupt_epoch = 0         # 打断计数（检测过期消息）
```

#### `speaker_owner`（谁可以说话）

| 值 | 含义 | TTS 行为 |
|----|------|---------|
| `user` | 用户正在说话 | 暂停所有 TTS，等待用户说完 |
| `fast` | Talker 主导对话 | Talker 可以自由播报 |
| `slow` | Slow 需要追问 | Talker 代为播报 Slow 的追问 |

#### `attention_owner`（谁在后台执行）

| 值 | 含义 | 行为 |
|----|------|------|
| `fast` | 无后台任务 | Talker 正常对话 |
| `slow` | Slow 后台跑任务 | Talker 找间隙播报 Slow 消息 |

---

### 4.1.1 `interrupt_epoch` 详解

**用途：**
1. **检测过期消息**：如果收到 `turn` 消息的 `interrupt_epoch` 小于当前值，说明是旧消息，忽略
2. **并发冲突检测**：如果两个 `turn` 消息的 `interrupt_epoch` 相同，说明是并发消息，需要合并处理
3. **会话恢复**：断线重连后，`interrupt_epoch` 重置为 0

**递增时机：**
- `on_stop_speech`：用户打断时递增
- `on_turn`（第一个分片）：用户开始说话时递增

**重置时机：**
- 会话过期清理时
- 断线重连时

**示例代码：**
```python
class Talker:
    async def on_turn(self, session: SessionState, msg: TurnMessage):
        async with session.lock:
            # 检测过期消息
            if hasattr(msg, 'interrupt_epoch') and msg.interrupt_epoch < session.interrupt_epoch:
                logger.warning(f"Stale turn message (epoch {msg.interrupt_epoch} < {session.interrupt_epoch}), ignoring")
                return
            
            # 第一个分片，递增 interrupt_epoch
            if not session.audio_buffer:
                session.interrupt_epoch += 1
            
            # 累积音频分片
            if msg.audio:
                session.audio_buffer.append(msg.audio)
```

**状态机：**
```
初始：interrupt_epoch = 0
  ↓
用户说话（turn 分片 1）：interrupt_epoch = 1
  ↓
用户打断（stop_speech）：interrupt_epoch = 2
  ↓
用户说话（turn 分片 1）：interrupt_epoch = 3
  ↓
会话过期清理：interrupt_epoch = 0（重置）
```

#### 完整状态组合表

| speaker_owner | attention_owner | 场景 | TTS 行为 | 示例 |
|---------------|-----------------|------|---------|------|
| `fast` | `fast` | 日常对话 | Talker 自由播报 | 闲聊、问答 |
| `fast` | `slow` | Slow 后台跑任务 | Talker 自由播报，Slow 消息找间隙 | 设闹钟后继续问天气 |
| `user` | `fast` | 用户正在说话 | 暂停 TTS，等待用户 | 用户说话中 |
| `user` | `slow` | 用户打断 Slow 任务 | 停止 TTS，暂停 Slow | 用户打断设闹钟 |
| `slow` | `slow` | Slow 追问用户 | Talker 代为播报追问 | Slow 问"你想设几点？" |

---

### 4.2 控制权切换

```python
class Talker:
    async def on_turn(self, session: SessionState, msg: TurnMessage):
        # 第一个分片到来时标记用户正在说话
        if not session.audio_buffer:
            session.speaker_owner = "user"
            session.interrupt_epoch += 1
        
        # 累积音频和 ASR 文本（与第二章一致，等 stop_speech 再处理）
        if msg.audio:
            session.audio_buffer.append(msg.audio)
        if msg.text:
            session.context["current_text"] = msg.text
        if msg.video_frame:
            session.context["vision_frame"] = msg.video_frame
            session.context["vision_mode"] = "turn-bound"
    
    async def on_stop_speech(self, session: SessionState, msg: StopSpeechMessage):
        # 停止当前 TTS 并清空待播队列
        if session.state == "responding":
            self.tts_generator.stop()
        self.tts_queue.clear_pending(dialog_id=session.dialog_id)
        
        # 如果 Slow 在后台执行，暂停所有后台任务（用户开口说话时暂停）
        if session.attention_owner == "slow":
            for tid in session.active_task_ids:
                await self.slow_agent.pause_task(tid)
        
        # 处理累积的完整输入，生成回复
        user_input = session.context.get("current_text", "")
        if not user_input:
            session.state = "waiting_user"
            return
        
        session.state = "responding"
        response = await self.handle_turn(user_input)
        
        # 开始播报 → speaker_owner = fast
        session.speaker_owner = "fast"
        session.state = "waiting_user"
        session.audio_buffer = []
        session.context["vision_frame"] = None
        await self.speak(response)
    
    async def on_handoff(self, session: SessionState, task_id: str):
        # handoff 给 Slow
        await self.slow_inbox.send({"type": "handoff", "task_id": task_id})
        
        # Talker 继续对话，Slow 后台执行
        session.speaker_owner = "fast"           # Talker 可以说话
        session.attention_owner = "slow"         # Slow 在后台执行
        session.active_task_ids.append(task_id)  # 追加到任务列表（支持并发多任务）
    
    async def on_handoff_resume(self, session: SessionState, msg: HandoffResumeMessage):
        # 用户回答 Slow 的追问
        # attention_owner 保持 "slow"（因为 Slow 任务还在执行）
        session.speaker_owner = "fast"  # 恢复 Talker 主导
        
        # 转发给 Slow Agent
        await self.slow_inbox.send({
            "type": "task_resume",
            "task_id": msg.task_id,
            "user_input": msg.text
        })
    
    async def on_task_event(self, session: SessionState, event: TaskEvent):
        if event.event_kind == "need_user_input":
            # Slow 需要追问 → speaker_owner = slow
            session.speaker_owner = "slow"
            await self.speak(event.message, priority="high")
        
        elif event.event_kind == "completed":
            # Slow 任务完成 → 找间隙播报
            await self._find_gap_and_speak(event.message)
            session.active_task_ids = [t for t in session.active_task_ids if t != event.task_id]
            if not session.active_task_ids:
                session.attention_owner = "fast"  # 所有后台任务结束才恢复空闲
```

**状态切换说明：**
| 方法 | speaker_owner | attention_owner | 说明 |
|------|---------------|-----------------|------|
| `on_turn`（第一个分片） | → user | 不变 | 标记用户正在说话，累积音频 |
| `on_stop_speech` | user → fast | 不变（Slow 暂停但不结束） | VAD 完成，触发 LLM 处理，生成回复 |
| `on_handoff` | fast | fast → slow | Slow 开始后台执行 |
| `on_handoff_resume` | fast | **保持 slow** | 用户回答 Slow 追问，Slow 继续执行 |
| `on_task_event(completed)` | fast | slow → fast | Slow 任务完成，恢复空闲 |

---

### 4.3 长时任务处理机制

**长时任务定义：** 执行时间超过 30 秒的任务（如写脚本、分析邮件、生成报告）

#### 4.3.1 Task Registry（任务注册表）

**整体设计中的任务存储：**
```python
# Runtime Store 保存任务状态（执行真相源）
runtime_store.update_task(task_id, {
    "execution_state": "running",      # 任务执行状态
    "delivery_state": "silent",        # 通知状态
    "attention_owner": "slow",
    "current_step": "正在分析联系人...",  # 当前进度
    "progress_percent": 20,            # 进度百分比（可选）
    "created_at": "...",
    "updated_at": "...",
})
```

**读写权限表：**

| 字段 | Fast 读 | Fast 写 | Slow 读 | Slow 写 | 说明 |
|------|--------|--------|--------|--------|------|
| `execution_state` | ✅ | ❌ | ✅ | ✅ | 任务执行状态 |
| `delivery_state` | ✅ | ❌ | ✅ | ✅ | 通知状态 |
| `current_step` | ✅ | ❌ | ✅ | ✅ | 当前进度 |
| `progress_percent` | ✅ | ❌ | ✅ | ✅ | 进度百分比 |
| `created_at` | ✅ | ❌ | ✅ | ✅ | 创建时间 |
| `updated_at` | ✅ | ❌ | ✅ | ✅ | 更新时间 |
| `error` | ✅ | ❌ | ✅ | ✅ | 错误信息 |

**Fast 可写的会话状态（SessionState）：**
- `active_task_ids`：当前所有后台任务 ID 列表（支持并发多任务）
- `speaker_owner`：发言权所有者
- `attention_owner`：注意力所有者
- `state`：会话状态
- `interrupt_epoch`：打断计数

**设计原则：**
- ✅ Task Registry 是任务执行的**真相源**，由 Slow Agent 维护
- ✅ Fast Agent 只能读取 Task Registry，不能直接修改任务状态
- ✅ Fast Agent 通过 `task_event` 间接影响任务状态
- ✅ SessionState 是会话状态，由 Fast Agent 维护

**Fast 查询 Task Registry：**
```python
class Talker:
    async def on_task_status_query(self, session: SessionState, user_input: str):
        """用户主动查询任务进度"""
        if not session.active_task_ids:
            await self.speak("当前没有进行中的任务")
            return
        
        # 从 Task Registry 读取所有后台任务进度
        parts = []
        for task_id in session.active_task_ids:
            task = self.runtime_store.get_task(task_id)
            if task:
                step = task.get("current_step", "处理中")
                percent = task.get("progress_percent", 0)
                parts.append(f"{step}（{percent}%）")
        
        response = "、".join(parts) if parts else "任务进行中"
        await self.speak(response)
```

#### 4.3.2 进度更新（两种兼容方式）

**方式 1：Slow 定期写 Task Registry（推荐）**
```python
class SlowAgent:
    async def execute_long_task(self, task_id: str):
        progress_steps = [
            "正在读取邮件...",
            "正在分析联系人...",
            "正在分类统计...",
            "正在生成报告...",
        ]
        
        for i, step in enumerate(progress_steps):
            await self.execute_step(i)
            
            # 更新 Task Registry（执行真相源）
            self.runtime_store.update_task(task_id, {
                "execution_state": "running",
                "current_step": step,
                "progress_percent": (i + 1) * 25,
                "updated_at": time.time(),
            })
            
            # 可选：发送 task_event（用于 UI 实时更新）
            await self.send_task_event(
                task_id,
                "progress",
                step,
                speak_policy="silent"  # 默认不播报，仅更新 UI
            )
        
        # 任务完成
        await self.send_task_event(
            task_id,
            "completed",
            "报告生成好了，已发送到你的邮箱",
            speak_policy="queue"  # 找间隙播报
        )
```

**方式 2：用户主动查询**
```
用户：刚才那个任务怎么样了？
  ↓
Talker 查询 Task Registry
  ↓
Talker：还在处理中，正在分析联系人，大约还需要 2 分钟
```

#### 4.3.3 长时任务状态机

```
┌─────────────────────────────────────────────────────────────┐
│                      任务创建                                │
│              execution_state = "queued"                      │
│              delivery_state = "silent"                       │
│              session.attention_owner = "fast"                │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ handoff
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Slow 后台执行（长时任务）                        │
│              execution_state = "running"                     │
│              delivery_state = "silent"                       │
│              session.attention_owner = "slow"                │
│              session.speaker_owner = "fast"                  │
│                     （Talker 继续对话，不阻塞）                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 定期更新进度（每 30 秒）
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      进度更新                                │
│              current_step = "正在分析联系人..."               │
│              progress_percent = 50                           │
│              event_kind = "progress"                         │
│              speak_policy = "silent"  ← 仅更新 UI，不播报    │
│                     （用户无感知，UI 显示进度条）               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 用户主动查询（可选）
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      查询进度                                │
│              task = runtime_store.get_task(task_id)          │
│              response = f"任务进行中，{task.current_step}"   │
│                     （Talker 读取并播报）                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 任务完成
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      完成通知                                │
│              execution_state = "completed"                   │
│              event_kind = "completed"                        │
│              speak_policy = "queue"  ← 找间隙播报            │
│                     （播报"任务完成了"）                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 恢复空闲
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      恢复空闲                                │
│              session.attention_owner = "fast"                │
│              session.active_task_ids = []                    │
└─────────────────────────────────────────────────────────────┘
```

#### 4.3.4 超时处理

```python
class SlowAgent:
    async def execute_with_timeout(self, task_id: str, timeout_seconds: int = 300):
        try:
            # 设置超时（默认 5 分钟）
            await asyncio.wait_for(
                self._execute_task(task_id),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            # 超时，通知用户
            await self.send_task_event(
                task_id,
                "failed",
                f"任务执行超时（{timeout_seconds}秒），可能需要更长时间",
                speak_policy="interrupt"
            )
            
            # 提供选项
            await self.send_task_event(
                task_id,
                "need_user_input",
                "需要我继续执行吗？还是取消任务？",
                speak_policy="interrupt"
            )
```

#### 4.3.5 多任务并发

```
用户：（任务 A）帮我写个 Python 脚本分析邮件
  ↓
Slow 开始执行任务 A（长时任务）
session_A.attention_owner = "slow"
session_A.active_task_ids = ["task_A"]
  ↓
用户：（任务 B）帮我查下上海天气
  ↓
Talker 直接回复（任务 B 是 fast 任务）
session_B.speaker_owner = "fast"
  ↓
用户：（任务 A）刚才那个任务怎么样了？
  ↓
Talker 查询任务 A 的 Task Registry
Talker：还在处理中，正在分析联系人
  ↓
（任务 A 完成）
  ↓
Talker 找会话 A 的间隙播报
Talker：对了，邮件分析报告生成好了
session_A.active_task_ids = []   # 移除已完成任务
session_A.attention_owner = "fast"  # 列表为空才恢复空闲
```

**关键设计：**
- ✅ 每个任务独立 `task_id`
- ✅ 每个会话独立 `session` 和 `active_task_ids`（列表，支持并发）
- ✅ 长时任务不阻塞快任务
- ✅ 完成消息按 `dialog_id` 路由

---

## 五、对话 Loop 设计

### 5.1 Fast Agent 同步 Loop（两轮规划限制）

```python
class Talker:
    async def handle_turn(self, user_input: str):
        messages = [{"role": "user", "content": user_input}]
        rounds = 0
        
        while rounds < 2:
            response = await self.llm.call(messages, tools=self.manifest)
            
            if response.tool_calls:
                rounds += 1
                for tool in response.tool_calls:
                    if tool.name in self.fast_tools:
                        result = await self.execute_tool(tool)
                        messages.append({"role": "tool", "content": result})
                    else:
                        await self.handoff(tool, messages)
                        return None  # 不播报，等 Slow 的 accepted 事件确认
            else:
                return response.content
        
        await self.handoff_with_context(messages)
        return None  # 不播报，等 Slow 的 accepted 事件确认
```

---

### 5.2 LLM Prompt 模板

```python
FAST_AGENT_PROMPT = """
你是一个快速响应的语音助手，负责实时对话交互。

## 你的能力边界

你可以直接调用的工具（fast_tools）：
{fast_tools_json}

需要 handoff 给后台系统的工具（slow_tools）：
{slow_tools_json}

## 规则

1. **两轮规划限制**：最多 2 轮内部规划
2. **Handoff 决策**：需要 slow_tools 或超过 2 轮 → handoff
3. **参数收集**：can_ask_upfront 参数提前问
4. **过渡话术**：handoff 时给过渡回复
"""
```

---

### 5.3 `_build_prompt` 实现（记忆 + 上下文注入）

**设计原则（Demo 阶段）：**
- 对话历史：保留最近 20 轮，超出部分丢弃
- 长期记忆：检索 top-5，注入 system prompt 末尾，plain text 格式，预留 ~500 token
- 视频帧：有则附加到 user 消息的 image content（multimodal）

**Prompt 结构：**
```
[System]
  静态指令（角色 + 能力边界 + 规则）
  工具 manifest（fast_tools + slow_tools）
  ## 关于用户的记忆        ← top-5 retrieved memories
  - {memory_1}
  - {memory_2}
  ...

[History]
  最近 20 轮对话（超出丢弃）

[User]
  {user_input}            ← 纯文本，或含 image 的 multimodal content
```

```python
class Talker:
    MAX_HISTORY_TURNS = 20  # demo 阶段：保留最近 20 轮

    def _build_prompt(
        self,
        user_input: str,
        memories: list[str],
        context: dict,
        history: list[dict],
    ) -> list[dict]:
        # ── 1. System prompt ──────────────────────────────────────
        memory_block = ""
        if memories:
            items = "\n".join(f"- {m}" for m in memories)
            memory_block = f"\n\n## 关于用户的记忆\n{items}"
        
        system_content = FAST_AGENT_PROMPT.format(
            fast_tools_json=self.manifest.fast_tools_json(),
            slow_tools_json=self.manifest.slow_tools_json(),
        ) + memory_block

        messages = [{"role": "system", "content": system_content}]

        # ── 2. 对话历史（最近 20 轮，超出丢弃）────────────────────
        recent = history[-(self.MAX_HISTORY_TURNS * 2):]  # 每轮含 user+assistant 两条
        messages.extend(recent)

        # ── 3. 当前 user 消息（含视频帧时为 multimodal）───────────
        vision_frame = context.get("vision_frame")
        if vision_frame:
            user_content = [
                {"type": "image", "source": {"type": "base64", "data": vision_frame}},
                {"type": "text", "text": user_input},
            ]
        else:
            user_content = user_input

        messages.append({"role": "user", "content": user_content})
        return messages
```

**说明：**
- `history` 由 `SessionState` 维护，每次 LLM 返回后追加 assistant 消息
- Demo 阶段超出 20 轮直接丢弃；后续可升级为滚动摘要（MemGPT 风格）
- 记忆检索在 `on_stop_speech` 中已完成，`_build_prompt` 直接接收结果

---

## 六、Handoff 协议

### 6.1 Handoff 消息格式

```json
{
  "type": "handoff",
  "task_id": "alarm_001",
  "intent": "用户要设闹钟，8 点，明天",
  "payload": {"action": "set_alarm", "params": {"time": "08:00", "date": "明天"}},
  "conversation_snapshot": [...],
  "timestamp": "2026-04-01T10:00:00Z"
}
```

---

### 6.2 参数收集（can_ask_upfront）

```python
class Talker:
    async def collect_params(self, session: SessionState, skill_name: str, user_input: str):
        """参数收集入口：从用户输入中提取已有参数，开始状态机追问。"""
        skill_schema = self.manifest.get_slow_tool(skill_name)
        collected = await self.llm.extract_params(user_input, skill_schema)
        
        missing = [p for p in skill_schema.params
                   if p.can_ask_upfront and p.name not in collected]
        
        if not missing:
            # 参数齐全，直接 handoff
            await self.handoff(session, skill_name, collected)
            return
        
        # 进入参数收集状态机：记录上下文，问第一个问题
        session.state = "collecting_params"
        session.collecting = {
            "skill": skill_name,
            "collected": collected,
            "missing": missing,          # 剩余待问参数列表（按顺序）
        }
        await self.speak(session, missing[0].question_for_user, priority="normal")
    
    async def _handle_param_answer(self, session: SessionState, user_input: str):
        """on_stop_speech 在 collecting_params 状态时调用：推进参数收集状态机。"""
        ctx = session.collecting
        current_param = ctx["missing"][0]
        
        # 用 LLM 从用户回答中提取当前参数值（也可简单直接用原文）
        value = await self.llm.extract_single_param(user_input, current_param)
        ctx["collected"][current_param.name] = value
        ctx["missing"] = ctx["missing"][1:]  # 移除已收集的参数
        
        if ctx["missing"]:
            # 还有参数没问，继续追问下一个
            await self.speak(session, ctx["missing"][0].question_for_user, priority="normal")
        else:
            # 参数齐全，handoff
            session.state = "waiting_user"
            session.collecting = None
            await self.handoff(session, ctx["skill"], ctx["collected"])
```

**状态流转：**
```
collect_params() 调用
  → 有缺失参数 → session.state = "collecting_params"，问第一个问题
  ↓
用户回答（stop_speech）
  → on_stop_speech 检测到 collecting_params
  → _handle_param_answer：填入答案，移除已问参数
  → 还有缺失？继续问 → 否则 handoff，state = "waiting_user"
```

**用户打断时的处理：**
- 用户在参数收集中途打断（新的 `stop_speech`），会先清空 TTS 队列，然后进入 `_handle_param_answer`
- 如果用户说的不像参数答案（如"算了不用了"），LLM 提取失败时应跳出状态机，将 `session.state` 重置为 `"waiting_user"`，`session.collecting` 清空

---

## 七、Task Event 回调

### 7.1 task_event 格式

```json
{
  "type": "task_event",
  "task_id": "alarm_001",
  "event_kind": "completed",
  "message": "闹钟设好了，明天 8 点",
  "speak_policy": "queue"
}
```

| event_kind | speak_policy | 行为 | 说明 |
|-----------|-------------|------|------|
| `accepted` | `interrupt` | 立即播报 | **用户听到的唯一 handoff 确认**，Talker 侧 handoff 后不额外播报 |
| `started` | `silent` | 不播报 | 任务开始执行（内部状态） |
| `progress` | `silent` | 仅更新 UI | 进度更新（长时任务定期通知） |
| `need_user_input` | `interrupt` | 立即追问 | 需要用户补充参数 |
| `completed` | `queue` | 找间隙播报 | 任务完成 |
| `failed` | `interrupt` | 报错 | 任务执行失败 |
| `cancelled` | `silent` | 不播报 | 任务被用户取消 |
| `superseded` | `silent` | 不播报 | 任务被新任务替代 |

**说明：**
- `accepted` 是用户听到的**唯一** handoff 确认：Talker 在 `handle_turn` 里 handoff 后不播任何话，等 Slow 发回 `accepted` 再播。确认内容由 Slow 生成（如"好的，帮你设明天 8 点的闹钟"），比 Talker 的通用话术更准确，也避免用户听到两句重复确认
- `started` 使用 `silent`：内部状态，不播报（与 `accepted` 区分）

### 7.2 长时任务的 task_event

**长时任务（>30 秒）的事件流：**

```
用户：帮我写个 Python 脚本分析邮件
  ↓
Talker → Slow：handoff
  ↓
Slow → Talker：task_event(accepted, "好的，开始处理，这可能需要几分钟")
  ↓
Talker 播报："好的，开始处理，这可能需要几分钟"
session.attention_owner = "slow"
  ↓
（Slow 执行中，每 30 秒更新 Task Registry）
runtime_store.update_task(task_id, {
    "current_step": "正在读取邮件...",
    "progress_percent": 25
})
  ↓
（可选）Slow → Talker：task_event(progress, "正在读取邮件...", speak_policy="silent")
Talker 仅更新 UI，不播报
  ↓
（用户主动查询）
用户：任务怎么样了？
Talker 查询 Task Registry → "正在读取邮件...（25%）"
  ↓
（Slow 完成）
Slow → Talker：task_event(completed, "报告生成好了", speak_policy="queue")
Talker 找间隙播报
session.attention_owner = "fast"
```

### 7.3 Talker 处理 task_event

```python
class Talker:
    async def on_task_event(self, session: SessionState, event: TaskEvent):
        if event.event_kind == "accepted":
            # 长时任务开始，立即播报让用户知道
            await self.speak(event.message, priority="high")
        
        elif event.event_kind == "progress":
            # 进度更新，仅更新 UI，不播报
            await self.ui.update_task_progress(event.task_id, event.message)
        
        elif event.event_kind == "need_user_input":
            # 需要用户输入，立即追问
            session.speaker_owner = "slow"
            await self.speak(event.message, priority="high")
            session.state = "waiting_user"
        
        elif event.event_kind == "completed":
            # 任务完成，找间隙播报
            if session.speaker_owner == "user":
                # 用户正在说话，等用户说完
                await self._wait_for_user_to_finish()
            
            # 找对话间隙
            await self._find_gap_and_speak(event.message)
            
            # 移除已完成任务，列表为空才恢复空闲
            session.active_task_ids = [t for t in session.active_task_ids if t != event.task_id]
            if not session.active_task_ids:
                session.attention_owner = "fast"
        
        elif event.event_kind == "failed":
            # 任务失败，立即播报
            await self.speak(event.message, priority="high")
            session.active_task_ids = [t for t in session.active_task_ids if t != event.task_id]
            if not session.active_task_ids:
                session.attention_owner = "fast"
        
        elif event.event_kind == "cancelled":
            # 任务取消，不播报
            session.active_task_ids = [t for t in session.active_task_ids if t != event.task_id]
            if not session.active_task_ids:
                session.attention_owner = "fast"
```

---

## 八、WebSocket 消息格式

### 8.1 端侧 → 云侧

| type | 说明 | 示例 |
|------|------|------|
| `turn` | 对话轮次（audio/text/video） | `{"text": "帮我查天气", "audio": "base64..."}` |
| `stop_speech` | 打断（VAD 检测后） | `{"dialog_id": "001"}` |
| `request_to_speak` | 请求说话（Push-to-Talk） | `{"dialog_id": "001"}` |
| `handoff_resume` | Slow 追问回答 | `{"task_id": "alarm_001", "text": "8 点"}` |
| `task_status_query` | 用户查询任务进度 | `{"task_id": "task_001"}` |
| `task_cancel` | 用户取消长时任务 | `{"task_id": "task_001", "reason": "用户取消"}` |

### 8.2 云侧 → 端侧

| type | 说明 | 示例 |
|------|------|------|
| `tts` | TTS 音频分片 | `{"data": "base64...", "seq": 0, "is_end": false}` |
| `need_param` | 追问（Fast/Slow 通用） | `{"task_id": "alarm_001", "message": "你想设几点？"}` |
| `task_done` | Slow 完成（播报用） | `{"task_id": "alarm_001", "message": "闹钟设好了"}` |
| `task_error` | Slow 失败（播报用） | `{"task_id": "alarm_001", "message": "设置失败"}` |
| `task_progress` | 长时任务进度更新（UI 用） | `{"task_id": "task_001", "step": "正在分析...", "percent": 50}` |
| `task_accepted` | 任务已接受通知（UI 用） | `{"task_id": "task_001", "message": "开始处理"}` |
| `stop_confirmed` | 打断确认 | `{"dialog_id": "001"}` |

---

### 8.3 消息格式详解

#### 8.3.1 `turn`（对话轮次）

```json
{
  "type": "turn",
  "dialog_id": "dialog_001",
  "text": "帮我查天气",        // 端侧 ASR 累积结果
  "audio": "base64...",       // 100ms 分片，原始音频
  "video_frame": "base64...", // 可选，按需拍照
  "timestamp": 1743400000000
}
```

#### 8.3.2 `task_status_query`（任务进度查询）

```json
{
  "type": "task_status_query",
  "dialog_id": "dialog_001",
  "task_id": "task_001",      // 可选，默认查询所有 active_task_ids
  "timestamp": 1743400000000
}
```

**Talker 处理：**
```python
async def on_task_status_query(self, session: SessionState, msg: TaskStatusQueryMessage):
    task_ids = [msg.task_id] if msg.task_id else session.active_task_ids
    if not task_ids:
        await self.speak("当前没有进行中的任务")
        return
    
    parts = []
    for task_id in task_ids:
        task = self.runtime_store.get_task(task_id)
        if task:
            step = task.get("current_step", "处理中")
            percent = task.get("progress_percent", 0)
            parts.append(f"{step}（{percent}%）")
    
    response = "、".join(parts) if parts else "未找到该任务"
    await self.speak(response)
```

#### 8.3.3 `task_cancel`（任务取消）

```json
{
  "type": "task_cancel",
  "dialog_id": "dialog_001",
  "task_id": "task_001",
  "reason": "用户取消",
  "timestamp": 1743400000000
}
```

**Talker 处理：**
```python
async def on_task_cancel(self, session: SessionState, msg: TaskCancelMessage):
    task_ids = [msg.task_id] if msg.task_id else list(session.active_task_ids)
    if not task_ids:
        return
    
    # 通知 Slow 取消任务
    for task_id in task_ids:
        await self.slow_inbox.send({
            "type": "task_cancel",
            "task_id": task_id,
            "reason": msg.reason
        })
    
    # 更新会话状态
    session.active_task_ids = [t for t in session.active_task_ids if t not in task_ids]
    if not session.active_task_ids:
        session.attention_owner = "fast"
    
    # 播报确认
    await self.speak("好的，已取消任务", priority="high")
```

#### 8.3.4 `task_progress`（长时任务进度更新）

```json
{
  "type": "task_progress",
  "task_id": "task_001",
  "step": "正在分析联系人...",
  "percent": 50,
  "eta_seconds": 120,        // 预计剩余时间（可选）
  "timestamp": 1743400000000
}
```

**端侧处理：**
```typescript
// UI 更新进度条，不播报
function onTaskProgress(msg: TaskProgressMessage) {
  progressBar.value = msg.percent
  progressLabel.text = msg.step
  if (msg.eta_seconds) {
    etaLabel.text = `预计剩余 ${formatTime(msg.eta_seconds)}`
  }
}
```

#### 8.3.5 `task_accepted`（任务已接受通知）

```json
{
  "type": "task_accepted",
  "task_id": "task_001",
  "message": "好的，开始处理，这可能需要几分钟",
  "timestamp": 1743400000000
}
```

**端侧处理：**
```typescript
// UI 显示任务已开始，同时 TTS 播报
function onTaskAccepted(msg: TaskAcceptedMessage) {
  taskStatus.text = "处理中"
  // TTS 消息会同时到达，由 AudioPlaybackService 播放
}
```

---

### 8.4 消息路由规则

```python
class ProtocolRouter:
    async def route(self, msg: WebSocketMessage):
        # 1. 按 dialog_id 路由到对应 session
        session = self.get_or_create_session(msg.dialog_id)
        
        # 2. 按 type 路由到对应处理器
        if msg.type == "turn":
            await self.talker.on_turn(session, msg)
        elif msg.type == "stop_speech":
            await self.talker.on_stop_speech(session, msg)
        elif msg.type == "task_status_query":
            await self.talker.on_task_status_query(session, msg)
        elif msg.type == "task_cancel":
            await self.talker.on_task_cancel(session, msg)
        # ...
```

---

### 8.5 端侧消息处理

```typescript
// WebSocketService.ets
class WebSocketService {
  private messageHandlers = new Map<string, (msg: any) => void>()
  
  registerHandler(type: string, handler: (msg: any) => void): void {
    this.messageHandlers.set(type, handler)
  }
  
  onMessage(event: MessageEvent): void {
    const msg = JSON.parse(event.data)
    const handler = this.messageHandlers.get(msg.type)
    if (handler) {
      handler(msg)
    }
  }
}

// 注册处理器
wsService.registerHandler('tts', (msg) => audioPlayback.enqueue(msg, msg.dialog_id))
wsService.registerHandler('task_progress', (msg) => ui.updateProgressBar(msg))
wsService.registerHandler('task_accepted', (msg) => ui.showTaskStarted(msg))
wsService.registerHandler('task_done', (msg) => ui.showTaskCompleted(msg))
wsService.registerHandler('task_error', (msg) => ui.showTaskError(msg))
```

---

## 九、错误处理与降级

### 9.1 错误类型与降级策略

| 错误类型 | 降级策略 | 用户感知 |
|---------|---------|---------|
| **LLM 超时** | 回复"响应有点慢，请稍后再试" | 轻微延迟 |
| **LLM 限流** | handoff 给 Slow 异步处理 | 无感知，稍后通知 |
| **网络断线** | 自动重连 + 恢复会话状态 | 短暂中断 |
| **TTS 失败** | 跳过当前 chunk，继续播下一个 | 可能丢字 |
| **Task Registry 读取失败** | 回复"暂时无法查询任务状态" | 无法查询进度 |
| **Slow Agent 无响应** | 超时后通知用户，提供取消选项 | 任务可能卡住 |
| **长时任务超时** | 通知用户，询问是否继续 | 任务中断 |
| **会话过期清理失败** | 记录日志，下次清理时重试 | 无感知 |

---

### 9.2 LLM 错误处理

```python
class Talker:
    async def handle_turn(self, user_input: str):
        try:
            response = await self.llm.call(
                prompt=self._build_prompt(user_input),
                tools=self.manifest,
                timeout_seconds=30
            )
            return response.content
        
        except LLMTimeoutError as e:
            logger.error(f"LLM timeout: {e}")
            return "抱歉，我现在响应有点慢，请稍后再试"
        
        except LLMRateLimitError as e:
            logger.error(f"LLM rate limit: {e}")
            # 降级：handoff 给 Slow 异步处理
            await self.handoff_async(user_input)
            return "好的，我会帮你处理，稍后告诉你结果"
        
        except Exception as e:
            logger.error(f"Unexpected LLM error: {e}")
            return "出了一些问题，请稍后再试"
```

---

### 9.3 Task Registry 错误处理

```python
class Talker:
    async def on_task_status_query(self, session: SessionState, msg: TaskStatusQueryMessage):
        try:
            task_ids = [msg.task_id] if msg.task_id else session.active_task_ids
            if not task_ids:
                await self.speak("当前没有进行中的任务")
                return
            
            parts = []
            for task_id in task_ids:
                task = self.runtime_store.get_task(task_id)
                if task:
                    step = task.get("current_step", "处理中")
                    percent = task.get("progress_percent", 0)
                    parts.append(f"{step}（{percent}%）")
            
            response = "、".join(parts) if parts else "未找到该任务"
            await self.speak(response)
        
        except TaskRegistryError as e:
            logger.error(f"Task Registry read failed: {e}")
            await self.speak("抱歉，暂时无法查询任务状态，请稍后再试")
        
        except Exception as e:
            logger.error(f"Unexpected error in task_status_query: {e}")
            await self.speak("出了一些问题，请稍后再试")
```

---

### 9.4 Slow Agent 无响应处理

```python
class Talker:
    async def on_handoff(self, session: SessionState, task_id: str):
        # 发送 handoff
        sent = await self.slow_inbox.send({"type": "handoff", "task_id": task_id})
        if not sent:
            logger.error(f"Failed to send handoff for task {task_id}")
            await self.speak("抱歉，任务提交失败，请稍后再试")
            return
        
        # 启动超时检查（30 秒）
        asyncio.create_task(self._handoff_timeout_check(session, task_id, timeout=30))
    
    async def _handoff_timeout_check(self, session: SessionState, task_id: str, timeout: int):
        await asyncio.sleep(timeout)
        
        task = self.runtime_store.get_task(task_id)
        if task and task.get("execution_state") == "handoff_pending":
            # Slow 未确认，handoff 失败
            logger.error(f"Handoff timeout for task {task_id}")
            
            self.runtime_store.update_task(task_id, {
                "execution_state": "failed",
                "error": "Slow agent unresponsive"
            })
            
            await self.speak("抱歉，任务提交超时，请稍后再试", priority="high")
            session.active_task_ids = [t for t in session.active_task_ids if t != task_id]
            if not session.active_task_ids:
                session.attention_owner = "fast"
```

---

### 9.5 长时任务超时处理

```python
class SlowAgent:
    async def execute_with_timeout(self, task_id: str, timeout_seconds: int = 300):
        try:
            # 设置超时（默认 5 分钟）
            await asyncio.wait_for(
                self._execute_task(task_id),
                timeout=timeout_seconds
            )
        
        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timeout after {timeout_seconds}s")
            
            # 更新 Task Registry
            self.runtime_store.update_task(task_id, {
                "execution_state": "failed",
                "error": f"Timeout after {timeout_seconds}s"
            })
            
            # 通知用户
            await self.send_task_event(
                task_id,
                "failed",
                f"任务执行超时（{timeout_seconds}秒），可能需要更长时间",
                speak_policy="interrupt"
            )
            
            # 提供选项
            await self.send_task_event(
                task_id,
                "need_user_input",
                "需要我继续执行吗？还是取消任务？",
                speak_policy="interrupt"
            )
```

---

### 9.6 会话过期清理失败处理

```python
class Talker:
    async def cleanup_expired_sessions(self):
        """定时清理过期会话（每 5 分钟执行一次）"""
        try:
            now = time.time()
            expired = []
            
            for dialog_id, session in self.sessions.items():
                if now - session.last_activity > self.session_timeout:
                    expired.append(dialog_id)
            
            for dialog_id in expired:
                try:
                    # 停止该会话的 TTS
                    self.tts_queue.stop_session(dialog_id)
                    
                    # 清理会话状态
                    del self.sessions[dialog_id]
                    
                    logger.info(f"Session expired: {dialog_id}")
                
                except Exception as e:
                    logger.error(f"Failed to cleanup session {dialog_id}: {e}")
                    # 记录失败，下次清理时重试
        
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            # 不抛出，避免影响定时任务
```

---

### 9.7 网络断线重连

```python
class WebSocketClient:
    async def connect(self, url: str):
        while True:
            try:
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    await self._on_connected()
                    await self._receive_loop()
            
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                await asyncio.sleep(self.retry_interval)
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(self.retry_interval)
    
    async def _on_connected(self):
        """重连后的状态恢复"""
        # 1. 重置所有会话的对话状态
        for session in self.sessions.values():
            session.state = "waiting_user"
            session.active_task_ids = []         # 先清空，下面按 checkpoint 重建
            session.attention_owner = "fast"
        
        # 2. 检查是否有 running 的 Slow Tasks，恢复执行并重建会话关联
        running_tasks = await self.runtime_store.get_running_tasks()
        for task in running_tasks:
            await self.slow_agent.resume_from_checkpoint(task.task_id)
            
            # 恢复对应 session 的 active_task_ids 和 attention_owner
            dialog_id = task.get("dialog_id")
            if dialog_id and dialog_id in self.sessions:
                self.sessions[dialog_id].active_task_ids.append(task.task_id)
                self.sessions[dialog_id].attention_owner = "slow"
        
        # 3. 通知端侧重连成功
        await self.send({"type": "reconnected", "timestamp": time.time()})
```

---

### 9.8 错误处理最佳实践

1. **所有外部调用都加 `try/except`**
   - LLM 调用
   - TTS 服务
   - Task Registry 读写
   - WebSocket 发送

2. **记录日志但不泄露给用户**
   ```python
   logger.error(f"LLM timeout: {e}")  # 详细日志
   await self.speak("抱歉，请稍后再试")  # 用户友好提示
   ```

3. **提供恢复选项**
   - 长时任务超时 → 询问是否继续
   - 任务失败 → 提供重试选项
   - 网络断线 → 自动重连

4. **优雅降级**
   - LLM 限流 → handoff 给 Slow 异步
   - TTS 失败 → 跳过当前 chunk
   - Task Registry 失败 → 提示无法查询

5. **会话隔离**
   - 一个会话的错误不影响其他会话
   - 按 `dialog_id` 独立处理错误

---

## 十、TODO 与待办事项

### 10.1 已修复的冲突

| ID | 问题 | 修复方案 | 状态 |
|----|------|---------|------|
| TODO-001 | `accepted` 事件的 `speak_policy` | 7.1 表格改为 `interrupt`，增加说明 | ✅ 完成 |
| TODO-002 | VAD 检测位置和降级方案 | 2.1 增加降级说明，2.3 增加云侧备用 VAD | ✅ 完成 |
| TODO-003 | Task Registry 读写权限 | 4.3.1 增加读写权限表 | ✅ 完成 |
| TODO-004 | `interrupt_epoch` 用途说明 | 4.1.1 新增详细说明 | ✅ 完成 |
| TODO-005 | `handoff_resume` 状态切换 | 4.2 增加方法和状态表 | ✅ 完成 |

### 10.2 待补充的功能

| ID | 功能 | 说明 | 优先级 |
|----|------|------|--------|
| TODO-010 | 语音打断（Wake Word） | 用户说"等等"打断当前播报 | 🟡 中 |
| TODO-011 | 多模态融合 | 音频 + 视频 + 文本的融合处理策略 | 🟡 中 |
| TODO-012 | 端侧离线模式 | 无网络时的降级处理 | 🟢 低 |
| TODO-013 | TTS 语音切换 | 多说话人/多语言 TTS 支持 | 🟢 低 |
| TODO-014 | 会话恢复 | 断线后会话状态完整恢复 | 🟡 中 |
| TODO-015 | 云侧备用 VAD | 端侧 VAD 失败时云侧静音检测兜底（见 2.3 节） | 🟢 低 |
| TODO-016 | 对话历史升级 | Demo 阶段截断 20 轮，后续可改为滚动摘要（MemGPT 风格） | 🟢 低 |

### 10.3 待创建的配套文档

| ID | 文档 | 说明 |
|----|------|------|
| TODO-030 | 端侧 SDK 设计文档（HarmonyOS） | AudioStream/Playback/Video 服务 |
| TODO-031 | Slow Agent 设计文档 | OneShotLoop/StreamingLoop 实现 |
| TODO-032 | Task Registry API 文档 | 读写接口、权限定义 |
| TODO-033 | WebSocket 协议完整规范 | 所有消息类型的详细 schema |
| TODO-034 | 错误码定义文档 | 统一错误码和用户提示映射 |
| TODO-035 | Web 端 SDK 设计文档 | 浏览器端语音/视频接入（MediaRecorder、Web Audio API、WebSocket） |

---

_文档版本：v2.12 | 最后更新：2026-04-02_
