# wafer_cell_shadow — Digital Shadow (real → sim, one way)

Three bridges, one per real device, each with a **fake source** so the whole
chain runs on this laptop with no hardware, plus two drivers that make the
Gazebo cell follow whatever the bridges publish, and a recorder.

```
real M1 Pro  ──30004 feedback──────► m1pro_bridge  ─┐
real Pro 600 ──pymycobot socket────► pro600_bridge ─┼─► /shadow/*  ─► shadow_driver (time replay, Level 2)
real Micro850──Modbus TCP, read-only► plc_bridge ──┘        │        task_shadow   (PLC phases,  Level 1)
                                                    ros2 bag record  (record:=true)  ─► replay with bridges:=false
fake_plc.py  ──Modbus TCP server, the cell's six-state sequencer──► plc_bridge  (no bench needed)
```

## Level 1: follow the PLC alone (the first milestone)

The bench PLC is a Modbus TCP server and already publishes the whole cell
state: holding registers 0/1 (Pro 600 command/status), 10/11 (M1 Pro
command/status) and coils 0/1 (vacuum on / blow-off); status 0 idle, 1 busy,
2 done, 99 fault. `plc_bridge.py` is a third, **read-only** client of those six
values and derives the PLC's six sequencer states from them; `task_shadow.py`
plays the matching stretch of `cell_plan.STEPS` for each state. Nothing on
the bench is written to, and no robot is touched.

```bash
# terminal 1: the cell
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_bringup cell.launch.py
# terminal 2: Level 1 against the fake PLC (no hardware)
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_shadow shadow.launch.py level1:=true fake_plc:=true plc_port:=5020
# terminal 2, at the bench instead:
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_shadow shadow.launch.py level1:=true plc_ip:=192.168.10.10 plc_port:=502
```

`fake_plc.py` runs the sequencer verbatim from the cell notes and answers it
the way `Bridge.py` and `m1_bridge.py` do, including the vacuum coils; its
timings are flags (`--m1-job`, `--belt`, `--p6-*`, `--fault-m1-cycle N` to
inject a 99). Port 502 needs root, so the fake defaults to 5020. With
`fake_plc:=true` the reader is pointed at 127.0.0.1 automatically; otherwise
`plc_ip` defaults to the bench PLC, 192.168.10.10.

Two things to know about the derivation:

* **The belt phase is invisible on Modbus.** `Run_Cmd`, `Move_Done` and
  `Step` are internal to the PLC, so during the conveyor index every register
  reads zero - indistinguishable from idle. `plc_bridge.py` calls all-zero
  `BELT_INDEX` when the M1 half has just finished and `IDLE` otherwise. That
  is the one inference in the chain; mapping `Step` to a holding register
  (promote to global + one mapping row) would remove it, and is on the ask
  list.
* **`M1_DONE` / `P6_DONE` are one-scan transients.** The PLC clears the
  command on the scan after it sees status 2, so a 20 Hz reader normally goes
  straight from `*_JOB` to `*_ACK`. Both names exist in case the reader
  catches the window.

`task_shadow.py` gates on the real transitions: it cannot finish a phase
before the cell does, and if the cell is quicker than the simulated segment
it logs that it is lagging rather than hiding it. At `IDLE` it returns the
carriage and puts the wafer back in the pick tower - the bench does both by
hand, so this is a declared stand-in, logged each time.

## Run

```bash
# terminal 1: the cell
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_bringup cell.launch.py
# terminal 2: the shadow with fake devices (no hardware)
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_shadow shadow.launch.py
```

`source:=real` switches every bridge to its device using `config/shadow.yaml`.
The fake devices play one cycle and then hold (`cycles:=N`, `0` loops; looping
only makes sense if someone returns the wafer to the yellow nest, because the
grasp plugin welds the wafer wherever it is, even across the bench).
`record:=true` bags every `/shadow/*` topic into `shadow_bag/` (stop the launch
with Ctrl-C so the recorder writes `metadata.yaml`; a killed recorder leaves
only the `.mcap`, recoverable with `ros2 bag reindex -s mcap shadow_bag`); replay
with `ros2 bag play shadow_bag` plus `shadow.launch.py bridges:=false`. That replay
is the safest first real shadow: nothing can go wrong on the hardware while
you check that the sim follows the recording.

## What is verified and what is not

| Item | Status |
|---|---|
| Dobot feedback packet layout (1440 B, q_actual @432, mode @24, DI @8) | ✅ from `Dobot-Arm/M1Pro-ROS` `commander.h` |
| pymycobot `ElephantRobot(host, port)`, `get_angles()`, `get_coords()`, `get_digital_in()` | ✅ from source; installed in `~/venvs/wafer_shadow` |
| Modbus TCP register map, addresses, status codes | ✅ from the PLC programmer's notes and scripts (`docs/shadow_bringup/`); fake and reader tested against each other 2026-09-10 |
| Fake devices reproduce the sim cycle end to end | ✅ tested 2026-09-04 |
| Bench addresses: PLC 192.168.10.10:502, Pro 600 .20:5001, M1 Pro .40 (LAN2) | ✅ from the bench notes; not yet exercised from this machine |
| Joint signs and zeros for both arms; whether the M1 Pro reports Z in mm | ⛔ UNKNOWN — one single-joint jog per axis settles each |
| Belt position | dead-reckoned from `belt_run` × `belt_speed`; the bench indexes a fixed 170 units at velocity 20 one way only and the carriage comes back by hand, so `belt_reverse` is always False and the return is a stand-in |
| Grasp timing | the sim arm trails the real one by ~one trajectory horizon; the driver applies grasp events after `event_delay` (0.35 s) so the sim fork has arrived |
| Cell phase without a `Step` register | derived from the four command/status registers; only the belt phase is inferred (see Level 1) |
| `M1_SET_DOWN` / `M1_DROP_BLADE` steps | a sim stand-in for the wafer hand-off into the belt holder (see CLAUDE.md); a real PLC has no such signals, the driver treats them as holder attach/detach |

## Real mode prerequisites

* Wired Ethernet to the bench switch (a MokerLink POE-G242GS; its mode slider
  must be on Default, not VLAN) with an address on 192.168.10.x - .5 is the
  cell laptop, .10 the PLC, .20 the Pro 600, .40 the M1 Pro. No gateway.
* The venv: `python3 -m venv --system-site-packages ~/venvs/wafer_shadow && ~/venvs/wafer_shadow/bin/pip install pymycobot "pymodbus==3.6.9"`
  (3.6.9 is the bench pin; the pymodbus API changed across 3.x)
  (the bridges add its site-packages to `sys.path` in real mode; set
  `SHADOW_VENV` if it lives elsewhere).
* Fill `config/shadow.yaml`.

## Mapping conventions

M1 Pro feedback arrives in Dobot label order `J1 J2 J3 J4` = shoulder, elbow,
Z, wrist, degrees and (assumed) millimetres; the sim chain is
`[z_lift, shoulder, elbow, wrist]`. `sign` and `offset` parameters per axis.
Pro 600 `get_angles()` is degrees J1–J6. The fake sources apply the inverse
mapping, so the same code path is exercised without hardware.
