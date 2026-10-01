"""Playwright Chromium session with a dedicated persistent profile."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote_plus, urlsplit

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright


HOME_URL = "https://duckduckgo.com/"
VIEWPORT = {"width": 1280, "height": 720}
CONTROL_SCRIPT = r"""() => {
  const selector = 'a[href],button,input:not([type="hidden"]),textarea,select,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])';
  return Array.from(document.querySelectorAll(selector)).slice(0, 800).flatMap((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    if (!rect.width || !rect.height || rect.right <= 0 || rect.bottom <= 0 ||
        rect.left >= innerWidth || rect.top >= innerHeight || style.display === 'none' ||
        style.visibility === 'hidden' || element.disabled) return [];
    const label = (element.getAttribute('aria-label') || element.getAttribute('title') ||
      element.getAttribute('placeholder') || element.innerText || element.textContent ||
      element.tagName).replace(/\\s+/g, ' ').trim().slice(0, 72);
    return [{x: rect.left + rect.width / 2, y: rect.top + rect.height / 2,
      label: label || element.tagName.toLowerCase()}];
  }).slice(0, 30);
}"""


def profile_directory() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "AYHAJAFCMD" / "V2" / "chromium-profile"


def resolve_target(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return HOME_URL
    if candidate.lower().startswith(("https://", "http://")):
        if not urlsplit(candidate).hostname:
            raise ValueError("Enter a valid HTTP or HTTPS address.")
        return candidate
    if "://" in candidate:
        raise ValueError("Only HTTP and HTTPS addresses are supported.")
    return f"https://duckduckgo.com/?q={quote_plus(candidate)}"


class BrowserSession:
    def __init__(self, start_url: str = HOME_URL, private: bool = False) -> None:
        self.start_url = start_url
        self.private = private
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.zoom = 1.0
        self._temporary_profile: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> BrowserSession:
        if self.private:
            self._temporary_profile = tempfile.TemporaryDirectory(prefix="AYHAJAFCMD-V2-")
            user_data_dir = self._temporary_profile.name
        else:
            user_data_dir = str(profile_directory())
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        self.playwright = sync_playwright().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport=VIEWPORT,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.set_default_timeout(10_000)
            self.page.goto(self.start_url, wait_until="domcontentloaded", timeout=30_000)
            return self
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None
        if self.playwright is not None:
            self.playwright.stop()
            self.playwright = None
        if self._temporary_profile is not None:
            self._temporary_profile.cleanup()
            self._temporary_profile = None

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser session is not running.")
        return self.page

    def screenshot(self) -> bytes:
        return self._require_page().screenshot(type="png", animations="disabled")

    def set_zoom(self, zoom: float) -> None:
        if not 0.5 <= zoom <= 2.0:
            raise ValueError("Zoom must be between 0.5 and 2.0.")
        if self.zoom == zoom:
            return
        self.zoom = zoom
        self._require_page().set_viewport_size({
            "width": round(VIEWPORT["width"] / zoom),
            "height": round(VIEWPORT["height"] / zoom),
        })

    def visible_controls(self) -> list[dict[str, Any]]:
        result = self._require_page().evaluate(CONTROL_SCRIPT)
        return result if isinstance(result, list) else []

    def click_control(self, number: int, controls: list[dict[str, Any]]) -> None:
        if not 1 <= number <= len(controls):
            raise ValueError("That control number is not visible in the current page.")
        control = controls[number - 1]
        self._require_page().mouse.click(float(control["x"]), float(control["y"]))

    def hover_control(self, number: int, controls: list[dict[str, Any]]) -> None:
        if not 1 <= number <= len(controls):
            raise ValueError("That control number is not visible in the current page.")
        control = controls[number - 1]
        self._require_page().mouse.move(float(control["x"]), float(control["y"]))

    def focus_control(self, number: int, controls: list[dict[str, Any]]) -> None:
        self.click_control(number, controls)

    def navigate(self, target: str) -> None:
        self._require_page().goto(target, wait_until="domcontentloaded", timeout=30_000)

    def scroll(self, direction: str) -> None:
        if direction not in {"up", "down"}:
            raise ValueError("Use up or down to scroll.")
        amount = -560 if direction == "up" else 560
        self._require_page().evaluate("amount => window.scrollBy(0, amount)", amount)

    def type_text(self, text: str) -> None:
        self._require_page().keyboard.insert_text(text)

    def press(self, key: str) -> None:
        self._require_page().keyboard.press(key)
