#!/bin/bash
# Pre-flight for a real-to-sim run: wired link at 192.168.10.60, the cell answers, firewall lets UDP 5005 in.
ok=1
if ip -br addr show eno1 2>/dev/null | grep -q "192.168.10.60"; then echo "[ok]   wired link up at 192.168.10.60"
else echo "[FAIL] no 192.168.10.60 on eno1 - plug the cable into the MokerLink switch; the 'workcell' profile comes up by itself (nmcli connection up workcell if not)"; ok=0; fi
for t in "192.168.10.40 M1 Pro" "192.168.10.20 Pro 600" "192.168.10.5 Alonso's laptop (Pro 600 broadcast)" "192.168.10.10 PLC"; do
  set -- $t; if ping -c1 -W1 $1 >/dev/null 2>&1; then echo "[ok]   $1 answers ($2 $3 $4 $5)"; else echo "[FAIL] $1 no answer ($2 $3 $4 $5)"; ok=0; fi
done
if systemctl is-active ufw >/dev/null 2>&1; then
  echo "[note] ufw is active: inbound UDP 5005 must be allowed or the Pro 600 shows 'no data'."
  echo "       once per machine:  sudo ufw allow from 192.168.10.0/24 to any port 5005 proto udp"
fi
echo "[info] listening 5 s for the Pro 600 broadcast (silence is normal while Alonso's bridge is idle) ..."
timeout 6 python3 - <<'PY'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', 5005)); s.settimeout(5.0)
n = 0; t0 = time.time()
try:
    while time.time() - t0 < 5: s.recvfrom(4096); n += 1
except socket.timeout: pass
print(f"[ok]   {n} broadcast packets in 5 s" if n else "[info] no broadcast packets in 5 s (his bridge idle or not running)")
PY
[ $ok = 1 ] && echo "PRE-FLIGHT OK" || echo "PRE-FLIGHT FAILED - fix the [FAIL] lines first"
