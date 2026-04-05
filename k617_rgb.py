#!/usr/bin/env python3
"""
k617_rgb — Per-key RGB controller for the Redragon K617 Fizz

Controls all 61 keys individually via USB HID feature reports.
Reverse-engineered from the Sinowealth SH68F83 controller protocol.

Usage:
    sudo python3 k617_rgb.py all red
    sudo python3 k617_rgb.py all ff8000
    sudo python3 k617_rgb.py wasd white
    sudo python3 k617_rgb.py key W ff0000
    sudo python3 k617_rgb.py row0 yellow
    sudo python3 k617_rgb.py demo
    sudo python3 k617_rgb.py custom
    sudo python3 k617_rgb.py map
    sudo python3 k617_rgb.py off

Warning:
    Every write commits to flash (~100K cycle endurance).
    Do not call this in a tight loop.
"""

import hid
import sys
import time
import json

# --- Hardware ---

VID, PID = 0x258A, 0x0049

BLUE_BASE = 8
GREEN_BASE = 134
RED_BASE = 260

# --- LED index map (from Cfg.ini) ---
# Stride-21 layout: row N starts at (N+1)*21, 14 data + 7 gap per row.

LED_INDEX = {
    # Row 0 — number row
    'Esc': 21, '1': 22, '2': 23, '3': 24,
    '4': 25, '5': 26, '6': 27, '7': 28,
    '8': 29, '9': 30, '0': 31, '-': 32,
    '=': 33, 'Bksp': 34,
    # Row 1 — qwerty row
    'Tab': 42, 'Q': 43, 'W': 44, 'E': 45,
    'R': 46, 'T': 47, 'Y': 48, 'U': 49,
    'I': 50, 'O': 51, 'P': 52, '[': 53,
    ']': 54, '\\': 55,
    # Row 2 — home row
    'CapsLk': 63, 'A': 64, 'S': 65, 'D': 66,
    'F': 67, 'G': 68, 'H': 69, 'J': 70,
    'K': 71, 'L': 72, ';': 73, "'": 74,
    'Enter': 76,
    # Row 3 — bottom row
    'LShift': 84, 'Z': 86, 'X': 87, 'C': 88,
    'V': 89, 'B': 90, 'N': 91, 'M': 92,
    ',': 93, '.': 94, '/': 95, 'RShift': 97,
    # Row 4 — modifier row
    'LCtrl': 105, 'LWin': 106, 'LAlt': 107, 'Space': 110,
    'RAlt': 113, 'Fn': 114, 'Menu': 117, 'RCtrl': 118,
}

ROWS = {
    'row0': ['Esc', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Bksp'],
    'row1': ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\'],
    'row2': ['CapsLk', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'Enter'],
    'row3': ['LShift', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/', 'RShift'],
    'row4': ['LCtrl', 'LWin', 'LAlt', 'Space', 'RAlt', 'Fn', 'Menu', 'RCtrl'],
}

WASD = ['W', 'A', 'S', 'D']

COLORS = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'white': (255, 255, 255),
    'yellow': (255, 255, 0),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
    'orange': (255, 128, 0),
    'purple': (128, 0, 255),
    'pink': (255, 64, 128),
    'off': (0, 0, 0),
}

# --- Protocol blobs (captured from OEM software, never modify) ---

INIT = bytes.fromhex('0583b6000000')

# Secondary region in P1 — routing metadata
SEC = bytes.fromhex(
    'ffffffffff000000000000000000000000000000'
    'ffffffffff0000000000000000000000000000000000'
    'ffffff00ff000000000000000000000000000000ff00'
    '0000000000ff0000000000000000000000000000ff00'
    'ff0000ff00000000000000000000000000000000'
)

# P2 — key routing packet (from red.pcapng frame 6591)
P2 = bytes.fromhex('0609c00040000000000000000000ffffffffffffff0000000000000000000000000000ffffffffff00000000000000000000000000000000ffffffffff000000000000000000000000000000ff000000ffff000000000000000000000000000000ff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ffffffffffffff0000000000000000000000000000ffffffff0000000000000000000000000000000000ffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ff00ff0000000000000000000000000000000000ffffff0000000000000000000000000000000000ff0000000000000000000000000000000000000000ff00ff0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')

# EXEC — effect config + flash commit (from red.pcapng frame 6595)
EX = bytes.fromhex('0603b600000000000000000000005aa50303030001152001000000005555010000000000ffff003207330733073307440733073307330733073307330722073307330733073307330733073307335aa50010074407440744074407440744074404040404040404040404000000000000000000000000000000000000000000000000000000000000005aa50303030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')


# --- Core ---

def build_p1(key_colors):
    """
    Build the 1032-byte P1 RGB canvas packet.
    key_colors: dict of key_name -> (r, g, b), values 0-255.
    """
    p1 = bytearray(1032)
    p1[0], p1[1], p1[2], p1[3], p1[4] = 0x06, 0x09, 0xBC, 0x00, 0x40

    for key, (r, g, b) in key_colors.items():
        if key not in LED_INDEX:
            print(f"  warning: unknown key '{key}', skipping")
            continue
        idx = LED_INDEX[key]
        p1[RED_BASE + idx] = r
        p1[GREEN_BASE + idx] = g
        p1[BLUE_BASE + idx] = b

    p1[660:660 + len(SEC)] = SEC
    return bytes(p1)


def send_colors(key_colors):
    """
    Send colors to the keyboard. Writes to flash.
    key_colors: dict of key_name -> (r, g, b)
    """
    devs = hid.enumerate(VID, PID)
    vendor = [d for d in devs if d['usage_page'] == 0xFF00]
    if not vendor:
        sys.exit("error: K617 not found. Is it plugged in? Try sudo.")

    dev = hid.Device(path=vendor[0]['path'])
    try:
        dev.send_feature_report(INIT)
        time.sleep(0.06)

        dev.get_feature_report(0x06, 1032)  # mandatory handshake
        time.sleep(0.06)

        dev.send_feature_report(build_p1(key_colors))
        time.sleep(0.06)

        dev.send_feature_report(P2)
        time.sleep(0.06)

        dev.send_feature_report(EX)

        active = sum(1 for v in key_colors.values() if any(c > 0 for c in v))
        print(f"✓ applied colors to {active} keys ({len(key_colors)} total)")
    finally:
        dev.close()


# --- Helpers ---

def parse_color(s):
    """Parse color name or hex string -> (r, g, b)."""
    s = s.lower().strip()
    if s in COLORS:
        return COLORS[s]
    h = s.lstrip('#')
    if len(h) == 6:
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except ValueError:
            pass
    sys.exit(f"error: unknown color '{s}'. Use a name ({', '.join(COLORS)}) or hex (ff8000)")


def print_key_map():
    """Print the full key -> LED index -> byte offset map."""
    print(f"\n{'Key':<10} {'LED':>4} {'Blue':>6} {'Green':>6} {'Red':>5}")
    print("─" * 37)
    for row_name, keys in ROWS.items():
        for key in keys:
            idx = LED_INDEX[key]
            print(f"{key:<10} {idx:>4} {BLUE_BASE+idx:>6} {GREEN_BASE+idx:>6} {RED_BASE+idx:>5}")
        print()


# --- CLI ---

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("colors:", ', '.join(COLORS))
        print("rows:  ", ', '.join(ROWS))
        print("keys:  ", ', '.join(sorted(LED_INDEX)))
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == 'map':
        print_key_map()
        return

    if cmd == 'off':
        send_colors({k: (0, 0, 0) for k in LED_INDEX})
        return

    if cmd == 'demo':
        colors = {}
        for k in WASD:
            colors[k] = (255, 255, 255)
        for k in ['Esc', '1', '2', '3', '4']:
            colors[k] = (255, 128, 0)
        for k in ['5', '6', '7', '8', '9']:
            colors[k] = (255, 255, 0)
        print("demo: WASD=white, Esc-4=orange, 5-9=yellow")
        send_colors(colors)
        return

    if cmd == 'wasd':
        color = parse_color(sys.argv[2]) if len(sys.argv) > 2 else COLORS['white']
        send_colors({k: color for k in WASD})
        return

    if cmd == 'all':
        color = parse_color(sys.argv[2]) if len(sys.argv) > 2 else COLORS['white']
        send_colors({k: color for k in LED_INDEX})
        return

    if cmd in ROWS:
        color = parse_color(sys.argv[2]) if len(sys.argv) > 2 else COLORS['white']
        send_colors({k: color for k in ROWS[cmd]})
        return

    if cmd == 'key':
        if len(sys.argv) < 4:
            sys.exit("usage: k617_rgb.py key <KEY> <COLOR>")
        key = sys.argv[2]
        color = parse_color(sys.argv[3])
        if key not in LED_INDEX:
            sys.exit(f"unknown key '{key}'. available: {', '.join(sorted(LED_INDEX))}")
        send_colors({key: color})
        return

    if cmd == 'custom':
        print('enter key:color pairs as JSON, e.g.:')
        print('  {"W": "white", "A": "ff0000", "Esc": "orange"}')
        raw = input("> ").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.exit(f"invalid JSON: {e}")
        colors = {}
        for key, val in data.items():
            if isinstance(val, str):
                colors[key] = parse_color(val)
            elif isinstance(val, (list, tuple)) and len(val) == 3:
                colors[key] = tuple(val)
            else:
                sys.exit(f"invalid color for '{key}': {val}")
        send_colors(colors)
        return

    # fallback: treat as color name for "all"
    try:
        color = parse_color(cmd)
        send_colors({k: color for k in LED_INDEX})
    except SystemExit:
        print(f"unknown command: {cmd}")
        print("commands: all, wasd, row0-row4, key, demo, custom, map, off")
        sys.exit(1)


if __name__ == '__main__':
    main()
