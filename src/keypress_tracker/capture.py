"""Глобальный перехват клавиатуры через WH_KEYBOARD_LL (ctypes)."""

from __future__ import annotations

import ctypes
import threading
import traceback
from typing import Callable

from . import win32
from .constants import LAYOUT_EN, LAYOUT_OTHER
from .layouts import active_layout

# Ctrl+Alt+K — статистика, Ctrl+Alt+O — оверлей.
HOTKEYS = {0x4B: "stats", 0x4F: "overlay"}


class KeyCapture(threading.Thread):
    """Поток с низкоуровневым хуком клавиатуры.

    Колбэк хука обязан быть очень быстрым: только счётчики, без работы с UI.
    """

    def __init__(
        self,
        store,
        on_hotkey: Callable[[str], None] | None = None,
        *,
        debug: bool = False,
    ) -> None:
        super().__init__(name="keypress-capture", daemon=True)
        self._store = store
        self._on_hotkey = on_hotkey
        self._debug = debug
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._pressed: set[int] = set()
        self._last_layout = LAYOUT_EN

    # --- жизненный цикл -----------------------------------------------------
    def start(self) -> None:
        super().start()
        self.wait_ready()

    def wait_ready(self, timeout: float = 5.0) -> None:
        if not self._ready.wait(timeout):
            raise RuntimeError("не удалось запустить перехват клавиатуры (таймаут)")
        if self._error is not None:
            raise RuntimeError(f"не удалось запустить перехват клавиатуры: {self._error}")

    def run(self) -> None:
        msg = win32.wintypes.MSG()
        try:
            self._thread_id = win32.kernel32.GetCurrentThreadId()
            # Очередь сообщений создаём заранее, иначе PostThreadMessage может
            # прийти до её появления и потеряться.
            win32.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, win32.PM_NOREMOVE)
            self._proc = win32.LowLevelKeyboardProc(self._hook_callback)
            self._hook = win32.user32.SetWindowsHookExW(
                win32.WH_KEYBOARD_LL,
                self._proc,
                win32.kernel32.GetModuleHandleW(None),
                0,
            )
            if not self._hook:
                code = ctypes.get_last_error()
                raise OSError(code, "SetWindowsHookExW(WH_KEYBOARD_LL) не удался")
        except BaseException as exc:  # noqa: BLE001 - ошибку отдаём в UI
            self._error = exc
            self._ready.set()
            return

        self._ready.set()
        if self._debug:
            print(f"[capture] хук установлен (поток {self._thread_id})", flush=True)
        try:
            while True:
                result = win32.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                win32.user32.TranslateMessage(ctypes.byref(msg))
                win32.user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self._hook:
                win32.user32.UnhookWindowsHookEx(self._hook)
                self._hook = None
            if self._debug:
                print("[capture] хук снят", flush=True)

    def stop(self) -> None:
        if self._thread_id:
            posted = win32.user32.PostThreadMessageW(self._thread_id, win32.WM_QUIT, 0, 0)
            if not posted and self._debug:
                error = ctypes.get_last_error()
                print(f"[capture] PostThreadMessageW не удался: {error}", flush=True)
        if self.is_alive():
            self.join(timeout=2.0)

    # --- обработка событий --------------------------------------------------
    def _hook_callback(self, code: int, w_param: int, l_param: int):
        try:
            if code >= 0:
                pointer = ctypes.cast(
                    ctypes.c_void_p(l_param), ctypes.POINTER(win32.KBDLLHOOKSTRUCT)
                )
                if self._handle_event(w_param, pointer.contents):
                    return 1  # хоткей обработан — не пропускаем символ в приложение
        except Exception:  # noqa: BLE001 - из колбэка нельзя выпускать исключения
            if self._debug:
                traceback.print_exc()
        return win32.user32.CallNextHookEx(self._hook, code, w_param, l_param)

    def _handle_event(self, message: int, info) -> bool:
        """Возвращает True, если событие нужно подавить (сработал хоткей)."""
        if info.flags & win32.LLKHF_INJECTED:
            return False
        vk = int(info.vkCode)
        scan = int(info.scanCode)
        if message in (win32.WM_KEYDOWN, win32.WM_SYSKEYDOWN):
            repeated = scan in self._pressed
            self._pressed.add(scan)
            if not repeated:
                return self._handle_press(vk, scan)
        elif message in (win32.WM_KEYUP, win32.WM_SYSKEYUP):
            self._pressed.discard(scan)
        return False

    def _handle_press(self, vk: int, scan: int) -> bool:
        layout = self._detect_layout()
        self._store.press(vk, layout)
        is_hotkey = False
        if (
            self._on_hotkey is not None
            and win32.is_key_down(win32.VK_CONTROL)
            and win32.is_key_down(win32.VK_MENU)
        ):
            action = HOTKEYS.get(vk)
            if action is not None:
                is_hotkey = True
                try:
                    self._on_hotkey(action)
                except Exception:  # noqa: BLE001
                    if self._debug:
                        traceback.print_exc()
        if self._debug:
            total = self._store.total
            print(
                f"[capture] vk=0x{vk:02X} scan={scan:3d} layout={layout} total={total}",
                flush=True,
            )
        return is_hotkey

    def _detect_layout(self) -> str:
        try:
            layout = active_layout()
        except Exception:  # noqa: BLE001 - Win32 может не ответить
            layout = LAYOUT_OTHER
        if layout == LAYOUT_OTHER:
            return self._last_layout
        self._last_layout = layout
        return layout
