from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

from chat_app.config import (
    ARCUEID_SYSTEM_PROMPT,
    CHARACTER_EMOTIONS,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    MEMORY_STRICT_JSON_GUARD_PROMPT,
    MEMORY_SUMMARY_PROMPT,
    MIN_REPLY_CHARS,
)
from chat_app.services.response_parser import ChatResponseParser


def _resolve_api_key(api_key: str) -> str:
    """解析 API 密钥：优先使用传入值，否则从环境变量读取"""
    return (api_key or os.getenv("DEEPSEEK_API_KEY", "")).strip()


def _post_chat_completion(
        api_key: str,
        messages: list[dict[str, str]],
        timeout_seconds: int = 60,
        json_mode: bool = False,
) -> str:
    """
    调用 DeepSeek Chat Completion，返回清洗后的 content。
    若 json_mode=True 则启用 JSON Output 并设置 max_tokens 防止截断。
    """
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        payload["max_tokens"] = 8192  # 大输出空间，避免 JSON 截断
    else:
        payload["max_tokens"] = 8192  # 普通模式也设上限，防止无限输出

    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))

    # 安全提取 content
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    # 如果 content 是 None，转为空字符串
    raw = str(content).strip() if content is not None else ""

    # ======= 新增清洗逻辑：剥离 Markdown 代码块标记 =======
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]

    if raw.endswith("```"):
        raw = raw[:-3]

    raw = raw.strip()
    # ======================================================

    # 有效性校验：空内容、仅空白或仅 {} / {"} 均视为无效应答
    if not raw or raw == "{}" or raw == '{"}':
        raise ValueError("Empty response from API (content is empty or just '{}')")

    return raw


class ChatRequestThread(QThread):
    finished_payload = Signal(dict)
    failed = Signal(str)

    def __init__(
            self,
            user_text: str,
            system_prompt: str = ARCUEID_SYSTEM_PROMPT,
            api_key: str = "",
            memory_messages: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.user_text = user_text
        self.system_prompt = system_prompt.strip() or ARCUEID_SYSTEM_PROMPT
        self.api_key = api_key.strip()
        self.memory_messages = memory_messages or []
        self.response_parser = ChatResponseParser()
        self._interrupted = False

    def stop(self) -> None:
        """设置中断标志，通知线程安全退出"""
        self._interrupted = True

    def run(self) -> None:
        resolved_api_key = _resolve_api_key(self.api_key)
        if not resolved_api_key:
            if not self._interrupted:
                self.failed.emit("请先在设置中填写 DeepSeek API 密钥。")
            return

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory_messages)

        # 将最高优先级 JSON 格式约束直接拼接到用户提问末尾，避免注意力错乱
        user_content_with_guard = f"{self.user_text}\n\n{MEMORY_STRICT_JSON_GUARD_PROMPT}"
        messages.append({"role": "user", "content": user_content_with_guard})

        raw_content = ""
        # ====== 第一阶段：优先尝试 JSON Output 模式（最多 2 次） ======
        for attempt in range(2):
            if self._interrupted:
                return
            try:
                raw_content = _post_chat_completion(
                    resolved_api_key, messages, timeout_seconds=60, json_mode=True
                )
                break  # 成功获取到非空内容，跳出重试
            except Exception as e:
                logger.debug("[Chat] JSON mode attempt %d failed: %s", attempt + 1, e)
                if attempt == 1:  # 最后一次 JSON 模式也失败，准备降级
                    logger.debug("[Chat] JSON mode exhausted, falling back to normal mode...")
                else:
                    time.sleep(0.5)  # 短暂延迟后重试

        # ====== 第二阶段：降级到普通模式（依旧尝试 2 次） ======
        if not raw_content and not self._interrupted:
            for attempt in range(2):
                if self._interrupted:
                    return
                try:
                    raw_content = _post_chat_completion(
                        resolved_api_key, messages, timeout_seconds=60, json_mode=False
                    )
                    break
                except Exception as e:
                    logger.debug("[Chat] Normal mode attempt %d failed: %s", attempt + 1, e)
                    if attempt == 1:
                        if not self._interrupted:
                            self.failed.emit(f"模型连续返回空内容，请稍后重试。最后错误: {e}")
                        return
                    time.sleep(0.8)

        # 最终兜底（理论上不会走到这里）
        if not raw_content:
            if not self._interrupted:
                self.failed.emit("模型返回了空内容，请重试。")
            return

        # 解析并发射结果
        if not self._interrupted:
            self.finished_payload.emit(self.parse_model_content(raw_content))

    def parse_model_content(self, raw_content: str) -> dict:
        parsed = self.response_parser.parse(raw_content)
        payload = parsed.to_payload()

        logger.info("=" * 40)
        logger.info("[解析模式] : %s", parsed.parse_mode)
        logger.info("[当前全局情绪] : %s", payload['emotion'])
        if payload["narration"]:
            logger.info("[旁白动作] : %s", payload['narration'])
        logger.info("[完整回复] : %s", payload['reply'])
        logger.info("[切片情绪明细] :")
        for i, seg in enumerate(payload["segments"]):
            logger.info("  片段 %d [%s] -> %s", i + 1, seg['emotion'], seg['reply'])
        if parsed.parse_mode.startswith("fallback"):
            preview = (parsed.raw_content or "").replace("\n", " ")
            logger.info("[原始返回预览] : %s", preview[:220])
        logger.info("=" * 40)

        return payload




class MemorySummaryThread(QThread):
    finished_summary = Signal(str)
    failed = Signal(str)

    def __init__(
            self, recent_turns: list[dict[str, str]], last_summary: str, api_key: str = ""
    ) -> None:
        super().__init__()
        self.recent_turns = recent_turns
        self.last_summary = last_summary.strip()
        self.api_key = api_key.strip()
        self._interrupted = False

    def stop(self) -> None:
        """设置中断标志，通知线程安全退出"""
        self._interrupted = True

    def run(self) -> None:
        resolved_api_key = _resolve_api_key(self.api_key)
        if not resolved_api_key:
            if not self._interrupted:
                self.failed.emit("记忆总结失败：未配置 API 密钥。")
            return

        turns_text = "\n".join(
            [
                f"第{i + 1}轮 用户: {turn.get('user', '').strip()}\n第{i + 1}轮 助手: {turn.get('assistant', '').strip()}"
                for i, turn in enumerate(self.recent_turns)
            ]
        ).strip()
        summary_seed = self.last_summary or "（无）"
        user_prompt = (
            f"上次总结:\n{summary_seed}\n\n"
            f"历史对话:\n{turns_text or '（无）'}\n\n"
            "请输出新的记忆总结："
        )
        messages = [
            {"role": "system", "content": MEMORY_SUMMARY_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # 记忆总结不启用 JSON 模式，也不需要重试复杂逻辑，简单抛出异常即可
            summary = _post_chat_completion(
                resolved_api_key, messages, timeout_seconds=60
            )
            if not self._interrupted:
                self.finished_summary.emit(summary.strip())
        except urllib.error.HTTPError as error:
            if not self._interrupted:
                self.failed.emit(f"记忆总结失败：{error.code}")
        except urllib.error.URLError as error:
            if not self._interrupted:
                self.failed.emit(f"记忆总结网络错误：{error.reason}")
        except Exception as error:
            if not self._interrupted:
                self.failed.emit(f"记忆总结异常：{error}")