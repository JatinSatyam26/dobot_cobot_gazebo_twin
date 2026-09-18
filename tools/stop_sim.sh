#!/bin/bash
# Stop everything a real-to-sim run started (Gazebo, bridges, controllers). Kills by PID: ros2 launch's
# SIGINT leaves the headless server and the bridges alive (CLAUDE.md trap table), so this is the reliable stop.
PAT='gz sim -r|gz sim -g|gz sim server|gz sim gui|ruby.*gz sim|parameter_bridge|robot_state_publisher|controller_manager/spawner|go_home|cell_sequencer|task_shadow|plc_bridge|fake_plc|shadow_driver|replay_telemetry|live_telemetry|fake_robots|gz topic -e|ros2 launch'
for p in $(ps -eo pid,args | grep -E "$PAT" | grep -v -E "grep|stop_sim" | awk '{print $1}'); do kill -INT $p 2>/dev/null; done
sleep 3
for p in $(ps -eo pid,args | grep -E "$PAT" | grep -v -E "grep|stop_sim" | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
source /opt/ros/jazzy/setup.bash 2>/dev/null && ros2 daemon stop >/dev/null 2>&1
echo "stopped; remaining sim processes: $(ps -eo pid,args | grep -E "$PAT" | grep -v -E 'grep|stop_sim' | wc -l)"
