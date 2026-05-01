import sys
import os

# Patch standard streams for PyInstaller noconsole mode on Windows multiprocessing
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

from chat_app.main import main
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
