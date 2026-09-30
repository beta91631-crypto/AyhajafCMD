# YouTubeCMD

YouTubeCMD is a Windows command-line YouTube player. Launch it from CMD or
Windows Terminal; video opens in a separate resizable RGB pixel window.

It uses:
- Python and `yt-dlp` to extract stream URLs and metadata into a temporary JSON file
- `renderer.exe`, a C++17 player with a native Windows pixel window
- FFmpeg for video decoding and FFplay for audio
- One independent RGB color per displayed pixel, plus legacy terminal modes

Audio plays through the normal Windows audio device. The terminal remains available for
launching the app; the video window handles display, resizing, and playback keys.

---

## What YouTubeCMD Does

YouTubeCMD launches a resizable video window from a command-line terminal.

You run:

```bat
YouTubeCMD.bat
```

Then you paste a YouTube URL:

```text
YouTube URL: https://www.youtube.com/watch?v=XXXXXXXXXXX
```

YouTubeCMD then:
1. Validates the URL.
2. Extracts playable streams using `yt-dlp`.
3. Starts audio playback.
4. Decodes video frames with FFmpeg.
5. Displays decoded RGB frames in a native Windows window.
6. Keeps playback paced to the source FPS.
7. Closes the video window cleanly when you quit.

---

## Important Limitation

Text terminals cannot draw eight independently colored subpixels inside a text
cell. The Windows launcher therefore uses GDI to display each decoded RGB pixel
directly, without character glyphs. The older ASCII and half-block modes remain
available when running the renderer manually.

---

## Features

- Launch playback from CMD / Windows Terminal
- Resizable native video window with independent RGB pixels
- Supports normal YouTube watch URLs
- Supports `youtu.be` short URLs
- Supports URLs with extra parameters
- Automatic stream extraction
- No manual stream URL input
- Audio playback through Windows
- Automatic video rescaling when the window is resized
- Aspect-ratio preservation
- HALF_BLOCK rendering mode
- ASCII compatibility mode
- Full RGB color per displayed pixel
- Source video quality selection from 360p to 1080p or best available
- Pause/resume
- Seek forward/backward
- Volume control
- Restart
- Quality adjustment
- Keyboard playback controls while the video window is focused
- Friendly error messages

---

## Requirements

### Operating System
- Windows 10
- Windows 11

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

### C++ compiler
The launcher builds the native player once. Install either MSVC Build Tools
(recommended) or MinGW-w64 with `g++` available in PATH.

### FFmpeg
Install an FFmpeg build that includes both `ffmpeg` and `ffplay` and add it to PATH.

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

Then paste your YouTube URL.

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

1. Create a local virtual environment.
2. Install required Python packages.
3. Check FFmpeg.
4. Start the player.

This may take a short time.

---

## Usage

When the launcher starts, enter a YouTube search or paste a video URL:

```text
Search YouTube or paste a video URL.
> nature documentary
```

Search results appear as a numbered list. Choose one, then choose its source
resolution: 360p, 480p, 720p, 1080p, or the best available. The default is 720p.
You can also pass a URL or search phrase directly:

```bat
YouTubeCMD.bat "nature documentary"
YouTubeCMD.bat https://www.youtube.com/watch?v=VIDEO_ID
```

Playback opens in a separate resizable window with full RGB color. Resize the
window while playing and the picture adjusts automatically. The terminal picker
shows search results; it does not render YouTube's full interactive webpage.

---

## Controls

| Key | Action |
|---|---|
| `Q` | Quit |
| `Esc` | Quit |
| `Space` | Pause / resume |
| `Left Arrow` | Seek backward 5 seconds |
| `Right Arrow` | Seek forward 5 seconds |
| `Up Arrow` | Volume up |
| `Down Arrow` | Volume down |
| `R` | Restart video |
| `F` | Maximize / restore the video window |
| `+` | Increase playback render resolution |
| `-` | Decrease playback render resolution |

The display refreshes automatically after the video window is resized. The C++
player drops late frames and lowers render resolution when it repeatedly misses
the 30 FPS frame budget. Use `--mode ascii`, `--mode halfblock`, or `--mode color`
for legacy terminal output when launching `renderer.exe` directly.

---

## Renderer Modes

### PIXEL — Windows default, full RGB

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

---

## Performance Tips

For the best experience:

1. Press `-` to lower render resolution if playback becomes slow.
2. Reduce the video window size.
3. Close heavy background applications.

---

## Recommended Settings for Low-End PCs

For weaker machines:

```text
Renderer: ASCII or HALF_BLOCK grayscale for legacy terminal output
Video window size: moderate
Quality: low or normal
FPS target: 30
```

If playback is stuttering:
- press `-` to lower quality
- switch to ASCII mode
- reduce video window size
- avoid true-color mode

---

## Configuration

Build and test the native executable directly:

```bat
python native\build.py
bin\renderer.exe --info
bin\renderer.exe --selftest
ffmpeg -f lavfi -i testsrc=size=320x180:rate=30 -vf format=gray -f rawvideo - | bin\renderer.exe --raw 320 180 30
```

`YouTubeCMD.bat` starts a separate RGB pixel window at high render resolution.
The `+` and `-` keys adjust render resolution during playback; source video
resolution is selected after choosing a video. The existing `config.json` is
retained for the Python compatibility player; the native player uses
command-line mode and quality options.

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

Install FFmpeg and make sure it is in PATH.

Check:

```bat
ffmpeg -version
```

If FFmpeg is installed but not detected, open a new terminal window so PATH can refresh.

---

### Invalid YouTube URL

Make sure the URL is a real YouTube link.

Supported examples:

```text
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://m.youtube.com/watch?v=VIDEO_ID
```

Unsupported or malformed URLs will show:

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

If the terminal is too small, YouTubeCMD may show a warning.

If possible, it will continue using the maximum usable area.

For better results:
- enlarge the terminal window
- use Windows Terminal
- reduce quality

---

### Colors look broken

Some terminals do not handle ANSI true color well.

Try:
- ASCII mode
- grayscale HALF_BLOCK mode
- Windows Terminal instead of legacy CMD

---

### Playback is slow or stuttering

Try:
- press `-` to reduce quality
- use ASCII mode
- disable true-color mode
- reduce terminal size
- close other applications
- use a lower source resolution

---

### Audio works but video does not

Possible causes:
- FFmpeg video decode failed
- selected stream format is unavailable
- terminal rendering is too slow
- video URL expired
- network problem

Try:
- restarting the video
- seeking again
- using another video
- checking FFmpeg installation

---

### Video works but audio does not

Possible causes:
- audio device problem
- FFmpeg audio output problem
- selected audio stream unavailable
- system volume muted

Check:
- Windows volume
- application volume
- FFmpeg installation
- another YouTube video

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

Native checks compile C++ and test `--info`, grayscale raw frames, RGB raw frames,
and stream metadata parsing. The full YouTube playback test requires FFmpeg and
network access.

---

## Development Roadmap

### Phase 1 — Bootstrap
- project structure
- launcher
- setup checks
- README

### Phase 2 — Stream Selection
- URL validation
- terminal search results and numbered selection
- yt-dlp extraction
- friendly errors

### Phase 3 — Native Renderer
- C++17 terminal detection and ANSI setup
- ASCII and HALF_BLOCK modes
- raw-frame input and terminal cleanup

### Phase 4 — Native Playback
- FFmpeg raw frames
- 30 FPS frame pacing and adaptive quality
- FFplay audio playback
- status bar

### Phase 5 — Controls
- pause/resume
- seek
- volume
- restart
- quality controls

### Phase 6 — Hardening
- clean errors
- config persistence
- resize handling
- documentation
- tests

---

## Future Experiments

Possible future improvements:

- Rust native renderer
- low-RAM ASCII mode
- smarter frame dropping
- adaptive quality
- better color quantization
- better terminal capability detection
- better Windows Terminal optimization

These experiments should stay separate until they are stable.

---

## Security Notes

YouTubeCMD should:
- use official or reputable dependencies
- avoid downloading random executables
- avoid installing unknown binaries automatically
- prefer Python packages from PyPI
- prefer FFmpeg from reputable sources

---

## Known Limitations

- Terminal output is not real video pixels.
- True-color rendering can be slow.
- Very large terminal windows can reduce FPS.
- Seeking may take a short time because streams are restarted.
- Some YouTube videos cannot be accessed automatically.
- Perfect frame synchronization is not guaranteed.
- Audio and video use separate FFplay/FFmpeg processes, so small sync offsets
  can vary with network and device startup time.
- The terminal picker shows search results; it does not render YouTube's full
  interactive webpage.
- CMD and Windows Terminal behave differently.
- Low-end PCs need lower quality settings.

---

## License

Add your chosen license here.

Example:

```text
MIT License
```