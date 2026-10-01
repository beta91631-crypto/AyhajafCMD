# YouTubeCMD Master Plan

## 1. Product Objective

Build a practical Windows 10/11 command-line application that allows the user to paste a YouTube URL and watch the video inside the active CMD-compatible terminal using ANSI escape sequences, Unicode block characters, half-block rendering, and ASCII fallback.

The final deliverable is a self-contained project folder named `YouTubeCMD`, launched by one file:

```bat
YouTubeCMD.bat
```

The application must:
- Accept normal YouTube watch URLs, `youtu.be` URLs, and URLs with extra parameters.
- Extract playable streams automatically using `yt-dlp`.
- Decode video with FFmpeg.
- Render frames inside the terminal.
- Play audio through the normal Windows audio device.
- Avoid opening a separate graphical video window.
- Restore the terminal cleanly on exit.

---

## 2. Core Success Criteria

The project is considered successful when:

1. `YouTubeCMD.bat` works from any current directory.
2. The user is prompted with:
   ```text
   YouTube URL:
   ```
3. A valid YouTube URL starts playback.
4. `yt-dlp` extracts stream information automatically.
5. Video renders inside the terminal without opening a normal video player window.
6. Audio plays normally through Windows.
7. The renderer adapts to terminal size.
8. Aspect ratio is preserved.
9. Frame pacing follows the source FPS instead of rendering as fast as possible.
10. The terminal is restored after exit, error, Ctrl+C, or end of playback.
11. Expected errors are shown as clean messages, not Python tracebacks.
12. The project can be set up with one launcher.
13. Tests exist for renderer logic and URL validation.
14. Documentation is clear and complete.

---

## 3. Main Architecture

```text
User
  ↓
YouTubeCMD.bat
  ↓
Python setup / URL extraction
  ↓
stream.json
  ↓
bin/renderer.exe
  ↓
FFmpeg video decode + FFplay audio
  ↓
native C++ frame loop and terminal renderer
```

Audio path:

```text
yt-dlp audio URL
  ↓
FFplay child process
  ↓
Windows audio device
```

---

## 4. Technology Stack

### Required
- Windows 10 or Windows 11
- Python 3.10+
- C++17 compiler: MSVC Build Tools or MinGW-w64
- FFmpeg installed and available in PATH
- `yt-dlp`
- Python standard library for URL extraction and setup

### Avoid unless necessary
- OpenCV
- Heavy GUI libraries
- Full video download
- Large frame queues
- Python in the per-frame render path

---

## 5. Repository Structure

```text
YouTubeCMD/
  .github/
    workflows/
      ci.yml
  docs/
    SPEC.md
    PLAN.md
    BENCHMARK.md
    CONTROLS.md
    LIMITATIONS.md
  src/
    youtubecmd/
      __init__.py
      extract.py
      streams.py
  scripts/
    make_venv.bat
    check_ffmpeg.bat
    local_render_test.py
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
  tests/
    test_native.py
    test_extract.py
    test_url_validation.py
    test_renderer.py
  YouTubeCMD.bat
  requirements.txt
  README.md
  config.json
  .gitignore
```

Python is limited to stream extraction and setup. C++ owns media processes, frame
buffers, timing, keyboard controls, and terminal rendering. The launcher builds
the executable once and reuses it until native sources change.

---

## 6. Playback Pipeline

### Step 1 — Launch
`YouTubeCMD.bat` resolves its own directory, checks dependencies, builds the C++
executable if needed, extracts stream metadata, then starts `renderer.exe`.

### Step 2 — Setup
The setup module:
- Checks Python.
- Creates or reuses `.venv`.
- Installs dependencies.
- Checks FFmpeg.
- Builds the C++17 player using MSVC or MinGW.

### Step 3 — URL Prompt
The Python extractor asks:

```text
YouTube URL:
```

It validates that the URL belongs to a supported YouTube host.

Supported hosts:
- `youtube.com`
- `www.youtube.com`
- `m.youtube.com`
- `youtu.be`

### Step 4 — Stream Extraction
Use `yt-dlp` to extract:
- title
- duration
- fps
- available formats
- video stream URL
- audio stream URL

Video selection:
- Prefer 360p or 480p.
- Do not decode 720p or 1080p unless necessary.
- Choose a format compatible with FFmpeg raw decode.

Audio selection:
- Choose a normal-quality audio stream.
- Prefer efficient formats.

### Step 5 — Process Launch
Start two logical pipelines:
- audio playback
- raw video decode

Both start from the same playback position.

### Step 6 — Frame Loop
For each frame:
1. Read raw frame from FFmpeg stdout into one reusable buffer.
2. Render using the selected C++ mode.
3. Write one frame to the terminal.
5. Respect frame timing.
6. Drop frames if rendering is behind.

### Step 7 — Controls
Poll keyboard input without blocking the frame loop.

Commands:
- quit
- pause/resume
- seek
- volume
- restart
- quality change
- renderer mode selection at launch
- fullscreen attempt

### Step 8 — Cleanup
Always restore:
- cursor visibility
- colors
- terminal mode
- child processes
- normal console behavior

---

## 7. Terminal Rendering Strategy

### Renderer Modes

#### HALF_BLOCK — default
Use Unicode upper half block:

```text
▀
```

Each terminal cell represents two vertical pixels:
- top pixel = foreground color
- bottom pixel = background color

Best balance between quality and terminal resolution.

#### ASCII — compatibility mode
Map luminance to characters such as:

```text
@%#*+=-:.
```

The mapping ends with a space character.

This is the fastest and most compatible mode.

#### ANSI_COLOR — optional
Use true-color ANSI output when supported.

This mode may be slower and should not be the default on low-end machines.

---

## 8. Performance Rules

The player must remain usable on low-end PCs.

### Rules
- Do not download the whole video.
- Do not store many frames in memory.
- Keep only the current frame and current rendered output.
- Prefer FFmpeg scaling instead of Python resizing when possible.
- Prefer small terminal grids instead of fake full resolution.
- Drop frames when behind.
- Do not render faster than source FPS.
- Avoid huge ANSI strings when possible.
- Use direct byte output where practical.
- Use cursor home instead of full clear when possible.
- Avoid flickering.

### Recommended default target
```text
Terminal grid: 100x30 to 160x45
Mode: HALF_BLOCK grayscale or ASCII
FPS: 30 stable
RAM: as low as possible, ideally near 100MB, realistically under 150MB
```

### Important limitation
A terminal cannot display real 720p pixels.

The correct target is:
```text
720p source → downscaled terminal grid
```

not:
```text
1280x720 terminal characters
```

---

## 9. Audio and Synchronization

FFplay owns audio output. Audio and FFmpeg video start from the same seek
position, and the native player uses a monotonic playback timeline capped at
the source rate and 30 FPS. The current implementation does not read FFplay's
internal audio clock, so long-run A/V drift still needs Windows playback testing.

Video rendering should:
- follow the selected source rate, capped at 30 FPS
- lower render dimensions and then output FPS when repeatedly late
- avoid accumulating raw frames in a large queue
- restart cleanly after seek
- stay reasonably synchronized with audio

Pause behavior:
- pause playback clock
- stop or suspend audio process
- resume from same position

Seek behavior:
- terminate current FFmpeg processes
- relaunch with `-ss`
- restart audio from same position

---

## 10. Controls

| Key | Action |
|---|---|
| `Q` or `Esc` | Quit |
| `Space` | Pause / resume |
| `Left Arrow` | Seek backward 5 seconds |
| `Right Arrow` | Seek forward 5 seconds |
| `Up Arrow` | Volume up |
| `Down Arrow` | Volume down |
| `R` | Restart video |
| `F` | Toggle fullscreen / maximize console if supported |
| `+` | Increase quality: low → normal → high |
| `-` | Decrease quality: high → normal → low |

The status bar should show:
- playback state
- elapsed time
- duration
- volume
- renderer mode
- quality, output dimensions, and measured FPS

Select `ascii`, `halfblock`, or `color` with the native executable's `--mode`
option. HALF_BLOCK grayscale and normal quality are the launcher defaults.

It must not scroll over the video.

---

## 11. Error Handling

The project must handle expected failures cleanly.

### URL errors
Invalid URL:

```text
Invalid YouTube URL.
```

### Extraction errors
Show concise messages for:
- private videos
- age-restricted videos
- login-required videos
- region-restricted videos
- unavailable formats
- network failure
- yt-dlp failure

### Dependency errors
If Python is missing:
- tell the user clearly what to install

If FFmpeg is missing:
- explain that FFmpeg is required
- recommend official or reputable installation methods

If terminal is too small:
- show warning
- continue with maximum usable size if possible

### Python tracebacks
Normal user errors must not show raw tracebacks.

Tracebacks may be logged for debugging, but the terminal should show a clean message.

---

## 12. Stream Contract and Configuration

Python writes a temporary `stream.json` containing video/audio URLs, title,
duration, FPS, and source dimensions. C++ consumes it with:

```text
renderer.exe --stream stream.json --mode halfblock --quality normal
```

Quality levels control terminal output dimensions, not source resolution.
Stream extraction prefers sources at or below 480p. The previous `config.json`
belongs to the Python compatibility player and is not read by the native path.

---

## 13. Development Phases

### Phase 1 — Bootstrap
Goal:
- project skeleton
- launcher
- setup checks
- README
- requirements

Done when:
```text
YouTubeCMD.bat starts and shows prompt
```
Status: implemented; Windows launcher still requires a Windows runtime check.

### Phase 2 — Stream Selection
Goal:
- URL validation
- yt-dlp extraction
- stream selection
- clean errors

Done when:
```text
valid URL returns stream info
invalid URL shows clean error
```
Status: implemented and unit-tested.

### Phase 3 — Renderer Foundation
Goal:
- terminal detection
- ANSI setup
- ASCII mode
- HALF_BLOCK mode
- cleanup

Done when:
```text
local generated frames render correctly
```
Status: implemented; `--info`, raw ASCII/RGB frames, and interactive selftest
were exercised in the Linux development environment.

### Phase 4 — Real-Time Playback
Goal:
- FFmpeg raw frame pipeline
- frame timing
- status bar
- audio playback

Done when:
```text
video and audio play together
```
Status: implemented, but end-to-end playback remains unverified because FFmpeg
and FFplay are unavailable in the current environment.

### Phase 5 — Controls
Goal:
- keyboard handling
- pause/resume
- seek
- volume
- restart
- quality controls

Done when:
```text
controls work without breaking playback
```
Status: implemented; controls need real Windows/FFmpeg playback validation.

### Phase 6 — Hardening
Goal:
- clean errors
- config persistence
- resize handling
- teardown safety
- tests
- documentation

Done when:
```text
project is stable and user-friendly
```
Status: native tests and CI build are in place; Windows terminal, memory, and
long-playback synchronization measurements remain outstanding.

---

## 14. GitHub Workflow

### Branches
```text
main
develop
feature/phase1-bootstrap
feature/phase2-stream-selection
feature/phase3-renderer
feature/phase4-playback
feature/phase5-controls
feature/phase6-hardening
exp/cpp-renderer
exp/rust-renderer
exp/low-ram
```

### Rules
- `main` must stay stable.
- New work goes to `develop` or feature branches.
- Experiments stay separate until proven useful.
- Every phase should have tests or acceptance checks.
- Pull requests should pass syntax checks and tests.

### Recommended issues
```text
Phase 1: Bootstrap launcher
Phase 2: Stream extraction
Phase 3: Renderer foundation
Phase 4: Real-time playback
Phase 5: Controls
Phase 6: Hardening
Performance: Low-RAM ASCII mode
Performance: Reduce ANSI output size
Bug: Terminal cleanup on exit
Docs: Complete README
Tests: Local renderer test
```

---

## 15. Testing Plan

### Unit tests
Test:
- URL validation
- renderer sizing
- aspect ratio
- luminance mapping
- ASCII output dimensions
- HALF_BLOCK output dimensions
- config load/save

### Local render test
Create a test that renders generated frames without YouTube.

Example target:
```text
scripts/local_render_test.py
```

This test must work offline.

### Manual tests
Check:
- launch from project folder
- launch from another folder
- valid watch URL
- `youtu.be` URL
- URL with parameters
- invalid URL
- unavailable video
- small terminal
- resize during playback
- pause/resume
- seek forward/backward
- volume up/down
- restart
- quit
- Ctrl+C
- FFmpeg missing
- Python missing

---

## 16. Benchmark Plan

Measure:
- CPU usage
- RAM usage
- average FPS
- dropped frames
- terminal output size
- input latency
- seek delay
- startup time

Targets:

```text
ASCII mode:
  stable 30 FPS on modest terminal size

HALF_BLOCK grayscale:
  stable 30 FPS if terminal size is moderate

RAM:
  as low as possible, ideally near 100MB, realistically under 150MB
```

If performance is bad:
1. Reduce terminal grid.
2. Use ASCII mode.
3. Use grayscale instead of true color.
4. Lower FPS cap.
5. Let FFmpeg do scaling.
6. Reduce ANSI escape changes.
7. Avoid Python-heavy loops.

---

## 17. Native Acceleration Plan — Optional

If Python rendering becomes the bottleneck, create experiments:

```text
experiments/cpp-renderer/
experiments/rust-renderer/
```

Possible native architecture:

```text
Python extractor
  ↓
stream.json
  ↓
renderer.exe
  ↓
FFmpeg raw pipe
  ↓
native renderer
  ↓
terminal output
```

Recommended native strategy:
- Keep Python for `yt-dlp` extraction.
- Keep FFmpeg for decoding.
- Move only the hot rendering path to native code.
- Start with one small native executable.
- Add DLLs later only if useful.
- Do not make native code mandatory until it is stable.

---

## 18. Final Acceptance Checklist

Before marking the project stable:

```text
YouTubeCMD.bat works from any folder
Prompt appears correctly
Valid URL starts playback
Invalid URL shows clean error
Audio plays
Video renders inside terminal
No separate video window appears
Terminal adapts to size
Aspect ratio is preserved
Controls work
Pause/resume works
Seek works
Volume works
Quit restores terminal
Ctrl+C restores terminal
Config saves correctly
README is complete
CI passes
Tests pass
```

---

## 19. Version Roadmap

### v0.1.0-alpha
- launcher works
- prompt works
- setup checks work

### v0.2.0-alpha
- stream extraction works
- clean URL errors

### v0.3.0-alpha
- local renderer works
- ASCII and HALF_BLOCK modes work

### v0.4.0-alpha
- real playback works
- audio works

### v0.5.0-alpha
- controls work

### v0.9.0-beta
- hardening, tests, docs

### v1.0.0
- stable public release

---

## 20. Guiding Principle

The project should always prefer:

```text
stable, clean, low-memory, terminal-friendly playback
```

over:

```text
fake high resolution, heavy dependencies, or unstable performance
```