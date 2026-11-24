"""Окно статистики: heatmap клавиатуры, топ-10 клавиш и сводка."""

from __future__ import annotations

import time
import tkinter as tk

from . import layouts
from .constants import (
    KEYBOARD_FULL,
    KEYBOARD_TKL,
    LAYOUT_EN,
    LAYOUT_RU,
    PERIOD_ALL,
    PERIOD_TODAY,
)
from .heat import format_count, heat_color, heat_intensity, text_color
from .store import Snapshot

FONT = "Segoe UI"
BG = "#141418"
HEAT_BG = "#101013"
TEXT = "#e8e8ea"
MUTED = "#8b8f98"
ACCENT = "#e53935"
ACCENT_DARK = "#b71c1c"
BUTTON_BG = "#242429"
BUTTON_HOVER = "#33333b"
BORDER = "#2f2f37"


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", "\u2009")


class StatsWindow:
    def __init__(self, root: tk.Tk, store, settings, on_settings_change=None) -> None:
        self._root = root
        self._store = store
        self._settings = settings
        self._on_settings_change = on_settings_change

        self._snapshot: Snapshot | None = None
        self._fingerprint = None
        self._hit_boxes: list[tuple[float, float, float, float, layouts.Key, int]] = []
        self._redraw_job: str | None = None
        self._last_refresh = 0.0

        self._layout = tk.StringVar(value=str(settings.get("view_layout")))
        self._period = tk.StringVar(value=str(settings.get("view_period")))
        self._keyboard_mode = str(settings.get("keyboard_mode") or KEYBOARD_FULL)

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.title("keypress-tracker — статистика")
        self.win.configure(bg=BG)
        self.win.geometry("1180x620")
        self.win.minsize(820, 500)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        self.win.bind("<Escape>", lambda _event: self.hide())

        self._build_toolbar()
        self._build_legend()
        self._build_bottom()
        self._build_heatmap()
        self._sync_buttons()
        self._update_summary()

    # --- построение интерфейса ---------------------------------------------
    def _segment_button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=(FONT, 9, "bold"),
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            relief="flat",
            bg=BUTTON_BG,
            fg=TEXT,
            activebackground=BUTTON_HOVER,
            activeforeground=TEXT,
            highlightthickness=0,
            takefocus=0,
        )

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.win, bg=BG, padx=18, pady=14)
        bar.pack(side="top", fill="x")

        tk.Label(bar, text="Раскладка", bg=BG, fg=MUTED, font=(FONT, 9, "bold")).pack(side="left")
        self._layout_buttons: dict[str, tk.Button] = {}
        for value, label in ((LAYOUT_EN, "EN"), (LAYOUT_RU, "RU")):
            button = self._segment_button(bar, label, lambda v=value: self.set_layout(v))
            button.pack(side="left", padx=(8, 0))
            self._layout_buttons[value] = button

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=16)

        tk.Label(bar, text="Период", bg=BG, fg=MUTED, font=(FONT, 9, "bold")).pack(side="left")
        self._period_buttons: dict[str, tk.Button] = {}
        for value, label in ((PERIOD_ALL, "Всё время"), (PERIOD_TODAY, "Сегодня")):
            button = self._segment_button(bar, label, lambda v=value: self.set_period(v))
            button.pack(side="left", padx=(8, 0))
            self._period_buttons[value] = button

        self._numpad_btn = self._segment_button(bar, "", self.toggle_keyboard_mode)
        self._numpad_btn.pack(side="right")

    def _build_legend(self) -> None:
        self._legend = tk.Canvas(self.win, height=24, bg=BG, highlightthickness=0)
        self._legend.pack(side="top", fill="x", padx=18)
        self._legend.bind("<Configure>", lambda _event: self._draw_legend())

    def _build_bottom(self) -> None:
        bottom = tk.Frame(self.win, bg=BG, padx=18, pady=0)
        bottom.pack(side="bottom", fill="x", pady=(0, 12))

        header = tk.Frame(bottom, bg=BG)
        header.pack(fill="x")
        tk.Label(
            header, text="Самые частые клавиши", bg=BG, fg=TEXT, font=(FONT, 10, "bold")
        ).pack(side="left")
        self._summary = tk.Label(header, text="", bg=BG, fg=MUTED, font=(FONT, 9))
        self._summary.pack(side="right")

        self._top_canvas = tk.Canvas(bottom, height=150, bg=BG, highlightthickness=0)
        self._top_canvas.pack(fill="x", pady=(4, 0))
        self._top_canvas.bind("<Configure>", lambda _event: self._draw_top())

        self._status = tk.Label(bottom, text="", bg=BG, fg=MUTED, font=(FONT, 9), anchor="w")
        self._status.pack(fill="x", pady=(6, 0))
        self._set_status_default()

    def _build_heatmap(self) -> None:
        self._heat = tk.Canvas(self.win, bg=HEAT_BG, highlightthickness=0)
        self._heat.pack(side="top", fill="both", expand=True, padx=18, pady=(2, 10))
        self._heat.bind("<Configure>", self._schedule_redraw)
        self._heat.bind("<Motion>", self._on_hover)
        self._heat.bind("<Leave>", lambda _event: self._set_status_default())

    # --- состояние кнопок и сводка -----------------------------------------
    def _sync_buttons(self) -> None:
        for value, button in self._layout_buttons.items():
            self._style_selected(button, value == self.current_layout())
        for value, button in self._period_buttons.items():
            self._style_selected(button, value == self._period.get())
        full = self._keyboard_mode == KEYBOARD_FULL
        self._numpad_btn.configure(text=f"Цифровой блок: {'вкл' if full else 'выкл'}")
        self._style_selected(self._numpad_btn, full)

    @staticmethod
    def _style_selected(button: tk.Button, selected: bool) -> None:
        button.configure(
            bg=ACCENT if selected else BUTTON_BG,
            fg="#ffffff" if selected else TEXT,
            activebackground=ACCENT_DARK if selected else BUTTON_HOVER,
        )

    def _update_summary(self) -> None:
        total = self._store.total
        today = self._store.total_today()
        kpm = self._store.kpm()
        self._summary.configure(
            text=f"Всего {_fmt_int(total)} · сегодня {_fmt_int(today)} · {kpm} кл/мин"
        )

    def _set_status_default(self) -> None:
        self._status.configure(
            text="Наведите курсор на клавишу, чтобы увидеть точное число нажатий"
        )

    def current_layout(self) -> str:
        value = self._layout.get()
        return value if value in (LAYOUT_EN, LAYOUT_RU) else LAYOUT_EN

    def view_layout(self) -> str:
        return self.current_layout()

    # --- обновление данных --------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        if not self.is_visible():
            return
        now = time.monotonic()
        if not force and now - self._last_refresh < 1.0:
            return
        self._last_refresh = now

        snapshot = self._store.snapshot(self.current_layout(), self._period.get())
        fingerprint = (snapshot.layout, snapshot.period, tuple(sorted(snapshot.counts.items())))
        if force or fingerprint != self._fingerprint:
            self._snapshot = snapshot
            self._fingerprint = fingerprint
            self._draw_heatmap()
            self._draw_top()
            self._draw_legend()
        self._update_summary()

    # --- heatmap ------------------------------------------------------------
    def _draw_heatmap(self) -> None:
        canvas = self._heat
        snapshot = self._snapshot
        if snapshot is None:
            return
        layout = snapshot.layout or LAYOUT_EN
        include_numpad = self._keyboard_mode == KEYBOARD_FULL
        keys = layouts.placed_keys(include_numpad)
        board_w, board_h = layouts.board_size(include_numpad)

        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 200)
        pad = 12.0
        unit = min((width - 2 * pad) / board_w, (height - 2 * pad) / board_h)
        unit = max(unit, 8.0)
        ox = (width - board_w * unit) / 2
        oy = (height - board_h * unit) / 2
        gap = max(1.5, unit * 0.055)
        max_count = snapshot.max_count
        show_counts = unit >= 24

        canvas.delete("all")
        self._hit_boxes = []
        for placed in keys:
            key = placed.key
            count = snapshot.counts.get(key.vk, 0)
            intensity = heat_intensity(count, max_count)
            x0 = ox + placed.x * unit + gap / 2
            y0 = oy + placed.y * unit + gap / 2
            x1 = ox + (placed.x + key.width) * unit - gap / 2
            y1 = oy + (placed.y + key.height) * unit - gap / 2
            fill = heat_color(intensity)
            color = text_color(intensity)
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=BORDER, width=1)

            label = key.label(layout)
            label_px = max(7, int(unit * 0.30))
            if len(label) > 5:
                label_px = max(7, int(label_px * 0.78))
            count_px = max(6, int(unit * 0.24))
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            if show_counts:
                canvas.create_text(
                    cx, cy - count_px * 0.55, text=label, fill=color, font=(FONT, -label_px)
                )
                canvas.create_text(
                    cx, cy + count_px * 0.85,
                    text=format_count(count), fill=color, font=(FONT, -count_px),
                )
            else:
                canvas.create_text(cx, cy, text=label, fill=color, font=(FONT, -label_px))
            self._hit_boxes.append((x0, y0, x1, y1, key, count))

    # --- топ клавиш и легенда ----------------------------------------------
    def _draw_top(self) -> None:
        canvas = self._top_canvas
        snapshot = self._snapshot
        if snapshot is None:
            return
        layout = snapshot.layout or LAYOUT_EN
        canvas.delete("all")
        width = max(canvas.winfo_width(), 400)
        height = int(canvas.cget("height"))
        items = sorted(
            ((vk, count) for vk, count in snapshot.counts.items() if count > 0),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        if not items:
            canvas.create_text(
                width / 2, height / 2,
                text="Пока нет нажатий в этой раскладке",
                fill=MUTED, font=(FONT, 10),
            )
            return

        names = layouts.key_by_vk()
        max_top = max(count for _, count in items)
        row_h = height / len(items)
        bar_x = 150.0
        bar_max = max(width - bar_x - 90.0, 80.0)
        for index, (vk, count) in enumerate(items):
            key = names.get(vk)
            label = key.label(layout) if key else f"VK {vk:02X}"
            intensity = heat_intensity(count, max_top)
            color = heat_color(intensity)
            top = index * row_h
            canvas.create_rectangle(0, top + 2, 5, top + row_h - 4, fill=color, outline="")
            canvas.create_text(
                14, top + row_h / 2 - 1, text=label, anchor="w", fill=TEXT, font=(FONT, -11)
            )
            bar_w = bar_max * (count / max_top)
            canvas.create_rectangle(
                bar_x, top + row_h * 0.28,
                bar_x + max(bar_w, 2), top + row_h * 0.72,
                fill=color, outline="",
            )
            canvas.create_text(
                width - 6, top + row_h / 2 - 1,
                text=_fmt_int(count), anchor="e", fill=MUTED, font=(FONT, -10),
            )

    def _draw_legend(self) -> None:
        canvas = self._legend
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        max_count = self._snapshot.max_count if self._snapshot else 0
        x0 = 46.0
        x1 = width - 180.0
        if x1 - x0 < 40:
            return
        y0, y1 = 6.0, 18.0
        steps = 90
        for index in range(steps):
            t0 = index / steps
            canvas.create_rectangle(
                x0 + (x1 - x0) * index / steps, y0,
                x0 + (x1 - x0) * (index + 1) / steps + 1, y1,
                fill=heat_color(t0), outline="",
            )
        canvas.create_text(x0 - 8, 12, text="0", anchor="e", fill=MUTED, font=(FONT, 8))
        canvas.create_text(
            x1 + 8, 12,
            text=f"… {_fmt_int(max_count)} нажатий",
            anchor="w", fill=MUTED, font=(FONT, 8),
        )

    # --- отложенная перерисовка при изменении размера ----------------------
    def _schedule_redraw(self, _event=None) -> None:
        if not self.is_visible():
            return
        if self._redraw_job is not None:
            try:
                self.win.after_cancel(self._redraw_job)
            except tk.TclError:
                pass
        self._redraw_job = self.win.after(80, self._redraw_cached)

    def _redraw_cached(self) -> None:
        self._redraw_job = None
        self._draw_heatmap()
        self._draw_top()
        self._draw_legend()

    def _on_hover(self, event: tk.Event) -> None:
        for x0, y0, x1, y1, key, count in self._hit_boxes:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                label = key.label(self.current_layout())
                self._status.configure(
                    text=f"{label} · VK 0x{key.vk:02X} · {_fmt_int(count)} нажатий"
                )
                return
        self._set_status_default()

    # --- переключатели ------------------------------------------------------
    def set_layout(self, value: str) -> None:
        if value not in (LAYOUT_EN, LAYOUT_RU):
            return
        self._layout.set(value)
        self._settings.set("view_layout", value)
        self._settings.save()
        self._sync_buttons()
        self.refresh(force=True)
        if self._on_settings_change is not None:
            self._on_settings_change()

    def set_period(self, value: str) -> None:
        if value not in (PERIOD_ALL, PERIOD_TODAY):
            return
        self._period.set(value)
        self._settings.set("view_period", value)
        self._settings.save()
        self._sync_buttons()
        self.refresh(force=True)
        if self._on_settings_change is not None:
            self._on_settings_change()

    def toggle_keyboard_mode(self) -> None:
        self._keyboard_mode = (
            KEYBOARD_TKL if self._keyboard_mode == KEYBOARD_FULL else KEYBOARD_FULL
        )
        self._settings.set("keyboard_mode", self._keyboard_mode)
        self._settings.save()
        self._sync_buttons()
        self.refresh(force=True)
        if self._on_settings_change is not None:
            self._on_settings_change()

    # --- видимость ----------------------------------------------------------
    def is_visible(self) -> bool:
        try:
            return bool(self.win.winfo_exists()) and self.win.state() != "withdrawn"
        except tk.TclError:
            return False

    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()
        try:
            self.win.focus_force()
        except tk.TclError:
            pass
        self.refresh(force=True)

    def hide(self) -> None:
        self.win.withdraw()

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def destroy(self) -> None:
        if self._redraw_job is not None:
            try:
                self.win.after_cancel(self._redraw_job)
            except tk.TclError:
                pass
            self._redraw_job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


