"""Тесты логики колбэка хука (без установки реального хука)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from keypress_tracker import capture
from keypress_tracker.capture import KeyCapture
from keypress_tracker.constants import LAYOUT_EN, LAYOUT_RU


class FakeStore:
    def __init__(self) -> None:
        self.events: list[tuple[int, str]] = []
        self.total = 0

    def press(self, vk: int, layout: str) -> None:
        self.events.append((vk, layout))
        self.total += 1


def make_info(vk: int, scan: int, flags: int = 0) -> SimpleNamespace:
    return SimpleNamespace(vkCode=vk, scanCode=scan, flags=flags)


class KeyCaptureLogicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.hotkeys: list[str] = []
        self.capture = KeyCapture(self.store, on_hotkey=self.hotkeys.append)
        self.capture._last_layout = LAYOUT_EN
        layout_patch = mock.patch.object(capture, "active_layout", return_value=LAYOUT_EN)
        layout_patch.start()
        self.addCleanup(layout_patch.stop)

    def test_ignores_injected_events(self) -> None:
        info = make_info(0x41, 30, flags=capture.win32.LLKHF_INJECTED)
        suppressed = self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.assertFalse(suppressed)
        self.assertEqual(self.store.events, [])

    def test_autorepeat_counted_once_until_keyup(self) -> None:
        info = make_info(0x41, 30)
        self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.assertEqual(self.store.events, [(0x41, LAYOUT_EN)])
        self.capture._handle_event(capture.win32.WM_KEYUP, info)
        self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.assertEqual(len(self.store.events), 2)

    def test_hotkey_is_detected_and_suppressed(self) -> None:
        info = make_info(0x4B, 37)
        with mock.patch.object(capture.win32, "is_key_down", return_value=True):
            suppressed = self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.assertTrue(suppressed)
        self.assertEqual(self.hotkeys, ["stats"])
        self.assertEqual(self.store.events, [(0x4B, LAYOUT_EN)])

    def test_hotkey_requires_modifiers(self) -> None:
        info = make_info(0x4F, 24)
        with mock.patch.object(capture.win32, "is_key_down", return_value=False):
            suppressed = self.capture._handle_event(capture.win32.WM_KEYDOWN, info)
        self.assertFalse(suppressed)
        self.assertEqual(self.hotkeys, [])

    def test_unknown_layout_falls_back_to_last_known(self) -> None:
        with mock.patch.object(capture, "active_layout", return_value="other"):
            self.capture._handle_event(capture.win32.WM_KEYDOWN, make_info(0x41, 30))
        self.assertEqual(self.store.events, [(0x41, LAYOUT_EN)])

    def test_detected_layout_is_stored(self) -> None:
        with mock.patch.object(capture, "active_layout", return_value=LAYOUT_RU):
            self.capture._handle_event(capture.win32.WM_KEYDOWN, make_info(0x41, 30))
        self.assertEqual(self.store.events, [(0x41, LAYOUT_RU)])
        self.assertEqual(self.capture._last_layout, LAYOUT_RU)


if __name__ == "__main__":
    unittest.main()
