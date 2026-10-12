"""Input and visualization helpers used by both interactive Python demos."""

from __future__ import annotations

from collections.abc import Iterable
import ctypes
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

import pychrono as chrono
import pychrono.irrlicht as chronoirr


WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 576

# Irrlicht E_DRIVER_TYPE values; the Linux PyChrono wrapper omits the enum.
NULL_DRIVER = 0
SOFTWARE_DRIVER = 2  # BurningVideo: CPU rendering, slows down as the window grows
OPENGL_DRIVER = 5


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
            if key == keyboard.Key.esc:
                return "esc"
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
    controls: Iterable[str] = (),
    null_driver: bool = False,
    balanced_lighting: bool = False,
    fullscreen: bool = False,
) -> chronoirr.ChVisualSystemIrrlicht:
    visual = chronoirr.ChVisualSystemIrrlicht()
    # The official PyChrono 10 Conda wrapper crashes while destroying this
    # SWIG-owned object during interpreter shutdown. One visual system lives
    # for the process lifetime, so let the operating system reclaim it.
    visual.thisown = False
    visual.AttachSystem(system)
    _set_linux_irrlicht_driver(visual, NULL_DRIVER if null_driver else _window_driver())
    width, height = WINDOW_WIDTH, WINDOW_HEIGHT
    if fullscreen and not null_driver:
        # A normal window the size of the desktop, which the window manager is
        # then asked to make fullscreen (below). Irrlicht's own exclusive mode
        # takes over the display and input, so a stalled run could not be
        # closed or switched away from.
        width, height = _desktop_size() or (width, height)
    visual.SetWindowSize(width, height)
    visual.SetWindowTitle(title)
    visual.SetCameraVertical(chrono.CameraVerticalDir_Z)
    visual.Initialize()
    if fullscreen and not null_driver:
        _request_window_manager_fullscreen(visual)
    _allow_linux_non_power_of_two_textures(visual)
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
    _add_controls_panel(visual, controls, width)
    return visual


def _window_driver() -> int:
    """OpenGL unless AES_IRRLICHT_DRIVER=software asks for the CPU renderer.

    Ubuntu's Mesa decompresses its shader disk cache with zstd. Inside the
    Conda environment it binds to the environment's own libzstd build and
    crashes while creating the OpenGL context, so that cache is turned off
    (Irrlicht's few shaders compile in milliseconds). This must happen before
    the first context is created.
    """
    if os.environ.get("AES_IRRLICHT_DRIVER", "opengl").lower() in ("software", "burning"):
        return SOFTWARE_DRIVER
    if sys.platform.startswith("linux"):
        os.environ.setdefault("MESA_SHADER_CACHE_DISABLE", "true")
    return OPENGL_DRIVER


def _primary_monitor_size(xrandr_output: str) -> tuple[int, int] | None:
    """The primary monitor's size from xrandr --current, else the first connected one."""
    monitors = re.findall(r"^\S+ connected (primary )?(\d+)x(\d+)\+", xrandr_output, re.MULTILINE)
    if not monitors:
        return None
    _, width, height = ([m for m in monitors if m[0]] or monitors)[0]
    return int(width), int(height)


class _X11VideoData(ctypes.Structure):
    """The Linux OpenGL part of Irrlicht's ``SExposedVideoData``."""

    _fields_ = [("display", ctypes.c_void_p), ("context", ctypes.c_void_p),
                ("window", ctypes.c_ulong)]


class _XClientMessageEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong),
                ("message_type", ctypes.c_ulong), ("format", ctypes.c_int),
                ("data", ctypes.c_long * 5)]


def _request_window_manager_fullscreen(visual: chronoirr.ChVisualSystemIrrlicht) -> bool:
    """Ask the window manager to fullscreen the window, as a video player does.

    Sends the standard ``_NET_WM_STATE_FULLSCREEN`` request, so Super, Alt+Tab
    and Alt+F4 keep working. Returns False (leaving a desktop-sized window) if
    the window cannot be found, for example with the CPU renderer.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        irrlicht = ctypes.CDLL(str(Path(chronoirr.__file__).resolve().parents[3] / "libIrrlicht.so"))
        exposed = irrlicht._ZN3irr5video11CNullDriver19getExposedVideoDataEv
        exposed.argtypes = [ctypes.c_void_p]
        exposed.restype = ctypes.POINTER(_X11VideoData)
        driver = visual.GetVideoDriver()
        window = exposed(int(getattr(driver, "this", driver))).contents.window
        if not window:
            return False
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                                   ctypes.c_void_p]
        x11.XFlush.argtypes = x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        if not display:
            return False
        try:
            message = _XClientMessageEvent()
            message.type = 33  # ClientMessage
            message.send_event = 1
            message.display = display
            message.window = window
            message.message_type = x11.XInternAtom(display, b"_NET_WM_STATE", 0)
            message.format = 32
            message.data[0] = 1  # add the state
            message.data[1] = x11.XInternAtom(display, b"_NET_WM_STATE_FULLSCREEN", 0)
            message.data[3] = 1  # sent by a normal application
            event = (ctypes.c_long * 24)()  # an XEvent is 24 longs
            ctypes.memmove(event, ctypes.byref(message), ctypes.sizeof(message))
            redirect_and_notify = (1 << 20) | (1 << 19)
            x11.XSendEvent(display, x11.XDefaultRootWindow(display), 0, redirect_and_notify, event)
            x11.XFlush(display)
        finally:
            x11.XCloseDisplay(display)
        return True
    except (OSError, AttributeError, ValueError):
        return False


def _desktop_size() -> tuple[int, int] | None:
    """The primary monitor's resolution, so a fullscreen window fills one screen.

    With several monitors the X screen spans all of them, so xrandr is asked
    first; the whole X screen is the fallback when xrandr is not installed.
    """
    try:
        output = subprocess.run(["xrandr", "--current"], capture_output=True, text=True,
                                timeout=5, check=True).stdout
        if size := _primary_monitor_size(output):
            return size
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        x11 = ctypes.CDLL("libX11.so.6")
    except OSError:
        return None
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XDisplayWidth.argtypes = x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        return None
    try:
        screen = x11.XDefaultScreen(display)
        return x11.XDisplayWidth(display, screen), x11.XDisplayHeight(display, screen)
    finally:
        x11.XCloseDisplay(display)


def _add_controls_panel(
    visual: chronoirr.ChVisualSystemIrrlicht,
    controls: Iterable[str],
    window_width: int = WINDOW_WIDTH,
) -> None:
    lines = tuple(controls)
    if not lines:
        return
    text = "CONTROLS\n" + "\n".join(lines)
    visual.GetGUIEnvironment().addStaticText(
        text,
        chronoirr.recti(window_width - 335, 12, window_width - 12, 38 + 17 * len(lines)),
        True,
        False,
        None,
        -1,
        True,
    )


def _set_linux_irrlicht_driver(visual: chronoirr.ChVisualSystemIrrlicht, driver: int) -> None:
    """Set an Irrlicht enum omitted by the official PyChrono 10 Linux wrapper.

    See NULL_DRIVER, SOFTWARE_DRIVER and OPENGL_DRIVER, and ``_window_driver``
    for why OpenGL needs Mesa's shader cache turned off.
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


def _allow_linux_non_power_of_two_textures(
    visual: chronoirr.ChVisualSystemIrrlicht,
) -> None:
    """Keep 2D images at their original aspect ratio (needed by BurningVideo).

    PyChrono omits Irrlicht's texture-creation enum from its Linux wrapper.
    BurningVideo supports non-power-of-two textures for GUI images, including
    Chrono's 123-by-64 logo, once ETCF_ALLOW_NON_POWER_2 is enabled.
    """

    if not sys.platform.startswith("linux"):
        return
    library = ctypes.CDLL(
        str(Path(chronoirr.__file__).resolve().parents[3] / "libIrrlicht.so")
    )
    setter = getattr(
        library,
        "_ZN3irr5video11CNullDriver22setTextureCreationFlagENS0_23E_TEXTURE_CREATION_FLAGEb",
    )
    setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_bool]
    setter.restype = None
    setter(ctypes.c_void_p(int(visual.GetVideoDriver().this)), 0x40, True)
