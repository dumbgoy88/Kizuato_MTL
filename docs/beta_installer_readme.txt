Kizuato PC-98 English beta (v6)
================================

This is a playtest build of Leaf's original PC-98 Kizuato. The installer
contains English edit instructions and build tools. It contains no game image,
graphics, music, font, or rebuilt game archive. You need your own clean HDI.

Requirements
------------
- Python 3.10 or newer. No Python packages or other tools are needed.
- A clean, unmodified Kizuato HDI with SHA-256:
  783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04
- Enough free space for a second 11 MB HDI.

Install
-------
1. Extract this ZIP to a folder.
2. Keep your original HDI outside the ZIP. Do not use an HDI with saves or an
   earlier English patch; the installer checks the complete source hash.
3. In a terminal in the extracted folder, run one of these:

   Linux/macOS:  python3 install.py "/path/to/Kizuato (J).hdi"
   Windows:      py -3 install.py "C:\path\to\Kizuato (J).hdi"

   On Windows you can also drag the clean HDI onto Install beta.bat.
4. A new "Kizuato (J)-English-v6-beta.hdi" appears next to your original.
   The installer never overwrites either file. To choose another output:

   python3 install.py "/path/to/Kizuato (J).hdi" --output "/path/to/beta.hdi"

5. Open the NEW HDI in a PC-98 emulator. Select FM audio and start a new game.
   Keep beta saves in this image. Space may advance text when Enter does not.

The installer verifies the original HDI and scene archive, rebuilds the English
archive, checks its hash and branch/layout audit, writes a new HDI, reads it
back, and confirms that only KIZUATO/MAX2_SCN.PAK changed among installed files.
If it reports an unsupported revision, stop: this beta only supports the exact
source hash above. Do not force it onto another release.

Beta status and feedback
------------------------
The English is a first-pass AI-assisted draft; spelling, voice, nuance, and
route context still need review. The opening English has been seen in Neko
Project II Kai and a player reported the pagination looked fixed. The entire
game, both paths of every choice, effects timing, and save/load have not yet
been verified. Static checks find all 47 choice groups within the measured
24-column/12-row limit. Twelve unreferenced bonus-scene messages still need
engine research. Adult scenes are present as in the original game.

Please note the route and nearest choice when you spot a problem. A screenshot,
the exact visible line, emulator name/version, and whether music/effects were
working make reports much easier to fix. Check for missing words after page
turns, clipped text, choice highlighting, wrong branches, and awkward wording.
Share the installer ZIP with other testers, never a patched HDI or game files.

Project source and current limitations: README.md and STATUS.md in the project
repository. This beta package is a local test artifact, not a finished release.
