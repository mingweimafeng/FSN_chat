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
├── .trae/knowledge-base.md         # 本知识库文件
├── characters/
│   ├── character_manifest.json     # 角色清单（默认角色、TTS 配置）
│   └── Saber/                      # Saber 角色包
│       ├── audio_package/
│       │   ├── onnx_model/         # TTS 推理模型 (.onnx, .bin)
│       │   └── reference_audio/    # 参考音频（按情绪分文件夹）
│       ├── dress/                  # 立绘（按装扮/情绪/状态）
│       │   └── dress_config.json   # 装扮级立绘位置参数
│       └── prompts/
│           ├── role_prompt.txt      ← 角色特有：角色设定
│           └── user_profile_prompt.txt ← 角色特有：用户档案
├── backgrounds/                    # 背景图片
├── music/                          # 音乐文件（可选）
├── GenieData/                      # genie_tts 数据包
└── chat_app/                       # 源代码（~5,200 行，46 个 .py）
    ├── __init__.py
    ├── main.py                     # QApplication 入口
    ├── config/                     # 配置包
    │   ├── __init__.py             # re-export 入口
    │   ├── _helpers.py             # 共享内部工具
    │   ├── ui_settings.py          # UI/渲染/光标常量
    │   ├── animation_settings.py   # 动画/翻页时间常量
    │   ├── api_settings.py         # API 提供商/模型配置
    │   ├── character_settings.py   # 角色/立绘/情绪配置
    │   ├── storage_settings.py     # TTS 参数/文件路径
    │   ├── prompt_settings.py      # 提示词加载逻辑
    │   ├── fixed_requirements_prompt.txt ← 系统级：固定要求
    │   ├── json_guard_prompt.txt   ← 系统级：JSON 格式约束
    │   └── summary_prompt.txt      ← 系统级：记忆摘要
    ├── audio/
    │   ├── audio_manager.py        # QMediaPlayer 封装
    │   ├── tts_client.py           # GenieTTSClient + 线程类
    │   └── tts_pipeline.py         # 合成队列管理
    ├── core/
    │   ├── app_context.py          # 服务容器 dataclass
    │   ├── memory_mixin.py         # 记忆管理（L1/L2）
    │   ├── state_machine.py        # 对话阶段状态机
    │   ├── window_protocol.py      # 共享接口协议
    │   └── window_runtime.py       # VirtualTimer
    ├── data/
    │   ├── assets.py               # 背景/立绘加载
    │   ├── credential_store.py     # keyring 密钥存储
    │   ├── favorites_store.py      # 收藏持久化
    │   ├── history_store.py        # 聊天历史 JSON
    │   └── settings_store.py       # 应用设置 + 记忆状态
    ├── extensions/
    │   ├── api.py                  # ExtensionContext + BaseExtension
    │   ├── manager.py              # ExtensionManager
    │   └── plugins/
    │       ├── cursor_idle_hider.py
    │       ├── favorites.py
    │       └── music_player.py
    ├── services/
    │   ├── api_client.py           # ChatRequestThread
    │   └── response_parser.py      # ChatResponseParser
    └── ui/
        ├── window.py               # BackgroundWindow（主窗口，8 mixin 多继承）
        ├── text_render_mixin.py    # paintEvent + 文字渲染
        ├── input_mixin.py          # 输入处理（键盘、IME、焦点）
        ├── dialogue_mixin.py       # 对话逻辑（提交、回复、翻页、菜单）
        ├── animation_mixin.py      # 动画过渡
        ├── character_mixin.py      # 立绘加载/绘制
        ├── audio_mixin.py          # TTS + 音频连接
        ├── background_mixin.py     # 背景抽屉
        ├── dialogs.py              # HistoryDialog + SettingsDialog
        └── backgrounds.py          # BackgroundCard + BackgroundDrawer
```

---

## 三、核心数据流（保持不变）

详见源码中的 `knowledge-base.md` 3.1-3.3 节。

---

## 四、关键配置项

### 4.1 提示词架构（2026-05-10 重构）

```
characters/{角色}/prompts/
    ├── role_prompt.txt           ← 角色特有：角色设定
    └── user_profile_prompt.txt   ← 角色特有：用户档案

chat_app/config/
    ├── fixed_requirements_prompt.txt  ← 系统级：固定输出要求
    ├── json_guard_prompt.txt          ← 系统级：JSON 格式约束（guard prompt）
    └── summary_prompt.txt             ← 系统级：记忆摘要提示词
```

`SYSTEM_PROMPT = role_prompt + user_profile_prompt + fixed_requirements_prompt`。用户可在设置对话框覆盖后两者。

---

## 五、架构约定

### 5.1 Mixin 继承链

```
BackgroundWindow
├── InputMixin         # 输入处理
├── DialogueMixin      # 对话逻辑
├── BackgroundMixin    # 背景抽屉
├── CharacterMixin     # 立绘
├── TextRenderMixin    # 绘制 (paintEvent)
├── AnimationMixin     # 动画
├── AudioMixin         # TTS
├── MemoryMixin        # 记忆（位于 core/）
└── QWidget            # Qt 基类
```

**重要**：状态现在统一由 `ChatStateMachine` 作为单一数据源，mixin 通过 `self.chat_state.*` 读取（`@property`）。`_apply_state_flags()` 已被移除。

### 5.2 状态机

`UiPhase` 枚举：`IDLE → WAITING_REPLY → OUTPUTTING_REPLY → OUTPUTTING_NARRATION → IDLE / CLOSING`

---

## 六、已修复问题（2026-05-10）

37 个 GLM 分析问题 → **已修复 14 个**，剩余 23 个。

| # | 修复内容 | 涉及文件 |
|---|---------|---------|
| C1 | 拒绝 `http://` 明文传输 API 密钥 | `api_client.py` |
| C2 | 引入 `keyring` 系统密钥库 | `credential_store.py`, `settings_store.py` |
| C3 | 移除 `os.environ` 写入 API 密钥 | `dialogue_mixin.py`, `window.py` |
| C4 | bytes 拼接 `+=` → `bytearray()` | `tts_client.py` |
| C5 | `list(deque).index()` → 单次遍历 | `tts_pipeline.py` |
| C6 | 移除重复/拼写错误情绪 | `character_settings.py` |
| C7 | 补充 `WindowProtocol` 类型标注 | `memory_mixin.py` |
| H1 | 引号嵌套 `""text""` 修复 | `dialogue_mixin.py` |
| H3 | 插件内部耦合解耦（`close_overlay()` API） | `api.py`, `manager.py`, `window.py`, `music_player.py` |
| H9 | `CHARACTER_DRESS_DIR` 路径统一 | `character_settings.py`, `window.py`, `dialogue_mixin.py` |
| M1 | `WindowProtocol` 运行时自检 | `window.py` |
| M8 | `current_narration/top_level_emotion` 声明 | `window_protocol.py`, `window.py` |
| M12 | 光标移动/Delete/Ctrl+V/光标处插入 | `input_mixin.py` |
| M13 | 翻页后光标错位 | `text_render_mixin.py` |

### 额外修复（chat_app_analysis.md 中发现的 6 个问题）

| # | 修复内容 | 涉及文件 |
|---|---------|---------|
| 1 | `MIN_REPLY_CHARS` 硬编码填充移除 | `api_settings.py`, `response_parser.py` |
| 2 | 默认模型 `deepseek-v4-flash` → `deepseek-chat` | `api_settings.py` |
| 3 | 移除 `api_client.py` 冗余 Markdown 剥离 | `api_client.py` |
| 4 | guard prompt 恢复（与 `json_mode` 互补，分别管字段和语法） | `api_client.py`, `prompt_settings.py` |
| 5 | 状态复制消除：删除 `_apply_state_flags()`，统一走 `chat_state` | `window.py`, `input_mixin.py`, `text_render_mixin.py`, `dialogue_mixin.py`, `audio_mixin.py`, `window_protocol.py` |
| 6 | 弹窗后输入法切回英文修复 | `input_mixin.py` |

---

## 七、剩余问题（23 个）

### 🛠 影响开发（6 个）
M2 (MRO 复杂) / M3 (monkey-patch input) / M6 (music_player 507行) / M7 (收藏音频竞态) / M9 (os.environ 重复) / M10 (重复代码)

### 👤 影响用户体验（13 个）
H2 (右键延迟) / H4 (缓存全清) / H5 (历史全量反序列化) / H6 (收藏空 I/O) / H7 (自动播放忽略暂停) / H8 (索引不同步) / M4 (临时文件不清理) / M5 (stop 清理文件) / M11 (max_tokens 冗余) / L7 (英文不分割) / L8 (硬编码 Arcueid)

### 🔄 同时影响（1 个）
M12 (Tab 键不可用，其余输入已修复)
