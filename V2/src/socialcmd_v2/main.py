"""Interactive terminal browser entry point."""

from __future__ import annotations

import argparse
import shutil
import sys

from playwright.sync_api import Error as PlaywrightError

from socialcmd_v2.browser import BrowserSession, HOME_URL, resolve_target
from socialcmd_v2.controller import SETTING_CONTROLS, adjust_setting, settings_panel
from socialcmd_v2.rendering import RenderSettings, render_screenshot, terminal_dimensions

HELP = """Browser: /search, g ADDRESS_OR_WORDS, click N, focus N, hover N, up/down,
t TEXT, enter, tab, space, escape, backspace, back, forward, reload, home, q
Controller: settings, [ ], - +, z/x, d, m; pixel N, colors N, zoom N,
dither none|floyd, mode halfblock|sixel"""


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browse websites in the terminal.")
    parser.add_argument("target", nargs="?", default=HOME_URL, help="HTTP(S) URL or DuckDuckGo search words")
    parser.add_argument("--private", action="store_true", help="Use a temporary browser profile")
    return parser.parse_args(argv)


def _show_page(session: BrowserSession, settings: RenderSettings) -> list[dict]:
    terminal = shutil.get_terminal_size(fallback=(100, 30))
    columns, rows = terminal_dimensions(terminal.columns, terminal.lines)
    session.set_zoom(settings.zoom)
    controls = session.visible_controls()
    frame = render_screenshot(session.screenshot(), columns, rows, settings)
    sys.stdout.write("\x1b[2J\x1b[H" + frame + "\x1b[0m\r\n")
    if controls:
        labels = " | ".join(f"{index}: {item['label']}" for index, item in enumerate(controls[:12], 1))
        sys.stdout.write(labels[:columns * 2] + "\r\n")
    sys.stdout.write(
        f"{session.page.url} | pixel={settings.pixel_size} colors={settings.colors} "
        f"zoom={settings.zoom:.1f}x dither={settings.dither} mode={settings.mode}\r\n"
    )
    sys.stdout.flush()
    return controls


def _dispatch(command: str, session: BrowserSession, settings: RenderSettings, controls: list[dict]) -> str:
    text = command.strip()
    if not text:
        return ""
    if text in {"q", "quit", "exit"}:
        return "quit"
    if text in {"help", "?"}:
        return HELP
    if text == "settings":
        return settings_panel(settings)
    control = text.lower()
    if control in SETTING_CONTROLS:
        action = SETTING_CONTROLS[control]
        if action == "mode" and settings.mode == "halfblock" and shutil.which("chafa") is None:
            return "Sixel needs Chafa on PATH. Keep using halfblock, or install Chafa first."
        adjust_setting(settings, action)
        return ""
    if text.startswith("/"):
        session.navigate(resolve_target(text[1:]))
        return ""
    if text.startswith("g "):
        session.navigate(resolve_target(text[2:]))
        return ""
    if text.startswith("click "):
        session.click_control(int(text[6:].strip()), controls)
        return ""
    if text.startswith("hover "):
        session.hover_control(int(text[6:].strip()), controls)
        return ""
    if text.startswith("focus "):
        session.focus_control(int(text[6:].strip()), controls)
        return ""
    if text in {"up", "down"}:
        session.scroll(text)
        return ""
    if text.startswith("t "):
        session.type_text(text[2:])
        return ""
    if text == "enter":
        session.press("Enter")
        return ""
    if text in {"back", "forward"}:
        getattr(session.page, "go_back" if text == "back" else "go_forward")()
        return ""
    if text == "reload":
        session.page.reload(wait_until="domcontentloaded")
        return ""
    if text == "home":
        session.navigate(HOME_URL)
        return ""
    if text.startswith("pixel "):
        value = text[6:].strip()
        if value in {"+", "-"}:
            adjust_setting(settings, "pixel" + value)
            return ""
        settings.pixel_size = int(value)
        settings.validate()
        return ""
    if text.startswith("colors "):
        value = text[7:].strip()
        if value in {"+", "-"}:
            adjust_setting(settings, "colors" + value)
            return ""
        settings.colors = int(value)
        settings.validate()
        return ""
    if text.startswith("zoom "):
        value = text[5:].strip()
        if value in {"+", "-"}:
            adjust_setting(settings, "zoom" + value)
            return ""
        settings.zoom = float(value)
        settings.validate()
        return ""
    if text.startswith("dither "):
        settings.dither = text[7:].strip().lower()
        settings.validate()
        return ""
    if text.startswith("mode "):
        mode = text[5:].strip().lower()
        if mode == "sixel" and shutil.which("chafa") is None:
            return "Sixel needs Chafa on PATH. Keep using halfblock, or install Chafa first."
        settings.mode = mode
        settings.validate()
        return ""
    if text in {"tab", "space", "escape", "backspace"}:
        session.press({"tab": "Tab", "space": "Space", "escape": "Escape", "backspace": "Backspace"}[text])
        return ""
    if text.lower().startswith(("http://", "https://")):
        session.navigate(resolve_target(text))
        return ""
    return f"Unknown command. Type help. Search with /words."


def run(start_url: str = HOME_URL, private: bool = False) -> int:
    settings = RenderSettings()
    try:
        with BrowserSession(resolve_target(start_url), private=private) as session:
            print("\x1b[?25l", end="")
            try:
                controls = _show_page(session, settings)
                while True:
                    try:
                        command = input("> ")
                    except EOFError:
                        break
                    try:
                        result = _dispatch(command, session, settings, controls)
                    except (ValueError, PlaywrightError) as error:
                        result = str(error)
                    if result == "quit":
                        break
                    if result:
                        print(result)
                        input("Press Enter to continue...")
                    controls = _show_page(session, settings)
            finally:
                print("\x1b[0m\x1b[?25h", end="", flush=True)
        return 0
    except (PlaywrightError, OSError, RuntimeError) as error:
        print(f"SocialCMD V2: {error}", file=sys.stderr)
        print("Run `python -m playwright install chromium` if its browser is missing.", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        target = resolve_target(args.target)
    except ValueError as error:
        print(f"SocialCMD V2: {error}", file=sys.stderr)
        return 2
    return run(target, private=args.private)
