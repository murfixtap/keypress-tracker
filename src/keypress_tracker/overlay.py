"""Плавающее полупрозрачное окно со счётчиком нажатий."""

from __future__ import annotations

import tkinter as tk

from .constants import LAYOUT_BADGE, LAYOUT_EN, LAYOUT_RU

FONT = "Segoe UI"
BG = "#1b1b20"
FG = "#f5f5f7"
MUTED = "#9aa0a6"
ACCENT = "#e53935"
BORDER = "#3a3a42"
TRANSPARENT = "#010203"


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", "\u2009")


class Overlay:
    """Небольшое always-on-top окно; перетаскивается мышью."""

    WIDTH = 262
    HEIGHT = 98

    def __init__(self, root: tk.Tk, app) -> None:
        self._app = app
        self._settings = app.settings
        self._visible = bool(self._settings.get("overlay_visible"))
        self._drag_offset: tuple[int, int] | None = None
        self._last_values: tuple[int, str, int] | None = None
        self._menu: tk.Menu | None = None

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.title("keypress-tracker")
        self.win.overrideredirect(True)
        try:
            self.win.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass
        self.win.wm_attributes("-topmost", True)
        try:
            self.win.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        try:
            self.win.wm_attributes("-alpha", float(self._settings.get("overlay_alpha")))
        except (tk.TclError, TypeError, ValueError):
            pass
        self.win.configure(bg=TRANSPARENT)

        self._canvas = tk.Canvas(
            self.win,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
            cursor="fleur",
        )
        self._canvas.pack()
        self._draw_static()
        self._bind_events()
        self._place_window()
        if self._visible:
            self.win.deiconify()

    # --- отрисовка ----------------------------------------------------------
    def _rounded_rect(self, x0: float, y0: float, x1: float, y1: float, radius: float, **kwargs):
        points = [
            x0 + radius, y0,
            x1 - radius, y0,
            x1, y0,
            x1, y0 + radius,
            x1, y1 - radius,
            x1, y1,
            x1 - radius, y1,
            x0 + radius, y1,
            x0, y1,
            x0, y1 - radius,
            x0, y0 + radius,
            x0, y0,
        ]
        return self._canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw_static(self) -> None:
        canvas = self._canvas
        self._rounded_rect(
            1, 1, self.WIDTH - 1, self.HEIGHT - 1, 16, fill=BG, outline=BORDER, width=1
        )
        self._rounded_rect(14, 26, 18, 72, 2, fill=ACCENT, outline="")
        canvas.create_text(30, 22, text="НАЖАТИЙ", anchor="w", fill=MUTED, font=(FONT, 8, "bold"))
        self._total_id = canvas.create_text(
            30, 49, text="0", anchor="w", fill=FG, font=(FONT, 23, "bold")
        )
        self._sub_id = canvas.create_text(
            30, 78, text="EN · 0 кл/мин", anchor="w", fill=MUTED, font=(FONT, 9)
        )
        for offset in (0, 6, 12):
            canvas.create_oval(
                self.WIDTH - 32 + offset, 16,
                self.WIDTH - 29 + offset, 19,
                fill=BORDER, outline="",
            )

    def set_values(self, total: int, layout: str, kpm: int) -> None:
        values = (total, layout, kpm)
        if values == self._last_values:
            return
        self._last_values = values
        self._canvas.itemconfigure(self._total_id, text=_format_number(total))
        badge = LAYOUT_BADGE.get(layout, "??")
        self._canvas.itemconfigure(self._sub_id, text=f"{badge} · {kpm} кл/мин")

    # --- события ------------------------------------------------------------
    def _bind_events(self) -> None:
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Double-Button-1>", lambda _event: self._app.show_stats())
        self._canvas.bind("<Button-3>", self._on_menu)

    def _on_press(self, event: tk.Event) -> None:
        self._drag_offset = (
            event.x_root - self.win.winfo_x(),
            event.y_root - self.win.winfo_y(),
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        dx, dy = self._drag_offset
        self.win.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _on_release(self, _event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        self._drag_offset = None
        self._settings.set("overlay_x", self.win.winfo_x())
        self._settings.set("overlay_y", self.win.winfo_y())
        self._settings.save()

    def _on_menu(self, event: tk.Event) -> None:
        view = self._app.view_layout()
        menu = tk.Menu(
            self.win,
            tearoff=0,
            bg="#232329",
            fg=FG,
            bd=0,
            activebackground=ACCENT,
            activeforeground="#ffffff",
        )
        menu.add_command(label="Статистика…  Ctrl+Alt+K", command=self._app.show_stats)
        menu.add_separator()
        for value, label in ((LAYOUT_EN, "EN"), (LAYOUT_RU, "RU")):
            prefix = "✓ " if view == value else "   "
            menu.add_command(
                label=f"{prefix}Раскладка: {label}",
                command=lambda v=value: self._app.set_view_layout(v),
            )
        menu.add_separator()
        menu.add_command(label="Сброс статистики…", command=self._app.confirm_reset)
        menu.add_command(label="Скрыть оверлей  Ctrl+Alt+O", command=self.hide)
        menu.add_separator()
        menu.add_command(label="Выход", command=self._app.request_quit)
        self._menu = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # --- видимость и позиция ------------------------------------------------
    @property
    def visible(self) -> bool:
        return self._visible

    def show(self) -> None:
        self._visible = True
        self.win.deiconify()
        self.win.wm_attributes("-topmost", True)
        self._settings.set("overlay_visible", True)
        self._settings.save()

    def hide(self) -> None:
        self._visible = False
        self.win.withdraw()
        self._settings.set("overlay_visible", False)
        self._settings.save()

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def _place_window(self) -> None:
        x = self._settings.get("overlay_x")
        y = self._settings.get("overlay_y")
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            x = screen_w - self.WIDTH - 40
            y = 40
        x = max(-self.WIDTH + 80, min(int(x), screen_w - 80))
        y = max(0, min(int(y), screen_h - 40))
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
