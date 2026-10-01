"""Render the real YouTube page in a true-color terminal pixel grid."""

from __future__ import annotations

import argparse
import base64
from http.client import HTTPConnection
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unicodedata import category
from urllib.parse import quote_plus, urlsplit

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from youtubecmd.setup import enable_ansi
from youtubecmd.visual_terminal import (
    prepare_terminal_pixels,
    render_control_markers,
    render_rgb_frame,
)


VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
DEFAULT_FPS = 8
MAX_FPS = 15
MAX_SCREENSHOT_BYTES = 16 * 1024 * 1024
MAX_CDP_MESSAGE_BYTES = 32 * 1024 * 1024
MAX_INTERACTIVE_ELEMENTS = 40
INTERACTIVE_SCRIPT = r"""(() => {
  const selectors = 'a[href],button,input:not([type="hidden"]),textarea,select,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"]),video';
    const candidates = Array.from(document.querySelectorAll(selectors)).slice(0, 3000);
    const offset = Math.max(0, Number(window.__youtubecmdOffset) || 0);
  const targets = [];
  const items = [];
    let visibleCount = 0;
    let hasMore = false;
  for (const element of candidates) {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0 ||
        rect.width < 3 || rect.height < 3 || rect.right <= 0 || rect.bottom <= 0 ||
        rect.left >= innerWidth || rect.top >= innerHeight || element.disabled) continue;
        if (visibleCount < offset) {
            visibleCount += 1;
            continue;
        }
        if (targets.length >= 40) {
            hasMore = true;
            break;
        }
    const label = (element.getAttribute('aria-label') || element.getAttribute('title') ||
      element.getAttribute('placeholder') || element.innerText || element.textContent ||
      element.getAttribute('alt') || element.tagName).replace(/\s+/g, ' ').trim().slice(0, 100);
    targets.push(element);
        visibleCount += 1;
    items.push({number: targets.length, tag: element.tagName.toLowerCase(), label,
      x: Math.max(0, rect.left), y: Math.max(0, rect.top),
      width: Math.min(rect.right, innerWidth) - Math.max(0, rect.left),
      height: Math.min(rect.bottom, innerHeight) - Math.max(0, rect.top)});
  }
  window.__youtubecmdTargets = targets;
    return {items, hasMore, offset, url: location.href.slice(0, 2048)};
})()"""


class VisualBrowserError(RuntimeError):
    """An expected browser or terminal visual-mode failure."""


def resolve_youtube_input(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return "https://www.youtube.com/"
    if candidate.lower().startswith(("https://", "http://")):
        parsed = urlsplit(candidate)
        if not parsed.hostname:
            raise VisualBrowserError("Enter a valid HTTP or HTTPS address.")
        return candidate
    if "://" in candidate:
        raise VisualBrowserError("Only HTTP and HTTPS addresses are supported.")
    return "https://www.youtube.com/results?search_query=" + quote_plus(candidate)


def _find_browser() -> tuple[str, str] | None:
    env_name = os.environ.get("YOUTUBECMD_BROWSER", "").strip().lower()
    explicit_order = {
        "chrome": ("Chrome", ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable")),
        "chromium": ("Chromium", ("chromium", "chromium-browser", "chromium.exe")),
        "brave": ("Brave", ("brave", "brave.exe", "brave-browser")),
        "edge": ("Edge", ("msedge", "msedge.exe")),
    }
    if env_name in explicit_order:
        ordered = [explicit_order[env_name]]
    else:
        ordered = [
            ("Chrome", ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable")),
            ("Brave", ("brave", "brave.exe", "brave-browser")),
            ("Chromium", ("chromium", "chromium-browser", "chromium.exe")),
            ("Edge", ("msedge", "msedge.exe")),
        ]
    for label, names in ordered:
        for name in names:
            path = shutil.which(name)
            if path:
                return label, path
    if os.name == "nt":
        roots = (
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
            Path(os.environ.get("LOCALAPPDATA", "")),
        )
        paths = (
            ("Chrome", Path("Google/Chrome/Application/chrome.exe")),
            ("Brave", Path("BraveSoftware/Brave-Browser/Application/brave.exe")),
            ("Chromium", Path("Chromium/Application/chrome.exe")),
            ("Chromium", Path("Chromium/chrome.exe")),
            ("Edge", Path("Microsoft/Edge/Application/msedge.exe")),
        )
        for label, relative in paths:
            for root in roots:
                candidate = root / relative
                if candidate.is_file():
                    return label, str(candidate)
    return None


def _browser_headless_variants(browser_label: str) -> tuple[str, ...]:
    return ("--headless=new", "--headless", "--headless=old")


def _profile_directory() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "YouTubeCMD" / "browser-profile-v2"


class ChromePage:
    def __init__(self, url: str):
        self.url = url
        self.label = ""
        self._profile_path: Path | None = None
        self._process: subprocess.Popen | None = None
        self._socket: Any = None
        self._command_id = 0
        self._targets: list[dict[str, Any]] = []
        self._has_more = False
        self._target_offset = 0

    def __enter__(self) -> ChromePage:
        found = _find_browser()
        if found is None:
            raise VisualBrowserError("Install Chrome, Chromium, Brave, or Edge.")
        self.label, browser_path = found
        self._profile_path = _profile_directory()
        self._profile_path.mkdir(parents=True, exist_ok=True)

        last_error: Exception | None = None
        headless_variants = _browser_headless_variants(self.label)
        for headless_flag in headless_variants:
            arguments = [
                browser_path,
                headless_flag,
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=0",
                f"--user-data-dir={self._profile_path}",
                "--no-first-run",
                "--no-default-browser-check",
                "--autoplay-policy=no-user-gesture-required",
                f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}",
                "about:blank",
            ]
            options: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "shell": False,
                "close_fds": True,
            }
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            else:
                options["start_new_session"] = True
            try:
                self._process = subprocess.Popen(arguments, **options)
                port = self._wait_for_debug_port()
                targets = self._get_json(port, "/json/list")
                if not isinstance(targets, list):
                    raise VisualBrowserError("The browser returned an invalid page list.")
                endpoint = next((item.get("webSocketDebuggerUrl") for item in targets
                                 if isinstance(item, dict) and item.get("type") == "page"), None)
                parsed = urlsplit(endpoint or "")
                if (parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                        or parsed.port != port):
                    raise VisualBrowserError("The browser returned an unsafe local debugging endpoint.")
                try:
                    self._socket = connect(
                        endpoint, origin=None, open_timeout=10, close_timeout=2,
                        max_size=MAX_CDP_MESSAGE_BYTES,
                    )
                except WebSocketException as error:
                    raise VisualBrowserError("Could not connect to the browser's local page session.") from error
                self.command("Page.enable")
                self.command("Runtime.enable")
                self.command("Emulation.setDeviceMetricsOverride", {
                    "width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT,
                    "deviceScaleFactor": 1, "mobile": False,
                })
                self.navigate(self.url)
                return self
            except Exception as error:
                last_error = error
                self.close()
                if headless_flag == headless_variants[-1]:
                    break
        if last_error is not None:
            raise last_error
        raise VisualBrowserError(f"{self.label} did not start successfully in any supported headless mode.")

    @staticmethod
    def _get_json(port: int, path: str) -> object:
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            if response.status != 200:
                raise VisualBrowserError("The browser rejected its local debugging request.")
            with response:
                payload = response.read(2 * 1024 * 1024 + 1)
        except OSError as error:
            raise VisualBrowserError("Could not contact the local browser endpoint.") from error
        finally:
            connection.close()
        if len(payload) > 2 * 1024 * 1024:
            raise VisualBrowserError("The browser returned an oversized page list.")
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise VisualBrowserError("The browser returned malformed debugging data.") from error

    def _wait_for_debug_port(self) -> int:
        assert self._profile_path is not None and self._process is not None
        active_port = self._profile_path / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise VisualBrowserError(f"{self.label} exited during startup.")
            try:
                port = int(active_port.read_text(encoding="ascii").splitlines()[0])
                if 1 <= port <= 65535:
                    return port
            except (OSError, ValueError, IndexError):
                pass
            time.sleep(0.05)
        raise VisualBrowserError(f"{self.label} did not start its local browser endpoint.")

    def command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._socket is None:
            raise VisualBrowserError("The browser connection is closed.")
        self._command_id += 1
        command_id = self._command_id
        self._socket.send(json.dumps({
            "id": command_id, "method": method, "params": params or {},
        }, separators=(",", ":")))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                raw = self._socket.recv(timeout=max(0.1, deadline - time.monotonic()))
            except TimeoutError as error:
                raise VisualBrowserError(f"Timed out waiting for browser command {method}.") from error
            if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_CDP_MESSAGE_BYTES:
                raise VisualBrowserError("The browser returned an invalid or oversized message.")
            try:
                response = json.loads(raw)
            except json.JSONDecodeError as error:
                raise VisualBrowserError("The browser returned malformed protocol data.") from error
            if not isinstance(response, dict) or response.get("id") != command_id:
                continue
            if "error" in response:
                details = response["error"]
                message = details.get("message", "command failed") if isinstance(details, dict) else "command failed"
                raise VisualBrowserError(str(message)[:300])
            result = response.get("result", {})
            if not isinstance(result, dict):
                raise VisualBrowserError("The browser returned an invalid command result.")
            return result
        raise VisualBrowserError(f"Timed out waiting for browser command {method}.")

    def evaluate(self, expression: str) -> Any:
        result = self.command("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": False,
        })
        if "exceptionDetails" in result:
            raise VisualBrowserError("The page rejected that interaction.")
        remote = result.get("result", {})
        return remote.get("value") if isinstance(remote, dict) else None

    def navigate(self, url: str) -> None:
        result = self.command("Page.navigate", {"url": url})
        if result.get("errorText"):
            raise VisualBrowserError(str(result["errorText"])[:300])
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if self.evaluate("document.readyState") in {"interactive", "complete"}:
                    self.url = url
                    time.sleep(0.6)
                    return
            except VisualBrowserError:
                pass
            time.sleep(0.1)
        raise VisualBrowserError("The page did not finish loading in time.")

    def visible_elements(self) -> list[dict[str, Any]]:
        result = self.evaluate(INTERACTIVE_SCRIPT)
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            self._targets = []
            return []
        current_url = result.get("url")
        if isinstance(current_url, str):
            current_url = current_url[:2048]
            if current_url != self.url and self._target_offset:
                self._target_offset = 0
                self.evaluate("window.__youtubecmdOffset = 0")
            self.url = current_url
        self._targets = [
            item for item in result["items"][:MAX_INTERACTIVE_ELEMENTS]
            if isinstance(item, dict)
        ]
        self._has_more = bool(result.get("hasMore"))
        self._target_offset = max(0, int(result.get("offset", 0) or 0))
        return self._targets

    def click(self, number: int) -> str:
        if not 1 <= number <= len(self._targets):
            raise VisualBrowserError("That number is not on the current page.")
        target = self._targets[number - 1]
        x = float(target.get("x", 0)) + float(target.get("width", 0)) / 2
        y = float(target.get("y", 0)) + float(target.get("height", 0)) / 2
        if not math.isfinite(x) or not math.isfinite(y):
            raise VisualBrowserError("That page control has invalid coordinates.")
        self.command("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "clickCount": 1,
        })
        self.command("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "clickCount": 1,
        })
        label = str(target.get("label", target.get("tag", "control")))[:80]
        return f"Clicked {number}: {label}"

    def hover(self, number: int) -> str:
        if not 1 <= number <= len(self._targets):
            raise VisualBrowserError("That number is not on the current page.")
        target = self._targets[number - 1]
        x = float(target.get("x", 0)) + float(target.get("width", 0)) / 2
        y = float(target.get("y", 0)) + float(target.get("height", 0)) / 2
        self.command("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        label = str(target.get("label", target.get("tag", "control")))[:80]
        return f"Hovering {number}: {label}"

    def page_controls(self, direction: str) -> str:
        if direction == "next":
            if not self._has_more:
                return "No more visible controls"
            self._target_offset += MAX_INTERACTIVE_ELEMENTS
        elif direction == "previous":
            self._target_offset = max(0, self._target_offset - MAX_INTERACTIVE_ELEMENTS)
        else:
            raise VisualBrowserError("Control page must be next or previous.")
        self.evaluate(f"window.__youtubecmdOffset = {self._target_offset}")
        return f"Showing controls {self._target_offset + 1}-{self._target_offset + MAX_INTERACTIVE_ELEMENTS}"

    def screenshot(self) -> str:
        result = self.command("Page.captureScreenshot", {
            "format": "png", "fromSurface": True,
            "captureBeyondViewport": False,
        })
        data = result.get("data")
        if not isinstance(data, str) or len(data) > MAX_SCREENSHOT_BYTES * 2:
            raise VisualBrowserError("The browser returned an invalid or oversized screenshot.")
        try:
            decoded = base64.b64decode(data, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise VisualBrowserError("The browser returned malformed screenshot data.") from error
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n") or len(decoded) > MAX_SCREENSHOT_BYTES:
            raise VisualBrowserError("The browser returned an invalid screenshot image.")
        return data

    def type_text(self, text: str) -> None:
        if len(text) > 1000:
            raise VisualBrowserError("Text input is limited to 1000 characters.")
        self.command("Input.insertText", {"text": text})

    def press_key(self, key: str) -> None:
        keys = {
            "enter": ("Enter", 13), "space": (" ", 32),
            "tab": ("Tab", 9), "escape": ("Escape", 27),
            "backspace": ("Backspace", 8),
        }
        key_name, key_code = keys.get(key.lower(), ("", 0))
        if not key_name:
            raise VisualBrowserError("Supported keys: enter, space, tab, escape, backspace.")
        self.command("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": key_name, "code": key_name,
            "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code,
        })
        self.command("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": key_name, "code": key_name,
            "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code,
        })

    def scroll(self, direction: str) -> None:
        if direction not in {"up", "down"}:
            raise VisualBrowserError("Scroll direction must be up or down.")
        amount = "-Math.floor(innerHeight * 0.75)" if direction == "up" else "Math.floor(innerHeight * 0.75)"
        self._target_offset = 0
        self.evaluate(
            f"window.__youtubecmdOffset = 0; "
            f"window.scrollBy({{top: {amount}, behavior: 'instant'}})"
        )

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=False, timeout=5,
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
    def __exit__(self, *_exc: object) -> None:
        self.close()


class _TerminalInput:
    def __init__(self) -> None:
        self._old_settings = None

    def __enter__(self) -> _TerminalInput:
        if os.name != "nt":
            import termios
            import tty

            self._old_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._old_settings is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings)

    @staticmethod
    def poll() -> str | None:
        if os.name == "nt":
            import msvcrt

            if not msvcrt.kbhit():
                return None
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                return {"H": "up", "P": "down"}.get(msvcrt.getwch())
            if key == "\x1b":
                return "escape"
            return key
        import select

        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        key = sys.stdin.read(1)
        if key == "\x1b" and select.select([sys.stdin], [], [], 0)[0]:
            if sys.stdin.read(1) == "[" and select.select([sys.stdin], [], [], 0)[0]:
                return {"A": "up", "B": "down"}.get(sys.stdin.read(1), "escape")
            return "escape"
        return key


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(100, 30))
    return min(240, max(1, size.columns)), min(120, max(4, size.lines))


def _safe_status(value: str, limit: int = 160) -> str:
    return "".join(
        char if char.isprintable() and category(char) not in {"Cf", "Cs"} else " "
        for char in value
    )[:limit]


def _write_terminal(
    browser: ChromePage,
    command_buffer: str,
    status: str,
    columns: int,
    rows: int,
) -> None:
    elements = browser.visible_elements()
    screenshot = browser.screenshot()
    pixels, width, height, markers = prepare_terminal_pixels(
        screenshot, elements, columns, rows, VIEWPORT_WIDTH, VIEWPORT_HEIGHT
    )
    page = render_rgb_frame(pixels, width, height)
    page_rows = height // 2
    page += render_control_markers(markers, width, page_rows)
    status_line = _safe_status(
        f"{browser.url} | {status} | {len(elements)} controls marked", columns
    )
    help_line = _safe_status("N click | h N hover | more/prev controls | /search | g URL | t text | arrows scroll | q quit", columns)
    prompt_line = _safe_status("> " + command_buffer, columns)
    output = ["\x1b[H", page, "\x1b[0m"]
    output.extend((
        f"\x1b[{page_rows + 1};1H\x1b[2K{status_line}",
        f"\x1b[{page_rows + 2};1H\x1b[2K{help_line}",
        f"\x1b[{page_rows + 3};1H\x1b[2K{prompt_line}",
    ))
    sys.stdout.write("".join(output))
    sys.stdout.flush()


def _run_command(browser: ChromePage, command: str) -> tuple[str, bool]:
    command = command.strip()
    lowered = command.lower()
    if lowered in {"q", "quit", ":quit"}:
        return "Closing YouTube browser", False
    if lowered.startswith("/"):
        query = command[1:].strip()
        if not query:
            return "Enter search words after /", True
        browser.navigate(resolve_youtube_input(query))
        return f"Searching YouTube: {query[:100]}", True
    if lowered.startswith("g "):
        browser.navigate(resolve_youtube_input(command[2:]))
        return "Page loaded", True
    if lowered.startswith("t "):
        browser.type_text(command[2:])
        return "Text entered in focused page control; use 'enter' to submit", True
    if lowered.startswith("h "):
        try:
            number = int(command[2:].strip())
        except ValueError:
            return "Use h followed by a visible control number", True
        return browser.hover(number), True
    if lowered in {"more", "prev"}:
        direction = "next" if lowered == "more" else "previous"
        return browser.page_controls(direction), True
    if lowered in {"enter", "space", "tab", "escape", "backspace"}:
        browser.press_key(lowered)
        return f"Sent {lowered}", True
    if lowered in {"up", "down"}:
        browser.scroll(lowered)
        return f"Scrolled {lowered}", True
    if lowered in {"r", "reload"}:
        browser.command("Page.reload", {"ignoreCache": False})
        return "Reloading page", True
    if command.isdigit():
        return browser.click(int(command)), True
    return "Unknown command. Use a marker number, /search, g URL, t text, or q.", True


def run_visual_browser(source: str | None = None, fps: int = DEFAULT_FPS) -> int:
    if not 1 <= fps <= MAX_FPS:
        raise VisualBrowserError(f"Refresh rate must be between 1 and {MAX_FPS} FPS.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not enable_ansi():
        raise VisualBrowserError("Run this mode in Windows Terminal or an ANSI-compatible terminal.")
    url = resolve_youtube_input(source)
    columns, rows = _terminal_size()
    with ChromePage(url) as browser, _TerminalInput():
        sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        command_buffer = ""
        status = f"{browser.label} | true-color terminal view"
        next_frame = 0.0
        running = True
        try:
            while running:
                key = _TerminalInput.poll()
                if key == "\x03":
                    break
                if key == "escape":
                    try:
                        browser.press_key("escape")
                        status = "Sent escape to the webpage"
                    except VisualBrowserError as error:
                        status = str(error)
                elif key in ("up", "down") and not command_buffer:
                    try:
                        browser.scroll(key)
                        status = f"Scrolled {key}"
                    except VisualBrowserError as error:
                        status = str(error)
                elif key in ("\r", "\n"):
                    try:
                        status, running = _run_command(browser, command_buffer)
                    except VisualBrowserError as error:
                        status = str(error)
                    command_buffer = ""
                    next_frame = 0.0
                elif key in ("\b", "\x7f"):
                    command_buffer = command_buffer[:-1]
                elif key and len(key) == 1 and key.isprintable() and len(command_buffer) < 256:
                    command_buffer += key

                now = time.monotonic()
                if running and now >= next_frame:
                    columns, rows = _terminal_size()
                    _write_terminal(browser, command_buffer, status, columns, rows)
                    next_frame = now + 1.0 / fps
                time.sleep(0.01)
        finally:
            sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
            sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browse real YouTube pages in a true-color terminal")
    parser.add_argument("source", nargs="*", help="YouTube URL or search words")
    parser.add_argument(
        "--fps", type=int, default=DEFAULT_FPS,
        help=f"terminal refresh rate (1-{MAX_FPS} FPS, default {DEFAULT_FPS})",
    )
    args = parser.parse_args(argv)
    try:
        return run_visual_browser(" ".join(args.source) or None, args.fps)
    except KeyboardInterrupt:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
        return 0
    except (VisualBrowserError, OSError, ValueError, WebSocketException) as error:
        print(f"YouTubeCMD: {_safe_status(str(error), 500)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())