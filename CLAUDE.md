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

---

## Traps — all of these cost real time here

| Trap | Symptom | Fix |
|---|---|---|
| `pkill -f` self-kill | Bash exits 1, no output, even a trailing `true` never runs | The Bash tool passes the script as one argv, so the pattern matches your own shell. Put kills in a SEPARATE call from the relaunch |
| `gz sim` runs as **ruby** | `pkill -x gz-sim-server` / `pgrep -x gz-sim-gui` match nothing, so a live sim reads as dead | `ps -eo pid,etimes,args \| grep -E "gz sim (server\|gui)$"` |
| Joint initialised **at** a limit | Joint silently ignores every command for the whole run | `initial_value` must sit strictly inside; this repo keeps ≥0.05 rad margin |
| Massless links | `FrameAttachedToGraph unable to find unique frame [...]`, model silently fails to spawn | The generator auto-adds placeholder inertia |
| Gravity collapse | Arms sag in the ~14 s spawn→controller window; JTC latches the sagged pose forever | `go_home.py` runs at spawn+7 s |
| PRIME offload env vars | `Failed to create OpenGL context` | Do not set them |
| Orphan processes | "Controller already loaded"; stale `/clock` publishers | Kill leftover `parameter_bridge` PIDs from dead runs |
| `robot_description` YAML-parsed | Launch mangles the URDF | `ParameterValue(Command([...]), value_type=str)` |
| ros2 daemon staleness | `topic list` disagrees with `topic hz` | `ros2 daemon stop` |

Vendor URDFs shipped real defects that are **fixed on import — do not restore
upstream values**. See the header of each xacro and the two `ATTRIBUTION.md`
files. Notably the M1 Pro `wrist_link` visual carries `origin z=0.08081` while
its collision had `0`; reading Link4's raw mesh extent instead of accounting
for that offset hangs the fork 81 mm below the arm in mid-air.

---

## ⛔ OPEN — layout is confirmed WRONG. Do not guess at it.

The owner reviewed the build on 2026-09-03 and confirmed **all four** of these
are wrong: tower opening direction, conveyor front-to-back position, robot base
yaw, and arm rest poses. **No fix was attempted — by the owner's instruction.**

Two rounds of guessing already failed. The two available sources disagree and
neither is a measurement: a plan-view photograph (sent in chat, **not saved in
this repo**) and a reference render (also sent in chat, **not saved**). Ask the
owner for measurements or for those images before changing any pose.

Full detail, plus what IS settled and must not be re-derived, is in
`PROJECT_CONTEXT.md` §14.

## Working style the owner has asked for

- **Verify before showing.** Standing instruction. Capture and check, then report.
- State provenance: ✅ VERIFIED / 🟡 ASSUMED / ⛔ UNKNOWN. Never state a negative
  as settled fact — `PROJECT_CONTEXT.md` §13 logs 9 times Revision A did and
  caused rework.
- To find a vendor model, enumerate the vendor's GitHub account. Searching by
  model name missed BOTH official models and cost a rebuild from GPLv2 sources.
