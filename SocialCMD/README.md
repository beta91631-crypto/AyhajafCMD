# SocialCMD

SocialCMD opens real websites in a local headless Edge, Chrome, Chromium, or
Brave browser, then presents their readable page text and controls in the
terminal. It does not take or scale screenshots. Text stays sharp at any
terminal size, and it does not poll the browser in the background.

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

Enter `links` to list links, buttons, and form controls on the page. Enter a
listed number to activate it. Use `more` or `prev` to page through long control
lists, and `h N` to hover a control. The page view shows readable text; use the
arrow keys to scroll the page.

- `g URL` opens an address; plain text after `g` is searched
- `/words` searches the web
- `back`, `forward`, `reload`, and `home` navigate
- `find words` finds text in the current page
- `update` rereads text and controls without reloading the page
- `help` shows all controls; `page` returns to the current page
- `t text` types into the focused page control
- `enter`, `space`, `tab`, `escape`, and `backspace` go to the page
- `q` quits

By default, SocialCMD blocks image, media, and font downloads because they are
not shown in its text interface. If a site needs them to work, start it with
`SocialCMD.bat --load-visual-resources`.

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

The launcher creates a local virtual environment and installs WebSockets on
first run. To run tests from this directory, install
`requirements-dev.txt` and run `python -m pytest`.