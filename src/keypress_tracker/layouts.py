"""Геометрия клавиатуры и подписи клавиш для раскладок EN/RU.

Координаты заданы в «юнитах» (ширина одной буквенной клавиши = 1.0),
перевод в пиксели делает UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import win32
from .constants import LAYOUT_EN, LAYOUT_OTHER, LAYOUT_RU


@dataclass(frozen=True)
class Key:
    """Клавиша: виртуальный код + подписи в раскладках EN/RU."""

    vk: int
    en: str
    ru: str | None = None
    width: float = 1.0
    height: float = 1.0
    kind: str = "char"  # char | named

    def label(self, layout: str) -> str:
        if layout == LAYOUT_RU and self.ru:
            return self.ru
        return self.en


@dataclass(frozen=True)
class Spacer:
    width: float


@dataclass(frozen=True)
class PlacedKey:
    x: float
    y: float
    key: Key


K = Key
S = Spacer


def _row(*items: Key | Spacer) -> tuple[Key | Spacer, ...]:
    return tuple(items)


# --- основной блок: 6 рядов (Esc/F1–F12 и нижние ряды, 15 юнитов) ----------
MAIN_ROWS: tuple[tuple[Key | Spacer, ...], ...] = (
    _row(
        K(0x1B, "Esc", kind="named"),
        S(0.25),
        K(0x70, "F1", kind="named"),
        K(0x71, "F2", kind="named"),
        K(0x72, "F3", kind="named"),
        K(0x73, "F4", kind="named"),
        S(0.25),
        K(0x74, "F5", kind="named"),
        K(0x75, "F6", kind="named"),
        K(0x76, "F7", kind="named"),
        K(0x77, "F8", kind="named"),
        S(0.25),
        K(0x78, "F9", kind="named"),
        K(0x79, "F10", kind="named"),
        K(0x7A, "F11", kind="named"),
        K(0x7B, "F12", kind="named"),
    ),
    _row(
        K(0xC0, "`", "Ё"),
        K(0x31, "1"),
        K(0x32, "2"),
        K(0x33, "3"),
        K(0x34, "4"),
        K(0x35, "5"),
        K(0x36, "6"),
        K(0x37, "7"),
        K(0x38, "8"),
        K(0x39, "9"),
        K(0x30, "0"),
        K(0xBD, "-"),
        K(0xBB, "="),
        K(0x08, "Backspace", width=2.0, kind="named"),
    ),
    _row(
        K(0x09, "Tab", width=1.5, kind="named"),
        K(0x51, "Q", "Й"),
        K(0x57, "W", "Ц"),
        K(0x45, "E", "У"),
        K(0x52, "R", "К"),
        K(0x54, "T", "Е"),
        K(0x59, "Y", "Н"),
        K(0x55, "U", "Г"),
        K(0x49, "I", "Ш"),
        K(0x4F, "O", "Щ"),
        K(0x50, "P", "З"),
        K(0xDB, "[", "Х"),
        K(0xDD, "]", "Ъ"),
        K(0xDC, "\\", width=1.5),
    ),
    _row(
        K(0x14, "Caps", width=1.75, kind="named"),
        K(0x41, "A", "Ф"),
        K(0x53, "S", "Ы"),
        K(0x44, "D", "В"),
        K(0x46, "F", "А"),
        K(0x47, "G", "П"),
        K(0x48, "H", "Р"),
        K(0x4A, "J", "О"),
        K(0x4B, "K", "Л"),
        K(0x4C, "L", "Д"),
        K(0xBA, ";", "Ж"),
        K(0xDE, "'", "Э"),
        K(0x0D, "Enter", width=2.25, kind="named"),
    ),
    _row(
        K(0xA0, "Shift", width=2.25, kind="named"),
        K(0x5A, "Z", "Я"),
        K(0x58, "X", "Ч"),
        K(0x43, "C", "С"),
        K(0x56, "V", "М"),
        K(0x42, "B", "И"),
        K(0x4E, "N", "Т"),
        K(0x4D, "M", "Ь"),
        K(0xBC, ",", "Б"),
        K(0xBE, ".", "Ю"),
        K(0xBF, "/", "."),
        K(0xA1, "Shift", width=2.75, kind="named"),
    ),
    _row(
        K(0xA2, "Ctrl", width=1.25, kind="named"),
        K(0x5B, "Win", width=1.25, kind="named"),
        K(0xA4, "Alt", width=1.25, kind="named"),
        K(0x20, "Space", width=6.25, kind="named"),
        K(0xA5, "Alt", width=1.25, kind="named"),
        K(0x5C, "Win", width=1.25, kind="named"),
        K(0x5D, "Menu", width=1.25, kind="named"),
        K(0xA3, "Ctrl", width=1.25, kind="named"),
    ),
)

MAIN_WIDTH = 15.0
NAV_X = 15.5
NUMPAD_X = 19.25
BOARD_HEIGHT = 6.0

NAV_KEYS: tuple[PlacedKey, ...] = (
    PlacedKey(0.0, 0.0, K(0x2C, "PrtSc", kind="named")),
    PlacedKey(1.0, 0.0, K(0x91, "ScrLk", kind="named")),
    PlacedKey(2.0, 0.0, K(0x13, "Pause", kind="named")),
    PlacedKey(0.0, 1.0, K(0x2D, "Ins", kind="named")),
    PlacedKey(1.0, 1.0, K(0x24, "Home", kind="named")),
    PlacedKey(2.0, 1.0, K(0x21, "PgUp", kind="named")),
    PlacedKey(0.0, 2.0, K(0x2E, "Del", kind="named")),
    PlacedKey(1.0, 2.0, K(0x23, "End", kind="named")),
    PlacedKey(2.0, 2.0, K(0x22, "PgDn", kind="named")),
    PlacedKey(1.0, 4.0, K(0x26, "↑", kind="named")),
    PlacedKey(0.0, 5.0, K(0x25, "←", kind="named")),
    PlacedKey(1.0, 5.0, K(0x28, "↓", kind="named")),
    PlacedKey(2.0, 5.0, K(0x27, "→", kind="named")),
)

NUMPAD_KEYS: tuple[PlacedKey, ...] = (
    PlacedKey(0.0, 1.0, K(0x90, "NumLk", kind="named")),
    PlacedKey(1.0, 1.0, K(0x6F, "/")),
    PlacedKey(2.0, 1.0, K(0x6A, "*")),
    PlacedKey(3.0, 1.0, K(0x6D, "-")),
    PlacedKey(0.0, 2.0, K(0x67, "7")),
    PlacedKey(1.0, 2.0, K(0x68, "8")),
    PlacedKey(2.0, 2.0, K(0x69, "9")),
    PlacedKey(3.0, 2.0, K(0x6B, "+", height=2.0)),
    PlacedKey(0.0, 3.0, K(0x64, "4")),
    PlacedKey(1.0, 3.0, K(0x65, "5")),
    PlacedKey(2.0, 3.0, K(0x66, "6")),
    PlacedKey(0.0, 4.0, K(0x61, "1")),
    PlacedKey(1.0, 4.0, K(0x62, "2")),
    PlacedKey(2.0, 4.0, K(0x63, "3")),
    PlacedKey(3.0, 4.0, K(0x0D, "Enter", height=2.0, kind="named")),
    PlacedKey(0.0, 5.0, K(0x60, "0", width=2.0)),
    PlacedKey(2.0, 5.0, K(0x6E, ".")),
)


def _place_main() -> tuple[PlacedKey, ...]:
    placed: list[PlacedKey] = []
    for y, row in enumerate(MAIN_ROWS):
        x = 0.0
        for item in row:
            if isinstance(item, Spacer):
                x += item.width
                continue
            placed.append(PlacedKey(x, float(y), item))
            x += item.width
    return tuple(placed)


MAIN_PLACED: tuple[PlacedKey, ...] = _place_main()


def placed_keys(include_numpad: bool = True) -> tuple[PlacedKey, ...]:
    """Все клавиши с абсолютными координатами в юнитах."""
    keys = list(MAIN_PLACED)
    keys.extend(PlacedKey(NAV_X + p.x, p.y, p.key) for p in NAV_KEYS)
    if include_numpad:
        keys.extend(PlacedKey(NUMPAD_X + p.x, p.y, p.key) for p in NUMPAD_KEYS)
    return tuple(keys)


def board_size(include_numpad: bool = True) -> tuple[float, float]:
    width = (NUMPAD_X + 4.0) if include_numpad else (NAV_X + 3.0)
    return width, BOARD_HEIGHT


def key_by_vk() -> dict[int, Key]:
    """Первая встреченная клавиша для каждого VK (для подписей в топ-10)."""
    result: dict[int, Key] = {}
    for placed in placed_keys(include_numpad=True):
        result.setdefault(placed.key.vk, placed.key)
    return result


def main_row_widths() -> list[float]:
    widths: list[float] = []
    for row in MAIN_ROWS:
        widths.append(round(sum(item.width for item in row), 3))
    return widths


def layout_from_hkl(hkl: int) -> str:
    """Определяет раскладку по описателю клавиатуры (HKL)."""
    lang_id = int(hkl) & 0xFFFF
    primary = lang_id & 0x03FF
    if primary == 0x09:
        return LAYOUT_EN
    if primary == 0x19:
        return LAYOUT_RU
    return LAYOUT_OTHER


def active_layout() -> str:
    """Раскладка активного (foreground) окна."""
    hwnd = win32.user32.GetForegroundWindow()
    thread_id = win32.user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
    hkl = win32.user32.GetKeyboardLayout(thread_id) if thread_id else 0
    if not hkl:
        hkl = win32.user32.GetKeyboardLayout(0)
    return layout_from_hkl(int(hkl or 0))
