"""Тесты геометрии и подписей клавиш."""

from __future__ import annotations

import unittest

from keypress_tracker import layouts
from keypress_tracker.constants import LAYOUT_EN, LAYOUT_OTHER, LAYOUT_RU


class LayoutTest(unittest.TestCase):
    def test_letter_labels(self) -> None:
        keys = layouts.key_by_vk()
        self.assertEqual(keys[0x51].label(LAYOUT_EN), "Q")
        self.assertEqual(keys[0x51].label(LAYOUT_RU), "Й")
        self.assertEqual(keys[0x57].label(LAYOUT_RU), "Ц")
        self.assertEqual(keys[0xBA].label(LAYOUT_RU), "Ж")
        self.assertEqual(keys[0xBC].label(LAYOUT_RU), "Б")
        self.assertEqual(keys[0xC0].label(LAYOUT_RU), "Ё")
        self.assertEqual(keys[0x20].label(LAYOUT_RU), "Space")

    def test_main_rows_have_equal_width(self) -> None:
        widths = layouts.main_row_widths()
        self.assertEqual(widths[0], 13.75)
        self.assertEqual(widths[1:], [15.0] * 5)

    def test_placed_keys_fit_board(self) -> None:
        for include_numpad in (False, True):
            width, height = layouts.board_size(include_numpad)
            for placed in layouts.placed_keys(include_numpad):
                self.assertLessEqual(placed.x + placed.key.width, width + 1e-9)
                self.assertLessEqual(placed.y + placed.key.height, height + 1e-9)

    def test_compact_board_narrower_than_full(self) -> None:
        tkl_width, _ = layouts.board_size(False)
        full_width, _ = layouts.board_size(True)
        self.assertLess(tkl_width, full_width)
        self.assertEqual(tkl_width, 18.5)
        self.assertEqual(full_width, 23.25)

    def test_layout_from_hkl(self) -> None:
        self.assertEqual(layouts.layout_from_hkl(0x04090409), LAYOUT_EN)
        self.assertEqual(layouts.layout_from_hkl(0x04190419), LAYOUT_RU)
        self.assertEqual(layouts.layout_from_hkl(0x04070407), LAYOUT_OTHER)

    def test_key_by_vk_covers_main_keys(self) -> None:
        keys = layouts.key_by_vk()
        for vk in (0x41, 0x5A, 0x20, 0x0D, 0x1B, 0x26, 0x60):
            self.assertIn(vk, keys)


if __name__ == "__main__":
    unittest.main()
