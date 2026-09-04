# wafer_cell_shadow — Digital Shadow (real → sim, one way)

Three bridges, one per real device, each with a **fake source** so the whole
chain runs on this laptop with no hardware, plus a driver that makes the Gazebo
cell follow whatever the bridges publish, and a recorder.

```
real M1 Pro  ──30004 feedback──► m1pro_bridge  ─┐
real Pro 600 ──pymycobot socket► pro600_bridge ─┼─► /shadow/*  ─► shadow_driver ─► sim controllers + grasp
real Micro850──pycomm3 EtherNet/IP► plc_bridge ─┘        │
                                                 ros2 bag record  (record:=true)  ─► replay later with bridges:=false
```

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
| pycomm3 `LogixDriver` auto-detects Micro800 | ✅ from its README |
| Fake devices reproduce the sim cycle end to end | ✅ tested 2026-09-04 |
| Robot IPs, Pro 600 port (5001), PLC tag names | ⛔ UNKNOWN — placeholders in `config/shadow.yaml` |
| Joint signs and zeros for both arms; whether the M1 Pro reports Z in mm | ⛔ UNKNOWN — one single-joint jog per axis settles each |
| Belt position | dead-reckoned from `belt_run` × `belt_speed`, sign from `belt_reverse` (stepper DIR tag, if exposed), reset to A at `CYCLE_DONE`: the real belt has no sensor |
| Grasp timing | the sim arm trails the real one by ~one trajectory horizon; the driver applies grasp events after `event_delay` (0.35 s) so the sim fork has arrived |
| Grasp events with a real PLC that has no step tag | needs inference from belt/vacuum edges — not written |

## Real mode prerequisites

* Wired Ethernet to the bench LAN (`eno1` is down on this laptop; Dobot's
  default is 192.168.1.6).
* The venv: `python3 -m venv --system-site-packages ~/venvs/wafer_shadow && ~/venvs/wafer_shadow/bin/pip install pymycobot pycomm3`
  (the bridges add its site-packages to `sys.path` in real mode; set
  `SHADOW_VENV` if it lives elsewhere).
* Fill `config/shadow.yaml`.

## Mapping conventions

M1 Pro feedback arrives in Dobot label order `J1 J2 J3 J4` = shoulder, elbow,
Z, wrist, degrees and (assumed) millimetres; the sim chain is
`[z_lift, shoulder, elbow, wrist]`. `sign` and `offset` parameters per axis.
Pro 600 `get_angles()` is degrees J1–J6. The fake sources apply the inverse
mapping, so the same code path is exercised without hardware.
