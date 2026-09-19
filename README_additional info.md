# Digital Twin Build — Session Notes & Plan
### Dobot M1 Pro + Cobot Pro 600 workcell → Gazebo Harmonic / ROS 2 Jazzy

This README captures everything decided/discussed in this planning session, for reference while running the actual Claude Code build.

> **Historical document — terminology superseded (note added 2026-09-19).**
> These are the pre-build planning notes, kept as written. "Digital twin" was
> the working term at the time. What was actually built is a **digital model**
> of the cell plus a one-way **real-to-sim digital shadow** of it, bench-proven
> 2026-09-17: real joint state drives the simulation, and nothing is ever sent
> back to the robots. There is no bidirectional twin and no sim-to-real path.
> See `PROJECT_CONTEXT.md` §10 for the distinction, and `README.md` for what
> the project actually does today.

---

## 1. What we're building

A digital twin of a real robotics workbench:
- Dobot M1 Pro (URDF available)
- Cobot Pro 600 (URDF available)
- Mini conveyor belt (STL available)
- 3D-printed part holders — yellow, blue, red (STLs available)
- Wafer with known dimensions, sitting on the red holder
- Wooden workbench with known dimensions and exact part-placement measurements

All source assets and measurements are already prepared — this significantly reduces the guesswork an agent would otherwise need to do.

---

## 2. Model choice: Fable 5.1

**Recommendation:** Run this build on **Fable 5.1** in Claude Code (`/model fable`).

**Why:** Fable-class models are Anthropic's tier built specifically for long, autonomous, multi-hour sessions — they investigate before acting and verify their own work more than smaller models, which matters for an unattended 24-hour build with lots of iteration (SDF assembly, physics tuning, ROS 2 wiring).

**Plan note:** Max plans (5x/20x) include Fable usage up to a portion of the regular weekly allowance (it draws down faster than Sonnet/Opus since it's the most capable tier). Terms can shift — double-check current limits at claude.ai/settings/usage before relying on it for a long run.

**Effort level:** Fable 5.1 uses *adaptive reasoning* — it already decides per-step how hard to think based on task difficulty. You don't need to manually manage effort level for this.

---

## 3. The "self-vision" problem — and the fix

**The issue:** Claude Code's built-in screen-vision tool (`computer-use`) is **macOS-only** and requires Pro/Max. It won't work on the Ubuntu Linux machine this build runs on.

**The fix — camera sensor, not screenshots:**
A camera sensor is a virtual camera placed inside the simulated world (defined in the SDF file) — like a tripod camera pointed at the table. Gazebo renders what it "sees" (the actual 3D models, positions, lighting) and publishes it as an image on a ROS 2 topic, same as a real camera driver would.

This is far more reliable than screenshotting the Gazebo GUI window, which just captures app pixels (menus, toolbars, chrome included) rather than a clean, physically accurate view of the scene.

**Workflow:**
1. Add a `<sensor type="camera">` to the SDF world, pointed at the workbench.
2. Bridge it to ROS 2 via `ros_gz_bridge` / `ros_gz_image`.
3. Have Claude subscribe to that image topic and periodically dump frames to disk.
4. Claude Code can view any image by file path — so it can read its own rendered frames mid-build to check part placement, scale, and collisions, without you manually screenshotting anything.

**Optional upgrade — custom MCP tool:** A small local MCP (Model Context Protocol) server could expose an on-demand "grab a frame" or "take a screenshot" tool that Claude Code calls whenever it needs to, throughout the session — not tied to macOS the way `computer-use` is. Not built yet; flagged as a future option.

---

## 4. `/goal` — autonomous completion mode

`/goal` turns "do this one thing" into "keep working until this is true." Instead of approving every step, you state a finish condition — e.g. *"all parts are placed within spec per my measurements, URDFs load with no errors, and a camera-frame check matches the reference photo"* — and Claude keeps iterating, across turns and context compactions, until that condition holds (or a configured safety cap is hit).

This is the mechanism that lets a multi-hour build run with minimal babysitting. Pair it with checkpoints so you can review/rewind if a step goes sideways.

---

## 5. Reducing token cost, hallucinations, and time

**Model/effort routing:**
- Adaptive reasoning already handles per-step effort automatically.
- Route routine sub-tasks (file cleanup, log checks, screenshot review) to **subagents** — Claude delegates to these automatically when appropriate, and each runs in its own isolated context window. A failed attempt inside a subagent doesn't pollute the main session's memory — only a summary comes back.

**Context hygiene ("refresh" behavior):**
- `/compact` manually clears/compresses context at a moment you choose — ideally right after a verified success, before starting the next component.
- A `TaskCompleted`/`SubagentStop` hook can auto-delete stale/failed files (broken world files, old failed launch logs) the moment a task is confirmed done — task-completion-based cleanup, not time-based.
- Commit (git or Claude Code checkpoints) at each verified milestone, giving a clean "known good" state to snap back to.

**Realistic impact:**
- **Cost savings:** meaningful — likely 30–50% token reduction from routing routine work to cheaper models.
- **Time savings:** modest — the real bottleneck is the physical sim iteration loop (launch → wait → observe → adjust), which a faster model doesn't speed up. Expect ~10–20% faster overall, not a multiple.
- **Biggest win is accuracy, not speed** — clean context prevents Claude from citing stale/wrong measurements or repeating an already-abandoned fix.

---

## 6. Prompt engineering strategies

- **Ground truth in code, not vibes:** have Claude write a verification script that checks positions/dimensions numerically against your measurements file. A failed check throws a hard error instead of a plausible-sounding guess.
- **Literal numbers over descriptions:** "place at X=0.42, Y=0.15" beats "place it near the belt."
- **Plan mode before big steps:** review the plan before Claude touches disk.
- **Explore → plan → code**, in that order, for any new component.
- **One verified milestone at a time**, each with a visible pass/fail check, committed before moving on.
- **Rich CLAUDE.md up front:** conventions, file locations, exact measurements — every time Claude has to re-derive something instead of reading it, that's wasted time and hallucination risk.
- **Precise `/goal` conditions:** "all 5 parts within 5mm of spec, verified by script" (checkable) beats "the scene looks right" (not checkable).

---

## 7. Step-by-step (baby steps)

1. Buy Max 5x, install Claude Code, log in with that account.
2. Create a project folder; organize URDFs, STLs, and a text file with all measurements (table, wafer, placement coordinates) into subfolders.
3. `cd` into that folder, run `claude`.
4. In your first message, state the full goal: where every resource file is, exact measurements, and what "done" looks like. Ask Claude to inventory everything and confirm ROS 2 Jazzy + Gazebo Harmonic are installed before it touches anything.
5. Switch models: `/model fable`.
6. Use plan mode first — review Claude's proposed approach before it builds.
7. Build the base world: table, both robot arms (from URDFs), conveyor, and the three holders, positioned per your measurements.
8. Add the camera sensor pointed at the table.
9. Set up a frame-capture workflow so Claude can visually check its own work as it goes.
10. Set the finish line with `/goal`, describing exactly what a correct build looks like.
11. Let it run — check in periodically, use checkpoints to rewind a bad step if needed.
12. When Claude reports done, open Gazebo yourself and visually compare against the real reference photo as a final sanity check.

---

## 8. Reference: how a professional would do this manually (no AI)

For context/timeline calibration — this is the traditional expert workflow:

1. **Scoping & reference capture** — measurements, photos, spec sheets, decide fidelity level (kinematics-only vs. full dynamics).
2. **Asset prep** — fix placeholder/zero inertia values in URDFs; split meshes into high-poly visual + simplified collision geometry.
3. **Standalone robot bring-up** — get each arm running alone in an empty world first (`ros2_control`, `gz_ros2_control`, TF tree sanity checks) before combining anything.
4. **Build the world** — SDF world file: physics engine (DART by default in Harmonic), solver settings, lighting, ground plane, static workbench.
5. **Populate the scene precisely** — exact x/y/z/roll/pitch/yaw for every object from real measurements; conveyor usually needs a custom/community "moving surface" plugin.
6. **Wire up control** — namespace each arm separately (two robots in one world need unique namespaces); joint trajectory controllers; MoveIt 2 setup if motion planning is needed.
7. **Add the camera sensor** — matched resolution/FOV to a real camera if one will eventually pair with it.
8. **End-effector behavior** — `DetachableJoint` or a custom grasp plugin, since friction-only grasping is notoriously unreliable in simulation.
9. **Calibrate against reality** — compare to reference photo and datasheets; tune friction/damping.
10. **End-to-end validation** — repeated full-cycle runs, watching for interpenetration, drops, instability.
11. **Package as a deliverable** — proper ROS 2 colcon package, launch files, README, clean git history, ideally a Dockerfile.

**Realistic professional timeline:** 1–3 weeks (closer to 3 with MoveIt integration and a working conveyor plugin), not 24 hours. The prep work already done here (clean URDFs, exact measurements) removes a lot of the normal front-loaded time — but the physics-tuning iteration loop remains the bottleneck regardless of who (or what) is driving it.

---

## 9. Honest expectations for the 24-hour goal

Good position to start from, given the ready assets and measurements. Realistic outcome: a **mostly-complete first working version** within 24 hours — not necessarily a fully polished, validated twin. Budget for a possible follow-up session to finish joint tuning, camera-verified placement, and full validation. Treat 24 hours as "mostly there," not a guarantee of "fully done."
