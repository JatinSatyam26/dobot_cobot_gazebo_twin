# Verification captures, 2026-09-04

## Cycle 16 (current): fork turns 90° and enters the belt holder across the belt

* `cycle_recording_09_04_2026.mp4` — one full cycle from all six camera
  sensors at 15 fps simulation time (front, plan, yellow nest, belt holder
  from behind the belt, unloading end, blue nest), step names overlaid, with
  the carriage centred on the belt's running surface (`BELT_SURFACE_Y`).
  Made with `record_frames.py` at 1/15 s per camera and `make_cycle_video.py`.

* `cycle16_closeups.jpg` — one full cycle through the four close-up cameras:
  yellow pick (engage, lift), the transfer (front view: the wrist turns the
  fork 90° on the way), belt hand-off seen from BEHIND the belt (the fork
  arrives from the bench front with the blade pointing to the rear, slides in
  between the two end posts 2 mm above the lip, sets the wafer down, drops
  the blade 4 mm, backs out underneath, wafer left seated), unloading end
  (release, cup descend), final blue nest and plan view.
  Pose log of the run: set down at 43.7 mm above the belt (seat + half
  thickness), 0.0 mm off the carriage centre, 0.0° tilt; rides seated; ends
  at (0.4300, −0.1530, 0.0997), the blue nest centre at ledge height.
* `belt_handoff_from_rear.jpg` — set-down, after retreat, and the wafer at
  the unloading end (streamed probe of the same motion).
* `belt_holder_seated_at_C.png` — the disc inside the lip after the ride,
  holder along the belt with the posts at the belt-axis ends.
* `owner_video_handoff_frames_19-27.jpg`, `..._46-54.jpg` — zoomed frames of
  the owner's clip "How to move dobot and place wafer on magenta color holder
  on the belt.mp4" (2.4 s, 30 fps). Read with the M1 Pro column at the
  rear-left: the fork points to the REAR (up-right in the picture) and comes
  in from the front across the belt, then withdraws to the front. I first
  misread this as an entry along the belt and turned the holder; the owner
  corrected both.

## Earlier the same day (superseded)

* `belt_holder_free_drop_failure.png` — with the fork entering along the belt
  it could not pass the posts; the wafer was dropped 5.5 mm and in 3 of 5
  runs ended standing on edge.
