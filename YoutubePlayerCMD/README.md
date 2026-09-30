# YouTubeCMD

YouTubeCMD displays the real YouTube website inside Windows Terminal using
24-bit color terminal pixels. Edge, Chrome, Chromium, or Brave renders the page;
the app scales each screenshot to the terminal and marks visible controls with
numbers you can activate from the command line.

It uses:
- Python, Pillow, and the browser's local Chrome DevTools Protocol connection
- The installed browser for YouTube's own search, playback, quality, and audio
- ANSI 24-bit foreground/background colors, two image pixels per terminal cell

The whole visible webpage, including video and audio, stays in the terminal
view. `YouTubeCMD.bat --native` keeps the older FFmpeg/FFplay video player
available as a fallback.

---

## What YouTubeCMD Does

YouTubeCMD launches an isolated headless browser and paints its live page into
the terminal as full-color pixels.

You run:

```bat
YouTubeCMD.bat
```

The YouTube home page opens. You can also start from a search or video URL:

```text
YouTubeCMD.bat "Arryadia"
YouTubeCMD.bat https://www.youtube.com/watch?v=VIDEO_ID
```

Search, select quality, captions, volume, and playback are the original YouTube
controls. Number badges are drawn over visible interactive page elements.

---

## Important Limitation

Terminal cells are not physical monitor pixels. The visual mode uses one Unicode
half-block cell for two independently colored screenshot pixels, then scales the
page to the current terminal size. A larger terminal gives the page more detail.

---

## Features

- Render YouTube's actual page and video in the terminal
- Full RGB color via ANSI 24-bit colors
- Numbered overlays for visible links, buttons, and form controls
- Activate any marked control by entering its number
- Use YouTube's own quality, audio, captions, and playback controls
- Search from CMD or navigate to a URL
- Scroll the live page and type into focused webpage controls
- Adaptive terminal-sized screenshot rendering
- Keep the previous FFmpeg/FFplay player with `--native`

---

## Requirements

### Operating System
- Windows 10 or newer
- Windows Terminal recommended; recent CMD with ANSI support may work

### Python
Python 3.10 or newer is required.

Check with:

```bat
python --version
```

If Python is missing, install it from:

```text
https://www.python.org/downloads/
```

During installation, make sure to enable:

```text
Add Python to PATH
```

The launcher installs Pillow and WebSockets into its local virtual environment
for screenshot decoding and the browser's local control connection.

### Browser
Install Microsoft Edge, Chrome, Chromium, or Brave. YouTube runs in an isolated
headless browser profile controlled through its local DevTools connection.

### Terminal
Windows Terminal is recommended for ANSI 24-bit color and Unicode half-blocks.
The terminal should be at least 80 columns wide for a useful page view.

### Native fallback requirements
The optional `--native` player requires FFmpeg/FFplay and a C++17 compiler
(MSVC Build Tools or MinGW-w64).

Check with:

```bat
ffmpeg -version
```

Recommended installation methods:

```bat
winget install Gyan.FFmpeg
```

or download from the official FFmpeg website.

Do not download random FFmpeg builds from unsafe websites.

---

## Project Structure

```text
YouTubeCMD/
	YouTubeCMD.bat
	native/
		build.py
		build_msvc.bat
		build_mingw.bat
		src/
			main.cpp
			console.cpp
			renderer.cpp
			stream.cpp
			media.cpp
			player.cpp
	bin/renderer.exe (built on first launch)
	requirements.txt
	requirements-dev.txt
	config.json
	src/youtubecmd/
		browse.py
		extract.py
		visual_browser.py
		visual_terminal.py
		player.py
		renderer.py
		streams.py
		input_controller.py
		setup.py
		config.py
	scripts/
		make_venv.bat
		check_ffmpeg.bat
		local_render_test.py
	tests/
		test_browse.py
		test_extract.py
		test_visual_browser.py
		test_visual_terminal.py
		test_native.py
		test_renderer.py
		test_url_validation.py
		test_config.py
		test_player.py
	docs/PLAN.md
```

---

## How to Run

### Method 1 — Double-click

Double-click:

```text
YouTubeCMD.bat
```

The YouTube home page appears in the terminal. You can search there or activate
the numbered search control.

---

### Method 2 — Command line

Open CMD inside the project folder and run:

```bat
YouTubeCMD.bat
```

Or from another directory:

```bat
path\to\YouTubeCMD\YouTubeCMD.bat
```

The launcher should work from any current directory.

---

## First Run

On first run, YouTubeCMD may:

1. Create or reuse a local virtual environment.
2. Install Python packages if any visual-browser dependency is missing.
3. Find an installed Edge, Chrome, Chromium, or Brave browser.
4. Start the terminal page view.

FFmpeg and a C++ compiler are checked only when using `--native`.

This may take a short time.

---

## Usage

The default launch renders YouTube in the terminal. Enter search terms or a
direct URL as optional command-line arguments:

```bat
YouTubeCMD.bat "nature documentary"
YouTubeCMD.bat https://www.youtube.com/watch?v=VIDEO_ID
YouTubeCMD.bat --fps 6
```

The visible page is refreshed at 8 FPS by default. Numbered markers are drawn
over clickable page elements. Type a marker number and press Enter to activate
it; selecting the YouTube search field lets you enter text with `t words`, then
submit it with `enter`. Use `/words` for an immediate YouTube search or `g URL`
to navigate directly.

Use YouTube's own visible player controls to select quality and manage audio.
For the legacy separate pixel window player, run `YouTubeCMD.bat --native`.

---

## Controls

| Command | Action |
|---|---|
| `number` + Enter | Activate the numbered visible control |
| `h number` + Enter | Hover a visible control to reveal hidden player controls |
| `more` / `prev` + Enter | Move through numbered control batches |
| `/words` | Search YouTube immediately |
| `g URL` | Navigate to a URL |
| `t text` | Type into the focused page control |
| `enter`, `space`, `tab`, `escape`, `backspace` | Send a key to the page |
| Up / Down arrows | Scroll the webpage |
| `q` + Enter or Ctrl+C | Quit and close the temporary browser |
| `--fps 1..15` | Change terminal screenshot refresh rate (default 8) |

---

## Native Fallback Renderer Modes

These modes are only used by `YouTubeCMD.bat --native`; the default browser
mode renders the webpage in full color.

### PIXEL — full RGB

Uses a native resizable graphics window. Every displayed pixel has its own RGB
color; no text glyphs or terminal color approximations are used.

### HALF_BLOCK — grayscale

Uses Unicode half-block characters:

```text
▀
```

Each terminal cell represents two vertical pixels.

This gives better vertical resolution than plain ASCII.

Best default mode:

```text
HALF_BLOCK
```

---

### ASCII

Uses brightness-based characters:

```text
@%#*+=-:.
```

The mapping ends with a space character.

This mode is faster and more compatible, but uses grayscale characters.

Use ASCII if:
- your terminal is slow
- your PC is weak
- colors look broken
- you want maximum FPS

---

## Performance Tips

For the best experience, use Windows Terminal, resize the terminal before
launching, and lower `--fps` if screenshot refresh uses too much CPU.

---

## Recommended Settings for Low-End PCs

For weaker machines:

```text
Terminal: Windows Terminal
Refresh: YouTubeCMD.bat --fps 2
Page quality: choose a lower YouTube player resolution
```

If playback is stuttering:
- lower the terminal refresh rate
- choose a lower video quality in YouTube
- close other applications

---

## Configuration

Build and test the native executable directly:

```bat
python native\build.py
bin\renderer.exe --info
bin\renderer.exe --selftest
ffmpeg -f lavfi -i testsrc=size=320x180:rate=30 -vf format=gray -f rawvideo - | bin\renderer.exe --raw 320 180 30
```

The default launcher draws the browser page in the terminal. Run
`YouTubeCMD.bat --native` to build and use the older separate RGB pixel window
player. The native player uses command-line mode and quality options.

---

## Troubleshooting

### The launcher says Python is missing

Install Python 3.10+ from:

```text
https://www.python.org/downloads/
```

Make sure to select:

```text
Add Python to PATH
```

Then reopen CMD and try again.

---

### The launcher says FFmpeg is missing

Install FFmpeg and make sure both `ffmpeg` and `ffplay` are in PATH. This is only
required for `YouTubeCMD.bat --native`.

Check:

```bat
ffmpeg -version
```

If FFmpeg is installed but not detected, open a new terminal window so PATH can refresh.

---

### Invalid address in native mode

Make sure the URL is a real YouTube link.

Supported examples:

```text
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://m.youtube.com/watch?v=VIDEO_ID
```

The `--native` fallback accepts YouTube video URLs only. The terminal browser
accepts search terms and HTTP(S) URLs.

Unsupported or malformed URLs in native mode show:

```text
Invalid YouTube URL.
```

---

### Video cannot be accessed automatically

Some videos cannot be played automatically because of:

- login requirement
- age restriction
- region restriction
- private video
- DRM or platform restriction
- unavailable formats

YouTubeCMD should show a clean error message instead of crashing.

---

### Terminal is too small

The rendered page uses the available terminal columns and rows. Resize the
terminal before launching for a larger image.

For better results:
- enlarge the terminal window
- use Windows Terminal
- lower refresh rate with `--fps 2`

---

### Colors look broken

Some terminals do not handle ANSI true color well.

Try:
- Windows Terminal
- confirm ANSI and UTF-8 support are enabled
- avoid legacy CMD if its colors or half-block glyphs look incorrect

---

### Playback is slow or stuttering

Try:
- lower the terminal refresh rate with `--fps 2`
- reduce the terminal window size
- close other applications
- select a lower quality in YouTube's player settings

---

### YouTube video does not appear

Possible causes:
- no supported Edge/Chrome/Chromium/Brave installation
- YouTube is still loading or showing a consent dialog
- terminal true-color/Unicode rendering is unavailable
- network or YouTube playback restrictions

Try clicking a numbered consent or play control, then wait for the next refresh.

---

### YouTube audio does not play

The real page uses the installed browser's audio output, not FFplay. Check the
Windows output device, system volume, and the player's mute control. Autoplay may
require clicking the numbered play control first.

This behavior has not been verified in this Linux workspace; test audio playback
on the target Windows machine.

---

## Testing

Install the development dependencies once:

```bat
python -m pip install -r requirements-dev.txt
```

Run the offline unit tests:

```bat
python -m pytest
```

Important test areas:
- true-color screenshot rendering and numbered overlays
- URL/search routing and terminal interaction commands
- terminal search and video selection
- URL validation
- renderer sizing
- aspect ratio
- luminance mapping
- ASCII output
- HALF_BLOCK output
- config loading
- terminal cleanup

Run the local renderer preview without YouTube or network access:

```bat
python scripts\local_render_test.py
```

Native fallback checks compile C++ and test `--info`, raw frames, and stream
metadata parsing. Live YouTube rendering and browser audio require a supported
system browser, network access, and a Windows terminal; these are manual checks.

---

## Current Verification

The image conversion, numbered overlay, URL routing, and command handling are
covered by offline unit tests. The live page, browser audio, Windows ANSI
behavior, and refresh performance still need a manual Windows run.

---

## Security Notes

YouTubeCMD launches only an installed system browser with an ephemeral profile.
It does not download a browser binary or extract media URLs in visual mode.

---

## Known Limitations

- Terminal cells are logical pixels, not physical display pixels; the page is
  downscaled to the terminal dimensions.
- Up to 40 visible interactive elements are numbered at a time; `more` and
  `prev` move between batches.
- The browser uses a fresh temporary profile, so sign-in cookies are not saved.
- Browser audio output and autoplay behavior can vary by Windows/browser setup.
- Rendering refresh is limited to 1-15 FPS to keep CPU use bounded.
- Legacy CMD may render Unicode/color differently; Windows Terminal is preferred.
- Live YouTube page, media, and audio behavior has not yet been verified on
  Windows from this workspace.

---

## License

Add your chosen license here.

Example:

```text
MIT License
```