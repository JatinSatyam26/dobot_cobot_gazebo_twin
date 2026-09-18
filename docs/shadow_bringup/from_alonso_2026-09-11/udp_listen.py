#!/usr/bin/env python3
"""Listen for pose broadcasts on UDP 5005.

    py udp_listen.py            # print every packet
    py udp_listen.py -q         # one line per second, rate only

Runs unchanged on either laptop. Bind is 0.0.0.0 on purpose: broadcast
packets are addressed to 192.168.10.255, and a socket bound to a specific
interface address may not receive them.
"""

import socket, sys, json, time

PORT = 5005
quiet = "-q" in sys.argv

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", PORT))
s.settimeout(1.0)

print(f"listening on UDP {PORT} — Ctrl+C to stop\n")

count = 0
window = 0
t_window = time.time()
t_prev = None

try:
    while True:
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            if not quiet:
                print("  ... no packets")
            continue

        count += 1
        window += 1
        now = time.time()

        if not quiet:
            gap = "" if t_prev is None else f"  (+{(now - t_prev) * 1000:5.0f} ms)"
            try:
                p = json.loads(data)
                angles = " ".join(f"{a:8.3f}" for a in p.get("angles", []))
                print(f"{p.get('device','?'):8} {angles}  {p.get('label','')}{gap}")
            except Exception:
                print(f"raw from {addr[0]}: {data[:120]}{gap}")
        t_prev = now

        if now - t_window >= 1.0:
            print(f"    -- {window} packets/s, {count} total, from {addr[0]}")
            window = 0
            t_window = now

except KeyboardInterrupt:
    print(f"\nstopped, {count} packets")
finally:
    s.close()
