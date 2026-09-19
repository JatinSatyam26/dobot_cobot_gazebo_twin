# myCobot Pro 600 description — licence provenance

The robot description and meshes in `src/mycobot_pro600_description/` derive
from Elephant Robotics' `mycobot_ros2`:

    https://github.com/elephantrobotics/mycobot_ros2
    branch: fix/mycobot_pro_600_joint_limits
    package: mycobot_description, version 0.4.0

## What upstream actually declares

`mycobot_description/package.xml` on that branch declares:

    <license>BSD</license>

That is the whole of it. As checked on 2026-09-19:

* the upstream repository publishes **no LICENSE file**, on that branch or on
  the default branch;
* the declaration names the BSD family but **not which variant** (2-clause,
  3-clause, or another);
* no per-file copyright headers accompany the meshes.

## What that means for reuse

This project therefore **cannot reproduce an upstream licence text, because
upstream does not publish one.** Earlier revisions of this repository
described the material as "BSD-3-Clause"; that was more specific than the
source supports, and the wording has been corrected to "BSD (variant
unspecified upstream)".

The material is redistributed here in good faith on the strength of that
declaration. Anyone reusing this repository, and particularly anyone
redistributing the meshes, should confirm the exact terms with Elephant
Robotics rather than relying on this file.

Local modifications made on import are documented in
`src/mycobot_pro600_description/ATTRIBUTION.md`.
