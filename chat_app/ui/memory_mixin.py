from __future__ import annotations

from chat_app.config import MEMORY_L1_TURNS, MEMORY_L2_MAX_SUMMARY_CHARS, MEMORY_L2_RECENT_TURNS, MEMORY_L2_TRIGGER_EVERY
from chat_app.services.api_client import MemorySummaryThread


class MemoryMixin:
    def _build_l1_memory_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.memory_state.last_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"【长期记忆】{self.memory_state.last_summary}",
                }
            )

        for record in self.history_store.get_recent_turns(
            MEMORY_L1_TURNS, chronological=True
        ):
            if record.user_text:
                messages.append({"role": "user", "content": record.user_text})
            if record.reply_text:
                messages.append(
                    {"role": "assistant", "content": record.reply_text}
                )
        return messages

    def _recent_turns_for_summary(self) -> list[dict[str, str]]:
        turns: list[dict[str, str]] = []
        for record in self.history_store.get_recent_turns(
            MEMORY_L2_RECENT_TURNS, chronological=True
        ):
            turns.append(
                {
                    "user": record.user_text,
                    "assistant": record.reply_text,
                }
            )
        return turns

    def _maybe_trigger_memory_summary(self) -> None:
        self.memory_state.turns_since_summary += 1
        try:
            self.settings_store.save_memory_state(self.memory_state)
        except Exception as error:
            print(f"[Memory] 保存记忆状态失败: {error}")

        if self.memory_state.turns_since_summary < MEMORY_L2_TRIGGER_EVERY:
            return
        if (
            self.memory_summary_thread is not None
            and self.memory_summary_thread.isRunning()
        ):
            return

        recent_turns = self._recent_turns_for_summary()
        self.memory_summary_thread = MemorySummaryThread(
            recent_turns=recent_turns,
            last_summary=self.memory_state.last_summary,
            api_key=self.settings.api_key,
        )
        self.memory_summary_thread.finished_summary.connect(
            self._on_memory_summary_ready
        )
        self.memory_summary_thread.failed.connect(self._on_memory_summary_failed)
        self.memory_summary_thread.start()

        self.memory_state.turns_since_summary = 0
        try:
            self.settings_store.save_memory_state(self.memory_state)
        except Exception as error:
            print(f"[Memory] 重置轮数后保存失败: {error}")

    def _on_memory_summary_ready(self, summary_text: str) -> None:
        summary = (summary_text or "").strip()
        if not summary:
            return
        if len(summary) > MEMORY_L2_MAX_SUMMARY_CHARS:
            summary = summary[:MEMORY_L2_MAX_SUMMARY_CHARS]
        self.memory_state.last_summary = summary
        try:
            self.settings_store.save_memory_state(self.memory_state)
        except Exception as error:
            print(f"[Memory] 保存摘要失败: {error}")

    def _on_memory_summary_failed(self, error_text: str) -> None:
        print(f"[Memory Summary Failed] {error_text}")
