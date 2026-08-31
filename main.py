"""Desktop entry point for the DX7 Voice Browser.

Run this to get the app as a native window:

    python main.py

Threading model: pywebview must own the main thread, because webview.start()
runs the WinForms message loop and blocks until the window closes. uvicorn
therefore runs on a daemon worker thread. That is directly supported -- uvicorn's
capture_signals() short-circuits when it is not on the main thread, so no signal
handler juggling is needed.

The dev flow (`uvicorn app:app`, via start.ps1) is unaffected and still works;
it just serves to a browser instead of a window.
"""

import ctypes
import logging
import multiprocessing
import os
import socket
import sys
import threading

import paths

# Keeps the Windows mutex handle alive for the process lifetime. If this is
# garbage collected the single-instance guard silently stops working.
_INSTANCE_MUTEX = None

MUTEX_NAME = "Local\\DX7VoiceBrowser.SingleInstance"
APP_USER_MODEL_ID = "DX7VoiceBrowser.App"

# WebView2 Evergreen runtime, per Microsoft's documented detection key.
_WEBVIEW2_KEYS = (
    r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
    r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    r"SOFTWARE\Microsoft\EdgeUpdate\Clients"
    r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
)


def _setup_logging():
    """Log to a file, never to stdout.

    Under a --windowed PyInstaller build sys.stdout and sys.stderr are None, so
    stream logging is silently discarded by Handler.handleError -- exactly when
    a broken build most needs to be diagnosable. The log file is the only
    diagnostic channel the packaged app has.
    """
    import paths

    handler = logging.FileHandler(paths.log_path(), encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [handler]


def _message_box(text, title="DX7 Voice Browser", flags=0x10):
    """Win32 MessageBox. The only way to talk to the user before the window
    exists (or when it never will). Default flags = MB_ICONERROR."""
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception:
        logging.getLogger("dx7.launcher").exception("MessageBox failed")


def _acquire_single_instance():
    """False if another copy is already running.

    A onefile build unpacks for a few seconds with no visible feedback, so users
    reliably double-click a second time. Without this guard that yields two
    servers on different ports, two windows, and two writers on one SQLite file
    -- which surfaces as 'database is locked' partway through a scan.
    """
    global _INSTANCE_MUTEX
    if sys.platform != "win32":
        return True

    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE

    handle = k32.CreateMutexW(None, True, MUTEX_NAME)
    if not handle or ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return False
    _INSTANCE_MUTEX = handle
    return True


def _webview2_installed():
    """Whether the WebView2 Evergreen runtime is present.

    It ships with Windows 11 and Windows 10 21H2+, but not with Windows 10 LTSC
    or some Server SKUs. Without it pywebview fails with an opaque COM error, so
    check first and say something useful instead.
    """
    if sys.platform != "win32":
        return True
    import winreg

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key in _WEBVIEW2_KEYS:
            try:
                with winreg.OpenKey(root, key) as k:
                    version, _ = winreg.QueryValueEx(k, "pv")
                    if version and version != "0.0.0.0":
                        return True
            except OSError:
                continue
    return False


def main():
    _setup_logging()
    log = logging.getLogger("dx7.launcher")

    if not _acquire_single_instance():
        log.info("Another instance is already running; exiting.")
        return 0

    if not _webview2_installed():
        log.error("WebView2 runtime not found.")
        _message_box(
            "DX7 Voice Browser needs the Microsoft Edge WebView2 runtime, "
            "which does not appear to be installed on this PC.\n\n"
            "Download the free 'Evergreen Bootstrapper' from:\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
            "Install it, then start DX7 Voice Browser again."
        )
        return 1

    import paths
    import uvicorn
    import webview
    from app import app as asgi_app

    if sys.platform == "win32":
        # Groups the window under its own taskbar icon rather than python.exe's.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except Exception:
            log.warning("Could not set AppUserModelID", exc_info=True)

    # Bind the socket here rather than letting uvicorn do it, so the port is
    # known before the server thread starts. This removes the startup race
    # outright: the socket is already listening, so the window's first request
    # queues in the backlog instead of being refused. Port 0 asks the OS for a
    # free ephemeral port, so nothing breaks when something else holds :8000.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # No SO_REUSEADDR: on Windows that would let another process steal the port.
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
    except OSError:
        log.exception("Could not bind a local port")
        _message_box("DX7 Voice Browser could not open a local network port.")
        return 1

    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/"
    log.info("Serving on %s (data dir: %s)", url, paths.user_data_dir())

    config = uvicorn.Config(
        asgi_app,
        loop="asyncio",   # explicit, so the uvloop probe never runs
        http="h11",       # explicit: httptools is not installed
        ws="none",        # the app uses no websockets
        lifespan="on",    # database init + demo seeding run here
        log_config=None,  # uvicorn's default logs to ext://sys.stdout, == None
        access_log=False,
        workers=1,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [sock]},
        name="uvicorn",
        daemon=True,
    )
    thread.start()

    webview.create_window(
        "DX7 Voice Browser",
        url,
        width=1440,
        height=900,
        min_size=(1024, 640),
        text_select=True,
        background_color="#0a0c0f",  # matches --ds-bg, so no white flash on open
    )

    try:
        webview.start(
            gui="edgechromium",
            private_mode=False,  # persist the profile between launches
            storage_path=str(paths.webview_storage_dir()),
            debug=bool(os.environ.get("DX7_DEBUG")),
        )  # blocks until the window is closed
    finally:
        # Server.main_loop() checks should_exit every 100 ms, so this is quick.
        # The thread is a daemon, so a hang cannot keep the process alive -- but
        # joining gives SQLite a chance to finish committing an in-flight scan.
        server.should_exit = True
        thread.join(timeout=5.0)
        if thread.is_alive():
            log.warning("uvicorn did not stop within 5s; forcing exit.")
            logging.shutdown()
            os._exit(0)

    log.info("Shut down cleanly.")
    logging.shutdown()
    return 0


def _run():
    """Runs main(), turning any unhandled failure into something visible.

    A --windowed build has sys.stderr set to None, so the default excepthook
    writes nowhere: an exception escaping main() means the process disappears
    with no window, no message and no clue. Both realistic startup failures land
    here -- paths.user_data_dir() raising PermissionError from its mkdir, and
    app.py raising RuntimeError when the bundled static assets are missing.
    """
    try:
        return main()
    except Exception:
        try:
            logging.getLogger("dx7.launcher").exception("Fatal startup error")
            log_hint = f"\n\nDetails were written to:\n{paths.log_path()}"
        except Exception:
            log_hint = ""
        _message_box(
            "DX7 Voice Browser could not start." + log_hint
        )
        return 1


if __name__ == "__main__":
    # Must come first: a frozen executable that touches multiprocessing at all,
    # directly or through a dependency, will otherwise re-run main() in every
    # child process and fork-bomb itself.
    multiprocessing.freeze_support()
    sys.exit(_run())
