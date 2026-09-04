# Research review — 2026-09-03 (late evening)

Full read of the repository, the reference photography, the Downloads folder,
and the machine itself, done before any further build work toward a **Digital
Shadow** (real → sim, one way). Provenance tags follow `PROJECT_CONTEXT.md` §0:
✅ VERIFIED · 🟡 ASSUMED / ESTIMATED · ⛔ UNKNOWN.

Nothing in the model was changed. No poses were edited, nothing was committed,
no system setting was touched. New files are confined to this directory.

---

## 1. Headline findings

1. **The "lost" reference images are on disk.** ✅ `HANDOVER.md` and
   `PROJECT_CONTEXT.md` §14 say the plan-view photograph and the reference
   render were sent in chat and never saved. Both exist:
   * plan-view photographs of the built cell:
     `docs/reference_photos_2/20260902_114748.heic` (16320 × 9180) and
     `20260902_113823.heic`; front elevation `20260902_114701.heic`
   * the reference render: `~/Downloads/Gemini_Generated_Image_uac9e6uac9e6uac9.png`
     (2026-09-03 19:38). It is an AI-generated concept image, not a measurement.
2. **A full-cycle video of the real cell exists.** ✅
   `~/Downloads/WhatsApp Video 2026-09-03 at 4.47.55 PM.mp4` (28 s, 848 × 478)
   and a background-removed copy `setup_isolated_28s.mp4`. It shows
   place-on-holder → belt run → Pro 600 pick → place in blue nest.
3. **The RTX 4060 is not in use.** ✅ apt auto-installed kernel 7.0.0-30 on
   2026-09-03 10:59 and the machine rebooted into it at 19:10, but the NVIDIA
   595 modules are only installed for 6.17.0-29. `nvidia-smi` fails and
   Gazebo/ogre2 renders on the Intel UHD iGPU (Mesa 25.2.8). This is why
   PRIME-offload variables fail with "Failed to create OpenGL context".
4. **The build works today on this machine, headless, on the iGPU.** ✅
   Fresh launch at 23:12: all four controllers `active` at +30 s, both
   inspection cameras render, `check_extents.py` reports 0 parts off the bench.
   Captures and the log are in this directory.
5. **The overhead photo, rectified with a homography, answers two of the four
   §14 questions and narrows the third.** See §4. Base yaw and rest poses still
   need the pendant and a rule; photographs cannot give them.
6. **The deadline is close.** `PROJECT_CONTEXT.md` puts it at roughly the
   morning of 2026-09-04 Phoenix time. It is now ~23:30 on 09-03.

---

## 2. What was read

| Source | Notes |
|---|---|
| `CLAUDE.md`, `PROJECT_CONTEXT.md` (Rev B) + `.rev-a.bak`, `HANDOVER.md`, `README.md`, `README_additional info.md` | All read in full. README.md still describes the two-manager Phase 1 layout; superseded by `cell.launch.py`. |
| `docs/metrology_spec.html` | 58 parameters extracted from the embedded `const P` array (the page says 61; 58 entries are present). Sections 02–08, tiers, tolerances and methods all read. |
| All three packages: xacros, controller YAMLs, launch files, generator, `go_home.py`, `check_extents.py`, `capture_view.py`, `cell_fk.py`, `dae_to_stl.py`, `conveyor.urdf.xacro`, `wafer.sdf`, `wafer_cell.sdf`, generated `cell.urdf` | Read in full. |
| 54 reference photographs (24 JPG + 30 HEIC) | Viewed as contact sheets; six decoded at full resolution. `heif-thumbnailer` silently caps output at 512 px; `GdkPixbuf` (heif-gdk-pixbuf) decodes the full 16320 px frames. |
| 10 verification PNGs in `docs/` | Viewed. `fixture_stl_check.png` preserves the original STL names: *3 Wafer Holder Yower.stl*, *Wafer Holder Conveyer.stl*, *Scara M1 Pro Wafer Grabber.stl*. |
| `~/dual_arm_ws` | The 2026-09-01 predecessor (Humble/Classic scaffold, placeholder M1 Pro). Historical only. |
| `~/Downloads` | Cycle videos, Gemini render, `Conveyor_Wafer_Holder.3MF` (holder print source), `Dobot+Conveyer.skp/.zip` (SketchUp source of `dobot_conveyor.stl`), the photo zips. |
| Vendor sources (fetched) | `Dobot-Arm/M1Pro-ROS` bringup (`commander.h`), `elephantrobotics/pymycobot` (`elephantrobot.py`), `ottowayi/pycomm3` README. |

---

## 3. This machine, as it is tonight ✅

| Item | Value |
|---|---|
| Host | HP OMEN 16-wf0xxx, i7-13700HX (16C/24T), 15 GiB RAM, 4 GiB swap, 267 GB free on `/`, 551 GB on `/home` |
| OS / kernel | Ubuntu 24.04.4, **running 7.0.0-30-generic**; 6.17.0-29-generic also installed. Secure Boot off. |
| GPU | RTX 4060 Laptop present on PCI but **no kernel module loaded**. Modules exist only under `/lib/modules/6.17.0-29-generic/`. `apt-cache` shows `linux-modules-nvidia-595-open-7.0.0-30-generic` is available. |
| Rendering | Mesa Intel UHD (ADL-S GT1), OpenGL 4.6. Wayland session, `DISPLAY=:0`. Headless camera sensors verified working. GUI on the iGPU not re-tested tonight. |
| ROS 2 | jazzy (413 pkgs), kilted (317), rolling (292) all installed; nothing auto-sourced; `.bashrc` has `jazzy/kilted/rolling` aliases. `gz sim --versions` → 8.11.0 under jazzy. kilted ships gz-sim 9 (vendor 0.2.3). |
| ros2_control | controller-manager 4.45.2, ros2-controllers 4.40.1, diagnostic-updater 4.2.7 (the ABI skew from the README is fixed). `position_controllers` and `forward_command_controller` are installed. |
| gz-sim8 plugins present | `detachable-joint`, `contact`, `sensors`, `camera-video-recorder`, `apply-joint-force`, `joint-position-controller` and the rest of the standard set under `/opt/ros/jazzy/opt/gz_sim_vendor/lib`. |
| Python | 3.12.3 with numpy 1.26, scipy 1.11, PIL 10.2, **opencv 4.6**, matplotlib, PyYAML, lxml. **Not installed:** pymycobot, pycomm3, trimesh, numpy-stl, pillow-heif. `pip`/`venv` work. |
| Tools | ffmpeg 6.1, GraphicsMagick, Blender, MeshLab, Docker 29.5, heif-gdk-pixbuf. |
| Network | Wi-Fi 192.168.0.205/24 only. **Wired `eno1` is DOWN.** Dobot's driver defaults to a robot at 192.168.1.6, so a live link will need the wired port on the bench LAN. |
| Orphans | After `ros2 launch` was sent SIGINT tonight, `robot_state_publisher` and two `parameter_bridge` processes survived and were killed by PID. The trap in `CLAUDE.md` is still live. |

---

## 4. Layout evidence from the photographs

### Method
`20260902_114748.heic` was decoded at full size, the wooden board segmented by
colour, its four edges fitted with RANSAC, and the corners intersected. A
homography onto the known 1524 × 609.6 mm board gives a 1 px = 1 mm plan view
(`plan_rectified_raw.jpg`; `plan_rectified_overlay.jpg` adds the sim's current
AABBs in blue and a 100 mm world grid). Decomposing the homography puts the
phone ≈1.72 m above the board, ≈0.34 m in front of its centre, focal ≈1759 px
(residual 3 × 10⁻⁴), which lets tall objects be corrected for parallax. World
frame as in the SDF: origin at bench centre, +X toward the Pro 600, +Y toward
the rear (top of the plan), z = 0 the board top.

Expected accuracy of positions below: **±20 mm** (corner fit, lens distortion,
parallax model). These are *estimates from a photograph*, not measurements; the
metrology spec's ±1 mm items still stand.

### The four §14 questions

| # | Question | Sim today | Photographic evidence | Tag |
|---|---|---|---|---|
| 1 | Tower opening | both open toward +Y (rear) | **Yellow opens toward −X** (toward the M1 Pro, the fork enters along +X). **Blue opens toward +X** (toward the Pro 600). Unambiguous in the rectified plan and the front elevation `114701`; the Gemini render agrees. | ✅ from photo |
| 2 | Conveyor front-to-back | centreline y = +0.130; mesh 215 mm wide (y +0.023…+0.237) | Rails at y ≈ **+0.07 … +0.20** after parallax correction → centreline ≈ **+0.135**. The centreline is essentially right; what looks wrong is the **mesh width** (real frame ≈ 135–140 mm across the rails) and, more importantly, the **mesh is rotated 180°**: the real stepper motor sits at the **−X end on the rear side**; the sim mesh has it at the +X end on the front. Length ≈ 0.70 m matches (x ≈ −0.36 … +0.35). | 🟡 ±15 mm |
| 3 | Base yaw | M1 Pro 0, Pro 600 π | Not measurable from these photos (parallax on a 0.69 m column is ~40 % of radial distance). Qualitatively the M1 Pro's arm-forward direction faces the front (−Y) / front-centre, not +X. | ⛔ measure |
| 4 | Rest poses | FK-solved targets | In the video the M1 Pro parks with the arm folded over the front-left and the Pro 600 upright over its base. Joint values need the pendant. | ⛔ pendant |

### Positions, sim vs photo

| Object | Sim (world, m) | Photo estimate (world, m) | Note |
|---|---|---|---|
| Yellow nest centre | (−0.500, −0.120) | **(−0.33, −0.17)**, opening −X | 170 mm further toward the bench centre, 50 mm further forward |
| Blue nest centre | (+0.550, −0.120) | **(+0.40, −0.16)**, opening +X | 150 mm further toward centre, 40 mm forward |
| Conveyor extent | x ±0.349, y +0.023…+0.237 | x −0.36…+0.35, y +0.07…+0.20, motor at −X rear | mesh yaw needs +π; mesh too wide |
| Holder at load point A | x = −0.25 | **x ≈ −0.14**, y ≈ +0.14 | holder centre; read from the photo at rest |
| M1 Pro black base plate | plate centre (−0.5525, +0.150), robot (−0.56, +0.15) | plate x −0.68…−0.52, y +0.13…+0.31 → **centre ≈ (−0.60, +0.22)** | board-level feature, small parallax |
| Pro 600 black flange | (+0.620, +0.180) | **≈ (+0.60, +0.21)** | partly occluded by the arm, ±25 mm |
| Bench, legs, shelf heights, fork mount, wafer Ø | as documented | unchanged | settled per §14 |

The nests being 150–170 mm closer to the centre than modelled also changes the
reach picture: M1 Pro base → yellow nest ≈ 0.47 m, well inside the 0.4 m arm +
0.123 m shoulder offset + fork length. The fork blade corridor problem in
`generate_cell_urdf.py` (102.7 mm between belt and tower) largely disappears
because the yellow nest sits *in front of* the belt's −X end, not beside it.

### Cycle timing from the video 🟡

Read off `cycle_video_timeline_1fps.jpg` and a 2 fps strip of the isolated
clip. Handheld camera, so ±1 s; the PLC program is the authority.

| t (s) | Event |
|---|---|
| 0 – 4 | M1 Pro carrying the wafer toward the belt (the yellow-nest pick is before the clip) |
| ≈5 – 6.5 | Fork lowers the wafer onto the magenta holder at the −X end, retracts |
| ≈8.5 | Belt starts |
| ≈14.5 | Belt stops at the +X end. ≈6 s run for ≈0.40–0.45 m ⇒ **≈70 mm/s** |
| ≈18 – 21 | Pro 600 approaches and descends |
| ≈21.5 / 22.5 | Cup contact / lift |
| ≈23 – 26 | Transfer to the blue nest |
| ≈27 | Place. Clip ends at 28.4 s |

**No mid-belt dwell is visible in this recording.** Either it was not yet
programmed on 09-03 or this run was a straight A → C. Worth asking.

---

## 5. State of the simulation (verified tonight)

* Builds in ~3 s; `cell.urdf` regenerates byte-identically (per HANDOVER; not
  re-run tonight).
* One `robot_description`, one `gz_ros2_control` plugin, 11 joints, four
  controllers → all `active` ≈30 s after launch on the iGPU.
* `go_home.py` at spawn + 7 s prevents the gravity-sag latch. Home reached.
* `check_extents.py`: 0 parts resting off the bench; Pro 600 links overhang the
  rear edge in the air by 14–20 mm, which is normal.
* Camera sensors `/cell_cam` and `/plan_cam` bridge and capture.

Not done, and unchanged: grasp (attach/detach), the sequencer, any real-data
link. The wafer is a free rigid body. Small things noticed on the way:

* `cell.urdf` embeds an absolute install path to `cell_controllers.yaml`; the
  repo breaks if moved without regenerating.
* `m1pro_wiggle.py` still targets the old 0.02–0.23 m Z range and the
  pre-cell topic name; `conveyor_controllers.yaml` and both per-robot
  controller YAMLs are unused by `cell.launch.py`.
* `wafer.sdf` header comment is garbled mid-sentence.
* Sim wafer is 1.5 mm thick (real ≈0.7); masses are vendor-light. Both fine
  for position control, as the docs already say.

---

## 6. Digital Shadow on this system

A shadow is the sim following the real cell's state, one way, with no
commands going back. For this cell there are **three independent sources plus
one thing that has no sensor at all**.

### 6.1 Data sources (what was verified)

| Source | Route | Verified from | Gives | Rate |
|---|---|---|---|---|
| Dobot M1 Pro | TCP to the controller: **29999** dashboard, **30003** motion, **30004** real-time feedback. Feedback is a fixed **1440-byte `RealTimeData`** packet with `q_actual[6]`, `tool_vector_actual[6]`, `robot_mode`, `digital_input_bits`. | ✅ `Dobot-Arm/M1Pro-ROS` `bringup/include/bringup/commander.h` | joint angles (Dobot J1–J4 order), TCP pose, mode, DI | streamed by the controller; Dobot documents 8 ms for 30004 🟡 (not verified in that code) |
| myCobot Pro 600 | TCP socket, `pymycobot.ElephantRobot(host, port)`; `get_angles()` → six floats, `get_coords()`, `get_digital_in/out()`. | ✅ `pymycobot/elephantrobot.py` | joint angles, TCP pose, IO (vacuum output) | poll; expect 10–20 Hz 🟡. Port value not in the constructor defaults; Elephant's Pro 600 docs use 5001 🟡 |
| Micro850 PLC | EtherNet/IP via **pycomm3 `LogixDriver`**, which auto-detects Micro800 and disables the unsupported CIP features. | ✅ pycomm3 README | sequence step, belt run/stop output, vacuum solenoid, pressure switch | poll 10–20 Hz 🟡. Needs the **global variable names** from the CCW project ⛔ |
| Belt position | **No sensor exists.** | ✅ owner | must be **dead-reckoned**: belt-run output × calibrated speed (stepper parameters or the ≈70 mm/s video estimate), reset at each stop | — |

### 6.2 Mapping into the sim

* M1 Pro `q_actual` arrives in Dobot label order and in degrees / mm. The sim
  chain is `[z_lift = J3 (mm → m), shoulder = J1, elbow = J2, wrist = J4]`.
  Signs and the Z zero are ⛔ until one single-joint jog is compared.
* Pro 600 `get_angles()` returns degrees J1–J6; the URDF's zero pose and each
  joint's sign versus the pendant is the metrology item
  `pro600_joint_zero_convention` ⛔. Limits are asymmetric; do not assume.
* Wafer: attach to `m1pro_fork_seat` when the PLC reports "placed on fork"
  state (or when the fork is under the wafer and Z rises), and to
  `pro600_cup_tip` when the vacuum solenoid output is on and the pressure
  switch input confirms. `gz-sim8-detachable-joint-system` is installed.
* Controllers: the current `JointTrajectoryController`s can be fed 50–100 ms
  trajectories, but `goal_time` and the 0.5 rad path tolerances will abort on
  a jittery stream. `position_controllers/JointGroupPositionController` is
  installed and is the better fit for a shadow. Keep `update_rate` 200.
* Time: run the sim at RTF ≈ 1 (iGPU is enough headless; verify with the GUI
  once NVIDIA is back). Stamp everything with wall time at the bridge and
  publish to `/clock`-independent topics so bag replay works.

### 6.3 Recommended order (given the deadline)

1. **Tonight, owner (5 min):** restore the GPU — `sudo apt install
   linux-modules-nvidia-595-open-7.0.0-30-generic` then reboot, or pick
   6.17.0-29 in GRUB. Verify with `nvidia-smi` and `glxinfo -B`.
2. **Save the found assets into the repo** (`docs/reference_render_gemini.png`,
   `docs/cycle_video/`) and correct the "not saved" claims in `HANDOVER.md`
   and §14. One commit.
3. **Layout:** the owner decides whether the §4 estimates go in as an interim
   (tagged 🟡 in the SDF header and `generate_cell_urdf.py`) or waits for the
   rule. Applying them is a 10-minute edit + regenerate + `check_extents` +
   both captures. The conveyor yaw flip and the two nest rotations are the
   visible fixes.
4. **Digital Model loop first** (what the deadline actually needs): detachable
   grasp + a sequencer node driven by the §4 timing table. The sequencer's
   inputs are topics, so the bridge nodes below plug in later unchanged.
5. **Shadow, step 1 — recorder, not live:** a `record_cell.py` that opens the
   three sources and writes a rosbag of `JointState` + a `CellState` message
   while the teammate runs cycles. Replay into the sim validates every mapping
   offline with zero risk to hardware. Needs `pymycobot`, `pycomm3` in a venv
   and the wired port.
6. **Shadow, step 2 — live:** the same three bridge nodes publishing in real
   time; sim controllers switched to group-position; belt dead-reckoned from
   the PLC output.
7. **Validation:** 20 real cycles vs 20 shadowed cycles, wafer landing
   positions, report σ. That is the honest fidelity number.

### 6.4 Risks specific to this setup

* Kernel/NVIDIA drift will recur on every HWE kernel update unless the
  `linux-modules-nvidia-595-open-generic-hwe-24.04` meta-package is installed
  (it is, but tracked 6.17 — check after the fix).
* Three ROS distros on one machine: sourcing kilted by accident pulls gz-sim 9
  and breaks the vendored plugin paths.
* The Micro850 tag names, the belt dwell, and the PLC step frequency are the
  three ⛔ that block a faithful sequence; all live with the teammate.
* The SketchUp conveyor mesh is a lookalike (wrong width, motor on the wrong
  end after the yaw fix is checked). Primitives sized from the rectified plan
  would be more honest than the mesh.

---

## 7. Files added by this review

```
docs/research_2026-09-03/
  RESEARCH_REVIEW.md                 this file
  plan_rectified_raw.jpg             overhead photo rectified to 1 px = 1 mm
  plan_rectified_overlay.jpg         + sim AABBs (blue) and 100 mm world grid
  photo_114748_bench_corners.jpg     RANSAC corner fit on the source photo
  cycle_video_timeline_1fps.jpg      28 frames of the real cycle, timestamped
  sim_verify_front_2026-09-03.png    /cell_cam capture from tonight's launch
  sim_verify_plan_2026-09-03.png     /plan_cam capture
  sim_verify_log_2026-09-03.txt      controllers, joint list, check_extents
```

---

## 8. Addendum, 2026-09-04 (after the reboot)

* **GPU restored.** Kernel 7.0.0-31 with `nvidia-driver-595-open` 595.84;
  `nvidia-smi` OK. Default GL is still the Intel iGPU (PRIME on-demand);
  `cell.launch.py` now exports the two PRIME offload variables whenever
  `/proc/driver/nvidia/version` exists. Verified: `gz sim server` and
  `gz sim gui` both on the RTX 4060, controllers active. RTF with GUI ≈ 0.5,
  headless ≈ 0.75 (mesh collisions on every M1 Pro link are the suspect).
* **The belt holder in the repo was the wrong part.** `belt_holder.stl` is a
  180 × 70 × 45 flat bridge; the part on the belt in every photograph and in
  the video is a 53 mm-tall C-nest, whose print source is
  `Conveyor_Wafer_Holder.3MF` (ring base r 29–45, four wall segments, 73.6°
  gaps on the belt axis → 65.6 mm chord for the 58.2 mm blade, a 3 mm ledge at
  r 57.5–60.7 two mm below the rim). The 127 mm wafer rests on the rim.
  Exported as `belt_nest.stl` and used for both visual and collision.
* **M1 Pro yaw −90° inferred.** See `cell_layout.py`. With yaw 0 the withdrawal
  from the belt nest needs the wrist 0.10 m from the shoulder; the elbow limit
  allows 0.15 m.
* **Fork wafer seat moved to 147 mm** from the wrist so the tine tips stop
  30 mm past the wafer centre, inside the nests' free radius; at 115 mm the
  tips sat under the 2 mm ledge ring and could never rise to lift the wafer.
* **Grasp and sequencer implemented.** DetachableJoint × 3, bridged; sequencer
  with IK from the layout, timing from the video; frame recorder. First cycle
  ran end to end in 45 s sim time with correct motions but the plugins could
  not find `m1pro_fork` / `pro600_cup`: sdformat merges fixed-joint children
  into their parents. Fixed by naming the surviving links.
* **Full cycle verified, 2026-09-04 00:43.** On a clean simulator the
  sequencer ran yellow nest → belt nest at A → belt → C → blue nest in ≈45 s
  of sim time; every carrier reported `attached`/`detached`; the wafer's final
  pose was (0.426, −0.166, 0.097), inside the blue nest. Artefacts in
  `cycle_2026-09-04/` (contact sheet, final plan/front, state timeline, log).
* **Two silent traps cost three runs.** (1) gz-sim 8.11's DetachableJoint has
  `attachRequested{true}`: all three carriers welded the wafer at spawn and
  every later attach was "Already attached"; fixed with a release at start-up.
  (2) A GUI-mode Gazebo from the 00:12 test (`gz sim server` / `gz sim gui`,
  which the headless-only cleanup pattern did not match) stayed alive under
  three headless tests and answered their action goals and pose queries. Both
  are in CLAUDE.md now.
* **RTF, corrected.** With the RTX 4060 active and no stale server, the
  mesh-collision model already ran at RTF 0.94 at rest and 0.97 during a
  cycle; the 0.5–0.75 figures earlier in this addendum were measured on the
  iGPU and with a second Gazebo alive. Primitive collisions replaced the
  M1 Pro meshes anyway (cheaper, and the base mesh alone was 25k triangles);
  the after-measurement is in `rtf_2026-09-04.txt`.
* **Digital Shadow skeleton** (`src/wafer_cell_shadow/`): three bridges with
  fake sources, a driver, bag recording; fake-device shadow verified end to
  end in the sim. Real mode blocked on the bench LAN, PLC tag names and joint
  conventions (all ⛔).
* **Recorder → replay path verified.** A bag of the fake devices' `/shadow/*`
  topics (`ros2 bag record` via `record:=true`), replayed into a fresh
  simulator with `bridges:=false`, drove the same cycle: wafer on the fork,
  into the belt nest, along the belt, lifted by the cup, placed in the blue
  nest (`shadow_2026-09-04/bag_replay_frames.jpg`). Two lessons: a recorder
  killed with SIGKILL leaves no `metadata.yaml` (`ros2 bag reindex -s mcap`
  recovers it), and the fake devices must not loop, because the grasp plugin
  welds the wafer wherever it is, even across the bench.
* **Correction from the owner, 2026-09-04:** the belt holder IS
  `belt_holder.stl`, lying plate-down with its posts up (photo
  `reference_photos_4/20260902_121240` shows exactly that); the 3MF C-nest was
  wrong (rim Ø124 < wafer Ø127). Both nests open toward −X per the owner.
  Wafer/nest fit measured off the STLs: tower step wall r 64 over a 6.5 mm
  ledge, holder lip r ≈ 64 over a seat at 43 mm; the Ø127 wafer fits both
  with ≈0.5 mm clearance. The holder's 180 mm side lies ALONG the belt with
  the posts at the belt-axis ends (owner's picture); the wrist turns the
  fork 90° during the transfer and it enters ACROSS the belt from the front
  between the posts, sets the wafer down 0.3 mm above the seat and backs out
  underneath (owner's videos, 2026-09-04). The holder loads beside the
  column (`BELT_A = −0.25`). Consequences: controller
  goal tolerances tightened to 0.0005 rad / 0.3 mm, and
  four close-up cameras added for seating checks. The seating itself needed
  four more fixes, all logged as traps in `CLAUDE.md`: the fork's approach
  point clipped the wafer rim, the cup's collision ran 9 mm past its tip, the
  Pro 600's joint-space descents bowed 5 mm, and the M1 Pro rest pose sits
  right above the pick nest.
* **Third M1 Pro vendor defect (2026-09-04):** the elbow joint's frame is
  rolled −1° and its axis tilted +1°, so the axis is vertical but the wrist
  axis and the fork blade come out rolled 1.000° (FK-measured). It tilted a
  carried wafer 2.2 mm edge to edge, enough to land one edge on a 2 mm lip.
  Fixed in the xacro; documented in ATTRIBUTION.md.
