cmake_minimum_required(VERSION 3.8)
project(wafer_cell_bringup)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch worlds config models meshes urdf
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS scripts/m1pro_wiggle.py scripts/generate_cell_urdf.py scripts/capture_view.py scripts/go_home.py
           scripts/check_extents.py scripts/cell_fk.py scripts/cell_layout.py
           scripts/solve_home_poses.py scripts/cell_sequencer.py scripts/record_frames.py
  scripts/make_cycle_video.py
  scripts/split_collision_mesh.py
           scripts/cell_plan.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
