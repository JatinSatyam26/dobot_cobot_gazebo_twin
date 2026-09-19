# Attribution — myCobot Pro 600 model

`meshes/*.dae` and the kinematic parameters in `urdf/mycobot_pro600.urdf.xacro`
are derived from **Elephant Robotics' own** `mycobot_ros2` repository:

> https://github.com/elephantrobotics/mycobot_ros2
> branch `fix/mycobot_pro_600_joint_limits`
> path `mycobot_description/urdf/mycobot_pro_600/`

**Licence: BSD**, declared in that repository's `mycobot_description/package.xml`.
(No top-level `LICENSE` file is present in the repo.) Upstream publishes no
licence text and does not name the variant, so the exact terms are unconfirmed
— see `LICENSES/BSD-ElephantRobotics.md` before redistributing.

## Corrections applied on import

1. **`velocity = "0"` on all six joints.** The upstream URDF declares a zero
   velocity limit on every joint, which makes `joint_trajectory_controller`
   refuse to move them. Replaced with real values.
2. **Meshes decimated.** Upstream ships 31 MB of COLLADA. Visual meshes are kept;
   collision geometry is primitives, since full-resolution mesh collision is
   far too expensive for real-time physics.

## Verified against the datasheet

Link offsets read out of the upstream URDF give 250 mm + 250 mm arm links plus
the wrist stack — consistent with the Pro 600's published **600 mm reach**. This
is a genuine Pro 600 model, not a rescaled 280.

> **Note:** this supersedes `PROJECT_CONTEXT.md` §5, which states that no Pro 600
> description exists on any branch. It does — just not on a branch named for a
> ROS distro, which is why a branch-name search missed it.
