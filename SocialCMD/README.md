# SocialCMD

SocialCMD displays real social media websites inside a terminal using a local
headless Edge, Chrome, Chromium, or Brave browser. The terminal shows a live
true-color pixel view; numbered page controls can be clicked with their number.

## Run

On Windows, launch `SocialCMD.bat`. Common destinations are available by name:

```bat
SocialCMD.bat instagram
SocialCMD.bat reddit
SocialCMD.bat x
SocialCMD.bat https://www.tiktok.com/
```

Supported shortcuts are `facebook`, `instagram`, `linkedin`, `pinterest`,
`reddit`, `threads`, `tiktok`, and `x`. `fb`, `ig`, and `twitter` are aliases.
With no argument SocialCMD opens Reddit. Any HTTP or HTTPS URL can be opened;
plain text is searched on the web.

## Controls

Enter a displayed number to click a control. Use `h N` to hover a control,
`more` or `prev` to page through controls, `/words` to search the web, `g URL`
to navigate, and `t text` to type into the focused page control. `enter`,
`space`, `tab`, `escape`, `backspace`, and the arrow keys are sent to the page.
Enter `q` to quit.

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
WebSockets on first run. To run tests from this directory, install
`requirements-dev.txt` and run `python -m pytest`.