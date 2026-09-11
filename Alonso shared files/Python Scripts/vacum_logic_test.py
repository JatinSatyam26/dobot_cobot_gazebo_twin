from pymodbus.client import ModbusTcpClient
plc = ModbusTcpClient("192.168.10.10", port=502)
plc.connect()

plc.write_coil(0, True)
print(plc.read_coils(0, count=2).bits[:2])   # expect [True, False]

plc.write_coil(0, False)
plc.write_coil(1, False)
print(plc.read_coils(0, count=2).bits[:2])   # expect [False, True]

plc.close()