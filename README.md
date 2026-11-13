# Kizuato PC-98 English v6 beta

This beta adds an AI-assisted English script to Leaf's original PC-98 Kizuato. You need your own clean game HDI. The installer ZIP contains no game image.
<img width="3840" height="2160" alt="image" src="https://github.com/user-attachments/assets/ffefba6b-890a-4e2b-9fb7-938b3b9db1d2" />


## Install

1. Download and extract the [v6 beta installer ZIP](https://github.com/dumbgoy88/Kizuato_MTL/releases/download/v6-beta/Kizuato-English-v6-beta.zip).
2. Install Python 3.10 or newer, then read the ZIP's `README.txt`.
3. Use a clean original Kizuato HDI with SHA-256 `783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04`.
4. Run the installer:

   - **Windows:** Drag the HDI onto `Install beta.bat`, or run `py -3 install.py "C:\path\to\Kizuato (J).hdi"`.
   - **Linux/macOS:** Run `python3 install.py "/path/to/Kizuato (J).hdi"`.

5. Open the newly created `Kizuato (J)-English-v6-beta.hdi` in a PC-98 emulator and start a new game. Your original HDI is unchanged.

The installer rejects modified or unsupported HDIs and will not overwrite an existing output. It needs no extra Python packages or `mtools`.

## Development update

A v7 installer candidate now rebuilds the English scenes with lossless compression and splits large main-story scenes to address a memory error found in v6. Targeted emulator checks reached two added scene transitions and both paths of one choice. Full-route testing is still underway, so the **v6 ZIP above remains the published download**; the v7 candidate is not yet a release. The source tools and current test limits are in [STATUS.md](STATUS.md).

## Report problems

Please report missing or clipped text, choice or branch problems, effects, audio, and awkward translation with the route, nearby line, emulator version, and a screenshot. [Open an issue](https://github.com/dumbgoy88/Kizuato_MTL/issues). The full game has not been verified yet, and the original adult content is present.

Do not share installed HDIs. Share the [installer ZIP](https://github.com/dumbgoy88/Kizuato_MTL/releases/download/v6-beta/Kizuato-English-v6-beta.zip) instead.

Developer setup and rebuild steps are in [docs/development_workflow.md](docs/development_workflow.md).
