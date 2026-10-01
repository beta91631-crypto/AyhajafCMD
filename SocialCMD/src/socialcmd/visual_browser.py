"""Browse web pages as readable text in a terminal."""

from __future__ import annotations

import argparse
import base64
from http.client import HTTPConnection
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unicodedata import category
from urllib.parse import quote_plus, urlsplit

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from socialcmd.setup import enable_ansi
from socialcmd.visual_terminal import (
    MAX_SCREENSHOT_BYTES,
    prepare_terminal_pixels,
    render_control_markers,
    render_rgb_frame,
)


VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
PLATFORMS = {
    "facebook": "https://www.facebook.com/",
    "instagram": "https://www.instagram.com/",
    "linkedin": "https://www.linkedin.com/feed/",
    "pinterest": "https://www.pinterest.com/",
    "reddit": "https://www.reddit.com/",
    "threads": "https://www.threads.net/",
    "tiktok": "https://www.tiktok.com/",
    "x": "https://x.com/",
}
PLATFORM_ALIASES = {"fb": "facebook", "ig": "instagram", "twitter": "x"}
MAX_CDP_MESSAGE_BYTES = 32 * 1024 * 1024
MAX_INTERACTIVE_ELEMENTS = 40
INTERACTIVE_SCRIPT = r"""(() => {
    const selectors = 'a[href],button,input:not([type="hidden"]),textarea,select,[role="button"],[role="link"],[role="textbox"],[contenteditable="true"],[tabindex]:not([tabindex="-1"]),video';
        const candidates = Array.from(document.querySelectorAll(selectors)).slice(0, 1000);
    const offset = Math.max(0, Number(window.__socialcmdOffset) || 0);
  const targets = [];
  const items = [];
    let visibleCount = 0;
    let hasMore = false;
  for (const element of candidates) {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0 ||
        rect.width < 3 || rect.height < 3 || element.getClientRects().length === 0 || element.disabled) continue;
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
                href: element.href || '', type: element.type || '',
                editable: element.isContentEditable || element.matches('input,textarea,select,[role="textbox"]'),
      x: Math.max(0, rect.left), y: Math.max(0, rect.top),
      width: Math.min(rect.right, innerWidth) - Math.max(0, rect.left),
      height: Math.min(rect.bottom, innerHeight) - Math.max(0, rect.top)});
  }
    window.__socialcmdTargets = targets;
    return {items, hasMore, offset, url: location.href.slice(0, 2048)};
})()"""
HELP_TEXT = """SOCIALCMD CONTROLS

N           Click numbered pixel marker
click NAME  Click a control by its visible name
open NAME   Open a link by its visible name
focus NAME  Focus a named input
type NAME=TEXT  Focus an input and enter text
/words      Search the web
g URL       Open an address or search words
back / b    Go back
forward / f Go forward
reload / r  Reload this page
home        Return to the site chosen at startup
h N         Hover a numbered control
more / prev Show another marker page
update      Refresh the live page image
t TEXT      Type into the focused page control
enter       Activate the focused page control
q           Quit SocialCMD"""


class VisualBrowserError(RuntimeError):
    """An expected browser or terminal visual-mode failure."""


def resolve_social_input(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise VisualBrowserError("Choose a social site or enter a URL.")
    platform = PLATFORM_ALIASES.get(candidate.lower(), candidate.lower())
    if platform in PLATFORMS:
        return PLATFORMS[platform]
    if candidate.lower().startswith(("https://", "http://")):
        parsed = urlsplit(candidate)
        if not parsed.hostname:
            raise VisualBrowserError("Enter a valid HTTP or HTTPS address.")
        return candidate
    if "://" in candidate:
        raise VisualBrowserError("Only HTTP and HTTPS addresses are supported.")
    return "https://duckduckgo.com/?q=" + quote_plus(candidate)


def _match_controls(
    elements: list[dict[str, Any]],
    query: str,
    *,
    links_only: bool = False,
    editable_only: bool = False,
) -> list[dict[str, Any]]:
    terms = " ".join(query.casefold().split())
    if not terms:
        return []
    matches = []
    for element in elements:
        tag = str(element.get("tag", "")).casefold()
        href = str(element.get("href", "")).casefold()
        label = " ".join(str(element.get("label", "")).casefold().split())
        if links_only and tag != "a" and not href:
            continue
        if editable_only and not element.get("editable"):
            continue
        searchable = f"{label} {href}"
        if terms == label or terms == href or terms in searchable:
            matches.append(element)
            continue
        if all(term in searchable for term in terms.split()):
            matches.append(element)
    return matches


def choose_start_url() -> str | None:
    choices = tuple(PLATFORMS.items())
    print("\x1b[2J\x1b[H\x1b[1;36mSOCIALCMD  /  CHOOSE YOUR SITE\x1b[0m")
    print("\x1b[2mPick any site, or paste a web address. Nothing is selected for you.\x1b[0m\n")
    for number, (name, _) in enumerate(choices, start=1):
        print(f"  \x1b[1;33m{number:>2}\x1b[0m  {name.title()}")
    print("\n  \x1b[1;33mU\x1b[0m   Custom URL or web search")
    print("  \x1b[1;33mQ\x1b[0m   Quit\n")
    while True:
        try:
            selection = input("Choose a site or enter a URL > ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if selection.lower() in {"q", "quit"}:
            return None
        if selection.lower() == "u":
            selection = input("URL or search terms > ").strip()
            if not selection:
                print("Enter an address or search terms.")
                continue
            return resolve_social_input(selection)
        if selection.isdigit() and 1 <= int(selection) <= len(choices):
            return choices[int(selection) - 1][1]
        try:
            return resolve_social_input(selection)
        except VisualBrowserError as error:
            print(str(error))


def _profile_directory() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "SocialCMD" / "browser-profile"


def _reserve_debug_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        return int(endpoint.getsockname()[1])


def _browser_candidates() -> list[tuple[str, tuple[str, ...]]]:
    env_name = os.environ.get("SOCIALCMD_BROWSER", "").strip().lower()
    explicit_order = {
        "chrome": ("Chrome", ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable")),
        "chromium": ("Chromium", ("chromium", "chromium-browser", "chromium.exe")),
        "brave": ("Brave", ("brave", "brave.exe", "brave-browser")),
        "edge": ("Edge", ("msedge", "msedge.exe")),
    }
    if env_name in explicit_order:
        return [explicit_order[env_name]]

    default_order = (
        ("Chrome", ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable")),
        ("Brave", ("brave", "brave.exe", "brave-browser")),
        ("Chromium", ("chromium", "chromium-browser", "chromium.exe")),
        ("Edge", ("msedge", "msedge.exe")),
    )
    return list(default_order)


def _find_browser() -> tuple[str, str] | None:
    for label, names in _browser_candidates():
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
    label = (browser_label or "").lower()
    if label in {"brave", "chrome", "chromium"}:
        return ("--headless=new", "--headless", "--headless=old")
    return ("--headless=new", "--headless", "--headless=old")


class ChromePage:
    def __init__(
        self,
        url: str,
        private: bool = False,
        load_visual_resources: bool = True,
    ):
        self.url = url
        self.home_url = url
        self.label = ""
        self._profile: tempfile.TemporaryDirectory | None = None
        self._private = private
        self._load_visual_resources = load_visual_resources
        self._process: subprocess.Popen | None = None
        self._startup_log_path: Path | None = None
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
        if self._private:
            self._profile = tempfile.TemporaryDirectory(prefix="SocialCMD-")
            profile_path = self._profile.name
        else:
            persistent_profile = _profile_directory()
            persistent_profile.mkdir(parents=True, exist_ok=True)
            profile_path = str(persistent_profile)

        last_error: Exception | None = None
        for headless_flag in _browser_headless_variants(self.label):
            port = _reserve_debug_port()
            arguments = [
                browser_path,
                headless_flag,
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_path}",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-gpu",
                "--disable-sync",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
                "--autoplay-policy=user-gesture-required",
                f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}",
                "about:blank",
            ]
            if not self._load_visual_resources:
                arguments.append("--blink-settings=imagesEnabled=false")
            options: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "shell": False,
                "close_fds": True,
            }
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            else:
                options["start_new_session"] = True
            try:
                with tempfile.NamedTemporaryFile(
                    prefix="SocialCMD-edge-", suffix=".log", delete=False
                ) as startup_log:
                    self._startup_log_path = Path(startup_log.name)
                    options["stderr"] = startup_log
                    self._process = subprocess.Popen(arguments, **options)
                targets = self._wait_for_page_list(port)
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
            except Exception as error:  # pragma: no cover - exercised by browser compatibility checks.
                last_error = error
                self.close()
                if headless_flag == _browser_headless_variants(self.label)[-1]:
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

    def _wait_for_page_list(self, port: int) -> list[dict[str, Any]]:
        assert self._process is not None
        deadline = time.monotonic() + 15
        last_error: VisualBrowserError | None = None
        while time.monotonic() < deadline:
            try:
                targets = self._get_json(port, "/json/list")
                if not isinstance(targets, list):
                    raise VisualBrowserError("The browser returned an invalid page list.")
                if any(
                    isinstance(item, dict)
                    and item.get("type") == "page"
                    and isinstance(item.get("webSocketDebuggerUrl"), str)
                    for item in targets
                ):
                    return targets
                last_error = VisualBrowserError("The browser has not created a page target yet.")
            except VisualBrowserError as error:
                if str(error) != "Could not contact the local browser endpoint.":
                    raise
                last_error = error
            time.sleep(0.1)
        return_code = self._process.poll()
        if return_code is None:
            message = f"{self.label} did not expose a page through its local endpoint on port {port}."
        else:
            message = f"{self.label} exited with code {return_code} before exposing a page on port {port}."
        details = self._startup_log_excerpt()
        if details:
            message += f" Browser output: {details}"
        raise VisualBrowserError(message) from last_error

    def _startup_log_excerpt(self) -> str:
        if self._startup_log_path is None:
            return ""
        try:
            lines = self._startup_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        return " | ".join(line.strip() for line in lines[-5:] if line.strip())[-500:]

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
                raise VisualBrowserError(f"{method}: {str(message)[:280]}")
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
                self.evaluate("window.__socialcmdOffset = 0")
            self.url = current_url
        self._targets = [
            item for item in result["items"][:MAX_INTERACTIVE_ELEMENTS]
            if isinstance(item, dict)
        ]
        self._has_more = bool(result.get("hasMore"))
        self._target_offset = max(0, int(result.get("offset", 0) or 0))
        return self._targets

    def screenshot(self) -> str:
        result = self.command("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": False,
        })
        data = result.get("data")
        if not isinstance(data, str) or len(data) > MAX_SCREENSHOT_BYTES * 2:
            raise VisualBrowserError("The browser returned an invalid or oversized screenshot.")
        return data

    def _target_coordinates(self, number: int) -> tuple[float, float]:
        if not 1 <= number <= len(self._targets):
            raise VisualBrowserError("That number is not in the current links list.")
        index = number - 1
        position = self.evaluate(
            "(() => {"
            f"const element = window.__socialcmdTargets[{index}];"
            "if (!element) return null;"
            "element.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'});"
            "const rect = element.getBoundingClientRect();"
            "return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};"
            "})()"
        )
        if not isinstance(position, dict):
            raise VisualBrowserError("That page control is no longer available.")
        x = float(position.get("x", 0))
        y = float(position.get("y", 0))
        if not math.isfinite(x) or not math.isfinite(y):
            raise VisualBrowserError("That page control has invalid coordinates.")
        return x, y

    def click(self, number: int) -> str:
        x, y = self._target_coordinates(number)
        target = self._targets[number - 1]
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
        x, y = self._target_coordinates(number)
        target = self._targets[number - 1]
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
        self.evaluate(f"window.__socialcmdOffset = {self._target_offset}")
        return f"Showing controls {self._target_offset + 1}-{self._target_offset + MAX_INTERACTIVE_ELEMENTS}"

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
            f"window.__socialcmdOffset = 0; "
            f"window.scrollBy({{top: {amount}, behavior: 'instant'}})"
        )

    def navigate_history(self, direction: str) -> str:
        if direction not in {"back", "forward"}:
            raise VisualBrowserError("History direction must be back or forward.")
        history = self.command("Page.getNavigationHistory")
        entries = history.get("entries", [])
        current_index = history.get("currentIndex")
        delta = -1 if direction == "back" else 1
        target_index = current_index + delta if isinstance(current_index, int) else -1
        if not isinstance(entries, list) or not 0 <= target_index < len(entries):
            return f"No page to go {direction}"
        entry_id = entries[target_index].get("id")
        if not isinstance(entry_id, int):
            return f"No page to go {direction}"
        self.command("Page.navigateToHistoryEntry", {"entryId": entry_id})
        return f"Going {direction}"

    def find_text(self, query: str) -> bool:
        if not query.strip():
            raise VisualBrowserError("Enter text to find on this page.")
        return bool(self.evaluate(f"window.find({json.dumps(query[:200])})"))

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
        if self._profile is not None:
            self._profile.cleanup()
            self._profile = None
        if self._startup_log_path is not None:
            try:
                self._startup_log_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._startup_log_path = None

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
    status: str,
    columns: int,
    frame: str,
    footer_row: int,
) -> None:
    status_line = _safe_status(
        f"{browser.label} | {browser.url} | {status}", columns
    )
    help_line = "click NAME | open NAME | focus NAME | type NAME=TEXT | N marker | / search | q quit"
    output = ["\x1b[H", frame, "\x1b[0m"]
    output.append(f"\x1b[{footer_row + 1};1H\x1b[2K\x1b[1;36m{status_line}\x1b[0m")
    output.append(f"\x1b[{footer_row + 2};1H\x1b[2K\x1b[2m{help_line[:columns]}\x1b[0m")
    sys.stdout.write("".join(output))
    sys.stdout.flush()


def _render_browser_frame(
    screenshot: str,
    elements: list[dict[str, Any]],
    columns: int,
    rows: int,
) -> tuple[str, int]:
    pixels, width, height, markers = prepare_terminal_pixels(
        screenshot, elements, columns, rows, VIEWPORT_WIDTH, VIEWPORT_HEIGHT
    )
    frame = render_rgb_frame(pixels, width, height)
    frame += render_control_markers(markers, width, height // 2)
    return frame, height // 2


def _write_prompt(command_buffer: str, columns: int, rows: int) -> None:
    prompt = _safe_status("> " + command_buffer, max(1, columns - 2))
    sys.stdout.write(f"\x1b[{rows};1H\x1b[2K\x1b[1m{prompt}\x1b[0m")
    sys.stdout.flush()


def _run_command(
    browser: ChromePage,
    command: str,
) -> tuple[str, bool]:
    command = command.strip()
    lowered = command.lower()
    if lowered in {"q", "quit", ":quit"}:
        return "Closing SocialCMD", False
    if not command:
        return "Ready", True
    if lowered in {"links", ":links"}:
        labels = [
            f"{item.get('number')}: {item.get('label') or item.get('tag')}"
            for item in browser._targets[:4]
        ]
        return "Controls: " + " | ".join(labels), True
    if lowered in {"page", "text"}:
        return "Page pixels", True
    if lowered == "help":
        return "Controls: N click, / search, g URL, back, forward, reload, home, update, q", True
    if lowered == "update":
        return "Page refreshed", True
    if lowered.startswith("/"):
        query = command[1:].strip()
        if not query:
            return "Enter search words after /", True
        browser.navigate(resolve_social_input(query))
        return f"Searching: {query[:80]}", True
    if lowered.startswith("g "):
        browser.navigate(resolve_social_input(command[2:]))
        return "Page loaded", True
    if lowered.startswith("t "):
        browser.type_text(command[2:])
        return "Text entered; press enter to submit", True
    if lowered.startswith("type "):
        field, separator, text = command[5:].partition("=")
        if not separator or not field.strip():
            return "Use type FIELD=TEXT", True
        matches = _match_controls(browser._targets, field, editable_only=True)
        if len(matches) != 1:
            if not matches:
                return f"No editable control matches '{field.strip()}'", True
            labels = ", ".join(str(item.get("label") or item.get("number")) for item in matches[:4])
            return f"Several fields match: {labels}", True
        browser.click(int(matches[0]["number"]))
        browser.type_text(text.lstrip())
        return f"Typed into {matches[0].get('label') or 'field'}", True
    if lowered.startswith(("click ", "open ", "focus ")):
        action, query = command.split(None, 1)
        action = action.lower()
        matches = _match_controls(
            browser._targets,
            query,
            links_only=action == "open",
            editable_only=action == "focus",
        )
        if len(matches) != 1:
            if not matches:
                return f"No control matches '{query[:60]}'", True
            labels = ", ".join(
                f"{item.get('number')}: {item.get('label') or item.get('tag')}"
                for item in matches[:4]
            )
            return f"Several controls match: {labels}", True
        return browser.click(int(matches[0]["number"])), True
    if lowered.startswith("h "):
        try:
            number = int(command[2:].strip())
        except ValueError:
            return "Use h followed by a control number", True
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
    if lowered in {"back", "b"}:
        return browser.navigate_history("back"), True
    if lowered in {"forward", "f"}:
        return browser.navigate_history("forward"), True
    if lowered == "home":
        browser.navigate(browser.home_url)
        return "Home page loaded", True
    if lowered in {"r", "reload"}:
        browser.command("Page.reload", {"ignoreCache": False})
        return "Reloading page", True
    if lowered.startswith("find "):
        found = browser.find_text(command[5:])
        return ("Text found" if found else "Text not found"), True
    if command.isdigit():
        return browser.click(int(command)), True
    return "Use click NAME, open NAME, focus NAME, type NAME=TEXT, or a marker number", True


def run_social_browser(
    source: str | None = None,
    private: bool = False,
    load_visual_resources: bool = True,
) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not enable_ansi():
        raise VisualBrowserError("Run this mode in Windows Terminal or an ANSI-compatible terminal.")
    if source is None:
        source = choose_start_url()
        if source is None:
            return 0
    url = resolve_social_input(source)
    columns, rows = _terminal_size()
    with ChromePage(
        url,
        private=private,
        load_visual_resources=load_visual_resources,
    ) as browser, _TerminalInput():
        sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        command_buffer = ""
        status = "Page loaded"
        screenshot = browser.screenshot()
        elements = browser.visible_elements()
        frame, footer_row = _render_browser_frame(screenshot, elements, columns, rows)
        _write_terminal(browser, status, columns, frame, footer_row)
        _write_prompt(command_buffer, columns, rows)
        running = True
        try:
            while running:
                key = _TerminalInput.poll()
                page_dirty = False
                prompt_dirty = False
                if key == "\x03":
                    break
                if key == "escape":
                    try:
                        browser.press_key("escape")
                        status = "Sent escape to the webpage"
                    except VisualBrowserError as error:
                        status = str(error)
                    page_dirty = True
                elif key in ("up", "down") and not command_buffer:
                    try:
                        browser.scroll(key)
                        status = f"Scrolled {key}"
                    except VisualBrowserError as error:
                        status = str(error)
                    page_dirty = True
                elif key in ("\r", "\n"):
                    try:
                        status, running = _run_command(browser, command_buffer)
                    except VisualBrowserError as error:
                        status = str(error)
                    command_buffer = ""
                    page_dirty = True
                    prompt_dirty = False
                elif key in ("\b", "\x7f"):
                    command_buffer = command_buffer[:-1]
                    prompt_dirty = True
                elif key and len(key) == 1 and key.isprintable() and len(command_buffer) < 256:
                    command_buffer += key
                    prompt_dirty = True

                if running and page_dirty:
                    screenshot = browser.screenshot()
                    elements = browser.visible_elements()
                    columns, rows = _terminal_size()
                    frame, footer_row = _render_browser_frame(
                        screenshot, elements, columns, rows
                    )
                    _write_terminal(
                        browser,
                        status,
                        columns,
                        frame,
                        footer_row,
                    )
                    _write_prompt(command_buffer, columns, rows)
                elif running and prompt_dirty:
                    _write_prompt(command_buffer, columns, rows)
                time.sleep(0.05)
        finally:
            sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
            sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browse social sites in full-color terminal pixels")
    parser.add_argument("source", nargs="*", help="platform name, URL, or search words")
    parser.add_argument("--private", action="store_true", help="use a temporary browser profile")
    parser.add_argument(
        "--light",
        action="store_true",
        help="disable image loading to reduce bandwidth and memory use",
    )
    args = parser.parse_args(argv)
    try:
        return run_social_browser(
            " ".join(args.source) or None,
            args.private,
            not args.light,
        )
    except KeyboardInterrupt:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
        return 0
    except (VisualBrowserError, OSError, ValueError, WebSocketException) as error:
        print(f"SocialCMD: {_safe_status(str(error), 500)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())