cmake_minimum_required(VERSION 3.2.2)




project(xnat)


if (APPLE)
    set(REV_HEADER ${CMAKE_CURRENT_BINARY_DIR}/shlaunch_build.h)
    add_custom_command(
        OUTPUT  ${REV_HEADER}
        COMMAND ${CMAKE_CURRENT_LIST_DIR}/../scripts/generateShsudoHeader.sh ${REV_HEADER}
        COMMENT "=================== Generating ${REV_HEADER} ..."
    )
    set(SHLAUNCH_SUDO SighthoundVideoLauncher)
    add_executable(${SHLAUNCH_SUDO} shsudoMac/shsudoMac/shsudoMac/shsudo.m ${REV_HEADER})
    set(SHLAUNCH_ADDITIONAL_INCLUDES ${CMAKE_CURRENT_BINARY_DIR})
    target_include_directories(${SHLAUNCH_SUDO} PRIVATE ${SHLAUNCH_ADDITIONAL_INCLUDES})
    target_link_libraries(${SHLAUNCH_SUDO} "-framework Foundation" "-framework Security")
    target_link_options(${SHLAUNCH_SUDO} PRIVATE -lobjc)

    set(EXESOURCE shlaunchMac/shlaunchMac)
    set(MYLIBS iconv)
else()
    set(EXESOURCE shlaunchWin/shlaunch)
    set(MYDEFINES UNICODE;_UNICODE;_WIN32)
    set(MYLIBS psapi;netapi32)
endif()

add_library(launch SHARED launch.c ${REV_HEADER})
target_compile_definitions(launch PRIVATE ${MYDEFINES})
target_include_directories(launch PUBLIC ${EXESOURCE} ${SHLAUNCH_ADDITIONAL_INCLUDES})
target_link_libraries(launch PRIVATE ${MYLIBS})
add_executable(shlaunch ${EXESOURCE}/shlaunch.c ${REV_HEADER})
target_include_directories(shlaunch PUBLIC ${EXESOURCE} ${SHLAUNCH_ADDITIONAL_INCLUDES})
target_compile_definitions(shlaunch PRIVATE ${MYDEFINES})
target_link_libraries(shlaunch PRIVATE ${MYLIBS})



install(TARGETS shlaunch launch ${SHLAUNCH_SUDO}
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib)



