# dobot_cobot_gazebo_twin

**Real-to-Sim Digital Model of a Two-Robot Semiconductor Wafer-Handling Cell**

**Project name:** `dobot_cobot_gazebo_twin`
**Workspace root:** `~/dobot_cobot_gazebo_twin`
**Owner:** Jatin Satyam
**Revision:** B — 2026-09-02, rewritten after photographic survey of the built cell
**Deadline:** ⚠️ **CONFIRM AND FIX THE EXACT TIMESTAMP.** Owner stated ~40 hours
remaining on the afternoon of 2026-09-02, i.e. roughly **2026-09-04, morning,
Phoenix time**. Revision A said "24 hours from 2026-09-01 22:00", which was
already stale and caused a planning decision to be made against a deadline that
had passed.

> **Naming note for ROS 2:** every package inside `src/` stays lowercase with
> underscores. `ament` rejects capitals in package names at build time.

---

## 0. HOW TO READ THIS FILE

Revision A of this document contained several confident, wrong statements that
were taken at face value and caused real rework — including building an entire
robot model from scratch when an official one existed. To stop that recurring,
**every factual claim below carries a provenance tag**:

| Tag | Meaning |
|---|---|
| ✅ **VERIFIED** | Confirmed this session by running it, measuring it, or reading it off hardware/a vendor file. Trust it. |
| 🟡 **ASSUMED** | Reasonable inference not yet confirmed. Check before relying on it. |
| ⛔ **UNKNOWN** | Genuinely not established. Do not guess — measure or look it up. |

### Three rules that follow from Revision A's failures

1. **Never state a negative as settled fact.** Revision A said "no public ROS 2
   URDF exists for the M1 Pro" and "no Pro 600 on any branch". **Both were
   wrong.** A negative claim is only ever ⛔ UNKNOWN. Absence of evidence found
   in ten minutes is not evidence of absence.

2. **To find a vendor model, enumerate the vendor's account — do not search
   names.** Both misses had the same cause. The Pro 600 lives on a branch named
   for a bugfix (`fix/mycobot_pro_600_joint_limits`), not a ROS distro. The
   M1 Pro lives under `Dobot-Arm/`, an account whose `/orgs/` API endpoint 404s
   and only resolves via `/users/`. Name-matching found neither; listing the
   account's repos found both immediately.

3. **Photographs beat prose.** Nearly every correction in Revision B came from
   looking at `docs/reference_photos*/`, not from reasoning. When something in
   this file disagrees with a photograph, the photograph wins.

---

## THE GOLDEN RULE

> **Make the impossible possible. Build the digital model in the time remaining.**

Unchanged and still correct. Every scope decision gets measured against it. When
in doubt: **a working end-to-end simulation beats a beautiful half-finished
one.** Ship the loop. Polish later.

---

## 1. What the physical cell is ✅ VERIFIED (photographs, 2026-09-02)

All three stations are bolted to **one wooden butcher-block board**, which rests
on a grey height-adjustable lab table. **The board — not the lab table — is the
cell's rigid body**, and the metrology datum belongs on it.

```
Yellow nest  →  [M1 Pro fork lifts wafer]  →  places on magenta holder riding the belt
             →  [belt runs to Point B, dwells 5–10 s]
             →  [belt runs to Point C]
             →  [Pro 600 suction cup lifts wafer]  →  places in blue nest
```

### Hardware inventory

| Item | Details | Tag |
|---|---|---|
| **Dobot M1 Pro** | SCARA. Black base bolted flat to the board through four corner bolts, column vertical. | ✅ |
| **M1 Pro end effector** | **Passive blue 3D-printed two-tine fork.** Slot runs most of the blade length; tips chamfered; thin flat section; two thumbscrews to the wrist. **NO vacuum port, no tube — the wafer rests on the tines by gravity alone.** | ✅ |
| **myCobot Pro 600** | Elephant Robotics, 6 DoF, AC100–240 V. Base bolted flat to the board. | ✅ |
| **Pro 600 end effector** | Flange adapter disc → black L-bracket → threaded stem → collar → **blue single-bellows suction cup**. Cup sits **well off the flange rotation axis**. | ✅ |
| **Conveyor** | **Dobot Mini Conveyor Belt, model `DT-AC-CB070-02E`.** Aluminium extrusion frame, adjustable feet both ends. | ✅ |
| **Conveyor drive** | **Stepper motor** coupled directly to one end roller, run from a DIP-switch stepper driver. No encoder, no gearbox. | ✅ |
| **Wafer** | Real silicon wafer: mirror finish, square die-scribe grid, "DAMAGED" marking, and a **primary flat** on one edge (so it is *not* rotationally symmetric). | ✅ |
| **Fixtures ×3** | One family: **stepped semicircular nests** with concentric terraces and an **open chord side**. Yellow (M1 Pro end), magenta (rides the belt), blue (Pro 600 end). | ✅ |
| **Wafer orientation** | **Horizontal end to end — never reoriented.** Fork lifts it flat, it travels flat, the cup picks and places it flat, top-down. The Pro 600's extra axes buy reach and approach angle, not a flip. | ✅ |
| **PLC** | **Allen-Bradley Micro850, cat. no. `2080-L60E-24QBB`, EtherNet/IP.** *(Revision A said `2080-LC50-24QBB`; the label in `reference_photos/20260826_191531.jpg` reads L60E.)* | ✅ |
| **Pneumatics** | Vacuum ejector, solenoid valves, regulator, **digital pressure switch**, and a controller labelled 正压/负压 (positive/negative pressure) — so a **blow-off pulse** likely exists. Serves the Pro 600 only. | ✅ |
| **"Magic Box"** | 24 V I/O breakout, screw terminals, numbered channels. | 🟡 |
| **Photoelectric sensors** | **NONE FITTED.** See §6. | ✅ |
| **Safety** | Two E-stops (red mushroom on yellow) on the support table. | ✅ |

---

## 2. Team split

- **Teammate:** hardware — making the real cell work.
- **Jatin:** simulation — the Gazebo model.

Parallel tracks. The sim does not block on hardware, or vice versa.

**Teammate's parallel track, in priority order:** the four fixture **STLs**
(they were 3D-printed, so exact CAD already exists — this replaces a dozen
caliper measurements for free), the ten critical measurements, the **PLC tag
list and ladder export**, and one video of a full cycle.

---

## 3. Software environment ✅ VERIFIED (2026-09-02, by running it)

| Component | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS (Noble), x86_64 |
| GPU | NVIDIA RTX 4060 Laptop |
| ROS 2 | **Jazzy Jalisco** |
| Gazebo | **Harmonic — `gz-sim` 8.11.0** |

### ⚠️ Environment gotchas — all VERIFIED the hard way this session

1. **Only ever source Jazzy.** Three distros are installed (`jazzy`, `kilted`,
   `rolling`). `source /opt/ros/jazzy/setup.bash` — that line and only that line.

2. **Nothing is auto-sourced.** A fresh terminal has no `ros2`. Symptom:
   `ros2: command not found`. That is a *sourcing* failure, not a missing
   install.
   ```bash
   cd ~/dobot_cobot_gazebo_twin && source /opt/ros/jazzy/setup.bash && source install/setup.bash
   ```

3. **apt ABI skew between ros-jazzy packages.** `gz sim` died with exit 127 and
   `libcontroller_manager.so: undefined symbol: ...diagnostic_updater...`.
   Cause: `controller-manager` from a June sync, `diagnostic-updater` from an
   April one. Fixed by upgrading the lagging package. **When a ROS library fails
   with `undefined symbol` naming another ROS package, compare `dpkg -l` build
   dates before suspecting your code.**

4. **`robot_description` must be wrapped.** Launch will try to YAML-parse the
   URDF and die on the first colon. Use
   `ParameterValue(Command([...]), value_type=str)`.

5. **Stale `ros2` daemon hides the entire graph.** If `ros2 topic list` shows
   only `/parameter_events` and `/rosout` while `ros2 topic hz /joint_states`
   reports 200 Hz, run `ros2 daemon stop`.

6. **`gz sim` survives a killed launch.** Orphans keep their own
   `controller_manager` on the DDS graph, so the *next* run's spawners talk to
   the dead sim and fail with "Controller already loaded". Kill with
   `pkill -9 -x gz-sim-server`. **Never `pkill -f "gz sim"`** — the pattern
   matches the cmdline of the shell running it, so the shell kills itself.

7. **Spawner timeouts.** `gz_ros2_control` runs `controller_manager` *inside*
   the sim process, so the service appears long before it can answer. Pass
   `--controller-manager-timeout 60 --service-call-timeout 60
   --switch-timeout 60` and delay the first spawner ~5 s past model spawn.

8. **Never initialise a joint AT its limit.** Setting `initial_value` to exactly
   a joint's lower limit made it report a value a hair *outside* that limit,
   after which it **ignored every command for the whole run** while other joints
   tracked normally. Looks exactly like a dead actuator. Start strictly inside.

9. **`GZ_SIM_RESOURCE_PATH` must point at the share ROOT** (`install/*/share`),
   not the package directory, or `package://` mesh URIs silently resolve to
   nothing and the robot spawns invisible.

10. **Two robots = two named controller managers.** Each robot's gz plugin needs
    `<controller_manager_name>`, and spawners need `-c /<that_name>`. Verified
    working for both arms.

---

## 4. The Humble → Jazzy decision (SETTLED — do not relitigate)

Ubuntu 24.04's native distro is Jazzy; Humble targets 22.04. The TA's "Jazzy has
middleware issues" warning is real but **narrowly scoped to mixed-distro
systems** — Humble and Jazzy nodes cannot talk to each other. This project is
100% Jazzy on one machine, so there is nothing to conflict with.

**The real cost of Jazzy is Gazebo Harmonic instead of Classic.** That is not
theoretical: it is why the community conveyor plugin in §7 cannot be reused.

| Gazebo Classic (Humble) | Gazebo Harmonic (Jazzy) |
|---|---|
| `gazebo_ros` | `ros_gz_sim` |
| `gazebo_ros2_control` | `gz_ros2_control` |
| `ros2 run gazebo_ros spawn_entity.py` | `ros2 run ros_gz_sim create` |
| `gazebo` / `gzserver` | `gz sim` |
| `gazebo::ModelPlugin` (C++ API) | `gz::sim::System` — **a rewrite, not a recompile** |

---

## 5. Model availability — ⚠️ REVISION A WAS WRONG ON EVERY POINT

> Revision A stated that no ROS 2 URDF existed for the M1 Pro and that no
> Pro 600 description existed on any branch. **Both claims were false.** Acting
> on them produced a hand-built M1 Pro model from GPLv2-licensed third-party
> meshes, which has since been deleted. This section is the corrected record.

### Dobot M1 Pro — ✅ OFFICIAL MODEL EXISTS, MIT LICENSED

> **`https://github.com/Dobot-Arm/M1Pro-ROS`** → `m1pro_description`
> **MIT License, © 2022 Dobot.** SolidWorks export: 5 STL meshes **plus real
> inertia tensors**.

**Kinematics ✅ VERIFIED** — the M1 Pro is **NOT** the layout Revision A
described ("2 revolute + 1 prismatic + 1 revolute" with a wrist spline). The
vertical axis is the **first** joint: the whole arm assembly rides a carriage up
the column, and there is no ball-screw spline at the wrist.

```
base → [PRISMATIC Z] → [REV] → [REV] → [REV]
```

Confirmed three ways: Dobot's official URDF, the linear rail visible on the
column in `docs/reference_photos_2/20260902_113748.jpg`, and an independent
third-party CAD conversion.

**Dobot's axis labels do not match chain order.** Map through this table when
mirroring PLC or robot commands — do not assume `joint[2]` is Z:

| Chain position | Our joint | Dobot's label | Range |
|---|---|---|---|
| 1 (prismatic) | `m1pro_z_lift` | **J3** | 0 – 0.25 m |
| 2 (revolute) | `m1pro_shoulder` | **J1** | ±85° |
| 3 (revolute) | `m1pro_elbow` | **J2** | ±135° |
| 4 (revolute) | `m1pro_wrist` | **J4** | ±360° |

Links are 200 mm + 200 mm → 400 mm reach, matching the datasheet.

**Three defects fixed on import** (see `src/dobot_m1pro_description/ATTRIBUTION.md`):
`effort="0" velocity="0"` on the prismatic joint; joints 2/3/4 shipped as
`continuous` — **no limits at all**, so the sim would reach poses the hardware
cannot; and (found 2026-09-04) the elbow frame rolled −1° with the axis tilted
back, which left the wrist axis and the fork blade rolled 1.000°.

### myCobot Pro 600 — ✅ OFFICIAL MODEL EXISTS, BSD LICENSED

> **`https://github.com/elephantrobotics/mycobot_ros2`**
> branch **`fix/mycobot_pro_600_joint_limits`** → `mycobot_description/urdf/mycobot_pro_600/`
> **BSD.** 6 revolute joints, 7 COLLADA meshes (31 MB).

**Verified numerically:** max horizontal reach 627 mm to our flange frame, which
sits 30 mm past link6 → **597 mm to the manufacturer's reference against a
600 mm spec.** Genuine Pro 600, not a rescaled 280.

**Joint limits are strongly asymmetric** — J2 is −270°…+90°, J4 is −260°…+80°.
Do not assume symmetric ranges. That branch exists precisely because earlier
limits were wrong.

**Three defects fixed on import** (see `src/mycobot_pro600_description/ATTRIBUTION.md`):
`velocity="0"` on all six joints; **no `<inertial>` elements anywhere**; and
full 31 MB mesh collision replaced with primitives.

### Conveyor `DT-AC-CB070-02E` — ⛔ NO MODEL EXISTS ANYWHERE (searched 2026-09-02)

Checked: all Dobot GitHub repos, GitHub repo search, community conveyor
projects. **No official URDF, SDF or CAD for this product.** See §7 for what was
found and why it is not usable.

---

## 6. Cell sequence and control ✅ VERIFIED (owner, 2026-09-02)

**The Micro850 PLC is the master.** Both robots and the conveyor are wired to it.

**There are no sensors. Belt motion is purely time-based.** The PLC knows the
M1 Pro has placed the wafer, starts the belt for a fixed duration, stops at
**Point B** for a **5–10 s dwell (duration not yet decided ⛔)**, then runs a
second fixed duration to **Point C**, where the Pro 600 picks.

```
Point A (load) ──run──► Point B (dwell 5–10 s) ──run──► Point C (unload)
```

### What follows from having no sensors

- **Belt speed error IS position error.** In a sensor-triggered cell the sensor
  defines the stop and speed error washes out. Here it does not: 3% speed error
  over 600 mm of travel is ~18 mm of wafer position error.
- **Because the drive is a stepper, speed can be *calculated* rather than timed:**
  `mm_per_step = (π × D_roller) / (steps_per_rev × microsteps)`. Capture roller
  diameter, motor steps/rev, driver DIP switches and PLC step frequency and you
  get a fraction of a percent. Then stopwatch it once as a check — if measured
  and calculated disagree by more than a few percent, **the belt is slipping**,
  which is itself something the model should not hide.
- **A fork changes the handshake.** After releasing, the arm is still *over* the
  belt. Belt start must wait for retraction, not just for release.

---

## 7. Conveyor: where we looked before deciding to build ✅ VERIFIED 2026-09-02

| Source | Finding | Usable? |
|---|---|---|
| Dobot official repos | No conveyor anywhere | ❌ |
| GitHub repo search | No `DT-AC-CB070` model | ❌ |
| `shantanuparabumd/conveyor_belt` | Has meshes + xacro, 22★ | ❌ **No licence declared**, and it is a *generic* conveyor with wrong dimensions |
| `IFRA-Cranfield/IFRA_ConveyorBelt` | Apache-2.0, 51★, maintained — a genuinely good ROS 2 conveyor **behaviour** plugin | ❌ **Gazebo Classic / ROS 2 Humble.** It is a `gazebo::ModelPlugin`; Harmonic needs a `gz::sim::System`. That is a rewrite (see §4). |
| Gazebo Harmonic built-ins | Only `track-controller` / `tracked-vehicle` (tank treads) | ❌ Not applicable |
| Dobot **Magician** conveyor community models | **Different product** from the DT-AC-CB070-02E | ❌ Wrong dimensions |
| RoboDK | Has Dobot + conveyor models natively | ❌ Commercial, and not ROS/Gazebo — wrong target |

**Decision: build it. 🟡** A conveyor is geometrically trivial (frame, belt,
two rollers) and any borrowed model is of a *different* conveyor, so primitives
plus measured dimensions will be **more** accurate than someone else's mesh.
This is the opposite of the robot-arm case, where vendor CAD was irreplaceable.

### Design decision: do not simulate friction-driven conveying 🟡

The real belt is **time-based and open-loop**, and the magenta holder rides it.
So model the holder on a **prismatic joint along the belt axis, position-driven
by the sequencer** — start, dwell, stop — exactly mirroring how the PLC actually
drives it. This is simpler *and* more faithful than simulating belt friction,
which is Layer-3 contact physics that would be wrong regardless (see §9).

Because there is no datasheet to fall back on, **belt width, drive-roller
diameter and belt-surface height have no backup source** and move up the
measurement priority list.

---

## 8. Scope — what ships, what gets cut

### ✅ IN SCOPE
- Both arms from **official vendor models**, spawning in one world
- Wooden board, conveyor, three stepped nests, wafer
- **M1 Pro fork as a passive attach/detach** — lateral insert, then lift
- **Pro 600 cup as attach/detach** — top-down
- Belt as a position-driven prismatic axis: A → B (dwell) → C
- Sequencer node mirroring the PLC state machine
- One clean end-to-end run, plus an explicit **"not modelled" list**

### ❌ OUT OF SCOPE
- Real vacuum or friction physics
- True PLC integration (see §10)
- Isaac Sim — Phase 6, not this deadline
- MoveIt planning — scripted joint trajectories are enough
- Photorealistic materials

**Decision rule:** if a task does not move the end-to-end loop forward, it waits.

---

## 9. What "100% real-to-sim" actually means ⚠️ READ BEFORE PROMISING IT

**100% is not achievable at any schedule.** Fidelity splits into three layers
that behave completely differently:

| Layer | Achievable? |
|---|---|
| **Geometry & kinematics** | ✅ Effectively exact — vendor CAD, bounded only by measurement |
| **Sequence & timing** | ✅ Exact — a deterministic PLC state machine, mirror it 1:1 |
| **Contact physics** | ❌ **Never.** The fork holds by friction and gravity; Gazebo's rigid-body Coulomb friction is a caricature of silicon-on-PLA. Belt slip and stepper scatter are *distributions*, not values. |

**The real ceiling is the cell's own repeatability, not 100%.** Once sim error
is smaller than the cell's cycle-to-cycle σ, further fidelity is *unmeasurable*.
Unlike "100%", σ is a number you can measure: run 20 cycles and record where the
wafer lands.

This cell is loose — printed fixtures, a passive gravity-held fork, a timed belt
with no feedback — so σ is likely several millimetres, and a good geometric
model may already sit inside it. **Claim "validated equivalence within measured
repeatability", never "100%".** It is both honest and much more defensible.

---

## 10. Digital Model vs Digital Shadow vs Digital Twin

| | Data flow | Status |
|---|---|---|
| **Digital Model** | none | **← what we are building** |
| **Digital Shadow** | real → sim, one way | Stretch goal, gated |
| **Digital Twin** | bidirectional | Out of scope |

**Be precise about which one you built.** Calling a Digital Model a "twin"
invites exactly the question you cannot answer.

**A live link needs three sources, not one** — the PLC does *not* know the arms'
joint angles; that never crosses it:

| Source | Route | Gives |
|---|---|---|
| Micro850 | EtherNet/IP via `pycomm3` (Micro800 support) | Sequence state, belt run/stop |
| M1 Pro | Dobot TCP/IP remote-control protocol | Joint angles |
| Pro 600 | `pymycobot` over TCP | Joint angles |

**Architectural decision:** the sequencer's inputs are ROS 2 topics/services, so
a PLC bridge can feed them exactly as the stub does. "Connect to the PLC" then
becomes *swap one node*, not *rewrite the sequencer*. Costs nothing now.

---

## 11. Reference commands

```bash
# Source (ONLY jazzy) and build
cd ~/dobot_cobot_gazebo_twin
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install && source install/setup.bash

# Run
ros2 launch wafer_cell_bringup m1pro_gazebo.launch.py
ros2 launch wafer_cell_bringup pro600_gazebo.launch.py

# Controllers (note the NAMED managers)
ros2 control list_controllers -c /m1pro_controller_manager
ros2 control list_controllers -c /pro600_controller_manager

# Kill orphan sims — never `pkill -f "gz sim"`
pkill -9 -x gz-sim-server
```

---

## 12. Known risks

| Risk | Mitigation |
|---|---|
| This document being wrong again | Provenance tags in §0. Never state a negative as fact. |
| Fork thicker than the wafer-to-belt gap | **Pass/fail, not gradual.** Measure both first; a thinner blade is a cheap reprint. |
| Belt speed error → position error | No sensor to correct it. Calculate from stepper parameters, verify by stopwatch. |
| Two arms in one world | ✅ De-risked — named controller managers verified on both. |
| Zero of 61 measurements taken | Model runs on placeholders until they land. |
| Shadow depends on hardware being cycle-ready | Gated stretch goal; the Model demos regardless. |

---

## 13. Corrections log — Revision A → B

| # | Revision A said | Truth | Cost |
|---|---|---|---|
| 1 | No ROS 2 URDF for M1 Pro | Official **MIT** model at `Dobot-Arm/M1Pro-ROS` | Built a whole model from GPLv2 meshes; deleted |
| 2 | No Pro 600 on any branch | Official **BSD** model on a bugfix-named branch | Nearly built a second one from scratch |
| 3 | M1 Pro is 2R + 1P + 1R with a wrist spline | **P + 3R** — arm rides a carriage up the column | Wrong placeholder kinematics |
| 4 | Vacuum gripper (implied both arms) | **M1 Pro is a passive fork, no vacuum** | Wrong grasp model and approach direction |
| 5 | Photoelectric sensors in the sequence | **None fitted** — belt is PLC time-based | Wrong sequencer architecture |
| 6 | PLC `2080-LC50-24QBB` | Label reads **`2080-L60E-24QBB`** | Minor |
| 7 | Deadline 24 h from 2026-09-01 22:00 | Stale by a full day | A planning call made against an expired deadline |
| 8 | "Blue curved cradles" as the nests | **Three** stepped semicircular nests: yellow, magenta, blue | Incomplete world model |
| 9 | Bench | A **wooden board on a lab table** — the board is the datum | Wrong datum choice |

---

## 14. OPEN — layout confirmed WRONG by the owner, 2026-09-03. Awaiting measurement.

> **UPDATE 2026-09-03, late evening.** On the owner's instruction an **interim,
> photo-derived layout** was applied (rectified overhead photograph
> `docs/reference_photos_2/20260902_114748.heic`, ±20 mm; method and the
> sim-vs-photo table in `docs/research_2026-09-03/RESEARCH_REVIEW.md` §4).
> Items 1 (opening direction: yellow → −X, blue → +X) and 2 (conveyor:
> centreline ≈ +0.135, mesh yawed 180° so the motor is at the −X rear corner)
> are addressed. Items 3 (base yaw) and 4 (rest poses) are **still unmeasured**;
> the yaws keep the old values and the rest poses are FK-solved. All poses now
> live in `src/wafer_cell_bringup/scripts/cell_layout.py`. The two images
> described below as "not saved" **are on disk** (see the review); the
> reference render is a Gemini-generated concept image, not a measurement.
>
> **2026-09-04:** M1 Pro yaw set to **−90° by kinematic inference** (with yaw 0
> the fork cannot withdraw from the belt nest along −X as the video shows; with
> the carriage facing the bench front every cycle waypoint is reachable). The
> belt carriage is `belt_holder.stl` ridden plate-down with its posts up
> (owner, 2026-09-04 evening; the Ø124 C-nest 3MF briefly used that afternoon
> was the wrong part and is gone); the wafer sits on its 43 mm seat inside a
> 2 mm lip of radius 64. The fork's wafer seat is 147 mm from the wrist (tips
> 30 mm past the wafer centre, inside the nests' 57.5 mm free radius). All
> three remain 🟡 until measured. The holder's 180 mm side lies ALONG the
> belt, posts at the belt-axis ends (owner's picture, 2026-09-04 late
> evening); the wrist turns the fork 90° on the way and it enters ACROSS the
> belt from the front between the posts, sets the wafer down and backs out
> underneath (owner's videos). Load position `BELT_A = −0.25`, beside the
> column, 🟡 from the video.

The owner reviewed the Gazebo build against a reference render and confirmed
**all four** of the following are wrong. No changes were made: they are recorded
here to be fixed once real measurements exist. **Do not guess at these again.**

Two rounds of guessing already failed. The root cause is that the two sources
disagree and neither is a measurement:

* the **plan-view photograph** of the real cell, and
* a **reference render** the owner supplied on 2026-09-03

⛔ **1. Tower opening direction.** Both C-shaped nests currently open toward
`+Y` (world), i.e. toward the arm that serves them. Reasoning was that both
robots sit behind their towers, so any other *common* direction puts the arm on
the closed side. The render shows them opening sideways. Verified from the STL
that the two are identical and do face the same way (material centroid 22 mm to
−Y of the bbox centre; confirmed in `docs/cell_plan.png`) — so the owner's
"flip the blue one 180°" was already satisfied. The *absolute* direction is what
is wrong. Metrology: `nest_poses`.

⛔ **2. Conveyor front-to-back position.** Currently `y = +0.130`. The plan-view
photo read as hard against the far edge (`+0.170`); the render shows clearly
more bench behind the belt. 40 mm apart, both eyeballed.
Metrology: `belt_centreline_y`. **Needed: back edge of bench → near rail of belt.**

⛔ **3. Robot facing / base yaw.** M1 Pro yaw `0`, Pro 600 yaw `π`. Never
measured. Highest-leverage number in the cell: **1° ≈ 7 mm** at the M1 Pro's
reach. Metrology: `m1pro_base_yaw`, `pro600_base_yaw`. Two-point method in the
metrology spec §02 gives ~0.14° with a steel rule.

⛔ **4. Arm rest poses.** Both home poses were solved by FK against targets
*chosen by Claude*, not observed. They are kinematically valid (limit margins
≥0.216 rad, no bench overhang) but do not match how the real arms sit at rest.
Metrology: `m1pro_home`, `pro600_home` — needs joint readouts from the teach
pendant, not a photograph.

### What IS settled and should not be re-derived

| Fact | How it was established |
|---|---|
| Nest shelf heights `z = 0.0550 / 0.0770 / 0.0990` | Mesh audit: three ledges of exactly 1760 mm² each; the 0.100 face is the rim (1003 mm²) |
| Fork mounts with its boss top at wrist-frame `z = 0` | `wrist_link` visual carries `origin z=0.08081`; Link4's raw extent (−0.0808) is a trap that hangs the fork in mid-air |
| M1 Pro wrist collision was 81 mm below its visual | Vendor defect, fixed |
| Nothing rests off the bench | `ros2 run wafer_cell_bringup check_extents.py` — run it after moving anything |
| Blade corridor between belt and tower is 102.7 mm | Blade is 58.2 mm wide, so max 22 mm side clearance; centreline-only checks report ~36 mm and are wrong |
