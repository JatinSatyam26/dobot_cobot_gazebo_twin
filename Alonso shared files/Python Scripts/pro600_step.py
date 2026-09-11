from pymycobot import ElephantRobot
import time

arm = ElephantRobot("192.168.10.20", 5001)
arm.start_client()
time.sleep(1)

SPEED = 1300      # slow for first run

HOME      = [ -81.287, -102.418, 130.242, -118.125, -89.736,  -2.109]
APPROACH  = [-105.256,  -54.941,  90.283, -124.980, -89.561, -25.928]
PICK      = [-105.726,  -50.312,  91.511, -132.451, -89.561, -25.928]
DROP_OVER = [ -41.208,  -64.017, 111.022, -137.197, -89.912,  38.320]
DROP      = [ -41.470,  -61.617, 111.499, -140.361, -89.824,  38.320]

STEPS = [
    ("home",            HOME),
    ("approach wafer",  APPROACH),
    ("down to wafer",   PICK),
    ("lift",            APPROACH),
    ("traverse",        DROP_OVER),
    ("down to drop",    DROP),
    ("lift",            DROP_OVER),
    ("home",            HOME),
]

print("current:", arm.get_angles())

for label, pose in STEPS:
    input(f"\nENTER to move -> {label}  (Ctrl+C to stop)")
    arm.write_angles(pose, SPEED)
    arm.command_wait_done()
    print("  at:", arm.get_angles())