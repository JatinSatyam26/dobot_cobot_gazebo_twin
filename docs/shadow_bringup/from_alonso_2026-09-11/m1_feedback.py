#!/usr/bin/env python3
"""M1 Pro real-time feedback reader — port 30004.

    python3 m1_feedback.py          # 20 Hz decimated print
    python3 m1_feedback.py --all    # every frame (fast, ~125 Hz)
    python3 m1_feedback.py --raw    # add ToolVectorActual

Read-only. Does NOT disturb m1_bridge.py, which holds 29999 and 30003.
Never connect to those two ports.

OFFSETS -- verified empirically against five taught waypoints
------------------------------------------------------------
    432   QActual            J1, J2, J3, J4  (+ 2 unused)
    624   ToolVectorActual   X, Y, Z, R      (+ 2 unused)
    192   looks like QTarget          (commanded, jumps immediately)
    768   looks like ToolVectorTarget

Confirmed by two independent checks at every waypoint:
    J3 == Cartesian Z exactly       (the vertical joint IS Z on a SCARA)
    J1 + J2 + J4 == Cartesian R     (rotary joints sum to tool rotation)

UNITS -- the trap
-----------------
    J1, J2, J4  degrees      -> radians for JointState
    J3          MILLIMETRES  -> METRES, it is a PRISMATIC joint

Converting J3 as an angle gives an arm that looks nearly right but
telescopes absurdly. Easy to lose an afternoon to.

DO NOT SLEEP ON THIS SOCKET
---------------------------
The robot streams at roughly 125 Hz. If you sleep between reads the
socket buffer backs up, TCP flow control kicks in, and you get runs of
consecutive frames punctuated by jumps -- motion that appears to
teleport between waypoints. Read EVERY frame in a tight loop and throw
away what you don't need. That is what this file does.
"""

import socket, struct, sys, time

M1_IP     = "192.168.10.40"
PORT      = 30004
PACKET    = 1440
OFF_Q     = 432        # QActual
OFF_TOOL  = 624        # ToolVectorActual
PRINT_HZ  = 20

show_all = "--all" in sys.argv
show_raw = "--raw" in sys.argv


def read_packet(sock):
    buf = b""
    while len(buf) < PACKET:
        chunk = sock.recv(PACKET - len(buf))
        if not chunk:
            raise ConnectionError("feedback port closed")
        buf += chunk
    return buf


def six(buf, off):
    return struct.unpack_from("<6d", buf, off)


def joints(buf):
    """J1, J2, J4 in degrees; J3 in millimetres."""
    q = six(buf, OFF_Q)
    return q[0], q[1], q[2], q[3]


def to_jointstate(j1, j2, j3_mm, j4):
    """Degrees -> radians, millimetres -> metres. This is the conversion
       your ROS 2 node needs. Joint order and signs still have to match
       whatever your URDF declares."""
    from math import radians
    return [radians(j1), radians(j2), j3_mm / 1000.0, radians(j4)]


def valid(buf):
    """Free integrity check: the rotary joints must sum to tool rotation.
       If this fails the frame is torn or the offsets have moved."""
    j1, j2, j3, j4 = joints(buf)
    r = six(buf, OFF_TOOL)[3]
    return abs((j1 + j2 + j4) - r) < 0.01


def main():
    print(f"connecting to {M1_IP}:{PORT} (read-only)")
    sock = socket.create_connection((M1_IP, PORT), timeout=10)
    print("connected — Ctrl+C to stop\n")

    frames = 0
    bad = 0
    t_last = 0.0
    t0 = time.time()
    interval = 0.0 if show_all else 1.0 / PRINT_HZ

    try:
        while True:
            buf = read_packet(sock)          # tight loop, NO sleep
            frames += 1
            if not valid(buf):
                bad += 1

            now = time.time()
            if now - t_last < interval:
                continue                     # decimate by discarding
            t_last = now

            j1, j2, j3, j4 = joints(buf)
            line = (f"{now - t0:8.2f}s  "
                    f"J1{j1:9.3f}  J2{j2:9.3f}  "
                    f"J3{j3:9.3f}mm  J4{j4:9.3f}")
            if show_raw:
                x, y, z, r = six(buf, OFF_TOOL)[:4]
                line += f"   |  X{x:9.3f} Y{y:9.3f} Z{z:9.3f} R{r:9.3f}"
            print(line)

    except KeyboardInterrupt:
        el = time.time() - t0
        print(f"\nstopped — {frames} frames in {el:.1f}s "
              f"({frames / el:.0f} Hz), {bad} failed the sum check")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
