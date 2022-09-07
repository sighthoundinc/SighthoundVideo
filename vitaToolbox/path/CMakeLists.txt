cmake_minimum_required(VERSION 3.2.2)




if (APPLE)

project(volumeUtils)


add_library(${PROJECT_NAME} SHARED srcMac/volumeUtils.c srcMac/volumeUtils.m)
target_link_libraries(${PROJECT_NAME} "-framework Carbon" "-framework Foundation")


install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib)

endif()
