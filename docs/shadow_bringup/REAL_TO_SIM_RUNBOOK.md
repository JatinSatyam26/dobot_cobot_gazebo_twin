# Real-to-sim run-book (both arms live in Gazebo)

Proven on the bench on 2026-09-17. Three terminals, in this order. Every
terminal needs the two `source` lines first.

## 0. Once per laptop

- Network profile `workcell` on the wired port: 192.168.10.60/24, no gateway,
  never-default (Alonso's `TWIN_LAPTOP_SETUP.md`). It comes up by itself when
  the cable is plugged into the MokerLink switch.
- Firewall: `sudo ufw allow from 192.168.10.0/24 to any port 5005 proto udp`
  (without it the Pro 600 broadcast is silently dropped while the M1 works).

## 1. Plug in, then pre-flight (terminal 1)

```bash
cd ~/dobot_cobot_gazebo_twin && tools/bench_check.sh
```

Wait for `PRE-FLIGHT OK`. The M1 Pro (.40), the Pro 600 (.20) and Alonso's
laptop (.5) must answer; his laptop is what broadcasts the Pro 600 pose.

## 2. Gazebo, telemetry mode (terminal 1)

```bash
cd ~/dobot_cobot_gazebo_twin && source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 launch wafer_cell_bringup cell.launch.py gui:=true cameras:=false telemetry:=true
```

Both arms hold their HOME. Nothing else moves; the carrier is not in this
world, the conveyor, towers and wafer are props.

## 3. The live bridge (terminal 2)

```bash
cd ~/dobot_cobot_gazebo_twin && source /opt/ros/jazzy/setup.bash && source install/setup.bash && tools/live_telemetry.py
```

One status line per second: `m1pro: LIVE ~123 Hz` as soon as the robot is on;
`pro600: LIVE` only while Alonso's bridge runs a job, `IDLE` between jobs,
`no data` if his bridge is not running (or the firewall rule is missing).

## 4. The check before anything moves

With both robots at HOME the Gazebo arms must sit at HOME too. If an arm sits
wrong, stop and report the six/four angles the bridge prints. Then Alonso runs
the cell's cycle (or his step scripts): the M1 transfers, the belt indexes, the
Pro 600 picks and places; Gazebo mirrors both arms. Your laptop writes nothing.

## 5. Stop (terminal 3, or after closing the Gazebo window)

```bash
cd ~/dobot_cobot_gazebo_twin && tools/stop_sim.sh
```

## Fallbacks

- No network: replay the 2026-09-11 recordings instead of the bridge:
  `tools/replay_telemetry.py --m1 First_test_withonly_M1Pro_sequence_onmyterminal/m1_feedback_20260911_144727.md --pro600 First_test_withonly_Pro600_sequence_onmyterminal/First_test_withonly_Pro600_sequence_onmyterminal.md`
- Alonso's bridge cannot run: `tools/live_telemetry.py --pro600-direct 192.168.10.20`
  polls the Pro 600 itself. Only with his bridge OFF (the robot accepts one client).
- Desk test with no robots: `tools/fake_robots.py --m1 <log> --pro600 <log> --loop`
  in one terminal, `tools/live_telemetry.py --m1-ip 127.0.0.1` in another.
