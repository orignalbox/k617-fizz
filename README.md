# K617 Fizz — RGB Controller

Per-key RGB control for the Redragon K617 Fizz (60% keyboard) on Linux.
Reverse-engineered from the Sinowealth SH68F83 USB HID protocol.

## What this does

- Set any of the 61 keys to any RGB color independently
- Screen sync — match keyboard colors to your screen
- Full protocol documentation for the SH68F83 controller

## Requirements

- Python 3
- `hid` library — `pip install hid`
- `sudo` for raw HID access
- `maim` for screen sync only

## Usage

```bash
sudo python3 k617_rgb.py all red
sudo python3 k617_rgb.py all ff8000
sudo python3 k617_rgb.py wasd white
sudo python3 k617_rgb.py key W ff0000
sudo python3 k617_rgb.py row0 yellow
sudo python3 k617_rgb.py demo
sudo python3 k617_rgb.py off
sudo python3 k617_rgb.py custom
sudo python3 k617_rgb.py map
```

### Screen sync

```bash
sudo python3 k617_screensync.py
```

Captures a screenshot and maps screen colors to keyboard keys. One-shot — every write goes to flash, so don't loop it.

## How it works

5-packet USB HID feature report sequence:

| Step | Packet | Purpose |
|------|--------|---------|
| 1 | INIT (6 bytes) | Tell firmware we want to write colors |
| 2 | GET_REPORT (1032 bytes) | Mandatory handshake |
| 3 | P1 (1032 bytes) | RGB canvas — the only packet we modify |
| 4 | P2 (1032 bytes) | Key routing — never modify |
| 5 | EXEC (1032 bytes) | Flash commit |

Colors in P1 use split-plane encoding:

```
p1[8   + led_index] = blue   (0-255)
p1[134 + led_index] = green  (0-255)
p1[260 + led_index] = red    (0-255)
```

## Files

| File | Description |
|------|-------------|
| `k617_rgb.py` | RGB controller with CLI |
| `k617_screensync.py` | Screen-to-keyboard color sync |
| `K617_PROTOCOL_COMPLETE.md` | Full protocol reference |
| `blog/` | Blog post about the process |

## Hardware

| Field | Value |
|-------|-------|
| Keyboard | Redragon K617 Fizz (60%, wired) |
| Controller | Sinowealth SH68F83 |
| USB VID | `0x258A` |
| USB PID | `0x0049` |
