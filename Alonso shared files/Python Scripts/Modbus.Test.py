from pymodbus.client import ModbusTcpClient

PLC_IP = "192.168.10.10"

CMD_REG = 0    # 400001
STAT_REG = 1   # 400002

plc = ModbusTcpClient(PLC_IP, port=502)

if not plc.connect():
    print("could not connect")
    raise SystemExit

# write a recognizable value
plc.write_register(CMD_REG, 1234)
print("wrote 1234 to Cmd_Word")

# read it back
rr = plc.read_holding_registers(CMD_REG, count=2)
if rr.isError():
    print("read error:", rr)
else:
    print("Cmd_Word    =", rr.registers[0])
    print("Status_Word =", rr.registers[1])

plc.close()