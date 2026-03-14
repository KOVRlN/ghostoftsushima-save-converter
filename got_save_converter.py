#!/usr/bin/env python3
"""
Ghost of Tsushima — Save File Converter
Converts save files between PS4 (dis.dat) and PC (manual_XXXX.sav)

Usage:
  python got_save_converter.py ps4_to_pc  <input.dat>  [output.sav] [-f] [-t VERSION]
  python got_save_converter.py pc_to_ps4  <input.sav>  [output.dat] [-f] [-t VERSION]
  python got_save_converter.py detect     <input_file>

Options:
  -f, --force               Ignore input file version/platform mismatches
  -t, --target-version <v>  Set a custom output version (default: 49 for PC, 48 for PS4)

How it works
------------
After the latest update the game embeds platform-specific marker bytes at
offset 0x180. Old saves (v46 was my only test version) have no markers; updated PS4 saves (v48 / 2.24) have
16 bytes; PC saves (v49) have 24 bytes. The game rejects saves that carry the
wrong platform marker, reporting them as "corrupted".

Structure discovered by reverse-engineering six save files:

  Offset  Size  Field
  0x00     4    Magic constant: 0x0000014E (334)
  0x04     4    Content size (bytes); PS4 saves are zero-padded to 555,008 B
  0x08     4    Checksum = sum(data[0x10:content_size]) + content_size + magic + version
  0x0C     4    Version: 48 > Pre v2.24, 48 = After v2.24, 49+ = PC
  0x10    32    Unknown (identical across all saves)
  0x30    ...   Game data
  ...
  0x180    8    Slot 1 — build hash (same on all platforms): 6a4b716a45ed4447
  0x188    8    Slot 2 — PLATFORM MARKER  (PS4: 7e8a516a45ed4447 / PC: d5cf106b395e5d10)
  0x190    8    Slot 3 — PC only extra:   bfe1bd115c5c51a2
  0x198   ...   Game payload (continues)

PS4 saves are always padded with zeros to exactly 555,008 bytes.
PC saves carry no padding.
"""

import sys
import os
import struct

# ── Constants ────────────────────────────────────────────────────────────────

MAGIC           = 334          # 0x0000014E — fixed for all saves
PS4_FILE_SIZE   = 555_008      # PS4 container is always this many bytes
VERSION_PS4     = 48
VERSION_PC      = 49
SLOT_OFFSET     = 0x180        # Where the platform block starts

SLOT1     = bytes.fromhex('6a4b716a45ed4447')  # Build hash — same everywhere
SLOT2_PS4 = bytes.fromhex('7e8a516a45ed4447')  # PS4 platform marker
SLOT2_PC  = bytes.fromhex('d5cf106b395e5d10')  # PC  platform marker
SLOT3_PC  = bytes.fromhex('bfe1bd115c5c51a2')  # PC-only extra slot


# ── Header helpers ────────────────────────────────────────────────────────────

def read_header(data: bytes) -> dict:
    magic, content_size, checksum, version = struct.unpack_from('<IIII', data, 0)
    return {
        'magic':        magic,
        'content_size': content_size,
        'checksum':     checksum,
        'version':      version,
    }


def compute_checksum(data: bytearray, content_size: int) -> int:
    """
    checksum = sum(data[0x10 : content_size]) + content_size + magic + version
    Verified against six reference saves.
    """
    magic   = int.from_bytes(data[0:4],   'little')
    version = int.from_bytes(data[12:16], 'little')
    return sum(data[0x10:content_size]) + content_size + magic + version


def verify_checksum(data: bytes) -> bool:
    h = read_header(data)
    content_size = h['content_size']
    expected = compute_checksum(bytearray(data), content_size)
    return expected == h['checksum']


# ── Detection ────────────────────────────────────────────────────────────────

def detect_platform(data: bytes) -> str:
    """Return 'ps4', 'pc', 'old_ps4', or 'unknown'."""
    h = read_header(data)
    if h['magic'] != MAGIC:
        return 'unknown'

    version = h['version']
    if version == 49:
        return 'pc'
    if version == 48:
        slot2 = data[0x188:0x190]
        if slot2 == SLOT2_PS4:
            return 'ps4'
        if slot2 == SLOT2_PC:
            return 'pc'   # edge case: wrong version byte?
        return 'unknown'
    if version == 46:
        return 'old_ps4'
    return 'unknown'


# ── Conversion ───────────────────────────────────────────────────────────────

def ps4_to_pc(data: bytes, force_version: bool = False, target_version: int = VERSION_PC) -> bytes:
    """Convert a PS4 save to PC format."""
    h = read_header(data)

    # Validation
    if h['magic'] != MAGIC:
        raise ValueError(f"Not a Ghost of Tsushima save (magic={h['magic']:#x})")

    if not force_version:
        if h['version'] == target_version:
            raise ValueError(f"This file is already at target version {target_version}.")
        if h['version'] != VERSION_PS4:
            raise ValueError(f"Unrecognised save version {h['version']} — cannot convert. Use -f to force bypass.")

    slot1 = data[SLOT_OFFSET:SLOT_OFFSET + 8]
    slot2 = data[SLOT_OFFSET + 8:SLOT_OFFSET + 16]

    if slot1 != SLOT1:
        msg = f"Unexpected slot 1 value: {slot1.hex()} — file may be corrupt."
        if not force_version:
            raise ValueError(msg)
        else:
            print(f"WARNING: {msg} Proceeding anyway (-f).")

    if slot2 != SLOT2_PS4:
        msg = f"Slot 2 is not the PS4 marker ({slot2.hex()}). File may already be converted or corrupt."
        if not force_version:
            raise ValueError(msg)
        else:
            print(f"WARNING: {msg} Proceeding anyway (-f).")

    content_size = h['content_size']
    buf = bytearray(data[:content_size])   # strip PS4 zero-padding

    # 1. Replace PS4 platform marker with PC marker
    buf[SLOT_OFFSET + 8 : SLOT_OFFSET + 16] = SLOT2_PC

    # 2. Insert slot 3 (PC-only) right after slot 2
    insert_pos = SLOT_OFFSET + 16
    buf = buf[:insert_pos] + bytearray(SLOT3_PC) + buf[insert_pos:]

    # 3. Update version
    struct.pack_into('<I', buf, 12, target_version)

    # 4. Update content size (+8 for the newly inserted slot 3)
    new_size = len(buf)
    struct.pack_into('<I', buf, 4, new_size)

    # 5. Recompute and write checksum
    cs = compute_checksum(buf, new_size)
    struct.pack_into('<I', buf, 8, cs)

    return bytes(buf)


def pc_to_ps4(data: bytes, force_version: bool = False, target_version: int = VERSION_PS4) -> bytes:
    """Convert a PC save to PS4 format."""
    h = read_header(data)

    # Validation
    if h['magic'] != MAGIC:
        raise ValueError(f"Not a Ghost of Tsushima save (magic={h['magic']:#x})")

    if not force_version:
        if h['version'] == target_version:
            raise ValueError(f"This file is already at target version {target_version}.")
        if h['version'] != VERSION_PC:
            raise ValueError(f"Unrecognised save version {h['version']} — cannot convert. Use -f to force bypass.")

    slot1 = data[SLOT_OFFSET:SLOT_OFFSET + 8]
    slot2 = data[SLOT_OFFSET + 8:SLOT_OFFSET + 16]
    slot3 = data[SLOT_OFFSET + 16:SLOT_OFFSET + 24]

    if slot1 != SLOT1:
        msg = f"Unexpected slot 1 value: {slot1.hex()} — file may be corrupt."
        if not force_version:
            raise ValueError(msg)
        else:
            print(f"WARNING: {msg} Proceeding anyway (-f).")

    if slot2 != SLOT2_PC:
        msg = f"Slot 2 is not the PC marker ({slot2.hex()}). File may already be converted or corrupt."
        if not force_version:
            raise ValueError(msg)
        else:
            print(f"WARNING: {msg} Proceeding anyway (-f).")

    if slot3 != SLOT3_PC:
        msg = f"Slot 3 is not the expected PC-only value ({slot3.hex()}). File may be corrupt."
        if not force_version:
            raise ValueError(msg)
        else:
            print(f"WARNING: {msg} Proceeding anyway (-f).")

    buf = bytearray(data)

    # 1. Replace PC platform marker with PS4 marker
    buf[SLOT_OFFSET + 8 : SLOT_OFFSET + 16] = SLOT2_PS4

    # 2. Remove slot 3 (the 8 PC-only bytes)
    remove_start = SLOT_OFFSET + 16
    buf = buf[:remove_start] + buf[remove_start + 8:]

    # 3. Update version
    struct.pack_into('<I', buf, 12, target_version)

    # 4. Update content size (-8 for the removed slot)
    new_size = len(buf)
    struct.pack_into('<I', buf, 4, new_size)

    # 5. Recompute and write checksum
    cs = compute_checksum(buf, new_size)
    struct.pack_into('<I', buf, 8, cs)

    # 6. Pad to PS4 container size
    if len(buf) > PS4_FILE_SIZE:
        raise ValueError(
            f"Content ({len(buf)} B) exceeds PS4 container size ({PS4_FILE_SIZE} B)."
        )
    buf += bytearray(PS4_FILE_SIZE - len(buf))

    return bytes(buf)


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_detect(path: str):
    with open(path, 'rb') as f:
        data = f.read()
    h = read_header(data)
    platform = detect_platform(data)
    cs_ok = verify_checksum(data)

    print(f"File:          {os.path.basename(path)}")
    print(f"Size:          {len(data):,} bytes")
    print(f"Magic:         0x{h['magic']:08X} ({'OK' if h['magic'] == MAGIC else 'WRONG'})")
    print(f"Version:       {h['version']}")
    print(f"Content size:  {h['content_size']:,} bytes")
    print(f"Checksum:      {'valid' if cs_ok else 'INVALID'}")
    print(f"Platform:      {platform.upper()}")
    if platform in ('ps4', 'pc'):
        slot2 = data[0x188:0x190]
        print(f"Platform marker (slot 2): {slot2.hex()}")


def cmd_convert(mode: str, input_path: str, output_path: str | None, force: bool = False, target: int | None = None):
    with open(input_path, 'rb') as f:
        data = f.read()

    platform = detect_platform(data)
    cs_ok = verify_checksum(data)
    if not cs_ok:
        print("WARNING: Input file checksum is invalid — the file may already be corrupt.")

    if mode == 'ps4_to_pc':
        if platform != 'ps4' and not force:
            print(f"ERROR: Expected a PS4 save, got '{platform}'. Aborting. Use -f to bypass.")
            sys.exit(1)

        tv = target if target is not None else VERSION_PC
        print(f"Converting PS4 to PC (Target Version: {tv}) ...")
        result = ps4_to_pc(data, force_version=force, target_version=tv)
        if output_path is None:
            base = os.path.splitext(input_path)[0]
            output_path = base + '_converted.sav'

    elif mode == 'pc_to_ps4':
        if platform != 'pc' and not force:
            print(f"ERROR: Expected a PC save, got '{platform}'. Aborting. Use -f to bypass.")
            sys.exit(1)

        tv = target if target is not None else VERSION_PS4
        print(f"Converting PC to PS4 (Target Version: {tv}) ...")
        result = pc_to_ps4(data, force_version=force, target_version=tv)
        if output_path is None:
            base = os.path.splitext(input_path)[0]
            output_path = base + '_converted.dat'

    else:
        print(f"ERROR: Unknown mode '{mode}'")
        sys.exit(1)

    # Verify the output
    out_h = read_header(result)
    out_cs_ok = verify_checksum(result)
    print(f"  Input:    {len(data):,} bytes  (v{read_header(data)['version']})")
    print(f"  Output:   {len(result):,} bytes  (v{out_h['version']})")
    print(f"  Checksum: {'valid' if out_cs_ok else 'INVALID — BUG, please report!'}")

    with open(output_path, 'wb') as f:
        f.write(result)
    print(f"  Saved to: {output_path}")


def print_usage():
    print(__doc__)
    print("Commands:")
    print("  detect    <file>              — inspect a save file")
    print("  ps4_to_pc <input.dat> [out]   — convert PS4 save to PC format")
    print("  pc_to_ps4 <input.sav> [out]   — convert PC save to PS4 format")
    print("\nOptions:")
    print("  -f, --force               — ignore input version/platform checks")
    print("  -t, --target-version <v>  — set custom output version")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', 'help'):
        print_usage()
        sys.exit(0)

    # Manual argument parsing to extract optional flags
    force_version = False
    target_version = None
    positional_args = []

    i = 0
    while i < len(args):
        if args[i] in ('-f', '--force'):
            force_version = True
            i += 1
        elif args[i] in ('-t', '--target-version'):
            if i + 1 >= len(args):
                print("ERROR: --target-version requires a version number.")
                sys.exit(1)
            try:
                target_version = int(args[i+1])
            except ValueError:
                print(f"ERROR: Target version must be an integer, got '{args[i+1]}'")
                sys.exit(1)
            i += 2
        else:
            positional_args.append(args[i])
            i += 1

    if not positional_args:
        print_usage()
        sys.exit(0)

    mode = positional_args[0]

    if mode == 'detect':
        if len(positional_args) < 2:
            print("ERROR: detect requires a file path.")
            sys.exit(1)
        cmd_detect(positional_args[1])

    elif mode in ('ps4_to_pc', 'pc_to_ps4'):
        if len(positional_args) < 2:
            print(f"ERROR: {mode} requires an input file path.")
            sys.exit(1)

        input_path  = positional_args[1]
        output_path = positional_args[2] if len(positional_args) >= 3 else None

        try:
            cmd_convert(mode, input_path, output_path, force=force_version, target=target_version)
        except (ValueError, OSError) as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    else:
        print(f"ERROR: Unknown command '{mode}'")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
