from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from chat_app.config import BACKGROUND_DIR, _BASE
from chat_app.ui.window import BackgroundWindow

GENIE_DATA_DIR = _BASE / "GenieData"


def _preflight_genie_data() -> None:
    if os.path.exists(GENIE_DATA_DIR):
        return
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("Genie Data Missing")
    msg_box.setText("GenieData folder not found.\nWould you like to download it automatically from HuggingFace?")
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.Yes)

    if msg_box.exec() != QMessageBox.Yes:
        return

    msg_box_progress = QMessageBox()
    msg_box_progress.setIcon(QMessageBox.Information)
    msg_box_progress.setWindowTitle("Downloading")
    msg_box_progress.setText("Downloading Genie-TTS resources... Please wait (this might take a while and the dialog will close when done).")
    msg_box_progress.setStandardButtons(QMessageBox.NoButton)
    msg_box_progress.show()
    QApplication.processEvents()

    try:
        from genie_tts import download_genie_data
        download_genie_data()
    except Exception as exc:
        QMessageBox.critical(None, "Download failed", f"Failed to download data: {exc}")
    finally:
        msg_box_progress.accept()


def main() -> int:
    # ========== 日志配置 ==========
    # 优先级（从高到低）：
    #   1. 命令行参数：--debug / -d / --verbose / -v
    #   2. 环境变量：FSN_LOG_LEVEL=DEBUG / INFO / WARNING
    #   3. 默认值：INFO

    if "--debug" in sys.argv or "-d" in sys.argv:
        log_level = logging.DEBUG
        print("🔍 [DEBUG 模式] 已启用 - 将显示所有调试信息")
    elif "--verbose" in sys.argv or "-v" in sys.argv:
        log_level = logging.DEBUG
        print("📝 [VERBOSE 模式] 已启用 - 显示详细信息")
    else:
        # 从环境变量读取（如果设置的话）
        env_level = os.getenv("FSN_LOG_LEVEL", "").upper()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        log_level = level_map.get(env_level, logging.INFO)
        if env_level and env_level in level_map:
            print(f"📊 [日志级别] 通过环境变量设置为: {env_level}")

    logging.basicConfig(
        level=log_level,
        format='%(message)s',
        datefmt='%H:%M:%S',
    )
    # ==============================

    app = QApplication(sys.argv)
    _preflight_genie_data()

    window = BackgroundWindow(BACKGROUND_DIR)
    if not BACKGROUND_DIR.exists():
        QMessageBox.warning(window, "Missing folder", f"Background folder not found:\n{BACKGROUND_DIR}")
    window.ready.connect(window.show)
    return app.exec()
