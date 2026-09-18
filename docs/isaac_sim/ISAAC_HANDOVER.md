# HAND-OVER — Phase 2, the same real-to-sim picture in Isaac Sim

Written 2026-09-17, the day Phase 1 was bench-proven and pushed. Read this
first if you are the session (or the person) taking the project into Isaac Sim.
`CLAUDE.md` is still the operating manual for the Gazebo twin; this file is
only about carrying the live picture across to Isaac.

Provenance marks are the project's own: ✅ VERIFIED / 🟡 ASSUMED / ⛔ UNKNOWN.
Never restate a 🟡 as a fact — `PROJECT_CONTEXT.md` §13 logs what that cost.

---

## 1. Where the project stands

**Phase 1 is done.** The TA's definition of real-to-sim, given 2026-09-11, is
joint telemetry of the two arms only: their joint angles travel over the lab
LAN into the simulator, everything else in the cell is a static prop, and the
laptop writes nothing to either robot. That works, on the bench, with both arms
live at once:

| | measured 2026-09-17 |
|---|---|
| M1 Pro tracking error | within 1.9° and 7.6 mm over the full cycle |
| Pro 600 tracking error | within 4.4° over the full cycle |
| M1 Pro feed rate | 123 Hz, zero torn frames, read-only beside the vendor's own control session |
| Pro 600 feed rate | 15–19 Hz while a job runs, silence between jobs |
| HOME agreement before motion | 0.1° / 0.0 mm |

**Phase 2 is: the same thing, in Isaac Sim.** Nothing about the robots, the
network or the mappings changes. What changes is the consumer of one ROS 2
topic pair.

## 2. The interface — the only thing Isaac has to consume

`tools/live_telemetry.py` is the producer. It is **simulator-agnostic**: it is a
plain `rclpy` node that opens the two robot sockets and publishes. It imports
nothing from Gazebo and needs no simulator running.

✅ Verified 2026-09-17 with no simulator on the machine at all: both topics
published at a steady 50.0 Hz off the desk stand-ins.

```
/telemetry/m1pro/joint_states    sensor_msgs/JointState   50 Hz
/telemetry/pro600/joint_states   sensor_msgs/JointState   50 Hz
/telemetry/health                std_msgs/String (JSON)    1 Hz
```

`position` is filled, in **radians** for every revolute joint and **metres** for
the one prismatic joint; `velocity` and `effort` are deliberately empty (the
robots do not give trustworthy derivatives at these rates). Name order is fixed
and matches the URDF:

| topic | `name` field, in order |
|---|---|
| m1pro | `m1pro_z_lift` (prismatic, m), `m1pro_shoulder`, `m1pro_elbow`, `m1pro_wrist` |
| pro600 | `pro600_joint1` … `pro600_joint6` |

`/telemetry/health` carries, per robot: `connected`, `rate_hz`, `age_ms`,
`frames`, `bad`. Use `age_ms` to decide whether to hold the last pose or show a
fault; the Pro 600 going quiet between jobs is **normal**, not a fault.

The Gazebo-specific part of the bridge is one extra publisher per robot,
`Float64MultiArray` on `/<robot>_position_controller/commands`. Isaac does not
need it and should ignore it. **Do not fork the bridge for Isaac.** Subscribe to
the JointState topics and drive Isaac's articulation targets from them.

## 3. The joint mappings — already solved, do not re-derive

Both live in `tools/replay_telemetry.py` as `m1_map()`, `p6_map()` and
`PRO600_MAP`. Import them rather than copying the numbers.

**M1 Pro** ✅ verified against every taught waypoint to 0.1°, then live:

```
m1pro_shoulder = J1
m1pro_elbow    = -J2 + 1.961 deg      (the URDF's elbow zero offset)
m1pro_wrist    = J4 - 17.54 deg
m1pro_z_lift   = (J3 + 24.4 mm) / 1000     J3 arrives in mm
```

**Pro 600** ✅ live-verified 2026-09-17 (it was 🟡 fitted until that run):

```
pro600_jointN = his angle N,  except  joint2 = his + 90 deg
                                      joint4 = his + 90 deg
```

Joint 6's offset is invisible on a round cup, so it is identity by assumption
🟡. His controller frame is the vendor URDF's base frame (agrees to 0.2° and
2 cm). His Cartesian table is the **cup tip** with a tool offset, and the real
tool point sits 31 mm above the model's cup tip: the real cup assembly is about
3 cm longer than the model. That matters the moment Isaac is used for anything
spatial; it does not matter for joint mirroring.

## 4. What to import, and what is not in the URDF

Import `src/wafer_cell_bringup/urdf/cell_telemetry.urdf`. It is **generated** —
never hand-edit it. Regenerate with:

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup generate_cell_urdf.py
```

It is one tree holding both arms plus the belt frame, with no belt carriage, no
wafer and no grasp welds, because none of those belong in a joint-telemetry
picture. Ten movable joints, listed with their limits and their HOME values in
§5. Thirteen meshes, all STL, all referenced as `package://`.

Three things the importer will meet that are Gazebo's, not the robot's, and
that Isaac should drop: a `gz_ros2_control` hardware block inside
`<ros2_control>`, the matching `<gazebo><plugin>` for it, and two
`DetachableJoint` plugin blocks left over from the grasp (they reference a
wafer model that telemetry mode never spawns). They are inert in Isaac. If the
importer complains rather than ignoring them, strip the `<gazebo>` element and
the `<ros2_control>` block into a copy; do not delete them from the generated
file.

**The props are NOT in the URDF.** The towers, the conveyor and the bench are
static models in `src/wafer_cell_bringup/worlds/wafer_cell.sdf`, mirrored by
hand from `cell_layout.py`. Isaac needs them rebuilt or imported separately.
Their poses, in the world frame, bench top at z = 0:

Meshes below live in `src/wafer_cell_bringup/meshes/`.

| prop | pose (x, y, z, roll, pitch, yaw) | mesh |
|---|---|---|
| workbench | slab centred at origin, top at z 0 | box, 60 × 24 × 1 in |
| tower_yellow (pick) | −0.281, −0.230, 0.005, 1.5708, 0, 3.14159 | `wafer_tower.stl` |
| tower_blue (place) | 0.407, −0.230, 0.005, 1.5708, 0, 3.14159 | `wafer_tower.stl` |
| conveyor_frame | 0.30407, 0.210, 0.02665, 1.5708, 0, 3.14159 | `dobot_conveyor.stl` |
| pro600_plate | 0.600, 0.124, 0.004 | box |
| M1 Pro mount | −0.609, 0.204, 0.0, yaw −90° | in the URDF |
| Pro 600 mount | 0.600, 0.124, 0.008, yaw −92.5° | in the URDF |

The conveyor mesh's pose is **anchor + the STL's own origin offset** (+0.28407
along, +0.019 across). That trap cost a whole demo once: the belt moved and the
grey mesh stayed behind. The running belt surface is at y = 0.161, which is
30 mm in front of the mesh's bounding-box centre because the box includes the
motor housing.

## 5. Joint table — limits and HOME

HOME is not a chosen rest pose. It is the real robots' HOME through the
mappings above, and matching it is the acceptance gate in §7.

| joint | type | lower | upper | HOME |
|---|---|---|---|---|
| `m1pro_z_lift` | prismatic (m) | 0.0000 | 0.2500 | 0.1815 |
| `m1pro_shoulder` | revolute | −1.4835 | 1.4835 | −0.5238 |
| `m1pro_elbow` | revolute | −2.3562 | 2.3562 | −1.2782 |
| `m1pro_wrist` | revolute | −6.2832 | 6.2832 | 0.7821 |
| `pro600_joint1` | revolute | −3.1400 | 3.1416 | −1.4187 |
| `pro600_joint2` | revolute | −4.7123 | 1.5708 | −0.2167 |
| `pro600_joint3` | revolute | −2.6179 | 2.6179 | 2.2732 |
| `pro600_joint4` | revolute | −4.5378 | 1.3962 | −0.4909 |
| `pro600_joint5` | revolute | −2.9321 | 2.9321 | −1.5662 |
| `pro600_joint6` | revolute | −3.0368 | 3.0368 | −0.0368 |

A joint initialised exactly **at** a limit silently ignores every command for a
whole run. That cost real time here. Keep the ≥ 0.05 rad margin this repo keeps.

## 6. Working without the bench

You do not need the lab to develop the Isaac side. `tools/fake_robots.py`
replays the 2026-09-11 recordings **in the robots' own wire formats** — a TCP
server on port 30004 serving 1440-byte frames at 125 Hz, and UDP JSON packets —
so the real bridge runs unmodified against it:

```bash
tools/fake_robots.py --m1 First_test_withonly_M1Pro_sequence_onmyterminal/m1_feedback_20260911_144727.md --pro600 First_test_withonly_Pro600_sequence_onmyterminal/First_test_withonly_Pro600_sequence_onmyterminal.md --loop
```

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && tools/live_telemetry.py --m1-ip 127.0.0.1 --no-park
```

Both source lines are not optional; forgetting the second is the most common
cause of "package not found" in this repo. `fake_robots.py` is plain Python and
needs neither.

That pair was the ✅ verification in §2. `tools/replay_telemetry.py` is the
simpler alternative: it reads the same recordings and publishes the same
JointState topics with no sockets at all.

⛔ **No rosbag of a live cycle exists yet.** The recordings are text logs from
the bench, which is why the stand-ins parse text. A bag taken during the next
live run would be the cleanest desk-side source for Isaac work, and it is
worth asking for before the hardware is next available.

## 7. Acceptance test for Phase 2

The same gate Phase 1 passed, in the same order. Do not skip the HOME step; it
is what catches a wrong mapping before anything moves.

1. Laptop on the switch, `tools/bench_check.sh` reports PRE-FLIGHT OK.
2. Isaac loaded with the telemetry scene, both arms at HOME per §5.
3. Bridge up. Both robots physically at HOME → **both Isaac arms at HOME**.
   Nothing proceeds until this passes.
4. The cell runs its cycle: M1 Pro first, then the Pro 600. Isaac mirrors both.
5. Compare against the numbers in §1.

**The cheapest correctness check in the whole phase:** run Gazebo and Isaac at
the same time off the one bridge. Both are subscribers to the same topics, so
they get bit-identical inputs, and any divergence between the two windows is an
Isaac-side import or drive problem, not a mapping or a network problem. Do this
before trusting any Isaac number.

## 8. Network, unchanged from Phase 1

192.168.10.x, no gateway. Laptop **.60**, M1 Pro **.40** (LAN2, feedback port
**30004**, read-only, accepts a second client), PLC .10, Pro 600 **.20** port
5001, the PLC programmer's laptop **.5**, .50 reserved for a laser device
server. The Pro 600's own socket is **single-client**: his bridge holds it and
broadcasts poses as JSON to UDP **5005**. Never open port 5001 while his bridge
runs. `--pro600-direct <ip>` is the fallback for when it is off.

**`ufw` is active on this laptop and drops inbound UDP.** The M1's TCP stream is
unaffected, so the symptom is "pro600: no data" while the M1 works perfectly.
The rule, which the owner runs:

```bash
sudo ufw allow from 192.168.10.0/24 to any port 5005 proto udp
```

## 9. Machine and Isaac-side unknowns

⛔ Isaac Sim is **not installed** on this machine as of 2026-09-17. Nothing
about its version, its ROS 2 bridge or its Jazzy compatibility has been tested
here, and this file deliberately asserts none of it. Confirm against NVIDIA's
current documentation before planning around it.

🟡 The GPU is an **RTX 4060 Laptop with 8 GB of VRAM**, driver 595.84, on
Ubuntu 24.04. That is at the low end for Isaac Sim. Expect to check VRAM
headroom early rather than after building a scene.

One hardware trap already in this project's history: after an HWE kernel
update the NVIDIA module was missing for the running kernel and everything
silently rendered on the Intel iGPU. Run `nvidia-smi` first after every kernel
update.

## 10. Inherited open items

None of these block Phase 2. They matter the moment Isaac is used for anything
beyond mirroring joint angles.

- **Absolute layout is 🟡, relative layout is ✅.** The cell is placed from the
  PLC programmer's taught poses, which fix everything rigidly *relative to the
  M1's J1 axis*. The measurement sheet in `docs/measurement_2026-09-11/` exists
  to settle the absolute numbers with a tape measure and is still unfilled.
- **A ~6 mm height disagreement** between the carrier and the towers: both
  robots' taught heights say the carrier's wafer sits ~5 mm lower relative to
  the towers than the meshes put it. Which mesh is wrong is ⛔ unknown.
- **The real Pro 600 cup is ~3 cm longer** than the model (§3).
- **The Level 1 PLC stack is parked**, not deleted: `src/wafer_cell_shadow/`
  follows the PLC's Modbus registers and was verified offline against a fake
  PLC. `Step_Mirror` is register 400031; 400021/22 belong to the laser.
- **Base yaws remain inferred, not measured**: M1 Pro −90° by inference,
  Pro 600 −92.5° fitted to the taught poses.

## 11. File map

| Path | What |
|---|---|
| `tools/live_telemetry.py` | the producer — both robots, read-only, 50 Hz out |
| `tools/replay_telemetry.py` | the mappings (`m1_map`, `p6_map`, `PRO600_MAP`) and a socket-free replay |
| `tools/fake_robots.py` | desk stand-ins in the robots' wire formats |
| `tools/bench_check.sh` | pre-flight: link, addresses, pings, a 5 s broadcast listen |
| `tools/stop_sim.sh` | kills a run by PID (never `pkill -f` here, see `CLAUDE.md`) |
| `src/wafer_cell_bringup/urdf/cell_telemetry.urdf` | the scene to import, generated |
| `src/wafer_cell_bringup/worlds/wafer_cell.sdf` | the props, mirrored by hand from `cell_layout.py` |
| `src/wafer_cell_bringup/scripts/cell_layout.py` | every pose in the cell, one file |
| `docs/shadow_bringup/REAL_TO_SIM_RUNBOOK.md` | the owner's three-terminal run-book |
| `docs/shadow_bringup/from_alonso_2026-09-11/` | the PLC programmer's own scripts and setup guide |
| `First_test_withonly_*_onmyterminal/` | 🔴 the bench recordings both stand-ins replay |
| `docs/measurement_2026-09-11/` | the unfilled measurement sheet and its figures |

## 12. First hour, concretely

1. Read §2 and §3. They are the whole interface.
2. Run the two commands in §6 and `ros2 topic echo` both JointState topics.
   You now have the real data stream on your desk, no lab needed.
3. Import `cell_telemetry.urdf` into Isaac; get both arms standing at the HOME
   values in §5 with nothing subscribed yet.
4. Write the subscriber: JointState in, articulation targets out, by joint
   **name** and never by index.
5. Run Gazebo and Isaac side by side off the one bridge (§7) and watch for
   divergence.
6. Only then book bench time.
