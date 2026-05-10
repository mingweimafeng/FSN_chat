import multiprocessing
multiprocessing.freeze_support()

from chat_app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
