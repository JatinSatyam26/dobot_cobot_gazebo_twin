# Attribution — Dobot M1 Pro model

## Current source: OFFICIAL, MIT licensed

`urdf/dobot_m1pro.urdf.xacro` and `meshes/*.STL` derive from **Dobot's own**
ROS package:

> https://github.com/Dobot-Arm/M1Pro-ROS — `m1pro_description`
> **MIT License, Copyright (c) 2022 Dobot**

Links, joint origins, meshes and **inertia tensors** are Dobot's, exported from
their SolidWorks model. MIT is permissive: attribution is the only obligation,
and there is nothing to resolve before distributing this project.

### Two defects fixed on import — do not restore upstream values

1. **`effort="0" velocity="0"` on `joint1`.** Zero limits make
   `joint_trajectory_controller` refuse to move the joint.
2. **Joints 2/3/4 were `type="continuous"` — no limits at all.** The real M1 Pro
   is ±85° (J1) and ±135° (J2). Left as continuous, the sim would reach poses
   the hardware cannot. Converted to `revolute` with datasheet limits.

Masses are Dobot's SolidWorks values and are **light** (base 1.65 kg) because the
export omits motors and castings; the real arm is ~41 kg. Harmless here — the
base is fixed to the world and joints are position-controlled — but not valid
for dynamics or payload work.

---

## Superseded: the hand-built model (and its GPLv2 problem)

`urdf/dobot_m1pro_handbuilt.urdf.xacro.bak` is kept only as a fallback. It used
STL meshes from **`smhaller/dobot-m1`** (Simon Haller, Universität Innsbruck),
which declares **GPLv2** in its `package.xml`. Those meshes were themselves
conversions of Dobot's public CAD (`M1-Volume_V6-180427.stp`), and the URDF
around them was written from scratch here.

**That whole licensing question is now moot** — the official MIT source replaces
it. If the `.bak` file is ever deleted, no GPLv2-derived material remains in
this package.

### What the hand-built version got right and wrong

**Right — the kinematic structure.** It identified that the M1 Pro is
prismatic-first (`base → [P] → [R] → [R] → [R]`), with the whole arm assembly
riding a carriage up the column and no ball-screw spline at the wrist. Dobot's
official file confirms this. `PROJECT_CONTEXT.md` §5, which specifies
"2 revolute + 1 prismatic + 1 revolute", is wrong.

**Wrong — several dimensions:**

| | Hand-built | Official Dobot |
|---|---|---|
| Z stroke | 0.02 – 0.23 m | **0 – 0.25 m** |
| Arm laid along | +Y | **+X** |
| Shoulder offset from carriage | 0 | **123 mm in X** |
| Prismatic joint origin | (0, 0.100, 0.097) | **(−0.003, 0, 0.0959)** |

## Lesson for finding vendor models

Both the M1 Pro and the myCobot Pro 600 models were initially judged
"non-existent" and both turned out to exist. In each case the failure was
searching repository and branch **names** rather than **enumerating the
vendor's GitHub account**. The Pro 600 lives on a branch named for a bugfix
(`fix/mycobot_pro_600_joint_limits`); the M1 Pro lives in a repo under
`Dobot-Arm/`, an account whose org endpoint 404s and only resolves as a user.
Enumerate the account first.
