# AYHAJAFCMD V2

V2 is a fresh terminal browser project. It runs its own Playwright Chromium, so it does not attach to or reuse the user's Brave/Edge profile. Its persistent browser profile is kept separately under the operating-system user data directory and reused between launches.

## Windows

Run `SocialCMDV2.bat`. On first launch it creates a virtual environment, installs the Python package and Playwright Chromium, then opens DuckDuckGo in the terminal. Windows Terminal is recommended for true-color output.

## Other platforms

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install --with-deps chromium
python -m socialcmd_v2
```

## Commands

- `/words` searches DuckDuckGo; `g ADDRESS_OR_WORDS` navigates or searches
- `click N` clicks one of the numbered visible controls
- `up` / `down` scroll; `t TEXT` types into the focused page; `enter` presses Enter
- `back`, `forward`, `reload`, and `home` navigate
- `pixel N` sets pixel-art block size (1-8); `colors N` sets palette size (2-256)
- `dither none` or `dither floyd` adjusts palette dithering
- `help` lists commands; `q` exits

The default profile is stored in `%LOCALAPPDATA%\\AYHAJAFCMD\\V2\\chromium-profile` on Windows, `$XDG_DATA_HOME/AYHAJAFCMD/V2/chromium-profile` on Linux when set, or `~/.local/share/AYHAJAFCMD/V2/chromium-profile` otherwise. Use `--private` to create a temporary profile for one session.

To make the terminal pixels physically smaller, maximize Windows Terminal and reduce its font size. Half-block mode already uses one terminal column per pixel and two vertical pixels per character. A wider terminal provides more image detail.
