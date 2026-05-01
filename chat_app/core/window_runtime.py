from __future__ import annotations


class VirtualTimer:
    """Lightweight timer state driven by a shared heartbeat timer."""

    def __init__(self, interval_ms: int = 0, single_shot: bool = False) -> None:
        self._interval_ms = max(0, int(interval_ms))
        self._single_shot = single_shot
        self._remaining_ms = self._interval_ms
        self._active = False

    def setInterval(self, interval_ms: int) -> None:
        self._interval_ms = max(0, int(interval_ms))
        if not self._active:
            self._remaining_ms = self._interval_ms

    def setSingleShot(self, single_shot: bool) -> None:
        self._single_shot = bool(single_shot)

    def start(self, interval_ms: int | None = None) -> None:
        if interval_ms is not None:
            self.setInterval(interval_ms)
        self._active = True
        self._remaining_ms = self._interval_ms

    def stop(self) -> None:
        self._active = False

    def isActive(self) -> bool:
        return self._active

    def tick(self, delta_ms: int) -> bool:
        if not self._active:
            return False
        self._remaining_ms -= max(0, int(delta_ms))
        if self._remaining_ms > 0:
            return False
        if self._single_shot:
            self._active = False
        self._remaining_ms = self._interval_ms
        return True

