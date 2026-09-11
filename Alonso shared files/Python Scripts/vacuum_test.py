from pymodbus.client import ModbusTcpClient

plc = ModbusTcpClient("192.168.10.10", port=502)
plc.connect()

plc.write_coil(0, True)      # Vac_On
input("suction on? press enter")
plc.write_coil(0, False)

plc.close()