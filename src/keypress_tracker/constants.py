"""Общие константы приложения."""

from __future__ import annotations

__version__ = "0.1.0"

APP_NAME = "keypress-tracker"

LAYOUT_EN = "en"
LAYOUT_RU = "ru"
LAYOUT_OTHER = "other"
LAYOUTS = (LAYOUT_EN, LAYOUT_RU, LAYOUT_OTHER)
LAYOUT_BADGE = {LAYOUT_EN: "EN", LAYOUT_RU: "RU", LAYOUT_OTHER: "??"}

PERIOD_ALL = "all"
PERIOD_TODAY = "today"

KEYBOARD_TKL = "tkl"
KEYBOARD_FULL = "full"
