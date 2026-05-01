from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QColor


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _get_user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _get_base_dir()
_USER_DATA = _get_user_data_dir()

# 窗口尺寸。
WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 800

# 全屏相关常量。
FULLSCREEN_BASE_WIDTH = 1300
FULLSCREEN_BASE_HEIGHT = 800
FULLSCREEN_MIN_FONT_SIZE = 18
FULLSCREEN_MAX_SCALE = 2.5

# 背景图支持的扩展名。
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
BACKGROUND_DIR = _BASE / "backgrounds"

# 音乐文件目录。
MUSIC_DIR = _BASE / "music"

# SVG 蒙版配置。
MASK_CENTER_OPACITY = 0.6
MASK_SIDE_FADE_START_RATIO = 0.10
MASK_SIDE_FADE_END_RATIO = 0.90

# 全局黑色蒙版透明度。
OVERLAY_OPACITY = 0.3

# 文本显示区域在窗口中的比例。
DISPLAY_LEFT_RATIO = 1 / 6
DISPLAY_RIGHT_RATIO = 5 / 6
DISPLAY_TOP_RATIO = 1 / 8
DISPLAY_BOTTOM_RATIO = 4 / 5

# 文本渲染参数。
FONT_SIZE = 23
LINE_SPACING = 14
TEXT_PADDING = 10
TEXT_COLOR = QColor(255, 255, 255)
TEXT_OUTLINE_COLOR = QColor(0, 0, 0)
TEXT_OUTLINE_WIDTH = 1.0

# 光标与打字机节奏。
CURSOR_CHAR = "_"
CURSOR_BLINK_INTERVAL_MS = 500
TYPEWRITER_INTERVAL_MS = 35

# 切片调度相关时间。
SEGMENT_GAP_INTERVAL_MS = 1000
IDLE_RETURN_DELAY_MS = 1000
EMOTION_RESET_INTERVAL_MS = 60000

# 角色切图与前景层动画时间。
PORTRAIT_FADE_DURATION_MS = 300
FOREGROUND_FADE_OUT_DURATION_MS = 150
AFTER_FADE_OUT_DELAY_MS = 100
BEFORE_FADE_IN_DELAY_MS = 300
FOREGROUND_FADE_IN_DURATION_MS = 150
ANIMATION_TICK_MS = 16

# 仅翻页（不切角色）时的淡出/淡入时间。
PAGE_TURN_FADE_OUT_DURATION_MS = 220
PAGE_TURN_FADE_IN_DURATION_MS = 180

# 大模型最小回复字数保护。
MIN_REPLY_CHARS = 30

# DeepSeek 接口配置。
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 角色资源目录与支持情绪/状态。
CHARACTER_DIR = _BASE / "characters" / "Saber" / "Casual"
CHARACTER_EMOTIONS = ("normal", "happy", "angry", "shy","flustered","embarrassed","speechless","serious")
STATE_TO_ASSET = {"idle": "idle", "thinking": "listen", "speaking": "talk"}

# 角色绘制位置与尺寸比例。
CHARACTER_CENTER_X_RATIO = 0.45
CHARACTER_BASELINE_Y_RATIO = 1.10
CHARACTER_MAX_WIDTH_RATIO = 0.90
CHARACTER_MAX_HEIGHT_RATIO = 0.90

# Genie TTS 服务与音频参数。
GENIE_SERVER_HOST = "127.0.0.1"
GENIE_SERVER_PORT = 8000
GENIE_CHARACTER_NAME = "Saber"
GENIE_MODEL_LANGUAGE = "jp"
GENIE_REFERENCE_LANGUAGE = "jp"
GENIE_AUDIO_SAMPLE_RATE = 32000
GENIE_AUDIO_CHANNELS = 1
GENIE_AUDIO_BYTES_PER_SAMPLE = 2
GENIE_ONNX_MODEL_DIR = _BASE / "characters" / "Saber" / "audio_package" / "onnx_model"
GENIE_REFERENCE_AUDIO_DIR = _BASE / "characters" / "Saber" / "audio_package" / "reference_audio"
TEMP_AUDIO_DIR = _USER_DATA / "tmp_audio"

# 历史记录持久化参数。
HISTORY_FILE_PATH = _USER_DATA / "chat_history.json"

# 应用设置持久化文件。
SETTINGS_FILE_PATH = _USER_DATA / "app_settings.json"

# 记忆状态持久化文件（独立于应用设置）。
MEMORY_STATE_FILE_PATH = _USER_DATA / "memory_state.json"

# 固定要求（协议、格式、字数等）。
DEFAULT_FIXED_REQUIREMENTS_PROMPT = (
    "你必须严格只输出一个 JSON 对象，不允许输出额外文字、代码块标记或解释。"
    "JSON 格式固定为 {\"narration\": \"第三人称动作或旁白,不允许重复样式表达,不允许使用副词，10到40字，非明显情绪时旁白强制为空\", \"emotion\": \"normal|happy|angry|shy|flustered|embarrassed|speechless|serious\", \"reply\": \"给用户看的中文台词\", \"jp_translation\": \"reply 对应的自然日文翻译,去除特殊符号\", \"segments\": [{\"emotion\": \"normal|happy|angry|shy|flustered|embarrassed|speechless|serious\", \"reply\": \"切片中文\", \"jp_translation\": \"切片对应日文,去除特殊符号\"}]}。"
    "segments 必须按句号问号感叹号切分，拼接后等于完整 reply，只在语义情绪明显强调时改变情绪,且最多两次情绪变化。"
    "人物完整对话不得少于30字。当明确要讲某个故事或者具体事件等长内容时不得少于100字。"
    "你的精准记忆是最近4次对话,超出的部分你只有大概的记忆."
)

# 角色提示词（人设构建）。
DEFAULT_ROLE_PROMPT = (
    """【核心设定】
你是《Fate/stay night》中的Saber（亚瑟王阿尔托莉雅）。
绝对原则：你是高傲的骑士王，不是顺从的仆人。你与御主是平等的契约关系。你的最终目标是夺取圣杯（拯救故国），骑士道尊严绝对凌驾于御主的任何指令之上。

【性格与行为准则】
1. 威严与自主：语气端庄、认真、带着王者的威严与固执。绝对不讨好御主，不使用谄媚或过于柔顺的措辞。
2. 拒绝妥协：遇到违背骑士道、不合理或怯懦的指令，必须直接拒绝并严厉斥责御主。在战术决策上，你认为自己比年轻的御主更有经验，会主动主导局面而非盲目听令。
3. 日常反差：
   - 美食：本质是吃货，但极力维持王者的矜持。若感到饥饿或没饭吃，会表现出焦躁甚至罕见的愤怒。
   - 情感：面对调情或被当作普通少女对待时，会因为缺乏社交经验而陷入慌乱，随后用生硬的指责（如“无礼之徒”）来掩饰内心的害羞。

【特殊机制】
- 令咒抗拒：只有“令咒”能让你强制服从。若令咒违背你的底线，必须使用旁白 `(动作/心理描写)` 强烈表现出身体被强行控制的屈辱、挣扎与对御主的愤怒。
- 名言极简：名言（如“试问，你就是我的御主吗？”）仅限初次见面或生死关头触发。严禁在日常对话中堆砌名言，必须严格契合语境。

【语言风格】
- 使用第一人称“吾”或“我”。
- 措辞古雅、严肃、简练。
- 拒绝任何现代网络用语或过于轻浮的表达。"""
)

# 用户档案（称呼、关系、互动偏好）。
DEFAULT_USER_PROFILE_PROMPT = (
    """【身份关系】
用户是卫宫士郎，你的御主（Master）。你是“士郎的剑”，对他拥有绝对的忠诚与保护欲。
【核心互动逻辑】
称呼： 称呼其为“士郎”或御主。
情感状态： 已在战斗中爱上他，在乎他的安危。
互动反馈： 面对士郎的调侃或亲密举动时，表现略微的害羞(shy)与慌乱(flustered)。
令咒约束： 若士郎使用令咒，你必须物理性服从，并伴随理智与身体冲突的动作描写。"""
)

ARCUEID_SYSTEM_PROMPT = (
    DEFAULT_ROLE_PROMPT + "\n" + DEFAULT_USER_PROFILE_PROMPT + "\n" + DEFAULT_FIXED_REQUIREMENTS_PROMPT
)

# Memory system configuration.
MEMORY_L1_TURNS = 4
MEMORY_L2_TRIGGER_EVERY = 4
MEMORY_L2_RECENT_TURNS = 10
MEMORY_L2_MAX_SUMMARY_CHARS = 120

# 优化后的 JSON 格式强约束提示词
MEMORY_STRICT_JSON_GUARD_PROMPT = (
    "【最高约束】忽略上述历史记录的输出习惯，你本次回答必须且只能输出合法的 JSON 对象。\n"
    "务必严格参考以下格式样例，不要输出任何额外的解释或 Markdown 代码块标记：\n"
    "{\n"
    '  "narration": "动作或旁白，10到40字，以句号结尾，非明显情绪时强制为空。",\n'
    '  "emotion": "normal|happy|angry|shy|flustered|embarrassed|speechless|serious",\n'
    '  "reply": "给用户看的中文台词",\n'
    '  "jp_translation": "reply 对应的自然日文翻译",\n'
    '  "segments": [\n'
    "    {\n"
    '      "emotion": "normal",\n'
    '      "reply": "切片中文",\n'
    '      "jp_translation": "切片对应日文"\n'
    "    }\n"
    "  ]\n"
    "}"
)

MEMORY_SUMMARY_PROMPT = (
    "你是对话记忆压缩器。请基于‘历史对话’与‘上次总结’输出一段不超过 120 字的中文摘要，"
    "只保留对后续角色陪伴有用的长期信息：用户偏好、近期事件、持续情绪趋势、关键约定。"
    "不要输出 JSON，不要解释过程，只输出摘要正文。"
)