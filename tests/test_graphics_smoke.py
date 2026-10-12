from __future__ import annotations

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from src import demo_common


class GraphicsSmokeTest(unittest.TestCase):
    def _run(self, module: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", module, "--smoke-test"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            self.fail(
                f"{module} returned {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        self.assertIn("graphics smoke test passed", result.stdout)
        self.assertRegex(result.stdout, r"SCM modified soil nodes: [1-9][0-9]*")

    def test_excavator_graphics_and_scm(self) -> None:
        self._run("src.excavator_main")

    def test_bulldozer_graphics_and_scm(self) -> None:
        self._run("src.bulldozer_main")


class RendererSelectionTest(unittest.TestCase):
    def test_opengl_is_the_default_and_avoids_the_mesa_zstd_crash(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "platform", "linux"):
            self.assertEqual(demo_common._window_driver(), demo_common.OPENGL_DRIVER)
            self.assertEqual(os.environ["MESA_SHADER_CACHE_DISABLE"], "true")

    def test_software_renderer_remains_available(self) -> None:
        for value in ("software", "SOFTWARE", "burning"):
            with self.subTest(value=value), patch.dict(os.environ, {"AES_IRRLICHT_DRIVER": value}):
                self.assertEqual(demo_common._window_driver(), demo_common.SOFTWARE_DRIVER)

    def test_large_windows_get_a_scaled_bitmap_font(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            xml = demo_common.write_bitmap_font(Path(tmp), 58)
            text = xml.read_text(encoding="utf-8")
            self.assertTrue((Path(tmp) / "gui_font.png").is_file())
        self.assertEqual(text.count("<c "), 95)  # every printable ASCII character
        self.assertIn('c="&amp;"', text)
        height = int(text.split('c="A" r="')[1].split('"')[0].split(", ")[3]) - \
            int(text.split('c="A" r="')[1].split('"')[0].split(", ")[1])
        self.assertGreaterEqual(height, 58)

    def test_fullscreen_uses_the_primary_monitor(self) -> None:
        two_monitors = (
            "Screen 0: minimum 320 x 200, current 5760 x 2160, maximum 16384 x 16384\n"
            "HDMI-1 connected 1920x1080+3840+0 (normal left inverted right) 600mm x 340mm\n"
            "eDP-1 connected primary 3840x2160+0+0 (normal left inverted right) 300mm x 190mm\n"
            "DP-1 disconnected (normal left inverted right x axis y axis)\n"
        )
        self.assertEqual(demo_common._primary_monitor_size(two_monitors), (3840, 2160))
        no_primary = two_monitors.replace(" primary", "")
        self.assertEqual(demo_common._primary_monitor_size(no_primary), (1920, 1080))
        self.assertIsNone(demo_common._primary_monitor_size("DP-1 disconnected\n"))


if __name__ == "__main__":
    unittest.main()
