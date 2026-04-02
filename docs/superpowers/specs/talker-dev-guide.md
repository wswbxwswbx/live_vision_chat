# Talker 开发指南

**面向**：后端开发  
**版本**：v1.0 | 2026-04-02  
**详细设计**：[talker 模型设计.md](./talker%20模型设计.md)

---

## 一、架构图

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  端侧（HarmonyOS）                                                                │
│                                                                                   │
│  麦克风 → AudioStreamService                  AudioPlaybackService → 扬声器       │
│             ├─ VAD（端侧，静音检测）                  ↑ 按 dialog_id 分队列         │
│             ├─ ASR（端侧优先，实时转录）               │ 顺序播放 base64 音频         │
│             └─ 100ms 分片推流                         │                            │
│                                                       │                            │
│  摄像头 → VideoStreamService                          │                            │
│             └─ turn-bound: 随 turn 附帧               │                            │
│                                                       │                            │
│  WebSocketService ─────────────────────────────────── │ ──────────────────────┐   │
└────────────────────────────────│───────────────────────│──────────────────────────┘
                                 │ WebSocket              │
           ┌─────────────────────▼───────────────────────┴──────────────────────┐
           │  turn / stop_speech / request_to_speak     tts / need_param / ...  │
           │  handoff_resume / task_status_query                                 │
           └─────────────────────┬───────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────────────────┐
│  云侧 Runtime                                                                   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  TALKER (Fast Agent)                                                      │  │
│  │                                                                           │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  Protocol Router                                                     │ │  │
│  │  │  按 dialog_id 路由到 Session，按 type 路由到对应 handler             │ │  │
│  │  └────────────────────────────┬────────────────────────────────────────┘ │  │
│  │                               │                                           │  │
│  │  ┌────────────────────────────▼────────────────────────────────────────┐ │  │
│  │  │  Session Manager                                                     │ │  │
│  │  │  sessions: dict[dialog_id → SessionState]                           │ │  │
│  │  │  每个 session 独立锁（asyncio.Lock），30min 无活动自动清理           │ │  │
│  │  │                                                                      │ │  │
│  │  │  ┌──────────────────────────────────────────────────────────────┐   │ │  │
│  │  │  │  SessionState                                                 │   │ │  │
│  │  │  │  state: waiting_user │ responding │ collecting_params        │   │ │  │
│  │  │  │  speaker_owner: user │ fast │ slow                           │   │ │  │
│  │  │  │  attention_owner: fast │ slow                                │   │ │  │
│  │  │  │  audio_buffer[]  context{}  history[]  collecting{}          │   │ │  │
│  │  │  │  active_task_ids[]  interrupt_epoch                          │   │ │  │
│  │  │  └──────────────────────────────────────────────────────────────┘   │ │  │
│  │  └────────────────────────────┬────────────────────────────────────────┘ │  │
│  │                               │                                           │  │
│  │         ┌─────────────────────┼──────────────────────┐                   │  │
│  │         │                     │                       │                   │  │
│  │  ┌──────▼──────┐    ┌─────────▼──────────┐   ┌───────▼──────────────┐   │  │
│  │  │ on_turn     │    │ on_stop_speech      │   │ on_task_event        │   │  │
│  │  │             │    │ (核心处理入口)      │   │ (Slow 回调入口)      │   │  │
│  │  │ 累积音频    │    │  ├─collecting?      │   │  ├─accepted → speak  │   │  │
│  │  │ 更新 ASR 文本│   │  │  └─_handle_param│   │  ├─progress → UI更新 │   │  │
│  │  │ 首帧标记    │    │  └─否则:            │   │  ├─need_input→追问   │   │  │
│  │  │ speaker=user│    │    Memory检索       │   │  ├─completed→找间隙  │   │  │
│  │  └─────────────┘    │    build_prompt     │   │  └─failed→立即播报   │   │  │
│  │                     │    LLM调用(≤2轮)    │   └──────────────────────┘   │  │
│  │                     │    ├─fast_tool→执行 │                               │  │
│  │                     │    ├─slow_tool→     │                               │  │
│  │                     │    │  collect_params│                               │  │
│  │                     │    │  └─handoff     │                               │  │
│  │                     │    └─文本→TTS队列   │                               │  │
│  │                     └────────────────────┘                               │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  TTS Queue（云侧）                                                  │  │  │
│  │  │  优先级: high > normal > low    按 dialog_id 独立播放状态           │  │  │
│  │  │  流式 TTS: 200ms 分片 → WebSocket → 端侧 AudioPlaybackService      │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  LLM Engine                                                         │  │  │
│  │  │  build_prompt: system(指令+manifest+记忆) + history(近20轮) + user  │  │  │
│  │  │  handle_turn: 最多 2 轮工具调用，超出自动 handoff                   │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────┬─────────────────────────────────────┘  │
│                           handoff ↓ │ ↑ task_event（云侧内部，不过 WebSocket） │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  SLOW AGENT                                                             │  │
│  │  OneShotLoop / AccumulationLoop / MonitoringLoop / GuidanceLoop         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Shared Runtime                                                          │  │
│  │  Task Registry（Slow 写，Talker 只读）  Checkpoint Store  Memory Index  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据结构

### SessionState
```python
state: "waiting_user" | "responding" | "collecting_params"
speaker_owner: "user" | "fast" | "slow"   # 谁可以说话
attention_owner: "fast" | "slow"           # 谁在后台执行任务
history: list[dict]                        # 对话历史，最近 20 轮
active_task_ids: list[str]                 # 当前后台任务列表
collecting: dict | None                    # 参数收集上下文
interrupt_epoch: int                       # 打断计数，用于丢弃过期消息
```

→ 详见[第二章](./talker%20模型设计.md#二talker-输入处理)

### TTS 优先级

| 优先级 | 来源 | 典型场景 |
|--------|------|---------|
| `high` | 系统错误、Slow 追问 | 立即打断当前播放 |
| `normal` | Talker 普通回复 | 排队等待 |
| `low` | Slow 后台通知 | 找对话间隙 |

用户打断（`stop_speech`）时清空 `high` 以外的所有待播内容。

→ 详见[第三章](./talker%20模型设计.md#三音频输出处理)

---

## 三、主流程

### 3.1 正常对话
```
端侧 turn×N (100ms 分片)
  → Talker 累积 audio_buffer / current_text
端侧 stop_speech
  → 清空 TTS 队列
  → 检索 Memory（top-5）
  → build_prompt（system+记忆+history+user）
  → LLM 调用（≤2 轮工具）
  → TTS 队列 → 流式下发端侧
```

### 3.2 Handoff（复杂任务）
```
LLM 返回 slow_tool 调用
  → collect_params：从用户输入提取参数
    → 缺参数？state=collecting_params，逐轮追问（状态机）
  → 参数齐全 → handoff 发 Slow inbox
  → Talker 不播确认，等 Slow 的 accepted 事件
  → Slow accepted → Talker 立即播报（interrupt）
```

→ 详见[第五章](./talker%20模型设计.md#五对话-loop-设计)、[第六章](./talker%20模型设计.md#六handoff-协议)

### 3.3 Task Event（Slow 回调）
| event_kind | speak_policy | Talker 行为 |
|-----------|-------------|------------|
| `accepted` | interrupt | 立即播报（唯一确认语） |
| `progress` | silent | 只更新 UI |
| `need_user_input` | interrupt | 立即追问，state=collecting_params |
| `completed` | queue | 找对话间隙播报 |
| `failed` | interrupt | 立即报错 |

→ 详见[第七章](./talker%20模型设计.md#七task-event-回调)

---

## 四、WebSocket 消息速查

### 端侧 → 云侧
| type | 说明 |
|------|------|
| `turn` | `{dialog_id, text, audio(base64), video_frame?, timestamp}` |
| `stop_speech` | `{dialog_id}` —— VAD 检测到用户说完 |
| `request_to_speak` | `{dialog_id}` —— Push-to-Talk 按下 |
| `handoff_resume` | `{dialog_id, task_id, text}` —— 回答 Slow 追问 |
| `task_status_query` | `{dialog_id, task_id?}` |
| `task_cancel` | `{dialog_id, task_id?, reason}` |

### 云侧 → 端侧
| type | 说明 |
|------|------|
| `tts` | `{dialog_id, data(base64), seq, is_end}` |
| `need_param` | `{task_id, message}` —— 追问参数 |
| `task_accepted` | `{task_id, message}` |
| `task_progress` | `{task_id, step, percent, eta_seconds?}` |
| `task_done` | `{task_id, message}` |
| `task_error` | `{task_id, message}` |
| `stop_confirmed` | `{dialog_id}` |

→ 详见[第八章](./talker%20模型设计.md#八websocket-消息格式)

---

## 五、错误处理原则

| 场景 | 处理 |
|------|------|
| LLM 超时 | 播报"响应有点慢"，恢复 waiting_user |
| LLM 限流 | 降级为 handoff 异步处理 |
| TTS 失败 | 跳过当前 chunk，继续下一个 |
| Slow 无响应 | 30s 超时后通知用户，清理任务 |
| 会话错误 | 按 dialog_id 隔离，不影响其他会话 |

→ 详见[第九章](./talker%20模型设计.md#九错误处理与降级)

---

## 六、暂不实现（TODO）

| ID | 内容 |
|----|------|
| TODO-015 | 云侧备用 VAD（Demo 阶段端侧 VAD 失败不兜底） |
| TODO-016 | 对话历史滚动摘要（Demo 截断 20 轮） |
| TODO-035 | Web 端 SDK（浏览器语音/视频接入） |
