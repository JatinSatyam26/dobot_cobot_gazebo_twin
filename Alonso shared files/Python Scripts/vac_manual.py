from pymodbus.client import ModbusTcpClient

VAC_ON, VAC_BLOW = 0, 1

plc = ModbusTcpClient("192.168.10.10", port=502)
if not plc.connect():
    print("could not reach PLC")
    raise SystemExit


def show():
    rr = plc.read_coils(0, count=2)
    if rr.isError():
        print("  coil read error")
    else:
        print(f"  Vac_On={rr.bits[0]}   Vac_Blow={rr.bits[1]}")


def set_coils(vac, blow):
    plc.write_coil(VAC_ON, vac)
    plc.write_coil(VAC_BLOW, blow)
    show()


print("""
  1  vacuum ON
  2  vacuum OFF
  3  blow ON
  4  blow OFF
  0  everything off
  s  show state
  q  quit
""")

set_coils(False, False)

try:
    while True:
        k = input("> ").strip().lower()
        if k == "q":
            break
        elif k == "1":
            plc.write_coil(VAC_ON, True);   show()
        elif k == "2":
            plc.write_coil(VAC_ON, False);  show()
        elif k == "3":
            plc.write_coil(VAC_BLOW, True); show()
        elif k == "4":
            plc.write_coil(VAC_BLOW, False); show()
        elif k == "0":
            set_coils(False, False)
        elif k == "s":
            show()
        else:
            print("  ?")
except KeyboardInterrupt:
    pass
finally:
    print("\nclearing coils")
    plc.write_coil(VAC_ON, False)
    plc.write_coil(VAC_BLOW, False)
    plc.close()