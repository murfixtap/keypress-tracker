"""Тесты хранилища статистики и настроек."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from keypress_tracker.constants import LAYOUT_EN, LAYOUT_RU, PERIOD_ALL, PERIOD_TODAY
from keypress_tracker.store import Settings, StatsStore


class StatsStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        self.store = StatsStore(self.data_dir, autosave=False)
        self.addCleanup(self.store.stop)

    def test_press_increments_total_and_layouts(self) -> None:
        self.store.press(0x51, LAYOUT_EN)
        self.store.press(0x51, LAYOUT_RU)
        self.store.press(0x51, LAYOUT_RU)

        self.assertEqual(self.store.total, 3)
        self.assertEqual(self.store.snapshot(LAYOUT_EN).counts, {0x51: 1})
        self.assertEqual(self.store.snapshot(LAYOUT_RU).counts, {0x51: 2})
        combined = self.store.snapshot(None)
        self.assertEqual(combined.counts, {0x51: 3})
        self.assertEqual(combined.max_count, 3)
        self.assertEqual(combined.total, 3)

    def test_unknown_layout_goes_to_other(self) -> None:
        self.store.press(0x41, "de")
        self.assertEqual(self.store.snapshot(None).counts, {0x41: 1})
        self.assertEqual(self.store.last_layout, "other")

    def test_today_snapshot_matches_all_for_fresh_store(self) -> None:
        self.store.press(0x20, LAYOUT_EN)
        today = self.store.snapshot(None, PERIOD_TODAY)
        overall = self.store.snapshot(None, PERIOD_ALL)
        self.assertEqual(today.counts, overall.counts)
        self.assertEqual(self.store.total_today(), 1)

    def test_kpm_counts_recent_presses(self) -> None:
        for _ in range(4):
            self.store.press(0x41, LAYOUT_EN)
        self.assertEqual(self.store.kpm(), 4)

    def test_save_and_load_roundtrip(self) -> None:
        self.store.press(0x51, LAYOUT_RU)
        self.store.press(0x41, LAYOUT_EN)
        self.store.save(force=True)

        loaded = StatsStore(self.data_dir, autosave=False)
        self.addCleanup(loaded.stop)
        self.assertEqual(loaded.total, 2)
        self.assertEqual(loaded.snapshot(LAYOUT_RU).counts, {0x51: 1})
        self.assertEqual(loaded.snapshot(LAYOUT_EN).counts, {0x41: 1})
        self.assertEqual(loaded.total_today(), 2)

        raw = json.loads((self.data_dir / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["counts"]["ru"], {"81": 1})
        self.assertEqual(raw["counts"]["en"], {"65": 1})
        self.assertFalse((self.data_dir / "stats.json.tmp").exists())

    def test_broken_file_is_backed_up(self) -> None:
        (self.data_dir / "stats.json").write_text("{not json", encoding="utf-8")
        store = StatsStore(self.data_dir, autosave=False)
        self.addCleanup(store.stop)
        self.assertEqual(store.total, 0)
        self.assertTrue((self.data_dir / "stats.json.bak").exists())

    def test_reset_clears_everything(self) -> None:
        self.store.press(0x51, LAYOUT_EN)
        self.store.reset()
        self.assertEqual(self.store.total, 0)
        self.assertEqual(self.store.snapshot(None).counts, {})
        self.assertEqual(self.store.total_today(), 0)

    def test_save_skips_when_not_dirty(self) -> None:
        self.store.save()
        self.assertFalse((self.data_dir / "stats.json").exists())
        self.store.press(0x41, LAYOUT_EN)
        self.store.save()
        self.assertTrue((self.data_dir / "stats.json").exists())


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)

    def test_defaults(self) -> None:
        settings = Settings(self.data_dir)
        self.assertEqual(settings.get("view_layout"), LAYOUT_RU)
        self.assertEqual(settings.get("view_period"), PERIOD_ALL)
        self.assertTrue(settings.get("overlay_visible"))
        self.assertIsNone(settings.get("overlay_x"))

    def test_roundtrip(self) -> None:
        settings = Settings(self.data_dir)
        settings.set("overlay_x", 120)
        settings.set("overlay_y", 240)
        settings.set("view_layout", LAYOUT_EN)
        settings.save()

        reloaded = Settings(self.data_dir)
        self.assertEqual(reloaded.get("overlay_x"), 120)
        self.assertEqual(reloaded.get("overlay_y"), 240)
        self.assertEqual(reloaded.get("view_layout"), LAYOUT_EN)


if __name__ == "__main__":
    unittest.main()
