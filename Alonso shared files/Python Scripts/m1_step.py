import socket, time

M1_IP = "192.168.10.40"
SPEED = 15

dash = socket.create_connection((M1_IP, 29999), timeout=10)
move = socket.create_connection((M1_IP, 30003), timeout=60)


def send(sock, cmd):
    sock.sendall((cmd + "\n").encode())
    r = sock.recv(1024).decode().strip()
    print(f"    {cmd} -> {r}")
    return r


def status():
    print("  --- status ---")
    send(dash, "RobotMode()")
    send(dash, "GetErrorID()")


def recover():
    print("  --- clearing error ---")
    send(dash, "ClearError()")
    time.sleep(0.5)
    send(dash, "EnableRobot()")
    time.sleep(2)
    send(dash, f"SpeedFactor({SPEED})")


send(dash, "ClearError()")
send(dash, "EnableRobot()")
time.sleep(2)
send(dash, f"SpeedFactor({SPEED})")

HOME = (314.38,  41.65, 157.12, 107.54)
P1   = (314.38,  41.65,  70.53, 107.54)
P2   = (314.13, 180.89,  70.53, 107.54)
P3   = (314.13, 180.89, 111.93, 107.54)
P4   = ( 69.49, 389.61, 110.40, 201.70)
P5   = ( 69.49, 389.61,  75.62, 201.70)
P6   = (203.78, 340.41,  75.62, 179.87)
P7   = (203.78, 340.41, 151.12, 179.87)

STEPS = [
    ("home",               HOME),
    ("descend to wafer",   P1),
    ("traverse low",       P2),
    ("lift",               P3),
    ("over conveyor",      P4),
    ("descend to carrier", P5),
    ("rotate",             P6),
    ("withdraw",           P7),
    ("home",               HOME),
]

print("\ncommands: ENTER = next move | s = status | c = clear error | q = quit\n")

i = 0
while i < len(STEPS):
    label, pose = STEPS[i]
    key = input(f"\n[{i}] ENTER to move -> {label}  (s/c/q): ").strip().lower()

    if key == "q":
        break
    if key == "s":
        status()
        continue
    if key == "c":
        recover()
        continue

    x, y, z, r = pose
    send(move, f"MovJ({x},{y},{z},{r})")
    send(move, "Sync()")
    status()
    i += 1

print("\ndone")