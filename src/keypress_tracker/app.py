"""Точка входа и связка компонентов приложения."""

from __future__ import annotations

import argparse
import queue
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from . import win32
from .capture import KeyCapture
from .constants import APP_NAME, __version__
from .overlay import Overlay
from .stats_window import StatsWindow
from .store import Settings, StatsStore


class Application:
    """Владеет окнами, хранилищем и потоком перехвата."""

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        debug: bool = False,
        reset: bool = False,
    ) -> None:
        self.settings = Settings(data_dir)
        self.store = StatsStore(data_dir)
        if reset:
            self.store.reset()

        self._shutdown = False
        self._running = False
        self._hotkeys: queue.SimpleQueue[str] = queue.SimpleQueue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)

        self.overlay = Overlay(self.root, self)
        self.stats = StatsWindow(self.root, self.store, self.settings)
        self.capture = KeyCapture(self.store, on_hotkey=self._hotkeys.put, debug=debug)

    # --- вызывается из UI ---------------------------------------------------
    def show_stats(self) -> None:
        self.stats.show()

    def view_layout(self) -> str:
        return self.stats.view_layout()

    def set_view_layout(self, value: str) -> None:
        self.stats.set_layout(value)

    def confirm_reset(self) -> None:
        parent = None
        if self.stats.is_visible():
            parent = self.stats.win
        elif self.overlay.visible:
            parent = self.overlay.win
        confirmed = messagebox.askyesno(
            "Сброс статистики",
            "Удалить всю накопленную статистику нажатий?",
            parent=parent,
        )
        if confirmed:
            self.store.reset()
            self.stats.refresh(force=True)

    def request_quit(self) -> None:
        self._running = False
        self.root.quit()

    # --- основной цикл ------------------------------------------------------
    def run(self) -> None:
        try:
            self.capture.start()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.shutdown()
            win32.message_box(
                f"Не удалось запустить перехват клавиатуры.\n\n{exc}",
                APP_NAME,
                error=True,
            )
            return

        self._running = True
        self.root.after(200, self._tick)
        try:
            self.root.mainloop()
        finally:
            self.shutdown()

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            self._drain_hotkeys()
            if self.overlay.visible:
                self.overlay.set_values(
                    self.store.total, self.store.last_layout, self.store.kpm()
                )
            self.stats.refresh()
        except Exception:  # noqa: BLE001 - UI-цикл не должен падать
            traceback.print_exc()
        if self._running:
            self.root.after(250, self._tick)

    def _drain_hotkeys(self) -> None:
        while True:
            try:
                action = self._hotkeys.get_nowait()
            except queue.Empty:
                return
            if action == "stats":
                self.stats.toggle()
            elif action == "overlay":
                self.overlay.toggle()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._running = False
        self.capture.stop()
        self.stats.destroy()
        self.overlay.destroy()
        self.store.stop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Глобальный счётчик нажатий клавиш с heatmap-статистикой.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="печатать события клавиатуры в консоль"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="каталог для stats.json и settings.json",
    )
    parser.add_argument(
        "--reset", action="store_true", help="сбросить статистику при запуске"
    )
    parser.add_argument("--version", action="store_true", help="показать версию и выйти")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {__version__}")
        return

    win32.set_dpi_awareness()
    if not win32.acquire_single_instance():
        win32.message_box(
            "keypress-tracker уже запущен.\n"
            "Откройте статистику из меню оверлея (правая кнопка мыши).",
            APP_NAME,
        )
        return

    try:
        app = Application(data_dir=args.data_dir, debug=args.debug, reset=args.reset)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        win32.message_box(f"Не удалось запустить приложение:\n{exc}", APP_NAME, error=True)
        return

    try:
        app.run()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        win32.message_box(f"Ошибка приложения:\n{exc}", APP_NAME, error=True)
