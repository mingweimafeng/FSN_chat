from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chat_app.config import HISTORY_FILE_PATH


@dataclass
class HistoryRecord:
    id: str
    timestamp: str
    user_text: str
    reply_text: str


class ChatHistoryStore:
    def __init__(self, file_path: Path = HISTORY_FILE_PATH) -> None:
        self.file_path = file_path

    def load_records(self) -> list[HistoryRecord]:
        if not self.file_path.exists():
            return []
        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        records: list[HistoryRecord] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                record_id = str(item.get("id", "")).strip()
                timestamp = str(item.get("timestamp", "")).strip()
                user_text = str(item.get("user_text", "")).strip()
                reply_text = str(item.get("reply_text", "")).strip()
                if not record_id or not timestamp:
                    continue
                records.append(HistoryRecord(record_id, timestamp, user_text, reply_text))
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records

    def append_record(self, user_text: str, reply_text: str) -> HistoryRecord:
        record = HistoryRecord(
            id=f"h_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_text=user_text,
            reply_text=reply_text,
        )
        records = self.load_records()
        records.insert(0, record)
        self._save(records)
        return record

    def delete_record(self, record_id: str) -> bool:
        records = self.load_records()
        new_records = [record for record in records if record.id != record_id]
        if len(new_records) == len(records):
            return False
        self._save(new_records)
        return True

    def delete_by_hour(self, hour_key: str) -> int:
        normalized = hour_key.strip()
        if len(normalized) < 13:
            return 0
        records = self.load_records()
        new_records = [record for record in records if not record.timestamp.startswith(normalized)]
        deleted_count = len(records) - len(new_records)
        if deleted_count > 0:
            self._save(new_records)
        return deleted_count

    def delete_by_date(self, date_key: str) -> int:
        normalized = date_key.strip()
        if len(normalized) < 10:
            return 0
        records = self.load_records()
        new_records = [record for record in records if not record.timestamp.startswith(normalized)]
        deleted_count = len(records) - len(new_records)
        if deleted_count > 0:
            self._save(new_records)
        return deleted_count

    def _save(self, records: list[HistoryRecord]) -> None:
        payload = [
            {
                "id": record.id,
                "timestamp": record.timestamp,
                "user_text": record.user_text,
                "reply_text": record.reply_text,
            }
            for record in records
        ]
        tmp_path = self.file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp_path.replace(self.file_path)
        except OSError:
            shutil.move(str(tmp_path), str(self.file_path))

    def get_recent_turns(self, limit: int, chronological: bool = True) -> list[HistoryRecord]:
        if limit <= 0:
            return []
        recent = self.load_records()[:limit]
        if chronological:
            recent.reverse()
        return recent
