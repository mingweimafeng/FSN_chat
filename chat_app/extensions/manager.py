from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from chat_app.extensions.api import BaseExtension, ExtensionContext

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ExtensionLoadResult:
    """记录批量加载结果，供主窗口日志展示。"""
    loaded: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ExtensionManager:
    """插件管理器：动态发现、加载、生命周期管理。

    初始化时接收 ExtensionContext（沙盒）和插件包路径，
    通过 pkgutil 自动扫描目标包下所有继承 BaseExtension 的类，
    实例化并注入上下文后调用 on_start()。
    """

    def __init__(self, context: ExtensionContext, plugin_package: str) -> None:
        self._context = context
        self._plugin_package = plugin_package
        self._extensions: list[BaseExtension] = []
        self._mouse_observers: list[Callable[[], None]] = []

    def load_all_extensions(self) -> ExtensionLoadResult:
        result = ExtensionLoadResult()

        try:
            pkg = importlib.import_module(self._plugin_package)
        except ModuleNotFoundError as exc:
            result.failed += 1
            result.errors.append(f"插件包 {self._plugin_package} 未找到: {exc}")
            return result

        module_names = self._discover_plugin_modules(pkg)

        for name in module_names:
            full_module = f"{self._plugin_package}.{name}"

            try:
                module = importlib.import_module(full_module)
            except Exception as exc:
                result.failed += 1
                msg = f"导入 {full_module} 失败: {exc}"
                result.errors.append(msg)
                traceback.print_exc()
                continue

            for _, cls in inspect.getmembers(module, inspect.isclass):
                if cls is BaseExtension or not issubclass(cls, BaseExtension):
                    continue
                try:
                    instance: BaseExtension = cls()
                    instance.set_context(self._context)
                    instance.on_start()
                    self._extensions.append(instance)

                    if hasattr(instance, 'on_mouse_moved'):
                        self._mouse_observers.append(instance.on_mouse_moved)

                    result.loaded += 1
                    print(f"[Extension] 加载成功: {instance.name}", flush=True)
                except Exception as exc:
                    result.failed += 1
                    msg = f"实例化 {cls.__name__} 失败: {exc}"
                    result.errors.append(msg)
                    traceback.print_exc()

        return result

    def _discover_plugin_modules(self, pkg) -> list[str]:
        names: list[str] = []
        try:
            for info in pkgutil.iter_modules(pkg.__path__):
                names.append(info.name)
        except Exception:
            pass

        if names:
            return names

        if getattr(sys, "frozen", False):
            for candidate in ("music_player", "cursor_idle_hider"):
                full = f"{self._plugin_package}.{candidate}"
                try:
                    importlib.import_module(full)
                    names.append(candidate)
                except ImportError:
                    pass

        return names

    def unload_all(self) -> None:
        """卸载所有插件，逐个调用 on_stop() 进行清理。"""
        for ext in self._extensions:
            try:
                ext.on_stop()
                print(f"[Extension] 卸载: {ext.name}", flush=True)
            except Exception as exc:
                print(f"[Extension] 卸载 {ext.name} 出错: {exc}", flush=True)
        self._extensions.clear()
        self._mouse_observers.clear()

    def process_user_input(self, text: str) -> str | None:
        """遍历所有激活插件，触发输入拦截钩子。

        若某插件返回非空字符串，立即短路并返回该字符串，
        否则返回 None（继续正常聊天流程）。
        """
        for ext in self._extensions:
            try:
                result = ext.on_user_input_intercept(text)
            except Exception as exc:
                print(
                    f"[Extension] {ext.name}.on_user_input_intercept 异常: {exc}",
                    flush=True,
                )
                continue
            if isinstance(result, str) and result.strip():
                print(
                    f"[Extension] {ext.name} 拦截了输入: {result[:40]}",
                    flush=True,
                )
                return result.strip()
        return None

    def notify_mouse_moved(self) -> None:
        """通知所有关注鼠标移动的插件：鼠标刚刚移动了。

        由主窗口的 mouseMoveEvent 中调用。
        """
        for observer in self._mouse_observers:
            try:
                observer()
            except Exception as exc:
                print(f"[Extension] mouse observer 异常: {exc}", flush=True)

    @property
    def active_extensions(self) -> list[BaseExtension]:
        """当前激活的插件只读列表。"""
        return list(self._extensions)
