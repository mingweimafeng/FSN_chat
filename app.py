import sys
import os

# Patch standard streams for PyInstaller noconsole mode on Windows multiprocessing
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

# Add the directory containing the executable to sys.path so that external config.py can be loaded
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)

from chat_app.main import main
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
