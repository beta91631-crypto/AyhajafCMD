# SocialCMD

SocialCMD opens the real website in Edge, Chrome, Chromium, or Brave and paints
its live page into the terminal using full 24-bit RGB half-block pixels. Social
feeds, images, and page colors are enabled by default; numbered markers let you
activate visible page controls.

Frames are captured as lossless PNG and scaled with nearest-neighbor sampling,
so pixel edges stay sharp rather than blurred. Each terminal cell uses two
vertically stacked color pixels to keep the displayed pixel shape close to
square.

## Run

On Windows, launch `SocialCMD.bat`. It first shows a site chooser. Pick a
platform or paste any URL; SocialCMD never picks a social network for you. You
can also open a destination directly:

```bat
SocialCMD.bat instagram
SocialCMD.bat reddit
SocialCMD.bat x
SocialCMD.bat https://www.tiktok.com/
```

Supported shortcuts are `facebook`, `instagram`, `linkedin`, `pinterest`,
`reddit`, `threads`, `tiktok`, and `x`. `fb`, `ig`, and `twitter` are aliases.
Any HTTP or HTTPS URL can be opened; plain text is searched on the web.

## Controls

You can control the page by a visible name or use numbered markers. If a name
matches multiple controls, SocialCMD shows the matching choices instead of
clicking one at random. Number markers remain a quick fallback. Use `more` or
`prev` to page through markers and the arrow keys to scroll the page.

- `click NAME` activates a control by its visible label
- `open NAME` opens a matching link
- `focus NAME` focuses a matching input
- `type FIELD=TEXT` focuses the named input and enters text
- `g URL` opens an address; plain text after `g` is searched
- `/words` searches the web
- `back`, `forward`, `reload`, and `home` navigate
- `find words` finds text in the current page
- `update` refreshes the page image without reloading the page
- `help` shows all controls; `page` returns to the current page
- `t text` types into the focused page control
- `enter`, `space`, `tab`, `escape`, and `backspace` go to the page
- `q` quits

For slow connections or low-memory PCs, start with `SocialCMD.bat --light` to
disable page images. Full visual mode is the default.

## Sign-in and privacy

The browser profile is stored locally and reused, so site sign-ins can persist
between runs. Use `SocialCMD.bat --private` for a temporary profile that is
removed when the app closes. The persistent profile is under
`%LOCALAPPDATA%\SocialCMD\browser-profile` on Windows and
`$XDG_DATA_HOME/SocialCMD/browser-profile` (or `~/.local/share/SocialCMD/browser-profile`)
on Linux. Do not use a shared or untrusted machine for personal accounts.

Sites may require sign-in, block automated browsers, or change their layouts.
SocialCMD does not provide platform APIs or bypass site restrictions; it
renders and controls the site's own page.

## Requirements

- Python 3.10 or newer
- Microsoft Edge, Chrome, Chromium, or Brave
- Windows Terminal or another ANSI true-color terminal

The launcher creates a local virtual environment and installs Pillow and
WebSockets when needed. To run tests from this directory, install
`requirements-dev.txt` and run `python -m pytest`.