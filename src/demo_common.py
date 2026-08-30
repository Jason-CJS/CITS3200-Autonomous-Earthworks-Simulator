"""Input and visualization helpers used by both interactive Python demos."""

from __future__ import annotations

from collections.abc import Iterable
import ctypes
from pathlib import Path
import sys
import threading

import pychrono as chrono
import pychrono.irrlicht as chronoirr


class KeyboardState:
    """Thread-safe key state with an optional cross-platform pynput listener."""

    def __init__(self, initially_pressed: Iterable[str] = ()) -> None:
        self._pressed = {key.lower() for key in initially_pressed}
        self._lock = threading.Lock()
        self._listener = None

    def start(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as error:
            raise RuntimeError(
                "Interactive controls need pynput. Recreate the Conda environment from environment.yml."
            ) from error

        def key_name(key: object) -> str | None:
            if key == keyboard.Key.space:
                return "space"
            char = getattr(key, "char", None)
            return char.lower() if isinstance(char, str) else None

        def on_press(key: object) -> None:
            if name := key_name(key):
                with self._lock:
                    self._pressed.add(name)

        def on_release(key: object) -> None:
            if name := key_name(key):
                with self._lock:
                    self._pressed.discard(name)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=1.0)

    def is_down(self, key: str) -> bool:
        with self._lock:
            return key.lower() in self._pressed


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def axis(keyboard: KeyboardState, positive: str, negative: str) -> float:
    return float(keyboard.is_down(positive)) - float(keyboard.is_down(negative))


def create_visual_system(
    system: chrono.ChSystem,
    title: str,
    camera_position: chrono.ChVector3d,
    camera_target: chrono.ChVector3d,
    *,
    null_driver: bool = False,
    balanced_lighting: bool = False,
) -> chronoirr.ChVisualSystemIrrlicht:
    visual = chronoirr.ChVisualSystemIrrlicht()
    # The official PyChrono 10 Conda wrapper crashes while destroying this
    # SWIG-owned object during interpreter shutdown. One visual system lives
    # for the process lifetime, so let the operating system reclaim it.
    visual.thisown = False
    visual.AttachSystem(system)
    _set_linux_irrlicht_driver(visual, 0 if null_driver else 2)
    visual.SetWindowSize(1280, 720)
    visual.SetWindowTitle(title)
    visual.SetCameraVertical(chrono.CameraVerticalDir_Z)
    visual.Initialize()
    visual.AddLogo()
    visual.AddSkyBox()
    visual.AddCamera(camera_position, camera_target)
    if balanced_lighting:
        visual.AddLightDirectional(
            55.0,
            -35.0,
            chrono.ChColor(0.22, 0.20, 0.16),
            chrono.ChColor(0.04, 0.04, 0.04),
            chrono.ChColor(0.72, 0.64, 0.50),
        )
        visual.AddLightDirectional(
            35.0,
            140.0,
            chrono.ChColor(0.08, 0.09, 0.10),
            chrono.ChColor(0.02, 0.02, 0.02),
            chrono.ChColor(0.30, 0.33, 0.36),
        )
    else:
        visual.AddTypicalLights()
    return visual


def _set_linux_irrlicht_driver(visual: chronoirr.ChVisualSystemIrrlicht, driver: int) -> None:
    """Set an Irrlicht enum omitted by the official PyChrono 10 Linux wrapper.

    Driver 0 is the null renderer used by tests. Driver 2 is Irrlicht's
    platform-independent Burning renderer; the Conda package's OpenGL backend
    crashes on current Wayland/Xwayland desktops.
    """

    if not sys.platform.startswith("linux"):
        return
    library = ctypes.CDLL(str(Path(chronoirr.__file__).resolve().parents[3] / "libChrono_irrlicht.so"))
    setter = getattr(
        library,
        "_ZN6chrono8irrlicht22ChVisualSystemIrrlicht13SetDriverTypeEN3irr5video13E_DRIVER_TYPEE",
    )
    setter.argtypes = [ctypes.c_void_p, ctypes.c_int]
    setter.restype = None
    shared_pointer_address = int(visual.this)
    object_address = ctypes.c_void_p.from_address(shared_pointer_address).value
    setter(object_address, driver)
