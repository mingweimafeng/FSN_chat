from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chat_app.config import DEFAULT_ROLE_PROMPT, DEFAULT_USER_PROFILE_PROMPT
from chat_app.data.history_store import ChatHistoryStore, HistoryRecord
from chat_app.data.settings_store import AppSettings, SettingsStore


class HistoryDialog(QDialog):
    def __init__(
        self,
        store: ChatHistoryStore,
        settings_store: SettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.settings_store = settings_store or SettingsStore()
        self.records: list[HistoryRecord] = []

        self.setWindowTitle("历史记录")
        self.resize(760, 520)

        root_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["分组/时间", "用户输入", "角色回复"])
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("记忆摘要（可编辑）", self))
        self.summary_edit = QPlainTextEdit(self)
        self.summary_edit.setPlaceholderText("这里显示用于长期记忆的摘要，可在此修改并保存。")
        self.summary_edit.setMaximumHeight(120)
        right_layout.addWidget(self.summary_edit)

        summary_btn_row = QHBoxLayout()
        self.save_summary_btn = QPushButton("保存记忆摘要", self)
        self.reload_summary_btn = QPushButton("重新读取摘要", self)
        self.save_summary_btn.clicked.connect(self.save_memory_summary)
        self.reload_summary_btn.clicked.connect(self.load_memory_summary)
        summary_btn_row.addWidget(self.save_summary_btn)
        summary_btn_row.addWidget(self.reload_summary_btn)
        right_layout.addLayout(summary_btn_row)

        self.detail_box = QPlainTextEdit(self)
        self.detail_box.setReadOnly(True)

        btn_row = QHBoxLayout()
        self.delete_selected_btn = QPushButton("删除选中", self)
        self.delete_hour_btn = QPushButton("按小时删除", self)
        self.delete_date_btn = QPushButton("按日期删除", self)
        self.refresh_btn = QPushButton("刷新", self)

        self.delete_selected_btn.clicked.connect(self.delete_selected_record)
        self.delete_hour_btn.clicked.connect(self.delete_by_selected_hour)
        self.delete_date_btn.clicked.connect(self.delete_by_selected_date)
        self.refresh_btn.clicked.connect(self.reload)

        for btn in (self.delete_selected_btn, self.delete_hour_btn, self.delete_date_btn, self.refresh_btn):
            btn_row.addWidget(btn)

        right_layout.addWidget(self.detail_box)
        right_layout.addLayout(btn_row)

        splitter.addWidget(self.tree)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 380])

        root_layout.addWidget(splitter)

        self.load_memory_summary()
        self.reload()

    def load_memory_summary(self) -> None:
        memory_state = self.settings_store.load_memory_state()
        self.summary_edit.setPlainText(memory_state.last_summary)

    def save_memory_summary(self) -> None:
        memory_state = self.settings_store.load_memory_state()
        memory_state.last_summary = self.summary_edit.toPlainText().strip()
        self.settings_store.save_memory_state(memory_state)
        QMessageBox.information(self, "提示", "记忆摘要已保存。")

    def reload(self) -> None:
        self.records = self.store.load_records()
        self.tree.clear()
        self.detail_box.clear()

        grouped_by_date: OrderedDict[str, list[HistoryRecord]] = OrderedDict()
        for record in self.records:
            date_key = record.timestamp[:10]
            grouped_by_date.setdefault(date_key, []).append(record)

        for date_key, date_records in grouped_by_date.items():
            date_item = QTreeWidgetItem([date_key, "", ""])
            date_item.setData(0, Qt.UserRole, {"level": "date", "key": date_key})
            self.tree.addTopLevelItem(date_item)

            hour_groups: OrderedDict[str, list[HistoryRecord]] = OrderedDict()
            for record in date_records:
                hour_key = record.timestamp[:13]
                hour_groups.setdefault(hour_key, []).append(record)

            for hour_key, hour_records in hour_groups.items():
                hour_item = QTreeWidgetItem([f"{hour_key}:00", "", ""])
                hour_item.setData(0, Qt.UserRole, {"level": "hour", "key": hour_key})
                date_item.addChild(hour_item)

                for record in hour_records:
                    user_preview = record.user_text.replace("\n", " ").strip()
                    reply_preview = record.reply_text.replace("\n", " ").strip()
                    child = QTreeWidgetItem([record.timestamp[-8:], user_preview[:30], reply_preview[:30]])
                    child.setData(0, Qt.UserRole, {"level": "record", "id": record.id})
                    hour_item.addChild(child)

            date_item.setExpanded(True)

    def on_selection_changed(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            self.detail_box.clear()
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")

        if level == "record":
            record_id = payload.get("id", "")
            record = self.find_record(record_id)
            if record is None:
                self.detail_box.clear()
                return
            self.detail_box.setPlainText(
                f"时间: {record.timestamp}\n\n你:\n{record.user_text}\n\nArcueid:\n{record.reply_text}"
            )
        elif level == "hour":
            self.detail_box.setPlainText(f"当前选中小时: {payload.get('key', '')}:00\n可点击“按小时删除”。")
        elif level == "date":
            self.detail_box.setPlainText(f"当前选中日期: {payload.get('key', '')}\n可点击“按日期删除”。")
        else:
            self.detail_box.clear()

    def find_record(self, record_id: str) -> HistoryRecord | None:
        for record in self.records:
            if record.id == record_id:
                return record
        return None

    def delete_selected_record(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        if payload.get("level") != "record":
            QMessageBox.information(self, "提示", "请先选中具体记录再删除。")
            return
        record_id = str(payload.get("id", "")).strip()
        if not record_id:
            return
        if QMessageBox.question(self, "确认", "确定删除这条历史记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_record(record_id)
        self.reload()

    def delete_by_selected_hour(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")
        if level == "record":
            record = self.find_record(str(payload.get("id", "")))
            hour_key = record.timestamp[:13] if record else ""
        elif level == "hour":
            hour_key = str(payload.get("key", "")).strip()
        else:
            hour_key = ""
        if not hour_key:
            QMessageBox.information(self, "提示", "请选中某小时或该小时内的一条记录。")
            return
        if QMessageBox.question(self, "确认", f"确定删除 {hour_key}:00 的全部记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_by_hour(hour_key)
        self.reload()

    def delete_by_selected_date(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")
        if level == "record":
            record = self.find_record(str(payload.get("id", "")))
            date_key = record.timestamp[:10] if record else ""
        elif level == "hour":
            date_key = str(payload.get("key", ""))[:10]
        elif level == "date":
            date_key = str(payload.get("key", "")).strip()
        else:
            date_key = ""

        if not date_key:
            QMessageBox.information(self, "提示", "请选中某日期/小时或该日期内的一条记录。")
            return
        if QMessageBox.question(self, "确认", f"确定删除 {date_key} 的全部记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_by_date(date_key)
        self.reload()





class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(760, 560)

        self.original_fixed_requirements_prompt = settings.fixed_requirements_prompt
        self.role_edit = QPlainTextEdit(self)
        self.user_profile_edit = QPlainTextEdit(self)
        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("请输入 API 密钥")

        self.role_edit.setPlainText(settings.role_prompt)
        self.user_profile_edit.setPlainText(settings.user_profile_prompt)
        self.api_key_edit.setText(settings.api_key)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("API 密钥", self))
        root.addWidget(self.api_key_edit)
        root.addWidget(QLabel("角色提示词", self))
        root.addWidget(self.role_edit)
        root.addWidget(QLabel("用户档案", self))
        root.addWidget(self.user_profile_edit)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认", self)
        save_btn = QPushButton("保存", self)
        cancel_btn = QPushButton("取消", self)

        reset_btn.clicked.connect(self.reset_defaults)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    def reset_defaults(self) -> None:
        self.role_edit.setPlainText(DEFAULT_ROLE_PROMPT)
        self.user_profile_edit.setPlainText(DEFAULT_USER_PROFILE_PROMPT)

    def to_settings(self) -> AppSettings:
        return AppSettings(
            fixed_requirements_prompt=self.original_fixed_requirements_prompt,
            role_prompt=self.role_edit.toPlainText().strip() or DEFAULT_ROLE_PROMPT,
            user_profile_prompt=self.user_profile_edit.toPlainText().strip() or DEFAULT_USER_PROFILE_PROMPT,
            api_key=self.api_key_edit.text().strip(),
        )