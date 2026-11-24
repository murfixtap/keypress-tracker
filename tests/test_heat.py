"""Тесты цветовой шкалы heatmap."""

from __future__ import annotations

import unittest

from keypress_tracker.heat import format_count, heat_color, heat_intensity, text_color


class HeatTest(unittest.TestCase):
    def test_intensity_bounds(self) -> None:
        self.assertEqual(heat_intensity(0, 100), 0.0)
        self.assertEqual(heat_intensity(10, 0), 0.0)
        self.assertEqual(heat_intensity(100, 100), 1.0)
        self.assertEqual(heat_intensity(200, 100), 1.0)

    def test_intensity_is_square_root(self) -> None:
        self.assertAlmostEqual(heat_intensity(25, 100), 0.5)
        self.assertGreater(heat_intensity(50, 100), heat_intensity(25, 100))

    def test_color_endpoints_and_clamp(self) -> None:
        self.assertEqual(heat_color(0.0), "#fafafc")
        self.assertEqual(heat_color(1.0), "#e53935")
        self.assertEqual(heat_color(-1.0), "#fafafc")
        self.assertEqual(heat_color(2.0), "#e53935")

    def test_text_color_contrast(self) -> None:
        self.assertEqual(text_color(0.9), "#ffffff")
        self.assertEqual(text_color(0.1), "#26262b")
        self.assertEqual(text_color(0.55), "#ffffff")

    def test_format_count(self) -> None:
        self.assertEqual(format_count(0), "0")
        self.assertEqual(format_count(999), "999")
        self.assertEqual(format_count(1_500), "1,5k")
        self.assertEqual(format_count(15_000), "15k")
        self.assertEqual(format_count(1_500_000), "1,5M")


if __name__ == "__main__":
    unittest.main()
