# Talker Use Case 库

**日期**：2026-04-02  
**用途**：梳理需要考虑的交互场景，明确哪些要实现、哪些架构需兼容、哪些不做

---

## Case 一览

| # | 场景 | 分类 | 难度 | 重要程度 |
|---|------|------|------|---------|
| C01 | 闲聊问"这个人演过什么电影"，Fast 两轮回复 | | ★★ | ★★★★★ |
| C02 | 用户询问任务进度，Fast 直接回复 | | ★★ | ★★★★ |
| C03 | Slow 定期上报进度，Talker 找间隙播报 | | ★★ | ★★★ |
| C04 | 多轮对话，询问其他对话中的任务情况 | | ★★ | ★★★ |
| C05 | 看到眼前物体，问"这是什么" / "这能吃吗" | | ★★ | ★★★★★ |
| C06 | 看到外文（菜单/路牌），实时翻译 | | ★★ | ★★★★★ |
| C07 | 拍下当前画面并备注，随时可查 | | ★★ | ★★★★ |
| C08 | 看着菜单/购物车，算总价或比较哪个更划算 | | ★★ | ★★★★ |
| C09 | 设置闹钟，追问参数直到 handoff 完成 | | ★★★ | ★★★★★ |
| C10 | 紧急求助，"帮我打 120 / 报警" | | ★★★ | ★★★★★ |
| C11 | 任务进行中，用户说"顺便问一下…"，不中断任务的同时回复 | | ★★★ | ★★★★ |
| C12 | 监控画面，出现 XX 时提醒用户 | | ★★★★ | ★★★★ |
| C13 | 记录整个会议的 PPT，监控屏幕变化，Slow 做信息汇总 | | ★★★★ | ★★★ |
| C14 | "下次我见到张三，提醒我还他钱" | | ★★★★★ | ★★★ |
| C15 | 任务进行中，用户打断追加信息，暂停后重启执行 | | ★★★★★ | ★★★ |

---

## Case 详情

### C01 · 闲聊问答

**用户行为**：问"XX 演过什么电影"  
**期望结果**：Fast 直接 LLM 回复，不涉及 Slow

**Talker 处理链路**：
```
stop_speech → LLM（≤2 轮）→ 文本回复 → TTS 队列 → 端侧播放
```

**关键点**：LLM 不返回任何 tool call，纯文本路径；`attention_owner` 保持 `fast`。

**对应实现**：Phase 3（LLM Engine 基础路径）

---

### C02 · 用户主动查询任务进度

**用户行为**：说"我的闹钟设好了吗"/"刚才那个任务进行到哪了"  
**期望结果**：Fast 查 Task Registry 后直接回复，无需转 Slow

**Talker 处理链路**：
```
stop_speech → LLM 识别意图为 task_status_query
  → fast_tool: query_task_registry(task_id?) → 返回状态文本
  → TTS 播报
```

**关键点**：LLM 通过 manifest 中的 fast tool 调用 Task Registry，结果直接拼入第二轮 LLM 生成自然语言回复。Task Registry 是全局共享结构，无需按 dialog 过滤。

**对应实现**：Phase 3（fast tool 机制）+ Task Registry stub

---

### C03 · Slow 定期上报进度

**触发方**：Slow Agent 主动推送  
**期望结果**：Talker 找到对话间隙后播报进度，不打断用户说话

**Talker 处理链路**：
```
task_event(progress) → on_task_event → speak_policy=queue
  → 加入 TTS 队列（low 优先级）
  → _find_gap_and_speak：speaker_owner ≠ user 时播报
```

**关键点**：`progress` 事件不强制打断，用低优先级排队；如果用户正在说话则等待。

**对应实现**：Phase 4（on_task_event 完整实现）

---

### C04 · 跨对话查任务

**用户行为**：在新对话中问"我之前让你做的那个事情做完了吗"  
**期望结果**：Fast 能查到其他 dialog_id 下的任务状态并回复

**Talker 处理链路**：
```
stop_speech → LLM 识别意图为 task_status_query（无特定 task_id）
  → fast_tool: query_task_registry() → 返回所有活跃任务列表
  → LLM 生成自然语言回复
```

**关键点**：
- 本项目为**单用户**（眼镜设备），Task Registry 是全局单例，无需按 user_id 过滤
- 跨 dialog 查询开箱即用，无需修改 Session 结构
- LLM 需根据任务描述推断用户意图指的是哪个任务

**对应实现**：Phase 3 fast tool + Task Registry 全局查询接口

---

### C05 · 眼前物体识别

**用户行为**：看着一株植物/一瓶药/一道菜问"这是什么"/"这个能吃吗"  
**期望结果**：Fast 直接用当前帧回答，无需 Slow

**Talker 处理链路**：
```
stop_speech（turn 消息已携带 video_frame）
  → build_prompt 时 video_frame 作为 multimodal 内容传入 LLM
  → LLM 直接识别并回答
  → TTS 播报
```

**关键点**：`video_frame` 来自最近一帧 turn 消息，`_build_prompt` 已支持 multimodal，此 case 无新增实现。

**对应实现**：Phase 3（已含 vision 路径）

---

### C06 · 实时翻译

**用户行为**：看着外文菜单/路牌说"这写的什么"/"翻译一下"  
**期望结果**：Fast 识别画面中的文字并翻译，直接播报

**Talker 处理链路**：
```
stop_speech（携带 video_frame）
  → LLM multimodal：OCR + 翻译合并一次调用
  → TTS 播报译文
```

**关键点**：与 C05 同路径，无需额外工具；LLM prompt 需引导模型同时做 OCR 和翻译。

**对应实现**：Phase 3

---

### C07 · 拍下画面并备注

**用户行为**：看着白板/名片/收据说"帮我记一下"  
**期望结果**：截取当前帧，附上 ASR 文字或 LLM 提取的摘要，存入记忆/笔记

**Talker 处理链路**：
```
stop_speech（携带 video_frame）
  → LLM 识别画面内容，生成摘要
  → fast_tool: save_note(image, summary) → 写入 MemoryIndex / RuntimeStore
  → TTS 确认"已记录"
```

**关键点**：需要 fast tool `save_note`；MemoryIndex 接口需支持图片或图片摘要存储。

**对应实现**：Phase 3 fast tool + MemoryIndex 扩展

---

### C08 · 视觉辅助计算

**用户行为**：看着菜单/价格标签说"这几样加起来多少钱"/"哪个更划算"  
**期望结果**：Fast 识别价格数字，完成计算后播报结果

**Talker 处理链路**：
```
stop_speech（携带 video_frame）
  → LLM multimodal：提取价格 + 计算
  → TTS 播报结果
```

**关键点**：纯 LLM multimodal 路径，无 tool call；LLM 需在 prompt 中被引导先提取数字再计算。

**对应实现**：Phase 3

---

### C09 · 设置闹钟

**用户行为**：说"给我设置一个闹钟"  
**期望结果**：Talker 逐步追问缺失参数（时间、内容），参数齐全后 handoff 给 Slow，Slow 执行并确认

**Talker 处理链路**：
```
stop_speech → LLM 识别 slow_tool → collect_params
  → 缺参数：state=collecting_params，TTS 追问
  → 每轮 stop_speech：_handle_param_answer 补全参数
  → 参数齐全：handoff → SlowInbox
  → 等待 Slow accepted 事件 → TTS 播报确认
```

**关键点**：追问轮次无上限，直到参数齐全或用户主动取消；Talker 在 handoff 后不播任何确认，唯一确认来自 Slow 的 `accepted` 事件。

**对应实现**：Phase 4（collect_params 状态机 + handoff）

---

### C10 · 紧急求助

**用户行为**：说"帮我打 120"/"快报警"  
**期望结果**：立即触发紧急呼叫，不追问参数，Talker 即时播报"正在拨打"

**Talker 处理链路**：
```
stop_speech → LLM 识别 slow_tool(emergency_call)
  → 无需 collect_params（紧急场景不追问）
  → 立即 handoff，priority=urgent
  → TTS 高优先级立即播报"正在为您拨打 120"
  → Slow 执行拨号，accepted 后播报确认
```

**关键点**：唯一不走 collect_params 的 slow_tool；handoff 前即播报（先安抚用户），不等 `accepted`。这是"handoff 后不播确认"规则的唯一例外，需在设计文档中明确标注。

**对应实现**：Phase 4，需在 handoff 设计中增加 `urgent` 标记

---

### C11 · BTW 闲聊，不中断后台任务

**用户行为**：Slow 任务运行中，用户说"顺便问一下，今天天气怎么样"  
**期望结果**：Fast 正常回复天气，Slow 任务不受影响继续运行

**Talker 处理链路**：
```
stop_speech（attention_owner=slow，active_task_ids 非空）
  → LLM 意图识别：casual / btw（无 tool call，不涉及任务）
  → 直接走普通回复路径（TTS normal 优先级）
  → attention_owner 保持 slow，active_task_ids 不变
```

**架构兼容要点**：
- `on_stop_speech` 需增加分支：`attention_owner=slow` 时不自动进入任务流程，先做意图识别
- LLM manifest 需有明确提示：当用户明显是 casual 问题时，不返回 task-related tool
- 边界情况：用户 btw 说了和任务相关的补充信息 → 归入 C15 流程

---

### C12 · 画面监控触发提醒

**用户行为**：说"如果摄像头里出现 XX，立刻提醒我"  
**期望结果**：Slow 持续监控视频流，检测到目标后主动触发通知

**Talker 处理链路**：
```
stop_speech → LLM 识别 slow_tool(monitor) → collect_params → handoff
  → attention_owner = slow，Talker 进入等待
  → Slow 持续运行（MonitoringLoop）
  → 检测到目标 → task_event(completed/progress) → Talker 立即播报
```

**架构兼容要点**：
- Talker 侧只需处理 `task_event` 回调，无特殊改动
- Slow 侧需实现 MonitoringLoop：持续拉视频帧，按条件触发 task_event
- 视频帧由端侧随 `turn` 消息发送，Slow 需能获取最新帧（通过 Shared Runtime 中转或 Talker 转发，待设计）

---

### C13 · 会议记录 PPT

**用户行为**：说"帮我记录这次会议，每次翻页时更新摘要"  
**期望结果**：Slow 持续监控屏幕变化，检测到翻页时提取 PPT 内容，汇总为会议记录

**Talker 处理链路**：
```
stop_speech → LLM 识别 slow_tool(record_meeting) → handoff
  → attention_owner = slow
  → Slow AccumulationLoop：持续拉屏幕帧，检测变化
  → 每次翻页：task_event(progress, summary) → Talker silent（只更新 UI）
  → 会议结束指令 → task_event(completed) → Talker 播报摘要
```

**架构兼容要点**：
- **视频帧路由**：当前设计视频帧只随 `turn` 消息附带给 LLM，此 case 需要 Slow 持续获取屏幕帧。需要设计视频帧的持续传递通道（端侧 → Talker 转发 → Slow，或端侧直接给 Slow，待定）
- Talker 侧：`task_event(progress)` 的 `speak_policy=silent`，不播报，只做 UI 更新
- 此 case 对视频帧传输架构有新要求，**Phase 1 时需在接口设计里预留**

---

### C14 · 见人触发提醒

**用户行为**：说"下次我见到张三，提醒我还他钱"  
**期望结果**：Slow 持续监控摄像头，识别到张三时主动提醒

**Talker 处理链路**：
```
stop_speech → LLM 识别 slow_tool(person_reminder) → collect_params(person, message)
  → handoff → Slow MonitoringLoop（人脸识别）
  → 识别到目标人物 → task_event(completed) → Talker 立即播报
```

**架构兼容要点**：
- 与 C12 同为 MonitoringLoop，但触发条件是人脸而非画面内容变化
- 人脸识别能力在 Slow 侧实现，Talker 不感知
- **隐私敏感**：人脸识别涉及隐私，产品层需明确使用边界，此处仅记录技术可行性

**对应实现**：Phase 4 扩展，依赖 Slow 人脸识别能力

---

### C15 · 任务中途打断，追加信息后重启

**用户行为**：任务执行中说"等等，我还要加一个条件：……"  
**期望结果**：暂停当前任务，追加信息后以新参数重新执行

**Talker 处理链路**：
```
stop_speech（interrupt_epoch++）
  → 检测到 active_task_ids 非空且用户意图为修改
  → 发 task_cancel(task_id)
  → 重新进入 collect_params，合并原参数 + 新信息
  → 重新 handoff
```

**架构兼容要点**：
- Talker 侧：需要在 `on_stop_speech` 中识别"修改任务"意图，触发 cancel + re-handoff 流程
- Slow 侧：需响应 task_cancel，停止当前执行（Slow 独立实现，Talker 不感知内部细节）
- **最复杂处**：合并原有参数与新增信息，避免重复追问已知参数

**对应实现**：Phase 4 扩展，依赖 Slow cancel 接口

---

## 架构兼容项汇总

需在 Phase 1 接口设计时预留扩展点，避免后期破坏性改动：

| 兼容项 | 涉及 Case | 预留方式 |
|--------|-----------|---------|
| 视频帧持续传递给 Slow | C12、C13、C14 | `interfaces.py` 中 `SlowInbox` 消息结构预留 `video_frame` 字段 |
| task_cancel 接口 | C15 | `SlowInbox` 消息类型中包含 `cancel` 类型 |
| Slow pause/resume | C15 | 接口预留，Slow 侧实现不在本仓库 |
| BTW 意图识别分支 | C11 | `on_stop_speech` 中 `attention_owner=slow` 分支结构预留 |
| handoff urgent 标记 | C10 | `HandoffMessage` 预留 `priority: "normal" \| "urgent"` 字段 |
| MemoryIndex 图片存储 | C07 | `MemoryIndex` 接口预留 `save_note(image, summary)` |
