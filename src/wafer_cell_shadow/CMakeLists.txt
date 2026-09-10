cmake_minimum_required(VERSION 3.8)
project(wafer_cell_shadow)
find_package(ament_cmake REQUIRED)
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/shadow_common.py scripts/m1pro_bridge.py scripts/pro600_bridge.py
                 scripts/plc_bridge.py scripts/shadow_driver.py
                 scripts/fake_plc.py scripts/task_shadow.py
        DESTINATION lib/${PROJECT_NAME})
ament_package()
