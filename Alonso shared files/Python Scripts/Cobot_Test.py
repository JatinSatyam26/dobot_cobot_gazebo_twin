from pymycobot import ElephantRobot
import time

arm = ElephantRobot("192.168.10.20", 5001)
arm.start_client()
time.sleep(1)

start = arm.get_angles()
print("starting angles:", start)

target = list(start)
target[0] = 10.0          # J1 only

SPEED = 300               # mm/s equivalent — deliberately slow

print("moving J1 to 10 degrees...")
arm.write_angles(target, SPEED)
arm.command_wait_done()
print("arrived:", arm.get_angles())

time.sleep(2)

print("returning...")
arm.write_angles(start, SPEED)
arm.command_wait_done()
print("back at:", arm.get_angles())