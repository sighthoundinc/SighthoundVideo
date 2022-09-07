cmake_minimum_required(VERSION 3.2.2)




project(optsearches)


add_library(${PROJECT_NAME} SHARED optsearches.c)


install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib)


