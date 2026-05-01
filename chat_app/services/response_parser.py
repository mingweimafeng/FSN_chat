from __future__ import annotations

import json
from dataclasses import dataclass

from chat_app.config import CHARACTER_EMOTIONS, MIN_REPLY_CHARS


@dataclass
class ParsedChatResponse:
    narration: str
    emotion: str
    reply: str
    jp_translation: str
    segments: list[dict[str, str]]
    raw_content: str
    parse_mode: str

    def to_payload(self) -> dict:
        return {
            "narration": self.narration,
            "emotion": self.emotion,
            "reply": self.reply,
            "jp_translation": self.jp_translation,
            "segments": self.segments,
            "_raw_content": self.raw_content,
            "_parse_mode": self.parse_mode,
        }


class ChatResponseParser:
    def parse(self, raw_content: str) -> ParsedChatResponse:
        raw_text = (raw_content or "").strip()
        payload, parse_mode = self._load_payload(raw_text)
        if payload is None:
            fallback_text = raw_text or "..."
            segments = self._split_to_segments(fallback_text, fallback_text, "normal")
            return ParsedChatResponse(
                narration="",
                emotion="normal",
                reply=fallback_text,
                jp_translation=fallback_text,
                segments=segments,
                raw_content=raw_text,
                parse_mode=parse_mode,
            )

        narration = str(payload.get("narration", "")).strip()
        emotion = self._normalize_emotion(str(payload.get("emotion", "normal")).strip().lower())
        reply = str(payload.get("reply", "")).strip() or "..."
        jp_translation = str(payload.get("jp_translation", "")).strip() or reply

        if len(reply) < MIN_REPLY_CHARS:
            reply += " 我会认真回应你，也会把现在的心情和想法说得更完整一些。"
        if len(jp_translation) < MIN_REPLY_CHARS:
            jp_translation += " もっと丁寧に、今の気持ちと考えをきちんと伝えるね。"

        segments = self._parse_segments(payload.get("segments"), emotion, reply, jp_translation)
        return ParsedChatResponse(
            narration=narration,
            emotion=emotion,
            reply=reply,
            jp_translation=jp_translation,
            segments=segments,
            raw_content=raw_text,
            parse_mode=parse_mode,
        )

    def _load_payload(self, raw_text: str) -> tuple[dict | None, str]:
        if not raw_text:
            return None, "empty"

        candidates = [raw_text]
        stripped_fence = self._strip_code_fence(raw_text)
        if stripped_fence != raw_text:
            candidates.append(stripped_fence)

        extracted_json = self._extract_first_json_object(raw_text)
        if extracted_json and extracted_json not in candidates:
            candidates.append(extracted_json)

        if stripped_fence:
            extracted_from_fence = self._extract_first_json_object(stripped_fence)
            if extracted_from_fence and extracted_from_fence not in candidates:
                candidates.append(extracted_from_fence)

        for index, candidate in enumerate(candidates):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload, f"json_candidate_{index}"

        return None, "fallback_plain_text"

    def _strip_code_fence(self, text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if not lines:
            return stripped
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _extract_first_json_object(self, text: str) -> str:
        start = -1
        depth = 0
        in_string = False
        escaped = False

        for index, ch in enumerate(text):
            if start < 0:
                if ch == "{":
                    start = index
                    depth = 1
                    in_string = False
                    escaped = False
                continue

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1].strip()

        return ""

    def _normalize_emotion(self, emotion: str) -> str:
        return emotion if emotion in CHARACTER_EMOTIONS else "normal"

    def _parse_segments(self, raw_segments, fallback_emotion: str, reply: str, jp_translation: str) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        if isinstance(raw_segments, list):
            for item in raw_segments:
                if not isinstance(item, dict):
                    continue
                seg_reply = str(item.get("reply", "")).strip()
                if not seg_reply:
                    continue
                seg_emotion = self._normalize_emotion(str(item.get("emotion", fallback_emotion)).strip().lower())
                seg_jp = str(item.get("jp_translation", "")).strip() or seg_reply
                normalized.append({"emotion": seg_emotion, "reply": seg_reply, "jp_translation": seg_jp})

        return normalized or self._split_to_segments(reply, jp_translation, fallback_emotion)

    def _split_to_segments(self, reply: str, jp_translation: str, emotion: str) -> list[dict[str, str]]:
        reply_parts = self._split_sentences(reply)
        jp_parts = self._split_sentences(jp_translation)
        segments: list[dict[str, str]] = []
        for idx, part in enumerate(reply_parts):
            jp_part = jp_parts[idx] if idx < len(jp_parts) else (jp_parts[-1] if jp_parts else part)
            segments.append({"emotion": emotion, "reply": part, "jp_translation": jp_part})
        return segments or [{"emotion": emotion, "reply": reply, "jp_translation": jp_translation}]

    def _split_sentences(self, text: str) -> list[str]:
        source = (text or "...").strip()
        if not source:
            return ["..."]
        parts: list[str] = []
        current = ""
        for ch in source:
            current += ch
            if ch in "。！？!?」』":
                parts.append(current.strip())
                current = ""
        if current.strip():
            parts.append(current.strip())
        return parts or [source]
