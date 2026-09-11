"""Laser engraver step test — motion only, laser never fired.

No M3/M4 and no S word appears anywhere in this file. With $32=1 the
diode only receives power during a commanded move carrying a non-zero
S value, so a G0 rapid cannot fire it.
"""

import serial, time

PORT  = "COM5"
BAUD  = 115200

# travel is X 0-150, Y 0-200 ($130/$131); these stay well inside it
STEPS = [
    ("near origin",   "X10  Y10"),
    ("far X",         "X140 Y10"),
    ("far corner",    "X140 Y190"),
    ("far Y",         "X10  Y190"),
    ("back to start", "X10  Y10"),
]


ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)                    # opening the port toggles DTR and resets the board
ser.reset_input_buffer()         # discard the banner and the homing-required alarm


def send(line, timeout=60):
    """Send a line, wait for ok. Raises on error or alarm."""
    ser.write((line + "\n").encode())
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = ser.readline().decode(errors="ignore").strip()
        if not r or r.startswith("<"):
            continue             # blank, or a status report we didn't ask for
        print(f"    {line.strip()} -> {r}")
        if r == "ok":
            return
        if r.startswith("error") or r.startswith("ALARM"):
            raise RuntimeError(f"{line.strip()}: {r}")
    raise TimeoutError(line.strip())


def status():
    """? is a real-time command — no newline, answers immediately."""
    ser.write(b"?")
    t0 = time.time()
    while time.time() - t0 < 2:
        r = ser.readline().decode(errors="ignore").strip()
        if r.startswith("<"):
            return r
    return "<no reply>"


def state():
    return status().split("|")[0].lstrip("<")


def wait_done(timeout=120):
    """Honest completion.

    'ok' on a G0 only means the line entered the planner buffer, not that
    the machine stopped. G4 P0 is a zero dwell, and GRBL answers it only
    once the buffer has drained -- so its ok IS the completion signal.
    The Idle check afterwards is belt and braces.
    """
    send("G4 P0", timeout=timeout)
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = state()
        if s == "Idle":
            return
        if s.startswith("Alarm"):
            raise RuntimeError("alarm during move")
        time.sleep(0.1)
    raise TimeoutError("never reached Idle")


print("status:", status())

input("\nENTER to home (the machine will move) ")
send("$H", timeout=90)
print("homed:", status())

send("G90")      # absolute positioning
send("G21")      # millimetres
send("F3000")    # feed rate, only matters if you switch G0 to G1

for label, target in STEPS:
    input(f"\nENTER to move -> {label}  (Ctrl+C to stop) ")
    t0 = time.time()
    send(f"G0 {target}")
    wait_done()
    print(f"  arrived in {time.time() - t0:.2f}s  {status()}")

print("\ndone")
ser.close()