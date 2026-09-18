# From Alonso, 2026-09-11

Files the PLC programmer sent for the digital-twin laptop, copied unchanged from
the owner's Downloads:

- `TWIN_LAPTOP_SETUP.md` — put the twin laptop on the cell subnet (192.168.10.60,
  no gateway, `never-default`), the address table, ping checks, receive the
  Pro 600 pose stream.
- `m1_feedback.py` — read-only reader of the M1 Pro's feedback port 30004:
  1440-byte frames, QActual at byte 432, ToolVectorActual at 624, integrity check
  J1 + J2 + J4 == R; read in a tight loop, never sleep on the socket.
- `udp_listen.py` — receiver for the Pro 600 pose broadcast on UDP 5005 (JSON
  `device`, `angles`, `label`; bind 0.0.0.0 because it is a subnet broadcast).
- `watch_reg.py` — Modbus register watcher; knows `Step_Mirror` at 400031 and the
  laser's command/status at 400021/22 (so those exist or are planned on the PLC).

`tools/live_telemetry.py` in this repo is the ROS 2 bridge built on these formats.
