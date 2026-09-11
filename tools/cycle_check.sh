#!/bin/bash
# One headless sequencer cycle with a streamed pose log, then the per-step report.
#   tools/cycle_check.sh <out_dir>
# Kills leftover sim processes first (by PID, see the CLAUDE.md trap table), never with pkill -f.
OUT="$1"; [ -z "$OUT" ] && { echo "usage: $0 <out_dir>"; exit 2; }
mkdir -p "$OUT"; cd "$(dirname "$0")/.." || exit 2
source /opt/ros/jazzy/setup.bash && source install/setup.bash
PAT='gz sim -r|gz sim -g|gz sim server|gz sim gui|ruby.*gz sim|parameter_bridge|robot_state_publisher|controller_manager/spawner|go_home|cell_sequencer|task_shadow|plc_bridge|fake_plc|shadow_driver|gz topic -e|ros2 launch'
for p in $(ps -eo pid,args | grep -E "$PAT" | grep -v -E "grep|cycle_check" | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
sleep 1; ros2 daemon stop >/dev/null 2>&1
ros2 launch wafer_cell_bringup cell.launch.py gui:=false cameras:=false > "$OUT/cell_log.txt" 2>&1 &
CP=$!; sleep 28
python3 tools/cycle_check.py stream "$OUT/poses.csv" >/dev/null 2>&1 & PS=$!
sleep 2
timeout 300 ros2 run wafer_cell_bringup cell_sequencer.py > "$OUT/seq_log.txt" 2>&1; echo "sequencer exit $?"
sleep 2; kill -INT $PS 2>/dev/null; sleep 1
for p in $(ps -eo pid,args | grep -E "gz topic -e" | grep -v grep | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
python3 tools/cycle_check.py report "$OUT/poses.csv" "$OUT/seq_log.txt"
grep -E "error_code|Traceback" "$OUT/seq_log.txt" | head -3
kill -INT $CP; sleep 6
for p in $(ps -eo pid,args | grep -E "$PAT" | grep -v -E "grep|cycle_check" | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
echo DONE
