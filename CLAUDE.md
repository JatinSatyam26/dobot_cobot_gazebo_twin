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

Grabs a frame headlessly. Topics: `/cell_cam` (front) and `/plan_cam` (top
down). The plan view exists because a C-shaped part's opening can hide behind
its own back wall in an oblique view.

```bash
source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run wafer_cell_bringup solve_home_poses.py
```

Numerical IK on `cell.urdf` for the rest poses and any pick pose; prints joint
values plus the worst limit margin. Its `solve()` is importable for reach checks.

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
| Nest / conveyor / base positions | from the rectified overhead photo, see `docs/research_2026-09-03/` | 🟡 ±20 mm |
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
state log for a contact sheet.

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
`[Dbg]` lines; `-v 3` hides them.

**The belt carriage is the magenta C-NEST**, not the flat bridge.
`meshes/belt_nest.stl` is exported from `meshes/Conveyor_Wafer_Holder.3MF`
(the print source); photographs `reference_photos_4/20260902_121240` and the
cycle video show it. The 127 mm wafer rests on its rim 53 mm above the belt.
`belt_holder.stl` (180 × 70 × 45 bridge) is a different part and unused.

**M1 Pro base yaw is −90° by inference, not measurement.** With yaw 0 the fork
cannot withdraw along −X out of the belt nest (the video shows it doing so);
with the carriage facing the bench front every waypoint is reachable, matching
the render and the parallax-corrected link positions. Still ⛔ metrology.

## Working style the owner has asked for

- **Verify before showing.** Standing instruction. Capture and check, then report.
- State provenance: ✅ VERIFIED / 🟡 ASSUMED / ⛔ UNKNOWN. Never state a negative
  as settled fact — `PROJECT_CONTEXT.md` §13 logs 9 times Revision A did and
  caused rework.
- To find a vendor model, enumerate the vendor's GitHub account. Searching by
  model name missed BOTH official models and cost a rebuild from GPLv2 sources.
