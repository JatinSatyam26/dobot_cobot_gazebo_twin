# Digital Twin Laptop — Setup

Everything here runs on the **Ubuntu laptop**. Nothing in this document
touches the cell laptop or the PLC.

Goal: get on the cell's subnet and receive the Pro 600 pose stream.

---

## 1. Network

The cell runs on an isolated subnet with no gateway and no DHCP server.
Every address is static.

| Address | Device |
|---|---|
| 192.168.10.5 | cell laptop (bridges, CCW) |
| 192.168.10.10 | Micro850 PLC |
| 192.168.10.20 | myCobot Pro 600 |
| 192.168.10.40 | Dobot M1 Pro |
| 192.168.10.50 | reserved — laser device server |
| **192.168.10.60** | **this laptop** |

Mask `255.255.255.0` on all of them. No gateway anywhere.

### Find the wired interface

```bash
ip -br link
```

Look for the wired name — `enp3s0`, `eno1`, or similar. Not `lo`
(loopback), not anything starting `wl` (Wi-Fi). Plug the cable into the
MokerLink switch first so you can see which one comes `UP`.

### Configure it

Substitute your real interface name for `enp3s0`:

```bash
sudo nmcli connection add type ethernet \
  con-name workcell ifname enp3s0 \
  ipv4.method manual \
  ipv4.addresses 192.168.10.60/24 \
  ipv4.never-default yes

sudo nmcli connection up workcell
```

`ipv4.never-default yes` matters. It stops Ubuntu routing internet
traffic down this interface, so Wi-Fi keeps working normally for
everything else. Without it you may lose internet whenever the cable
is plugged in.

### GUI alternative

Settings → Network → wired connection gear icon → IPv4:
- Method: Manual
- Address `192.168.10.60`, Netmask `255.255.255.0`
- Gateway and DNS left **empty**
- Under Routes, tick **"Use this connection only for resources on its
  network"** (this is the `never-default` equivalent)

### Verify

```bash
ip -br addr show enp3s0
```

Should show `192.168.10.60/24`.

```bash
ping 192.168.10.5     # cell laptop
ping 192.168.10.10    # PLC
```

Both should answer. Also ask for a `ping 192.168.10.60` from the cell
laptop — **both directions need to work.** If only one direction
answers, it's a firewall, not a cable.

---

## 2. Firewall

Ubuntu ships `ufw` installed but usually inactive.

```bash
sudo ufw status
```

If **inactive**, nothing to do — packets will arrive.

If **active**:

```bash
sudo ufw allow 5005/udp
```

This is the single most common reason the listener sees nothing while
the packets are in fact arriving.

---

## 3. Receive the pose stream

`udp_listen.py` uses only the standard library — no pip installs
needed. Copy it across and run:

```bash
python3 udp_listen.py
```

It prints `... no packets` once a second while the cell is idle. That's
normal: nothing broadcasts until a robot moves.

Ask for the home job to be run on the cell laptop (`py send_cmd.py 0 2`,
then `py send_cmd.py 0 0` to clear). You should see six joint angles
arriving with roughly 53 ms gaps.

### If nothing arrives

1. Firewall — check `sudo ufw status` again
2. Bind address — the listener must bind `0.0.0.0`, **not**
   `192.168.10.60`. Broadcast packets are addressed to
   `192.168.10.255` and a socket bound to a specific interface address
   may not receive them
3. Wrong interface — confirm with `ip -br addr` that .60 is on the
   wired port
4. Confirm the cell laptop's own listener sees the packets. If it
   doesn't either, the problem is on that side, not yours

---

## 4. What's in the stream

One UDP packet per poll to `192.168.10.255:5005`, about 20 per second
**while a move is in progress**. JSON:

```json
{
  "t": 1789157488.123,
  "device": "pro600",
  "label": "traverse",
  "angles": [-81.287, -102.418, 130.242, -117.861, -89.912, -2.285]
}
```

- `t` — sender's wall clock, `time.time()` on the cell laptop. The two
  machines' clocks are not synchronised, so use this for **intervals**,
  not for absolute alignment against anything on your side
- `label` — which leg of the trajectory: `over wafer`, `down to wafer`,
  `lift`, `traverse`, `down to drop`, `home`. A label ending
  `(settled)` is the final reading after the move completed
- `angles` — J1 to J6 in degrees

### Verified behaviour

Confirmed on a full pick-and-place cycle:

- The Pro 600 **does** answer position queries during motion. Gaps held
  at 52–53 ms throughout every leg. Joint-level following is possible
- Encoder quantization is visible: J4 and J6 move in steps of about
  0.088°
- **A ~2 s silence between `down to wafer (settled)` and `lift` is
  normal.** That's the vacuum dwell after the suction valve energises.
  The arm is stationary and holding. It is not a dropped stream

### Known gaps

- **No gripper state in the packet.** During the vacuum dwell you see a
  frozen arm with no indication a wafer was just acquired. Adding the
  two vacuum coil booleans is on the list; say if you want it sooner
- **Pro 600 only.** The M1 Pro is not on this stream — see below

---

## 5. M1 Pro — use port 30004 directly

Do **not** ask for a UDP patch for the M1 Pro. It already has a
real-time feedback port that broadcasts a fixed-size status packet
continuously, including joint actuals, and it is designed for exactly
this kind of read-only consumer alongside the control connection.

```
192.168.10.40 : 30004
```

Ports 29999 (control) and 30003 (motion) are held by `m1_bridge.py` on
the cell laptop — **do not connect to those.**

Check the packet layout against Dobot's TCP/IP protocol documentation
for the M1 Pro before parsing.

---

## 6. Sequencer step — register 400031

`Step_Mirror` is mapped and live. Modbus TCP to `192.168.10.10:502`,
**protocol address 30** (= 400031 minus 400001).

The sequencer currently has **six states**:

```
0  idle — waiting for start
1  M1 Pro: run transfer
2  acknowledge M1 Pro
3  conveyor: index
4  Pro 600: pick and place
5  acknowledge Pro 600, cycle complete
```

Other registers worth reading:

| Protocol addr | 4xxxxx | Meaning |
|---|---|---|
| 0 | 400001 | Pro 600 command |
| 1 | 400002 | Pro 600 status |
| 10 | 400011 | M1 Pro command |
| 11 | 400012 | M1 Pro status |
| 20 | 400021 | laser command |
| 21 | 400022 | laser status |
| 30 | 400031 | Step_Mirror |

Status values: `0` idle, `1` busy, `2` done, `99` fault.

### Please read the map from a table, not hardcoded

Two changes to the state numbering are already planned:

1. **Laser station** — adds states for index-to-laser, command laser,
   acknowledge laser, index-to-pick. Six states becomes about nine
2. **Fault handling** — the sequencer does not currently test for
   status 99. Adding it will add states and may renumber again

So don't hardcode `3 == conveyor`. A lookup table you can edit will
save you a rewrite.

`Step_Mirror` is a **mirror**, deliberately. The sequencer's real `Step`
is not exposed, because a Modbus holding register is writable and a
stray write to the live variable would jump the state machine mid-cycle
with two arms in shared space. The mirror is reassigned from `Step`
every scan, so a bad write is overwritten within one scan and cannot
affect anything.

---

## 7. Modbus client notes

Two Python bridges already poll the PLC at roughly 10 Hz each. Yours
would be the third client.

- **Open one connection and hold it.** Connecting and closing per poll
  will exhaust sockets — this is the realistic way a third client
  causes trouble
- 20 Hz read-only polling is fine on top of the existing load
- First run should be with the cell idle and both bridge consoles
  being watched, in case the third connection disturbs them

---

## 8. Still open — belt calibration

Your model predicts ~363 mm for the conveyor's 170-unit move. Before
hunting for a gear ratio that justifies it, note that 363 mm is the
model's **output**, not a measurement. The plan on the cell side:

1. Read the actual units-per-revolution scaling from CCW's motion axis
   configuration. If units are already millimetres, 170 units is
   170 mm and the question dissolves
2. Run five indexes, measure the total with a tape, divide by five
3. Record the pulley pitch diameter and gearbox ratio as documentation
   of what the machine is — not as free parameters to tune until the
   model agrees

If the measurement and the CCW configuration disagree with each other,
that's a real finding about the axis setup and matters more than the
model does.

---

## Quick reference

```bash
# one-time
sudo nmcli connection add type ethernet con-name workcell \
  ifname enp3s0 ipv4.method manual \
  ipv4.addresses 192.168.10.60/24 ipv4.never-default yes
sudo nmcli connection up workcell
sudo ufw status                    # allow 5005/udp if active

# every session
ping 192.168.10.10                 # PLC reachable?
python3 udp_listen.py              # pose stream
```
