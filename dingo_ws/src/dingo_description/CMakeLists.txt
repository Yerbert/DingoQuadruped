cmake_minimum_required(VERSION 3.8)
project(dingo_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch rviz
  DESTINATION share/${PROJECT_NAME})

# meshes/main.py (mesh inertia helper) and "dingo copy.urdf" (a backup copy) are not part of the runtime package
install(DIRECTORY meshes urdf
  DESTINATION share/${PROJECT_NAME}
  PATTERN "*.py" EXCLUDE
  PATTERN "* copy.urdf" EXCLUDE)

ament_package()
