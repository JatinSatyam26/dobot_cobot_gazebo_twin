from pymodbus.client import ModbusTcpClient

c = ModbusTcpClient("192.168.10.40", port=502)
c.connect()

rr = c.read_coils(0, count=100)
if not rr.isError():
    on = [i for i, b in enumerate(rr.bits) if b]
    print("coils set:", on)

rr = c.read_discrete_inputs(0, count=100)
if not rr.isError():
    on = [i for i, b in enumerate(rr.bits) if b]
    print("discrete set:", on)

for base in range(0, 200, 20):
    rr = c.read_holding_registers(base, count=20)
    if not rr.isError():
        nz = {base+i: v for i, v in enumerate(rr.registers) if v}
        if nz:
            print(f"holding nonzero at {base}:", nz)

c.close()