# Better Together: Dead by Daylight Launcher

Better Together is a Windows launcher for running Dead by Daylight with
multiple Epic Games profiles from one installation.

## Download

[Download Better Together v1.2beta](https://github.com/Analagentin/Better-Together-Dead-By-Daylight-Launcher/releases/download/v1.2beta/Better.Together.-.Dead.By.Daylight.Launcher.exe)

The executable's SHA-256 digest is recorded in `SHA256SUMS.txt`.

## Features

Better Together is especially useful for RDC setups with multiple accounts and
different graphics or control settings.

- Add as many profiles as you need.
- Launch multiple game instances in an ordered sequence.
- Switch between profiles in seconds.
- Create reusable graphics and input presets.
- Create launch sequences that combine profiles with graphics and input presets.

## Setup

1. Install Dead by Daylight through the **official Epic Games Launcher** and launch
   it once. This installs Epic Online Services and other required components. You can skip this step if your existing Epic installation already works.(The built-in install option in Better Together should work, but due to some newer Better Together features and a new version of Legendary, you might run into some issues.)
2. Download the executable or build the project from source.
3. Open the executable. If Windows SmartScreen appears, verify that you
   downloaded it from this repository before choosing **More info** and
   **Run anyway**.
4. Create a folder anywhere on your PC and select it as the **Profile Library**.
5. Create at least one profile.
6. Select **Sign in to Epic Games** and complete the sign-in window.
7. Select the Dead by Daylight installation **folder**, not `DeadByDaylight.exe`.


   


Keep **Skip version check** enabled when launching.

Set **time between launches** to 30 seconds in launch presets.

Make sure to select the install **after** signing into an Epic account.


## ‼️Important: profile security‼️

Profile folders contain sensitive Epic authentication data. Treat all local
profile files like passwords or login credentials. Do not share, copy, or
distribute them unless you fully trust the recipient and understand the risks.

Additional account-security protections are planned for a future update.

## About

Better Together uses [Legendary](https://github.com/derrod/legendary), an
open-source alternative to the Epic Games Launcher. It uses Legendary 0.21.0
for normal Epic Games operations and Legendary 0.20.34 for the embedded Epic
sign-in window.

The branding was inspired by [@crweul's make-your-choice](https://github.com/crweul/make-your-choice).

## Build from source

Windows 10 or 11, Python 3.11 or newer, Tkinter, pip, and an internet
connection are required for the first build.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The script downloads and verifies the required Legendary clients, then creates
the executable in `dist`.

## To do

- Make graphics and input presets launch more reliable in every sequence.
- Add shortcuts, such as a single key for running in place during pixel tech.
- Support multiple game installations, for example for HidHide.
- Add advanced account-security protections.

## Feedback

Suggestions and bug reports are welcome on Discord: `@analagentin`.

Licensed under GPL-3.0-only. See `THIRD_PARTY_NOTICES.md` for bundled-component
attribution.
