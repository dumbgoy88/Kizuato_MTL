# Emulator checks on this Linux desktop

The local emulator is `sdlnp21kai` (`sdlnp21kai`, SHA-256 `b464c5fda7de63e8b16211460342bedcedebdbc70b77187b94ec5e6bc117dece`). Its `--help` does not print a version, so this hash identifies the tested binary. The desktop is KDE Plasma on Wayland; the emulator runs through XWayland with `SDL_VIDEODRIVER=x11`. Synthetic X11 input was unreliable after the opening, so those attempts do not prove a choice or branch.

`tools/portal_keys.c` is a small input helper using [liboeffis and libei](https://libinput.pages.freedesktop.org/libei/api/), version 1.6.0 locally. It requests keyboard access through the desktop's RemoteDesktop portal. The desktop user must approve the KDE dialog; this is a local OS permission, and the helper never sends keys before approval or without a command on stdin. Build it with:

```sh
mkdir -p build
cc -Wall -Wextra -Werror tools/portal_keys.c -o build/portal_keys $(pkg-config --cflags --libs liboeffis-1.0 libei-1.0)
```

Run an ignored HDI **copy** in one terminal:

```sh
SDL_VIDEODRIVER=x11 XDG_CONFIG_HOME="$PWD/build/emulator-config" sdlnp21kai "$PWD/build/kizuato-choice-probe.hdi"
```

Run `build/portal_keys` in another terminal, approve KDE's keyboard-control dialog, wait for `ready`, then enter one command per line: `enter`, `space`, `up`, `down`, `left`, `right`, `esc`, `f12`, or `quit`. Do not send repeated Enter blindly at a choice. This path has advanced the FM/title/bookmark menus and opening text locally. It has not yet exercised a choice.

The choice probe skips introductory text in `001.SCN` only. Its `--skip-opening` option also skips the 23 display commands in `000.SCN` while preserving that scene's conditions and load commands. It leaves the exact original choice event and its three targets in place. It is useful for measuring the choice layout and checking each target, but normal-path reachability must also be checked on the nine-message demo. For a milestone claim, record the exact scene/branch reached after each option, visual line boundaries, emulator settings, and separate FM music/effect observations. Keep screenshots and recordings in ignored `build/` and describe evidence in `STATUS.md`.
