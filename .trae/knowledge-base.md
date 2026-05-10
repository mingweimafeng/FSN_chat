# FSN_chat 项目知识库

> 本文件供 AI 助手在对话开始时读取，以快速恢复对项目的完整认知。
> **每次执行任务前需先读取此文件了解当前状态。对代码做出改动后，必须同步更新此文件。**

---

## 零、AI 工作约定

1. **每次执行任务前**：先读取 `.trae/knowledge-base.md`，了解项目当前状态。
2. **每次对代码做出改动后**：同步更新本文件中对应的部分（目录结构、已修复问题、配置变更等），保持知识库与代码实际状态一致。
3. **本文件是最高优先级的上文参考**，如果本文件内容与模型记忆冲突，以本文件为准。

---

## 一、项目概况

- **项目名**：FSN_chat
- **技术栈**：Python 3.13, PySide6 (Qt), genie_tts (TTS), ONNX Runtime, pyopenjtalk
- **打包**：PyInstaller (onedir 模式), conda 环境 (chatenv)
- **许可**：MIT（仅代码，资源不属于本项目）
- **仓库**：`git@github.com:mingweimafeng/FSN_chat.git` (master 分支)

---

## 二、目录结构

```
FSN_chat/
├── app.py                          # 入口（含 freeze_support）
├── build_exe.py                    # 打包脚本（已合并 DLL 修复）
├── LICENSE                         # MIT 许可证
├── Saber.ico                       # 程序图标
├── characters/
│   ├── character_manifest.json     # 角色清单（默认角色、TTS 配置）
│   └── Saber/                      # Saber 角色包
│       ├── audio_package/
│       │   ├── onnx_model/         # TTS 推理模型 (.onnx, .bin)
│       │   └── reference_audio/    # 参考音频（按情绪分文件夹）
│       │       ├── normal/         #   audio.wav + reference.txt
│       │       ├── happy/            ...
│       │       └── ...
│       ├── dress/                  # 立绘（按装扮/情绪/状态）
│       │   ├── Casual/
│       │   │   ├── normal/idle/
│       │   │   ├── normal/listen/
│       │   │   ├── normal/talk/
│       │   │   └── ...
│       │   ├── Servant/
│       │   ├── Misc/
│       │   └── dress_config.json   # 装扮级立绘位置参数
│       └── prompt_Saber.txt
├── backgrounds/                    # 背景图片
├── music/                          # 音乐文件（可选）
├── GenieData/                      # genie_tts 数据包
└── chat_app/                       # 源代码
    ├── __init__.py                 # 公开导入
    ├── main.py                     # QApplication 入口
    ├── config/                     # 配置包（按领域拆分为 7 个子模块）
    │   ├── __init__.py             # 向后兼容的 re-export 入口
    │   ├── _helpers.py             # 共享内部工具函数
    │   ├── ui_settings.py          # UI/渲染/字体/光标常量
    │   ├── animation_settings.py   # 动画/翻页/淡入淡出时间常量
    │   ├── api_settings.py         # API 提供商/模型配置
    │   ├── character_settings.py   # 角色/立绘/服装/情绪配置
    │   ├── storage_settings.py     # TTS 参数 + 文件持久化路径
    │   └── prompt_settings.py      # 提示词/记忆参数
    ├── audio/
    │   ├── audio_manager.py        # QMediaPlayer 封装
    │   ├── tts_client.py           # GenieTTSClient + 线程类
    │   └── tts_pipeline.py         # 合成队列管理
    ├── core/
│   ├── app_context.py          # 服务容器 dataclass
│   ├── memory_mixin.py         # 记忆管理（L1/L2）
│   ├── state_machine.py        # 对话阶段状态机
│   ├── window_protocol.py      # 共享接口协议（所有 mixin 的显式接口声明）
│   └── window_runtime.py       # VirtualTimer（虚拟定时器）
    ├── data/
│   ├── assets.py               # find_backgrounds() + load_character_images()
│   ├── favorites_store.py      # 收藏数据持久化
│   ├── history_store.py        # 聊天历史 JSON 持久化
│   └── settings_store.py       # 应用设置 + 记忆状态
    ├── extensions/
    │   ├── api.py                  # ExtensionContext（沙盒）+ BaseExtension（抽象基类）
    │   ├── manager.py              # ExtensionManager（动态发现/加载/卸载）
    │   └── plugins/
    │       ├── cursor_idle_hider.py # 鼠标闲置自动隐藏
    │       ├── favorites.py         # 收藏夹（含 TTS 预览）
    │       └── music_player.py      # 音乐播放器（507 行，最大插件）
    ├── services/
    │   ├── api_client.py           # ChatRequestThread + HTTP 请求
    │   └── response_parser.py      # ChatResponseParser（JSON 解析）
    └── ui/
        ├── window.py               # BackgroundWindow（主窗口，多继承）
        ├── text_render_mixin.py    # paintEvent + 文字渲染
        ├── input_mixin.py          # 输入处理（键盘、IME、焦点）
        ├── dialogue_mixin.py       # 对话逻辑（提交、回复、翻页、菜单）
        ├── animation_mixin.py      # 动画过渡（立绘切换、翻页、淡入淡出）
        ├── character_mixin.py      # 立绘加载、索引、绘制区域计算
        ├── audio_mixin.py          # TTS + 音频连接
        ├── background_mixin.py     # 背景抽屉联动
        ├── dialogs.py              # HistoryDialog + SettingsDialog
        └── backgrounds.py          # BackgroundCard + BackgroundDrawer
```

---

## 三、核心数据流

### 3.1 启动流程

```
app.py
  → multiprocessing.freeze_support()
  → chat_app.main.main()
    → QApplication(sys.argv)
    → _preflight_genie_data()        # 检查 GenieData/，缺失则弹窗下载
    → BackgroundWindow(BACKGROUND_DIR)  # 构造窗口
      → _init_basic_state()
        → _loading = True             # ← 新增：加载状态标记
        → find_backgrounds()
      → _init_ui_state()
      → _init_character_state()
        → load_dress_config(current_dress)
        → load_character_images(CHARACTER_DIR)
      → _build_context()
      → _init_timers()
      → _setup_window()
        → start_tts_warmup()          # 启动 TTSWarmupThread（后台）
        → warmed_up → _on_warmup_done
          → _loading = False           # 解除加载状态
    → window.show()                   # 立即显示窗口（不等 warmup）
    → app.exec()
```

### 3.2 对话流程

```
用户输入 → submit_input()
  → audio_manager.stop()
  → tts_pipeline.reset()
  → extension_manager.process_user_input()   # 插件拦截
    → （如果拦截成功）on_reply_ready（本地回复）
    → （如果未拦截）ChatRequestThread 开始 HTTP 请求
      → finished_payload → on_reply_ready()
  → normalize_reply_segments()               # 标准化 segments
  → set_character_emotion()
  → begin_tts_for_reply()                     # 开始预合成
  → set_character_state("react")
    → _after_react()
      → start_next_reply_segment()           # 逐个播放 segment
        → begin_tts_for_reply(segment, start_when_ready=True)
        → TTS 完成 → audio_ready
          → start_segment_after_audio_ready()
            → audio_manager.play()
            → set_character_state("speaking")
            → start_reply_output()
              → typewriter_timer 逐字输出
```

### 3.3 TTS 链路

```
GenieTTSClient (HTTP client)
  → ensure_server_running()
    → 启动 genie_tts 子进程（multiprocessing）
    → 等待服务器就绪（轮询端口）
  → initialize()
    → POST /load_character（onnx_model_dir）
  → _set_reference_audio(emotion)
    → 读取 reference.txt
    → POST /set_reference_audio（audio_path, audio_text, language）
  → synthesize_to_temp_file(text, emotion)
    → POST /tts → 返回 PCM bytes
    → 写入 tmp_audio/tts_{uuid}.wav
```

**线程清单位置**：`window.closeEvent()` + `tts_pipeline.reset()` + `extensions.manager.unload_all()`

---

## 四、关键配置项

配置已拆分为 `config/` 包（`chat_app/config/`），按领域分 6 个子模块。所有已有的 `from chat_app.config import XXX` 导入方式保持不变。

### 4.1 UI 配置 (ui_settings.py)

| 变量 | 说明 | 默认值 |
|---|---|---|
| `WINDOW_WIDTH/HEIGHT` | 窗口尺寸 | 1280x720 (16:9) |
| `FONT_SIZE` | 对话字体大小 | 23 |
| `CURSOR_BLINK_INTERVAL_MS` | 光标闪烁间隔 | 500ms |
| `TYPEWRITER_INTERVAL_MS` | 打字机速度 | 35ms |

### 4.2 动画配置 (animation_settings.py)

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ANIMATION_TICK_MS` | 动画节拍 | 16 (≈60fps) |
| `SEGMENT_GAP_INTERVAL_MS` | 段落间隔 | 1000ms |
| `PORTRAIT_FADE_DURATION_MS` | 立绘切换时间 | 300ms |

### 4.3 API 配置 (api_settings.py)

| 变量 | 说明 |
|---|---|
| `PROVIDERS` | 7 家 API 提供商配置 |
| `resolve_api_config()` | 根据 provider/base_url/model 解析最终地址 |

### 4.4 角色配置 (character_settings.py)

| 变量 | 说明 |
|---|---|
| `CHARACTER_DIR` | 当前角色立绘目录（从 manifest 动态加载） |
| `GENIE_CHARACTER_NAME` | TTS 角色名 |
| `STATE_TO_ASSET` | 状态 → 资源目录映射 |
| `load_dress_config()` | 加载装扮级立绘位置参数 |

### 4.5 存储配置 (storage_settings.py)

| 变量 | 说明 |
|---|---|
| `TEMP_AUDIO_DIR` | 临时音频目录 |
| `HISTORY_FILE_PATH` | 聊天记录 JSON 路径 |
| `SETTINGS_FILE_PATH` | 应用设置 JSON 路径 |

### 4.6 提示词配置 (prompt_settings.py)

| 变量 | 说明 |
|---|---|
| `DEFAULT_ROLE_PROMPT` | 角色设定提示词 |
| `SYSTEM_PROMPT` | 组合后的 system prompt |
| `MEMORY_L1_TURNS` | L1 记忆轮数 |

---

## 五、耦合度分析

| 层次 | 耦合度 | 说明 |
|---|---|---|
| **包间**（audio/core/data/services/ui/extensions） | **低** ✅ | `config/` 包被多依赖，但按领域拆分后职责明确 |
| **包内模块间**（services/api_client → response_parser 等） | **低** ✅ | 无跨包 import，通过名称查找访问插件 |
| **mixin 类间**（dialogue_mixin/audio_mixin/animation_mixin 等 7 个 mixin） | **中** ⚠️ | 通过 `self.xxx` 跨文件访问（31+ 处），但有 `WindowProtocol` 显式接口声明 |

**核心问题**：mixin 之间通过 `self.xxx` 直接访问属性，例如 `dialogue_mixin.py` 依赖 8 个外部属性（分布 31 处）。这些接口已通过 [core/window_protocol.py](file:///c:/Development/可爱的角色们/FSN_chat/chat_app/core/window_protocol.py) 显式声明，每个 mixin 的 `self` 参数标注为 `WindowProtocol`。重构时只需对照该文件即可知道哪些属性/方法被跨 mixin 共享。

---

## 六、剩余技术债务

| # | 问题 | 影响 | 优先级 | 说明 |
|---|---|---|---|---|
| 1 | 日志体系不统一（print + logging 混用，无文件日志） | 远程排查困难，崩溃后无法追溯 | 中 | 应统一为 logging + FileHandler |
| 2 | TTS/API 失败时仅 toast 提示 5 秒后消失 | 用户错过就无法追溯 | 低 | 缺少重试和降级机制 |
| 3 | `music_player.py` 507 行占插件代码一半 | 插件稳定性影响整个应用 | 低 | 可拆分或简化 |
| 4 | `music_player.py` 重复创建 QMediaPlayer | 应用中有两个独立播放器且互不互通 | 中 | 应复用 AudioManager |
| 5 | `tts_client.py` 包含 TtsSynthesisThread + TtsWarmupThread | 线程类与客户端混在一起，223 行 | 低 | 建议提取到 `audio/tts_threads.py` |
| 6 | `api_client.py` 包含 MemorySummaryThread | 聊天请求和记忆摘要是不同业务 | 低 | 建议提取到 `services/memory_summary.py` |
| 7 | `settings_store.py` 包含 3 个存储类（124 行） | AppSettingsStore + MemoryStateStore + SettingsStore 挤在一起 | 低 | MemoryStateStore 可独立为 `data/memory_state_store.py` |

**重构必要性**：目前不需要大规模重构。项目功能完整，无团队协作。剩余债务均为低优先级，不影响日常开发。

---

## 七、架构约定

### 7.1 Mixin 继承链

```
BackgroundWindow
├── InputMixin         # 输入处理（键盘、IME、焦点、鼠标）
├── DialogueMixin      # 对话逻辑
├── BackgroundMixin    # 背景抽屉
├── CharacterMixin     # 立绘
├── TextRenderMixin    # 绘制 (paintEvent)
├── AnimationMixin     # 动画
├── AudioMixin         # TTS
├── MemoryMixin        # 记忆（位于 core/）
└── QWidget            # Qt 基类
```

**重要**：mixin 之间通过 `self.xxx` 直接访问其他 mixin 或 window 的属性（如 `self.audio_manager`、`self.tts_pipeline`）。这些接口已通过 [core/window_protocol.py](file:///c:/Development/可爱的角色们/FSN_chat/chat_app/core/window_protocol.py) 显式声明，每个 mixin 的 `self` 参数标注为 `WindowProtocol` 类型。`AppContext` dataclass 在 `_build_context()` 中创建，持有 chat_state / tts_client / tts_pipeline / audio_manager / settings_store / history_store / extension_manager 七个服务实例。

### 7.2 动画阶段

- `idle` / `fade_out` / `after_fade_out_delay` / `portrait` / `before_fade_in_delay` / `fade_in` / `portrait_only` / `page_fade_out` / `page_fade_in`
- 控制 `animation_phase` 字符串，由 `advance_animation()` 跳转
- `VirtualTimer` 替代 QTimer 用于高频 tick（typewriter、cursor、animation、text_fade）

### 7.3 状态机

`UiPhase` 枚举：`IDLE → WAITING_REPLY → OUTPUTTING_REPLY → OUTPUTTING_NARRATION → IDLE / CLOSING`

状态通过 `ChatStateMachine` 的 `phase_changed` 和 `flags_changed` 信号广播。

### 7.4 HTTP API

```
POST /load_character       {character_name, onnx_model_dir, language}
POST /unload_character     {character_name}
POST /set_reference_audio  {character_name, audio_path, audio_text, language}
POST /clear_reference_audio_cache
POST /tts                  {character_name, text, split_sentence}
```

---

## 八、情绪体系

```python
CHARACTER_EMOTIONS = (
    "normal", "happy", "angry", "shy", "flustered",
    "embarrassed", "flustered", "speechless", "serious",
    "shocked", "worried", "disguested"
)
STATE_TO_ASSET = {"idle": "idle", "listen": "listen", "speaking": "talk", "react": "react"}
```

立绘目录约定：`{dress}/{emotion}/{state}/{filename}`

---

## 九、扩展机制

- 位置：`extensions/plugins/`（通过 `pkgutil` 自动发现）
- 基类：`BaseExtension`（`on_start()` / `on_stop()` / `on_user_input_intercept()`）
- 沙盒：`ExtensionContext`（`speak()` / `change_emotion()` / `play_audio()` / `stop_audio()`）
- 现有插件：CursorIdleHider / Favorites / MusicPlayer

---

## 十、逐文件功能分析与职责评估

> 2026-05-10 完整分析，共 44 个 .py 文件，总计约 4,300 行有效代码。

### 10.1 根级（2 文件 + 1 配置包）

| 文件/模块 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `__init__.py` | 2 | 公开导出 `config.*` 和 `BackgroundWindow` | ✅ 合理 |
| `main.py` | 69 | QApplication 入口、GenieData 预检弹窗、日志级别配置 | ✅ 合理，职责单一 |
| `config/` (包) | 283 | 按 6 领域拆分：ui_settings(33行) / animation_settings(18行) / api_settings(59行) / character_settings(75行) / storage_settings(19行) / prompt_settings(32行) + _helpers(36行) + __init__(65行) | ✅ 已拆分，每模块职责单一 |

### 10.2 `core/`（5 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `app_context.py` | 20 | `AppContext` dataclass，持有 7 个服务引用 | ✅ 简洁 |
| `memory_mixin.py` | 82 | `MemoryMixin`：L1 记忆消息构建、L2 摘要触发 | ✅ 已从 ui/ 移入，位置正确 |
| `state_machine.py` | 61 | `ChatStateMachine` + `UiPhase` 枚举，管理对话阶段转换 | ✅ 合理 |
| `window_protocol.py` | 205 | `WindowProtocol`：mixin 共享接口协议，声明全部跨 mixin 属性和方法 | ✅ 新增，解决隐式接口问题 |
| `window_runtime.py` | 33 | `VirtualTimer`，由共享心跳驱动的轻量定时器 | ✅ 合理 |

### 10.3 `audio/`（3 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `audio_manager.py` | 58 | `AudioManager`：QMediaPlayer 封装，播放/停止/音量/自动清理临时文件 | ✅ 合理 |
| `tts_client.py` | 223 | `GenieTTSClient`：HTTP 客户端 + genie_tts 子进程管理 + **`TtsSynthesisThread`** + **`TtsWarmupThread`** | ⚠️ 线程类与客户端混在一起 |
| `tts_pipeline.py` | 119 | `TtsPipelineManager`：合成队列（deque）、预取、线程调度 | ✅ 合理 |

### 10.4 `services/`（2 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `api_client.py` | 228 | `ChatRequestThread`：HTTP Chat Completion（JSON模式→普通模式降级重试）+ **`MemorySummaryThread`** | ⚠️ 记忆摘要线程与聊天请求混在一起 |
| `response_parser.py` | 158 | `ChatResponseParser`：JSON 解析（多候选策略）、情绪标准化、segment 拆分 | ✅ 合理 |

### 10.5 `data/`（4 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `assets.py` | 21 | `find_backgrounds()` + `load_character_images()` | ✅ 合理 |
| `favorites_store.py` | 82 | `FavoritesStore`：收藏 JSON 持久化 | ✅ 已从 extensions/plugins/ 移入，位置正确 |
| `history_store.py` | 98 | `ChatHistoryStore`：聊天记录 JSON 持久化，按日期/小时分组删除 | ✅ 合理 |
| `settings_store.py` | 124 | **`AppSettingsStore`** + **`MemoryStateStore`** + **`SettingsStore`**（3 个类） | ⚠️ 三个存储类挤在一起 |

### 10.6 `extensions/`（5 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `api.py` | 81 | `ExtensionContext`（沙盒，6 个 API）+ `BaseExtension`（抽象基类，4 个钩子） | ✅ 合理 |
| `manager.py` | 111 | `ExtensionManager`：pkgutil 动态发现、实例化、生命周期管理、输入拦截 | ✅ 合理 |
| `plugins/cursor_idle_hider.py` | 87 | 鼠标闲置 5 秒自动隐藏，智能空间感知（弹窗/菜单/播放器上方不隐藏） | ✅ 合理 |
| `plugins/favorites.py` | 209 | **`FavoritesStore`**（数据层）+ **`FavoritesExtension`**（插件逻辑）+ **`FavoritesDialog`**（UI） | ⚠️ 三层混在一起 |
| `plugins/music_player.py` | **507** | 音乐播放器：悬浮岛 UI、QMediaPlayer 播放、歌单管理、进度/音量控制 | ⚠️ 项目最大文件，但作为自包含插件可接受 |

### 10.7 `ui/`（9 文件）

| 文件 | 行数 | 职责 | 评估 |
|---|---|---|---|
| `window.py` | 442 | `BackgroundWindow`：多继承 8 个 mixin，初始化所有状态、服务、定时器 | ⚠️ 偏大，初始化逻辑冗长 |
| `input_mixin.py` | 134 | `InputMixin`：keyPressEvent、inputMethodEvent、IME、焦点、鼠标拦截 | ✅ 拆分后职责清晰 |
| `dialogue_mixin.py` | 460 | `DialogueMixin`：submit_input、on_reply_ready、segment 管理、翻页、右键菜单、收藏 | ⚠️ 仍偏大，菜单逻辑可独立；已解除 FavoritesExtension 直接 import |
| `animation_mixin.py` | 237 | `AnimationMixin`：渲染 tick 调度、立绘过渡（5 阶段）、翻页过渡、文字淡出 | ✅ 合理 |
| `character_mixin.py` | 100 | `CharacterMixin`：立绘索引/随机选择、状态/情绪切换、绘制区域计算、角色层绘制 | ✅ 合理 |
| `audio_mixin.py` | 65 | `AudioMixin`：TTS 信号连接、音频播放协调、warmup、临时文件清理 | ✅ 合理 |
| `background_mixin.py` | 127 | `BackgroundMixin`：背景切换/持久化、抽屉触发区、蒙版渐变、UI 可见性同步 | ✅ 合理 |
| `text_render_mixin.py` | 289 | `TextRenderMixin`：paintEvent、文字换行/缓存、alpha span 渲染、光标矩形 | ✅ 合理 |
| `dialogs.py` | 298 | `HistoryDialog`（树形分组+记忆摘要编辑+收藏）+ `SettingsDialog`（API/提示词配置） | ⚠️ 偏大；已改为从 data.favorites_store 导入 |
| `backgrounds.py` | 210 | `BackgroundCard`（悬停动画）+ `BackgroundDrawer`（滑入/滑出抽屉） | ✅ 合理 |

### 10.8 位置不当汇总

| 文件 | 当前位置 | 建议位置 | 原因 |
|---|---|---|---|
| `FavoritesDialog`（在 favorites.py 中） | `extensions/plugins/` | `ui/` | 纯 UI 组件 |
| `MemorySummaryThread`（在 api_client.py 中） | `services/` | `services/memory_summary.py` | 与聊天请求是不同的业务 |
| `TtsSynthesisThread`/`TtsWarmupThread`（在 tts_client.py 中） | `audio/` | `audio/tts_threads.py` | 线程类与 HTTP 客户端职责不同 |
| `MemoryStateStore`（在 settings_store.py 中） | `data/` | `data/memory_state_store.py` | 独立的数据实体 |

### 10.9 优化优先级建议

| 优先级 | 任务 | 成本 | 收益 |
|---|---|---|---|
| **中** | 将 FavoritesDialog 移出插件到 ui/ | 低（1 个新文件） | 符合分层架构 |
| **低** | #5~#7 提取线程类和存储类 | 低（各 1 个新文件） | 代码组织更清晰 |

---

## 十一、打包说明

```bash
conda activate chatenv
python build_exe.py     # 打包 + 自动修复 DLL
# 手动复制资源：backgrounds/  characters/  GenieData/  music/  Saber.ico
```

打包输出：`dist/FSN_chat/FSN_chat.exe`（~17MB）+ `_internal/`（~950MB，含 PySide6、onnxruntime、genie_tts 等）
