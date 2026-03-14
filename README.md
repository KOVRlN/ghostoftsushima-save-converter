```markdown
# Ghost of Tsushima — Save File Converter

A command-line tool to convert save files between the latest (2.24) PS4 and PC versions of Ghost of Tsushima (Director's Cut). Allows you to continue your progress across platforms without starting over.

> **Disclaimer:** This tool is not affiliated with, endorsed by, or connected to Sony Interactive Entertainment or Sucker Punch Productions. Use it only with save files for games you legally own on both platforms. The author is not responsible for lost save data — always back up your saves before converting.

---

## Requirements

* Python 3.10 or newer

---

## Usage

### Inspect a save file

```bash
python got_save_converter.py detect dis.dat

```

Output:

```text
File:          dis.dat
Size:          555,008 bytes
Magic:         0x0000014E (OK)
Version:       48
Content size:  334,440 bytes
Checksum:      valid
Platform:      PS4
Platform marker (slot 2): 7e8a516a45ed4447

```

### Standard Conversion

**PS4 → PC:**

```bash
python got_save_converter.py ps4_to_pc dis.dat output.sav

```

The output file must be of the naming convention 'manual_XXXX.sav' (where XXXX are any numbers) for the game to recognize it once placed in your PC save directory.

**PC → PS4:**

```bash
python got_save_converter.py pc_to_ps4 manual_XXXX.sav output.dat

```

The output file must then be encrypted / imported into a PS4 save before the PS4 will recognize it.

*Note: If you omit the output filename, the tool generates one automatically (e.g., `dis_converted.sav`).*

### Advanced Options: Force & Custom Versions

Option allows you to bypass version checks and manually set the output version. This is useful if you are dealing with unsupported/unexpected save versions or if a future update changes the tool's expected version numbers.

* **`-f` or `--force**`: Ignores input version and platform marker mismatches. The tool will warn you but proceed with the conversion anyway.
* **`-t <version>` or `--target-version <version>**`: Explicitly sets the save version written to the header of the output file. By default, the tool safely assumes version `49` for PC and `48` for PS4.

**Example — Forcing conversion of an unknown version to a specific PC version (e.g., v50):**

```bash
python got_save_converter.py ps4_to_pc unrecognised_ps4.dat my_converted.sav -f -t 50

```

---

## Troubleshooting

* **"Unrecognised save version X — cannot convert."**
The tool expects v48 for PS4 and v49 for PC. If your save is a different version (e.g., v47), bypass this error by adding the `-f` flag to force the conversion. You can also pair it with `-t <version>` to explicitly specify the output version.
* **"Unexpected slot 1 value" / "Slot 2 is not the PS4/PC marker"**
The file may be corrupt, or the game has released a new update that changed the format.
* **"This file is already a PC/PS4 save"**
The file is already in the target format. No conversion needed.
* **"Old save (v46) detected"**
No conversion is needed. Will load fine on either platform.
* **"Checksum: INVALID" on input**
The file is already in a bad state before conversion. Try recovering from a backup. The tool will warn you but still attempt conversion.

---

## What the tool does (and doesn't do)

| What it does | What it doesn't do |
| --- | --- |
| Swaps the platform marker bytes at offset `0x180` | Touch PSN authentication or encryption |
| Inserts/removes the PC-only slot (8 bytes) | Modify any game data or progress |
| Updates the version field (default or custom target) | Decrypt or re-encrypt anything |
| Recalculates the checksum for the target version ||
| Strips/restores PS4 zero-padding ||

---

## How it works

For the technically curious, see TECHNICAL.md for a writeup of the reverse engineering process: how the format was discovered, what each field means, and the checksum formula.

---

## Contributing

Bug reports and pull requests are welcome. If the game updates and breaks the format again, the most useful thing you can do is open an issue with your game version and full documentation of what you've tried so far.

---

## License

MIT License. See LICENSE for details.

```
