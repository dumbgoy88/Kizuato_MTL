#!/usr/bin/env bash
# Launch the hash-checked disposable all-English HDI in Neko Project II Kai.
set -euo pipefail
cd "$(dirname "$0")/.."

source_image="$PWD/build/all-english-diagnostic-20261111-v6.hdi"
expected='ba0e0aca114925dde277ef3ad3b9695623fcf2d1557e3a9cc77e15cbea6ecc6a'
test -f "$source_image" || { printf 'Missing demo HDI: %s\n' "$source_image" >&2; exit 1; }
actual=$(sha256sum "$source_image")
actual=${actual%% *}
if [[ "$actual" != "$expected" ]]; then
  printf 'Demo HDI hash changed: %s (expected %s)\n' "$actual" "$expected" >&2
  exit 1
fi
emulator="${KIZUATO_EMULATOR:-$(command -v sdlnp21kai || true)}"
test -x "$emulator" || { printf 'Neko Project II Kai was not found.\n' >&2; exit 1; }
mkdir -p build/all-english-emulator-config
playtest_image="$PWD/build/all-english-playtest-$(date -u +%Y%m%dT%H%M%SZ)-$$.hdi"
cp --reflink=auto "$source_image" "$playtest_image"
printf 'Starting fresh playtest copy: %s\n' "$playtest_image"
printf 'This v6 continuation build is an emulator test; bonus scene 201 remains unresolved.\n'
exec env SDL_VIDEODRIVER=x11 XDG_CONFIG_HOME="$PWD/build/all-english-emulator-config" \
  "$emulator" "$playtest_image"
