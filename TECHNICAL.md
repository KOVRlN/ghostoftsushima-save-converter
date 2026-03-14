
# Technical Notes — Save Format Reverse Engineering

This document describes the Ghost of Tsushima save file format as discovered through binary analysis of six save files across PS4 and PC platforms.

---

## File structure overview

All saves share a common 16-byte header, followed by an unknown 32-byte block, followed by a platform marker block (v48+), followed by game data.


```
Offset   Size  Field

---

0x00      4    Magic: always 0x0000014E (334 decimal)
0x04      4    Content size — number of meaningful bytes in this file
0x08      4    Checksum (see formula below)
0x0C      4    Save format version (48, 49)
0x10     32    Unkown — identical across all saves
0x30    ...    Game data begins here (v46 only — no platform block)

--- v48+ only ---
0x180     8    Slot 1: build hash — 6a4b716a45ed4447 (same on all platforms)
0x188     8    Slot 2: platform marker (see below)
0x190     8    Slot 3: PC-only constant — bfe1bd115c5c51a2 (absent on PS4)
0x198   ...    Game data begins here (v48 PS4) / 0x198 (v49 PC)
```

---

## Platform markers

The value at offset `0x188` (slot 2) is what the game checks when loading a save. It is a fixed constant per platform, verified as identical across multiple saves on the same platform:


```
PS4:  7e8a516a45ed4447
PC:   d5cf106b395e5d10
```

Slot 3 (`bfe1bd115c5c51a2`) is present only in PC saves and also constant. Its exact purpose is unknown — it may be a secondary platform identifier or a PC build-specific value. It must be present for the game to accept the save on PC, and must be absent on PS4.

---

## Version history

| Version | Platform | Notes |
|---|---|---|
| 46 | PS4 (pre-update) | No platform block at 0x180; smaller content |
| 48 | PS4 (post-update) | 16-byte platform block added; content grew ~22KB |
| 49 | PC | 24-byte platform block; no zero-padding |

---

## PS4 container format

PS4 saves are always exactly 555,008 bytes. The game writes its content starting at byte 0, and the remainder of the file is zero-padded. The `content_size` field at offset `0x04` marks where the content ends and the padding begins.

PC saves carry no padding — the file is exactly `content_size` bytes long, and the `content_size` field equals the file size.

---

## Checksum formula

The checksum at `0x08` is a simple sum of bytes. The formula, verified against six reference saves:


```
checksum = sum(data[0x10 : content_size]) + content_size + magic + version
```

Where:
- `data[0x10 : content_size]` is every byte from offset 16 to the end of content
- `content_size` is the value stored at `0x04`
- `magic` is 334 (the value at `0x00`)
- `version` is the value at `0x0C`

The checksum deliberately skips `data[0x00:0x10]` (the first 16 bytes) because that region contains the checksum field itself — a field cannot be included in its own checksum. Bytes `0x00–0x03` (magic) and `0x0C–0x0F` (version) are instead incorporated as discrete addends.

The version-dependent term (`+ version`) means that converting between versions changes the checksum even if no other bytes change — the new checksum must always be recomputed using the final version field value. The tool handles this automatically, even when using the custom `-t` target version flag.

---

## Methodology

Six saves were used for analysis:

- `PrePS4.dat` — PS4 v46 (pre-update)
- `UpdatedPrePS4.dat` — PS4 v48 (same base save loaded on updated PS4)
- `PCPrePS4.sav` — PC v49 (same base save loaded on PC)
- `PCPrePS42.sav` — PC v49 (same base save, different slot)
- `dis.dat` — PS4 v48 (unrelated save, different game progress)
- `manual_0001.sav` — PC v49 (unrelated save, different game progress)

Having saves that were confirmed to be the same underlying data across platforms was essential for distinguishing structural format differences from game state differences.

The approach:
1. Compare headers byte-by-byte to identify fixed fields (magic, version)
2. Cross-reference `data[0x04]` against file sizes to identify the content length field
3. Diff the content regions between platform-paired saves to locate structural insertions
4. Check field values across all saves to identify constants vs. per-save vs. per-platform values
5. Derive the checksum formula empirically using the known-good checksum values as constraints

No game code was disassembled or decompiled. The entire analysis was based on observable patterns in the binary data.
