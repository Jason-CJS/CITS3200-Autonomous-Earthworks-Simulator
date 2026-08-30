from __future__ import annotations

import subprocess
import sys
import unittest


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


if __name__ == "__main__":
    unittest.main()
