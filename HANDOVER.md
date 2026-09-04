# HANDOVER — asset inventory and provenance

Written 2026-09-03 for a fresh session taking this project over. The point of
this file is to let you **rearrange, delete and re-download freely** without
destroying anything you cannot get back.

Everything below is classified as one of:

* 🔴 **IRREPLACEABLE** — exists nowhere else. Losing it loses the project.
* 🟠 **RE-DOWNLOADABLE** — exact upstream source recorded; can be fetched again.
* 🟢 **REGENERABLE** — produced by a script or a build in this repo.

Total on disk: ~161 MB, of which ~111 MB is reference photography.

---

## 🔴 IRREPLACEABLE — do not delete

| Path | What it is | Why it cannot be recovered |
|---|---|---|
| `docs/reference_photos/` … `_5/` | 54 photos of the real cell, 111 MB | Photographs of the owner's physical bench. Sole source for the layout, the PLC label, the end effectors, the nest colours |
| `src/wafer_cell_bringup/meshes/wafer_tower.stl` | 3D-printed nest, 107.5 × 135 × 100 mm | Customer print file. Shelf ledges measured from it at z = 0.055 / 0.077 / 0.099 |
| `src/wafer_cell_bringup/meshes/Conveyor_Wafer_Holder.3MF` → `belt_nest.stl` | The magenta belt nest that actually rides the belt: ring base, four 53 mm walls, 74° fork gaps on the belt axis | Customer print source (3MF) and its STL export |
| `src/wafer_cell_bringup/meshes/belt_holder.stl` | 180 × 70 × 45 mm flat bridge ("Wafer Holder Conveyer.stl") | Customer print file, but **not** the part on the belt (photos 2026-09-02); kept, unused |
| `docs/cycle_video/`, `docs/reference_render_gemini_2026-09-03.png` | 28 s cycle video (phone + isolated), AI concept render | Copied from ~/Downloads on 2026-09-04 |
| `src/wafer_cell_bringup/meshes/m1pro_fork.stl` | M1 Pro passive fork | Customer print file. Blade 3 mm thick, 58.2 wide, 189.5 long; 25 mm boss |
| `PROJECT_CONTEXT.md` | Project brief, Revision B | Contains owner-supplied measurements and the §13 corrections log |
| `docs/metrology_spec.html` | 61-parameter measurement spec | Defines every number still to be measured |
| `README_additional info.md` | The owner's own planning notes | Written by the owner, not by an agent |

### Owner measurements recorded only in prose

These came over chat and exist nowhere but in the docs. Re-derive nothing:

* wafer **5 in = 127.0 mm** diameter
* bench slab **60 × 24 × 1 in**, top surface **39 in** above the floor
* legs **1.5 × 1.5 in**, inset **2 in** from the long edges and **8 in** from the short
* belt is **PLC time-based, open loop, no sensors**; dwell 5–10 s at point B
* PLC label reads **`2080-L60E-24QBB`**

### Reference images and video — found on disk 2026-09-03

Earlier revisions of this file said the plan-view photograph and the reference
render were sent in chat and never saved. Both exist, plus a cycle video:

* plan-view photographs: `docs/reference_photos_2/20260902_114748.heic` (16320 × 9180)
  and `20260902_113823.heic`; front elevation `20260902_114701.heic`
* reference render: `~/Downloads/Gemini_Generated_Image_uac9e6uac9e6uac9.png`
  (AI-generated concept image, not a measurement — copy it into `docs/` if you
  want it under git)
* 28 s cycle video: `~/Downloads/WhatsApp Video 2026-09-03 at 4.47.55 PM.mp4`
  and `setup_isolated_28s.mp4` (background removed)
* print sources: `~/Downloads/Conveyor_Wafer_Holder.3MF`, conveyor SketchUp
  `~/Downloads/Dobot+Conveyer.skp`

Derived from them, and 🔴 worth keeping: `docs/research_2026-09-03/` (the
rectified plan with the sim overlay, the corner fit, the cycle timeline and
the written review).

### Layout source of truth (added 2026-09-03)

`src/wafer_cell_bringup/scripts/cell_layout.py` holds every pose; the SDF
mirrors it and `check_extents.py` asserts agreement. `solve_home_poses.py`
re-solves the rest poses after a layout change. Both are 🟢 regenerable in the
sense that they are code, but the numbers inside `cell_layout.py` carry the
photo-derived layout and are not reproducible without redoing the analysis.

## 🟠 RE-DOWNLOADABLE — exact sources

| Path | Upstream | Licence |
|---|---|---|
| `src/dobot_m1pro_description/meshes/*.STL` + joint origins | `github.com/Dobot-Arm/M1Pro-ROS`, `m1pro_description` | MIT © 2022 Dobot |
| `src/mycobot_pro600_description/meshes/*.dae` + joint origins | `github.com/elephantrobotics/mycobot_ros2`, branch **`fix/mycobot_pro_600_joint_limits`** | BSD-3-Clause |
| `src/wafer_cell_bringup/meshes/dobot_conveyor.stl` | 3D Warehouse (SketchUp), `DT-AC-CB070-02E` lookalike | third-party, unverified |

**Re-download with care.** All three carry local modifications that are
deliberate and are documented in each package's `ATTRIBUTION.md` and in the
xacro headers. Fetching upstream fresh and overwriting will reintroduce:

* M1 Pro — `effort="0" velocity="0"` on joint1; joints 2/3/4 shipped as
  `continuous` with **no limits at all**; `wrist_link` collision missing the
  `z=0.08081` offset its visual has
* Pro 600 — `velocity="0"` on all six joints; **no `<inertial>` anywhere**;
  31 MB mesh collision
* conveyor — mesh is in **metres** (scale 1.0, not 0.001) and 5518 of 11603
  facets had inverted normals, repaired in place

The Pro 600 `.dae` files use COLLADA `<polygons>`, which **ogre2 cannot render**
— the robot was invisible for hours while physics worked perfectly. The `.stl`
siblings were produced by `src/mycobot_pro600_description/scripts/dae_to_stl.py`,
which also bakes in the file's `<unit meter="0.001">`. Keep the script. The
`.dae` originals are kept only as the conversion source and are otherwise unused.

---

## 🟢 REGENERABLE — safe to delete at any time

| Path | Regenerate with |
|---|---|
| `build/`, `install/`, `log/` | `colcon build --symlink-install` (~3 s, verified from scratch) |
| `src/wafer_cell_bringup/urdf/cell.urdf` | `ros2 run wafer_cell_bringup generate_cell_urdf.py` — byte-identical on re-run |
| `docs/cell_layout.png`, `docs/cell_plan.png` | `ros2 run wafer_cell_bringup capture_view.py <out> [/plan_cam]` |
| `src/mycobot_pro600_description/meshes/*.stl` | `scripts/dae_to_stl.py` from the `.dae` originals |
| `**/__pycache__/` | Python |

## Probably disposable — your call

| Path | Note |
|---|---|
| `PROJECT_CONTEXT.md.rev-a.bak` | Revision A. Superseded and known wrong on 9 points; §13 already records what it got wrong. Historical only |
| `docs/metrology_spec.html.bak` | Older spec draft |
| `docs/*_check.png`, `docs/urdf_render.png`, `docs/cell_render.png`, `docs/cell_verified.png` | One-off verification screenshots from earlier sessions. Superseded by `cell_layout.png` / `cell_plan.png` |
| `README.md` | Agent-written status page. Overlaps `PROJECT_CONTEXT.md`; its status table predates the §14 findings and reads more finished than the project is |
| `src/*/launch/m1pro_gazebo.launch.py`, `pro600_gazebo.launch.py` | Single-robot bringups from before the combined cell. Superseded by `cell.launch.py`, kept for isolating one arm |
| `src/wafer_cell_bringup/scripts/m1pro_wiggle.py` | Early joint-motion smoke test |

---

## State of the build

Verified 2026-09-03 from `rm -rf build install log`:

* 3 packages build in ~3 s
* all 4 controllers reach `active` (`joint_state_broadcaster`, two arms, belt)
* **11/11 joints settle exactly on the commanded home pose** — no sag, no latch
* `check_extents.py` reports **0 parts resting off the bench**
* `cell.urdf` regenerates byte-identically

**Added 2026-09-04:** grasp (three DetachableJoint plugins), `cell_sequencer.py`
(full yellow → belt A → B → C → blue cycle, IK from `cell_layout.py`),
`record_frames.py`, the corrected belt nest mesh, M1 Pro yaw −90° (inferred).
**What is NOT done:** the Digital Shadow (real → sim bridges), any measured
yaw or pendant rest pose, the PLC sequence details (dwell, tag names).

## Git

A git repository was initialised on 2026-09-03 with everything in one commit,
purely so that reorganising this folder is reversible. `build/`, `install/`,
`log/` and `__pycache__` are ignored. If you would rather start from your own
history, `rm -rf .git` costs nothing.
