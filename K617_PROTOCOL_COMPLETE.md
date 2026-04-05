# K617 Fizz — Complete Reverse Engineering Reference
*Last updated: probe round 6 — ALL THREE CHANNELS CONFIRMED*
*All findings empirically confirmed via USB capture + Linux hidraw probing + pcapng analysis*

---

## 1. Hardware

| Field | Value |
|---|---|
| Keyboard | Redragon K617 Fizz (60% wired) |
| Controller chip | Sinowealth SH68F83 |
| USB VID | `0x258A` |
| USB PID | `0x0049` |
| Linux HID node | `/dev/hidraw1` (verify with grep below) |
| HID interface | Interface 1, usage page `0xFF00` (vendor-defined) |
| Report ID | `0x06` for all large packets, `0x05` for INIT |
| Report size | 1032 bytes per large packet |

Find your hidraw node:
```bash
grep -rl "258A" /sys/class/hidraw/*/device/uevent
# Then pick the one with usage_page 0xFF00:
python3 -c "
import hid
for d in hid.enumerate(0x258A, 0x0049):
    print(d['interface_number'], hex(d['usage_page']), d['path'])
"
```

---

## 2. Packet Sequence — Static Custom Color

Always exactly 5 steps in this order:

```
Step 1: SET_REPORT  ID=0x05  len=6      → INIT
Step 2: GET_REPORT  ID=0x06  len=1032   → Handshake (mandatory — read and discard)
Step 3: SET_REPORT  ID=0x06  len=1032   → P1  (RGB canvas — this is what you modify)
Step 4: SET_REPORT  ID=0x06  len=1032   → P2  (routing — NEVER modify)
Step 5: SET_REPORT  ID=0x06  len=1032   → EXEC (effect config + 5AA5 flash commit)
```

**The GET_REPORT handshake (step 2) is mandatory.**
Without it, all subsequent writes are silently ignored by the firmware.

---

## 3. INIT Packet (6 bytes)

```
05 83 b6 00 00 00
```
Fixed. Never changes. Report ID = 0x05.

---

## 4. P1 — RGB Canvas (1032 bytes)

This is the only packet you need to modify to control colors.

### 4.1 Header (bytes 0-4)

```
06 09 bc 00 40
```
Fixed. Never change.

### 4.2 Channel Layout — ALL THREE CHANNELS CONFIRMED ✓

The P1 packet encodes RGB using a **split-plane architecture**.
Each color channel occupies a separate region of the packet.

**Universal formula:**
```
p1[base + led_index] = color_value (0-255)

  Blue  base =   8
  Green base = 134
  Red   base = 260
```

LED indices follow a stride-21 pattern: row N starts at `(N+1)*21`,
14 data bytes per row + 7 gap bytes. All indices from `Cfg.ini [KEY]` section.

```
Bytes   5 – 126  : BLUE  channel (base=8, all rows)
Bytes 127 – 252  : GREEN channel (base=134, all rows)
Bytes 253 – 280  : Zeros (green padding)
Bytes 281 – 378  : RED   channel (base=260, all rows)
Bytes 379 – 659  : Zeros — leave as 00
Bytes 660 – 748  : Secondary region — copy verbatim, never modify
Bytes 749 – 1031 : Zeros — leave as 00
```

**Discovery method:** Isolated each region with 0xFF fill, observed which
keys lit and what color. Three rounds of probing (probe4, probe5).

### 4.3 Red Channel — Stride-21 Layout (bytes 281-378)

Each row occupies 14 consecutive bytes followed by a 7-byte gap.
Row N starts at: `281 + N * 21`

**Confirmed from probe16 (bytes 281-287 → Esc to 6) and probe17 (bytes 302-308 → Tab to Y).**

```
Row 0 — Number row (base = 281):
  p1[281] = Esc      p1[282] = 1       p1[283] = 2       p1[284] = 3
  p1[285] = 4        p1[286] = 5       p1[287] = 6       p1[288] = 7
  p1[289] = 8        p1[290] = 9       p1[291] = 0       p1[292] = -
  p1[293] = =        p1[294] = Bksp
  [295-301] = 7-byte gap (do not write)

Row 1 — QWERTY row (base = 302):
  p1[302] = Tab      p1[303] = Q       p1[304] = W       p1[305] = E
  p1[306] = R        p1[307] = T       p1[308] = Y       p1[309] = U
  p1[310] = I        p1[311] = O       p1[312] = P       p1[313] = [
  p1[314] = ]        p1[315] = \
  [316-322] = 7-byte gap

Row 2 — Home row (base = 323):
  p1[323] = CapsLk   p1[324] = A       p1[325] = S       p1[326] = D
  p1[327] = F        p1[328] = G       p1[329] = H       p1[330] = J
  p1[331] = K        p1[332] = L       p1[333] = ;       p1[334] = '
  p1[335] = Enter    p1[336] = (gap)
  [337-343] = 7-byte gap

Row 3 — Bottom row (base = 344):
  p1[344] = LShift   p1[345] = Z       p1[346] = X       p1[347] = C
  p1[348] = V        p1[349] = B       p1[350] = N       p1[351] = M
  p1[352] = ,        p1[353] = .       p1[354] = /       p1[355] = RShift
  p1[356] = (gap)    p1[357] = (gap)
  [358-364] = 7-byte gap

Row 4 — Modifier row (base = 365):
  p1[365] = LCtrl    p1[366] = LWin    p1[367] = LAlt    p1[368] = Space
  p1[369] = (gap)    p1[370] = (gap)   p1[371] = (gap)   p1[372] = RAlt
  p1[373] = (gap)    p1[374] = (gap)   p1[375] = RCtrl   p1[376] = Fn
  p1[377] = Menu     p1[378] = (gap)
```

### 4.4 Blue and Green Channel Layout — CONFIRMED ✓

All three channels use the **same LED index** with different base offsets.
The formula `p1[base + led_index]` was confirmed by parsing `packetsss.pcapng`
(WASD=White, first-5=Orange, next-5=Yellow) and cross-referencing with
LED indices from `Cfg.ini`.

**Blue channel (base=8):**
```
p1[8 + led_index] = blue_value
Example: W (led=44) → p1[52], A (led=64) → p1[72]
```

**Green channel (base=134):**
```
p1[134 + led_index] = green_value
Example: W (led=44) → p1[178], A (led=64) → p1[198]
```

**All 14 capture data points verified with 100% accuracy.**

### 4.5 Secondary Region (bytes 660-748)

Copy verbatim from capture. Routing/matrix metadata. Never modify.

```python
SEC = bytes.fromhex(
    'ffffffffff000000000000000000000000000000'
    'ffffffffff0000000000000000000000000000000000'
    'ffffff00ff000000000000000000000000000000ff00'
    '0000000000ff0000000000000000000000000000ff00'
    'ff0000ff00000000000000000000000000000000'
)
p1[660:660+len(SEC)] = SEC
```

---

## 5. P2 — Key Routing (1032 bytes)

**NEVER MODIFY.** Corrupting P2 causes immediate firmware crash (keyboard
restarts). Copy verbatim from a known-good capture.

Header: `06 09 c0 00 40`

Confirmed safe P2 blob (from red.pcapng frame 6591):
```
0609c00040000000000000000000ffffffffffffff0000000000000000000000...
[full hex in k617_tool.py]
```

---

## 6. EXEC — Effect Config (1032 bytes)

**NEVER MODIFY** the 5AA5 region. Every sequence in every capture contains
5AA5 in EXEC, meaning every send is a flash write.

Header: `06 03 b6 00 00`

Key fields (for reference only — do not hand-construct):
```
Byte  14-15 : 5A A5        magic marker — DO NOT TOUCH
Byte  20    : 0x01         effect_id = custom static color (confirmed)
Byte  21    : 0x15         brightness = full
Bytes 16-18 : 03 03 03     firmware-critical — DO NOT TOUCH
```

Confirmed safe EXEC blob (from red.pcapng frame 6595):
```
0603b600000000000000000000005aa503030300011520010000000055550100...
[full hex in k617_rgb.py]
```

---

## 7. Flash vs RAM

**Every single captured sequence includes 5AA5 in EXEC = flash write.**
The blink you see when applying = firmware restart after flash commit.

**Flash endurance:** ~100,000 cycles (typical Sinowealth chip).
**At 1 write/second:** dead in ~27 hours.
**At 30 writes/second:** dead in ~55 minutes.

**DO NOT loop this protocol at high frequency.**

RAM-only path: **confirmed not available.**
Tested: skipping EXEC, zeroing 5AA5 marker, skipping P2+EXEC entirely.
Even the OEM software's preview mode triggers a flash write.
This firmware does not support RAM-only color updates.

---

## 8. Usage

See `k617_rgb.py` for the full implementation with CLI, all 61 keys mapped across
all three channels (blue, green, red).

```bash
sudo python3 k617_rgb.py all red
sudo python3 k617_rgb.py wasd white
sudo python3 k617_rgb.py key W ff0000
sudo python3 k617_rgb.py demo
```

For screen-to-keyboard color sync:

```bash
sudo python3 k617_screensync.py
```

---

## 9. Status

| # | Item | Status | Method |
|---|---|---|---|
| 1 | Blue plane per-key offsets | ✅ Done | Parsed packetsss.pcapng + Cfg.ini LED indices |
| 2 | Green plane per-key offsets | ✅ Done | Same — universal formula confirmed |
| 3 | Exact Ctrl+Menu green bytes | ✅ Done | LCtrl=134+105=239, Menu=134+117=251 |
| 4 | RAM-only path | ❌ Not available | Tested all variants — firmware always writes to flash |
| 5 | Full key index → physical key map | ✅ Done | All 61 keys mapped via Cfg.ini LED indices |

---

## 10. RE Methodology

### Tools used
- Windows: Redragon OEM software + USBPcap + Wireshark
- Linux: Python3 + `hid` library (`pip install hid`) + `/dev/hidraw1`

### Capture approach
1. Set OEM software to a specific color/effect
2. Capture with filter: `usb.src == "host" && usb.transfer_type == 0x02`
3. Extract with tshark: `tshark -r file.pcapng -T json`
4. Parse `usb.data_fragment` fields

### Key discoveries in order
1. VID/PID identification from Device Manager
2. Feature reports (not output reports) — report ID 0x06
3. 5-packet sequence structure from Wireshark
4. GET_REPORT handshake mandatory (discovered after hours of writes being ignored)
5. effect_id = 0x01 for custom static color (brute-forced 0x00-0x14)
6. P2 must never be modified (caused firmware crash)
7. P1 RGB canvas confirmed working (4-corner test)
8. Split-plane architecture discovered via region flooding
9. Red plane stride-21 layout confirmed (probes 16-17)
10. Blue/green channel boundaries narrowed (probes 1-5)

---

## 11. Probe History

| Probe | Bytes written | Result | Conclusion |
|---|---|---|---|
| probe4 test0 | 281-378 = FF | All keys red | RED plane confirmed |
| probe4 test1 | 66-126 = FF | Rows 3-5 blue | BLUE rows3-5 at 66-126 |
| probe4 test5 | r=FF g=FF | Rows1-2 red, rows3-5 pink | RED+BLUE mixing confirmed |
| probe4 test7 | 66-79 = FF | CapsLk-K blue (9 keys) | Blue plane index ordering starts at home row |
| probe5 test0 | 281-378 = FF | All keys red | RED baseline reconfirmed |
| probe5 test1 | 5-65 = FF | Rows 1-2 blue | BLUE rows1-2 at 5-65 |
| probe5 test2 | 127-187 = FF | Rows 1-2 green (minus 2) | GREEN starts at 127 |
| probe5 test3 | 188-248 = FF | Those 2 + rows 3-5 (minus Ctrl+Menu) | GREEN continues at 188 |
| probe5 test4 | 249-280 = FF | Ctrl + Menu green | GREEN ends ~250 |
| probe5 test5 | 127-280 = FF | All keys green | Full green range confirmed |
| probe5 test9 | blue[0] = FF | Nothing lit | Index 0 is a gap |
| probe5 test10 | blue[0-9] = FF | CapsLk,A,S,D,F blue | Blue indices 0-9 cover row3 first 5 |
| probe5 test16 | 281-287 = FF | Esc,1,2,3,4,5,6 red | RED row0 map confirmed |
| probe5 test17 | 302-308 = FF | Tab,Q,W,E,R,T,Y red | RED row1 map confirmed, stride=21 ✓ |
