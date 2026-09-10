# CLAUDE.md — dobot_cobot_gazebo_twin

Gazebo Harmonic / ROS 2 Jazzy digital twin of a two-robot semiconductor
wafer-handling cell. **ROS 2 Jazzy · gz-sim 8.11.0 · Ubuntu 24.04.**

Deep background: `PROJECT_CONTEXT.md`. Asset inventory and what is safe to
delete: `HANDOVER.md`. Read `PROJECT_CONTEXT.md` §14 before touching layout.

---

## Build and run

Every command needs BOTH source lines. Forgetting the second is the most
common cause of `ros2: command not found` / "package not found".

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash
```

```bash
cd ~/dobot_cobot_gazebo_twin && source /opt/ros/jazzy/setup.bash && colcon build --symlink-install
```

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_bringup cell.launch.py gui:=true
```

Launch arguments (2026-09-04): `gui` (server always headless, the GUI is a
separate process and closing its window shuts everything down),
`gui_nvidia` (GUI on the RTX 4060, default true; false puts the window on the
Intel iGPU), `cameras` (bridge the six camera sensors, default true; they
render only while bridged), `demo` (start `cell_sequencer.py` by itself 8 s
after go_home; `demo_cycles`), `step` (physics step, default 0.001; 0.002 for
a real-time GUI demo only, it moves the final place by 2 mm, see the trap table), `verbose`, `world`. One-command
demo at the exact 1 ms physics: `ros2 launch wafer_cell_bringup cell.launch.py gui:=true cameras:=false demo:=true`.

Verified working end-to-end from a clean `rm -rf build install log` on
2026-09-03: 3 packages build in ~3 s, all 4 controllers reach `active`,
11/11 joints settle on the commanded home pose.

## Architecture — one description, one controller manager

`urdf/cell.urdf` is **GENERATED**. Never hand-edit it. It merges both arms and
the belt into ONE `robot_description` with ONE `ros2_control` block (11 joints)
and ONE `gz_ros2_control` plugin.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup generate_cell_urdf.py
```

Regenerate after changing any robot xacro or any cell pose, then rebuild.
It is reproducible — regenerating without edits gives a byte-identical file.

**Do not split this into three plugins.** It was tried. `gz_ros2_control`
blocks inside `Configure()` waiting for `robot_description` on Gazebo's main
thread, so multiple instances deadlock the sim, and per-instance
`<ros><namespace>` is not honoured (2 of 3 plugins loaded; the second ignored
its namespace). Every robot is bolted to the bench anyway, so one URDF tree is
also the physically honest model.

## Verification tools — use them, do not trust numeric checks alone

This project repeatedly shipped changes that passed every numeric check and
were visually broken (an invisible robot, arms collapsed under gravity, a fork
floating in mid-air).

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup check_extents.py
```

AABB of every visual vs the bench rectangle. Run after moving anything. An
earlier check tested footprint *centres* — all passed while the M1 Pro's base
hung 30 mm off the rear edge.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup capture_view.py out.png /plan_cam
```

Grabs a frame headlessly. Topics: `/cell_cam` (front), `/plan_cam` (top
down), `/detail_yellow_cam`, `/detail_belt_cam` and `/detail_blue_cam` (close-ups
of the pick nest, the belt holder and the place nest for millimetre seating
checks). The plan view exists because a C-shaped part's opening can hide behind
its own back wall in an oblique view.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup solve_home_poses.py
```

Numerical IK on `cell.urdf` for the rest poses and any pick pose; prints joint
values plus the worst limit margin. Its `solve()` is importable for reach checks.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup split_collision_mesh.py in.stl out.stl 8 1
```

Cuts a collision STL into horizontal bands (surface unchanged) so the mesh
collider can cull by height; the towers' and the belt holder's collision meshes are made this way.

---

## Traps — all of these cost real time here

| Trap | Symptom | Fix |
|---|---|---|
| `pkill -f` self-kill | Bash exits 1, no output, even a trailing `true` never runs | The Bash tool passes the script as one argv, so the pattern matches your own shell. Put kills in a SEPARATE call from the relaunch |
| `gz sim` runs as **ruby** and a headless run has NO `server` suffix | `pkill -x gz-sim-server` matches nothing, and `grep "gz sim (server\|gui)$"` misses `gz sim -r -s -v 3 <world>`, so a live headless sim reads as dead. Two stale servers were found this way on 2026-09-03; the next launch's spawners then reported `Controller already loaded` | `ps -eo pid,etimes,args \| grep -E "gz sim\|parameter_bridge\|robot_state_publisher" \| grep -v grep`, kill by PID. Headless children are `gz sim -r -s ...`, GUI-mode children are `gz sim server` and `gz sim gui`: a pattern that matches only one form misses the other (a GUI-mode server from 00:12 survived four cycle tests on 2026-09-04 and answered their action goals and pose queries). `ros2 launch` SIGINT left the server AND the bridges alive repeatedly |
| Joint initialised **at** a limit | Joint silently ignores every command for the whole run | `initial_value` must sit strictly inside; this repo keeps ≥0.05 rad margin |
| Massless links | `FrameAttachedToGraph unable to find unique frame [...]`, model silently fails to spawn | The generator auto-adds placeholder inertia |
| Gravity collapse | Arms sag in the ~14 s spawn→controller window; JTC latches the sagged pose forever | `go_home.py` runs at spawn+7 s |
| PRIME offload env vars | `Failed to create OpenGL context` | Only when the NVIDIA kernel module is not loaded for the running kernel (happened 2026-09-03 after an HWE kernel update; `nvidia-smi` fails, Mesa Intel renders). Fixed 2026-09-04 by installing `linux-modules-nvidia-595-open-<running kernel>` and rebooting. With the module loaded, `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` gives the RTX 4060; without them the default GL is still the Intel iGPU (prime is on-demand). Check `nvidia-smi` first after every kernel update |
| Orphan processes | "Controller already loaded"; stale `/clock` publishers | Kill leftover `parameter_bridge` PIDs from dead runs |
| `robot_description` YAML-parsed | Launch mangles the URDF | `ParameterValue(Command([...]), value_type=str)` |
| ros2 daemon staleness | `topic list` disagrees with `topic hz` | `ros2 daemon stop` |
| A world plugin silently absent | `[Err] SystemLoader ... library does not contain requested plugin` once at start-up; then `/world/.../dynamic_pose/info` has NO publisher and every pose logger returns empty blocks | A regex on `name="..."` also matches `filename="..."`; that renamed the SceneBroadcaster to its library name on 2026-09-04 and cost two hours of false conclusions. After any world edit, `gz topic -i -t /world/wafer_cell/dynamic_pose/info` must list a publisher |
| GUI demo at half speed (solved 2026-09-04) | RTF 0.3–0.5 whenever an arm or the wafer was near a nest, headless too | Not the GPU. ODE's mesh tree culls by triangle bounding box, and the towers' 100 mm-tall wall triangles all overlap any query at any height, so every step tested all 1568. The towers and the belt holder now collide with `meshes/wafer_tower_collision.stl` / `belt_holder_collision.stl`, the same surfaces cut into 8 mm bands by `split_collision_mesh.py`: RTF 0.98 overall at 1 ms headless, seating numbers unchanged. Apply the same tool to any tall mesh that a moving part passes. `step:=0.002` remains a demo-only fallback that moves the final place by 2 mm |

Vendor URDFs shipped real defects that are **fixed on import — do not restore
upstream values**. See the header of each xacro and the two `ATTRIBUTION.md`
files. Notably the M1 Pro `wrist_link` visual carries `origin z=0.08081` while
its collision had `0`; reading Link4's raw mesh extent instead of accounting
for that offset hangs the fork 81 mm below the arm in mid-air.

---

## 🟡 Layout is INTERIM (photo-derived, ±20 mm) — applied 2026-09-03 late evening

The owner reviewed the earlier build and confirmed four things wrong: tower
opening direction, conveyor position, robot base yaw, arm rest poses. On
2026-09-03 the owner then instructed that a **photo-derived interim layout be
applied**. It is in, verified (build, 4 controllers active, `check_extents`,
both captures), and committed. Status now:

| Item | State | Tag |
|---|---|---|
| Tower opening | yellow opens −X (toward M1 Pro), blue opens +X (toward Pro 600) | ✅ direction from photo |
| Nest / conveyor / base positions | from the rectified overhead photo, see `docs/research_2026-09-03/`; carriage centred on the belt band (`BELT_SURFACE_Y`) | 🟡 ±20 mm |
| Conveyor mesh | yawed 180°: motor at the −X rear corner as in the photos | 🟡 |
| Base yaw (both) | **still the old values, never measured** | ⛔ metrology `m1pro_base_yaw`, `pro600_base_yaw` |
| Rest poses | FK-solved by `solve_home_poses.py`, not pendant values | ⛔ metrology `m1pro_home`, `pro600_home` |

**Every pose lives in ONE file: `src/wafer_cell_bringup/scripts/cell_layout.py`.**
The generator, `go_home.py`, `check_extents.py` and `cell.launch.py` import it.
`worlds/wafer_cell.sdf` mirrors the same numbers by hand and `check_extents.py`
exits non-zero if they disagree. Edit `cell_layout.py`, then:

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup solve_home_poses.py
```

paste the solved home back into `cell_layout.HOME`, regenerate the URDF,
rebuild, run `check_extents.py` and both captures.

The reference material the older notes call "lost" is on disk: overhead photos
`docs/reference_photos_2/20260902_114748.heic` / `113823.heic`, the Gemini
render and a 28 s cycle video in `~/Downloads` (paths in
`docs/research_2026-09-03/RESEARCH_REVIEW.md`). Decode HEIC with GdkPixbuf;
`heif-thumbnailer` silently caps at 512 px.

## ✅ Owner-approved cycle (2026-09-04, late evening)

The owner watched the cycle in the GUI, reviewed the six-camera recording
(`docs/verification_2026-09-04/cycle_recording_09_04_2026.mp4`) and declared
the simulation correct at commit 5645a1f. What that approval covers: the
belt holder's orientation and centring, the fork's 90° wrist turn and its
entry across the belt from the front, the set-down / release / retreat
hand-off, the ride, the cup pick and the place into the blue nest, and the
Pro 600 colour. It does NOT turn the ⛔ / 🟡 items below into measurements:
base yaws, pendant rest poses and the ±20 mm photo positions are unchanged.
Treat the approved motion sequence as fixed; change geometry only with a
measurement or an owner instruction, and re-record the cycle afterwards.

## Grasp and sequencer (added 2026-09-04)

The wafer is grasped by **gz DetachableJoint** fixed joints, three of them,
emitted into `cell.urdf` by the generator: fork, cup and the belt nest (so the
wafer rides the belt by a joint, not by friction). Attach/detach are
`std_msgs/Empty` on `/wafer/<fork|cup|nest>/<attach|detach>`, bridged in
`cell.launch.py`; the plugin's state comes back on `/wafer/<carrier>/state`.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup cell_sequencer.py
```

Runs one full cycle (parameters `belt_speed`, `dwell_b`, `speed_scale`,
`cycles`; `--dry-run` prints the IK of every waypoint without a sim). Every
waypoint is solved at start-up from `cell_layout.py`. Step names are published
on `/cell/state`; a PLC bridge publishing the same names is the shadow hook.
`record_frames.py <dir> [/cell_cam] [interval]` saves timestamped frames and the
state log for a contact sheet; `make_cycle_video.py <recdir> <out.mp4> [fps]`
composes six such recordings into one step-labelled video (cameras run at
15 Hz).

**Trap: DetachableJoint parent links must survive URDF→SDF.** sdformat merges
every link that hangs off a *fixed* joint into its parent, so `m1pro_fork` and
`pro600_cup` do not exist in the spawned model (the plugin logs
`Link with name m1pro_fork not found in model wafer_cell` and silently never
attaches). `GRASP_LINKS` therefore names `m1pro_wrist_link`, `pro600_link6` and
`belt_carriage`. The same merging is why `check_extents.py` sees the fork under
its own link name only in the URDF, not in the SDF.

**Trap: gz-sim 8.11's DetachableJoint ATTACHES ON START** (`attachRequested{true}`
in its header, verified in source and in the log: three `Attaching entity`
events the moment the wafer spawns). All three carriers weld the wafer where it
lies and every later attach answers `Already attached`, so nothing ever moves
and no error is printed. `go_home.py` and the sequencer's `release_all()`
therefore detach all three at start. Run with `verbose:=4` to see the plugin's
`[Dbg]` lines; `-v 3` hides them. The plugin also attaches the wafer WHEREVER
it is, with no proximity check: an attach sent while the wafer sits in the blue
nest welds it to the fork across the bench and the next move flings it. Only
send attach when the carrier is at the wafer (the fake devices therefore run one
cycle and hold).

**The belt carriage is `meshes/belt_holder.stl` lying PLATE-DOWN, its
180 mm side ALONG the belt, the two 45 mm posts at the belt-axis ends**
(owner, 2026-09-04 late evening, with a picture). A 180 × 70 plate on the
belt, concave 57.5 mm arcs on the posts' inner faces, a ring seat at 43 mm
and a 2 mm lip of radius ≈64 mm. The STL is modelled plate-up, so the xacro
rolls it −90° about X and lifts it 45 mm. **The fork enters ACROSS the belt,
not along it**: during `M1_TO_BELT` the wrist turns the fork 90° so the blade
points toward the rear (+Y), it comes in from the bench front between the two
posts 2 mm above the lip, lowers the wafer to 0.3 mm above the seat,
releases, drops the blade 4 mm and backs out to the front underneath
(`cell_plan.py`: `FORK_AX_BELT`, `APPROACH_BELT`, `M1_SET_DOWN`,
`FORK_DETACH`, `M1_DROP_BLADE`, `NEST_ATTACH`, `M1_RETREAT`). The holder
loads beside the M1 Pro column with its end at the belt's end
(`BELT_A = −0.25`; the photo had −0.14, and from −0.14 the across-belt entry
is out of the M1 Pro's reach). Source: the owner's videos `~/Downloads/How
to move dobot and place wafer on magenta color holder on the belt.mp4`
(2.4 s, 72 frames) and `WhatsApp Video 2026-09-03 at 4.47.55 PM.mp4`.
I got this wrong twice on 2026-09-04 (a drop stand-in, then the holder
turned across the belt): read the videos for the FORK's motion, including
the wrist rotation, before touching the fixture. The C-nest 3MF in
`~/Downloads` is NOT the belt part (its rim is Ø124) and was removed.

**Wafer vs nest geometry (measured off the STLs):** wafer Ø127.0; tower step
wall r = 64 with a 6.5 mm ledge (r 57.5…64) under it; belt holder lip r ≈ 64
over a seat ring. Both fit the wafer with ≈0.5 mm radial clearance. The sim
therefore runs the controllers with 0.001 rad / 0.3 mm goal bands and 3 s
goal_time, settles 0.8 s before every attach or release, stops the cup 2 mm
above the wafer (a joint needs no contact), and gives the wafer a 63.0 mm
COLLISION radius under its 63.5 mm visual so the ~7 mm drop into the holder
lip has 1 mm per side, standing in for the chamfers a real print has.

**Trap: the M1 Pro rest pose parks the fork 26 mm above the yellow nest, and
the blade tip overhangs the fork seat by 30 mm.** A joint-space move from
rest straight to a low approach point sweeps the blade down through the
wafer's rim, and an approach point closer than 93.5 mm (30 mm overhang +
63.5 mm wafer radius) behind the nest centre lands the descending tip on the
rim. Both happened on 2026-09-04: the wafer was tipped 20°, flipped, or shoved
40 mm out of the nest, and every later step inherited the offset (cycles 5–9
all failed at the Pro 600 place). `cell_plan.py` therefore retreats at carry
height first (`back_high`), descends 115 mm behind the nest, slides in 4 mm
under the wafer, then raises the blade 1 mm above the wafer's resting
underside (`engage`) so the wafer physically rests on the tines before the
joint is made. Diagnose pick faults with a streamed pose log (wafer z and
pitch against fork tip x), not with 2 s samples: the 20° tilt is invisible in
the front camera. `/detail_yellow_cam` is the close-up for the pick.

**Trap: a collision body that reaches past the frame the plan steers to.**
The Pro 600 cup's collision cylinder ran 9 mm beyond `pro600_cup_tip`; the
plan stopped the tip 2 mm above the wafer and the collision rammed the wafer
17 mm down through the belt holder before the joint was made, so the wafer
hung 20 mm below the cup and the place drove it into the blue ledge (cycle
11). Any tool collision must end at its tip frame. The cup and the fork now
do; check with the FK table `cell_sequencer.py --dry-run` prints against the
xacro before trusting a new tool.

**Rule: the last stretch of a cup pick or place is 20 mm, straight down.**
A joint-space move of the 6-axis Pro 600 bows sideways mid-path (5 mm over a
120 mm descent, cycle 10) and the nests leave 1 mm radial clearance, so
`cell_plan.py` inserts `near_c` / `near_blue` waypoints 20 mm above the wafer
and descends from there.

**Trap: a free drop onto a position-driven fixture is a lottery.** When
the fork still entered along the belt it could not pass the posts, and the
wafer had to fall 5.5 mm onto the two crescent seats; in 3 of 5 runs it landed ~3° tilted and climbed at ~15 mm/s
until it stood at 23°, welded that way for the ride. Teleported onto the seat,
or dropped level, it was stable; the static yellow tower never misbehaved.
The carriage is position-driven (`JointPositionReset`), so its contacts are
kinematic. ODE `max_vel` / `min_depth` tags do nothing here: DART solves the
contacts itself, and one lucky run misled me. With the fork entering across
the belt the wafer is set down 0.3 mm above the seat and the problem is gone.

**Trap: the conveyor mesh's bounding-box centre is not the belt.** The box
includes the motor housing on the rear side, so a carriage placed at
`BELT_XYZ` y rode 30 mm toward the rear of the running surface (owner's GUI
screenshot, 2026-09-04). A cross-section of `dobot_conveyor.stl` at
mid-length puts the belt band at world y 0.045..0.165, hence
`BELT_SURFACE_Y = 0.105` and `CARRIAGE_XYZ` in `cell_layout.py`; the plan,
the solver helper and both belt cameras use it, `BELT_XYZ` only anchors the
mesh. Check any fixture against a section of the mesh it rides on, not its
bounding box.

**Both nests open toward −X** (owner, 2026-09-04). The 2026-09-02 photograph
shows the blue one opening +X; the owner's instruction wins, noted in
`cell_layout.py`.

**M1 Pro base yaw is −90° by inference, not measurement.** With yaw 0 the fork
cannot back away along −X from the belt holder (the video shows it doing so);
with the carriage facing the bench front every waypoint is reachable, matching
the render and the parallax-corrected link positions. Still ⛔ metrology.

## Digital Shadow package (added 2026-09-04)

`src/wafer_cell_shadow/`: `m1pro_bridge.py` (Dobot port 30004, 1440-byte
`RealTimeData`), `pro600_bridge.py` (pymycobot `ElephantRobot`),
`plc_bridge.py` (**Modbus TCP, read-only**, since 2026-09-10), `shadow_driver.py`
(time-replay driver), `task_shadow.py` (Level 1 driver), `fake_plc.py`
(Modbus server stand-in for the Micro850), `launch/shadow.launch.py`
(`source:=fake|real`, `record:=true`, `bridges:=false` for bag replay,
`level1:=true fake_plc:=true` for the Level 1 stack offline). Real-mode client
libraries live in `~/venvs/wafer_shadow` (system-site-packages venv, pymodbus
pinned 3.6.9 like the bench); the bridges add it to `sys.path` only in real
mode. The cycle table both the sequencer and the fake devices use is
`scripts/cell_plan.py` in the bringup package.

**The bench is known (2026-09-10, from the PLC programmer's files, see
`docs/shadow_bringup/`):** 192.168.10.x, no gateway; PLC .10 is a Modbus TCP
server (holding 0/1 Pro 600 cmd/status, 10/11 M1 Pro cmd/status, coils 0/1
vacuum on/blow; status 0 idle 1 busy 2 done 99 fault); Pro 600 .20:5001; M1 Pro
.40 on LAN2, ports 29999/30003, single controlling session. The PLC runs a
six-state sequencer and the two bridge scripts answer it; `Step`, `Run_Cmd` and
`Move_Done` are internal, so the belt phase reads as all-zero registers and
`plc_bridge.py` infers it from order. Level 1 = follow the PLC alone; Level 2
(joint feedback) waits on a bench test of whether a second read-only session
disturbs the bridges. Verified offline against `fake_plc.py` on 2026-09-10.

## Working style the owner has asked for

- **Verify before showing.** Standing instruction. Capture and check, then report.
- State provenance: ✅ VERIFIED / 🟡 ASSUMED / ⛔ UNKNOWN. Never state a negative
  as settled fact — `PROJECT_CONTEXT.md` §13 logs 9 times Revision A did and
  caused rework.
- To find a vendor model, enumerate the vendor's GitHub account. Searching by
  model name missed BOTH official models and cost a rebuild from GPLv2 sources.
