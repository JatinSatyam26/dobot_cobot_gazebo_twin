import sys
from pymodbus.client import ModbusTcpClient

plc = ModbusTcpClient("192.168.10.10", port=502)
plc.connect()

reg = int(sys.argv[1])
val = int(sys.argv[2])
plc.write_register(reg, val)
print(f"wrote {val} to register {reg}")
plc.close()