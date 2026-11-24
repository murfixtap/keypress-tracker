"""Расчёт интенсивности и цвета для heatmap клавиатуры."""

from __future__ import annotations

import math

COLOR_COLD = (250, 250, 252)
COLOR_HOT = (229, 57, 53)

TEXT_THRESHOLD = 0.55
TEXT_ON_HOT = "#ffffff"
TEXT_ON_COLD = "#26262b"


def heat_intensity(count: int, max_count: int) -> float:
    """Насколько «горячая» клавиша: 0 для нуля, 1 для максимума.

    Используется квадратный корень, иначе при одном очень частом пробеле
    все остальные клавиши визуально останутся белыми.
    """
    if count <= 0 or max_count <= 0:
        return 0.0
    ratio = min(count / max_count, 1.0)
    return math.sqrt(ratio)


def heat_color(intensity: float) -> str:
    """Цвет клавиши: белый -> красный, линейная интерполяция в RGB."""
    t = min(max(float(intensity), 0.0), 1.0)
    r = round(COLOR_COLD[0] + (COLOR_HOT[0] - COLOR_COLD[0]) * t)
    g = round(COLOR_COLD[1] + (COLOR_HOT[1] - COLOR_COLD[1]) * t)
    b = round(COLOR_COLD[2] + (COLOR_HOT[2] - COLOR_COLD[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def text_color(intensity: float) -> str:
    """Цвет подписи на клавише с учётом контраста."""
    return TEXT_ON_HOT if intensity >= TEXT_THRESHOLD else TEXT_ON_COLD


def format_count(count: int) -> str:
    """Компактная запись числа для подписи под буквой."""
    if count < 1_000:
        return str(count)
    if count < 10_000:
        return f"{count / 1_000:.1f}k".replace(".", ",")
    if count < 1_000_000:
        return f"{count // 1_000}k"
    return f"{count / 1_000_000:.1f}M".replace(".", ",")
