"""Хранилище статистики и настроек: JSON, автосохранение, потокобезопасность."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .constants import (
    KEYBOARD_FULL,
    LAYOUT_EN,
    LAYOUT_RU,
    LAYOUTS,
    PERIOD_ALL,
    PERIOD_TODAY,
)

SCHEMA_VERSION = 1
DAILY_KEEP_DAYS = 400
RECENT_WINDOW_SECONDS = 60.0


def app_data_dir(base: Path | None = None) -> Path:
    """Каталог с данными приложения."""
    if base is not None:
        return Path(base)
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".local" / "share"
    return root / "keypress-tracker"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Пишет JSON через временный файл, чтобы не терять данные при сбое."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Snapshot:
    """Срез счётчиков для отрисовки."""

    layout: str | None
    period: str
    counts: dict[int, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def max_count(self) -> int:
        return max(self.counts.values(), default=0)


class StatsStore:
    """Счётчики нажатий по раскладкам + дневная история."""

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        autosave: bool = True,
        flush_interval: float = 10.0,
    ) -> None:
        self.data_dir = app_data_dir(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "stats.json"

        self._lock = threading.RLock()
        self._flush_interval = flush_interval
        self._counts: dict[str, dict[int, int]] = {layout: {} for layout in LAYOUTS}
        self._daily: dict[str, dict[str, dict[int, int]]] = {}
        self._total = 0
        self._created_at = _iso_now()
        self._recent: deque[float] = deque(maxlen=8192)
        self._last_layout = LAYOUT_EN
        self._dirty = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._load()
        if autosave:
            self._thread = threading.Thread(
                target=self._autosave_loop, name="stats-autosave", daemon=True
            )
            self._thread.start()

    # --- чтение -------------------------------------------------------------
    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def last_layout(self) -> str:
        with self._lock:
            return self._last_layout

    @property
    def created_at(self) -> str:
        with self._lock:
            return self._created_at

    def snapshot(self, layout: str | None = None, period: str = PERIOD_ALL) -> Snapshot:
        with self._lock:
            if period == PERIOD_TODAY:
                source = self._daily.get(date.today().isoformat(), {})
            else:
                source = self._counts
            if layout is None:
                combined: dict[int, int] = {}
                for name in LAYOUTS:
                    for vk, count in source.get(name, {}).items():
                        combined[vk] = combined.get(vk, 0) + count
                return Snapshot(None, period, combined)
            return Snapshot(layout, period, dict(source.get(layout, {})))

    def total_today(self) -> int:
        with self._lock:
            buckets = self._daily.get(date.today().isoformat(), {})
            return sum(sum(bucket.values()) for bucket in buckets.values())

    def kpm(self) -> int:
        """Нажатий за последнюю минуту."""
        with self._lock:
            cutoff = time.monotonic() - RECENT_WINDOW_SECONDS
            while self._recent and self._recent[0] < cutoff:
                self._recent.popleft()
            return len(self._recent)

    # --- запись -------------------------------------------------------------
    def press(self, vk: int, layout: str) -> None:
        if layout not in self._counts:
            layout = "other"
        now = time.monotonic()
        with self._lock:
            bucket = self._counts[layout]
            bucket[vk] = bucket.get(vk, 0) + 1
            today = date.today().isoformat()
            day = self._daily.setdefault(today, {name: {} for name in LAYOUTS})
            day_bucket = day.setdefault(layout, {})
            day_bucket[vk] = day_bucket.get(vk, 0) + 1
            self._total += 1
            self._last_layout = layout
            self._recent.append(now)
            self._dirty = True

    def reset(self) -> None:
        with self._lock:
            self._counts = {layout: {} for layout in LAYOUTS}
            self._daily.clear()
            self._total = 0
            self._recent.clear()
            self._last_layout = LAYOUT_EN
            self._dirty = True
        self.save(force=True)

    # --- сохранение ---------------------------------------------------------
    def save(self, force: bool = False) -> None:
        with self._lock:
            if not (self._dirty or force):
                return
            self._prune_daily_locked()
            payload = {
                "schema": SCHEMA_VERSION,
                "created_at": self._created_at,
                "updated_at": _iso_now(),
                "total": self._total,
                "counts": {
                    layout: {str(vk): n for vk, n in bucket.items() if n}
                    for layout, bucket in self._counts.items()
                },
                "daily": {
                    day: {
                        layout: {str(vk): n for vk, n in bucket.items() if n}
                        for layout, bucket in buckets.items()
                    }
                    for day, buckets in self._daily.items()
                },
            }
            self._dirty = False
        try:
            _atomic_write_json(self.path, payload)
        except OSError:
            with self._lock:
                self._dirty = True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.save(force=True)

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            self._backup_broken_file()
            return
        if not isinstance(data, dict):
            self._backup_broken_file()
            return

        with self._lock:
            self._created_at = str(data.get("created_at") or self._created_at)
            try:
                self._total = max(int(data.get("total") or 0), 0)
            except (TypeError, ValueError):
                self._total = 0

            counts = data.get("counts")
            if isinstance(counts, dict):
                for layout in LAYOUTS:
                    bucket = counts.get(layout)
                    if isinstance(bucket, dict):
                        self._counts[layout] = self._parse_bucket(bucket)

            daily = data.get("daily")
            if isinstance(daily, dict):
                for day, buckets in daily.items():
                    if not isinstance(buckets, dict):
                        continue
                    parsed = {
                        layout: self._parse_bucket(buckets[layout])
                        for layout in LAYOUTS
                        if isinstance(buckets.get(layout), dict)
                    }
                    if parsed:
                        self._daily[str(day)] = parsed

    @staticmethod
    def _parse_bucket(bucket: dict) -> dict[int, int]:
        parsed: dict[int, int] = {}
        for vk, count in bucket.items():
            try:
                key = int(vk)
                value = int(count)
            except (TypeError, ValueError):
                continue
            if value > 0:
                parsed[key] = value
        return parsed

    def _backup_broken_file(self) -> None:
        try:
            self.path.replace(self.path.with_name(self.path.name + ".bak"))
        except OSError:
            pass

    def _prune_daily_locked(self) -> None:
        cutoff = date.today().toordinal() - DAILY_KEEP_DAYS
        for day in list(self._daily):
            try:
                ordinal = date.fromisoformat(day).toordinal()
            except ValueError:
                ordinal = -1
            if ordinal < cutoff:
                del self._daily[day]

    def _autosave_loop(self) -> None:
        while not self._stop_event.wait(self._flush_interval):
            try:
                self.save()
            except Exception:
                continue


SETTINGS_DEFAULTS: dict[str, object] = {
    "overlay_x": None,
    "overlay_y": None,
    "overlay_visible": True,
    "overlay_alpha": 0.88,
    "view_layout": LAYOUT_RU,
    "view_period": PERIOD_ALL,
    "keyboard_mode": KEYBOARD_FULL,
}


class Settings:
    """Пользовательские настройки (позиция оверлея, вид статистики)."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = app_data_dir(data_dir)
        self.path = self.data_dir / "settings.json"
        self._data: dict[str, object] = dict(SETTINGS_DEFAULTS)
        self._load()

    def get(self, key: str):
        return self._data.get(key, SETTINGS_DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def update(self, **values: object) -> None:
        self._data.update(values)

    def as_dict(self) -> dict[str, object]:
        return dict(self._data)

    def save(self) -> None:
        try:
            _atomic_write_json(self.path, self._data)
        except OSError:
            pass

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        for key, value in data.items():
            if key in SETTINGS_DEFAULTS:
                self._data[key] = value
