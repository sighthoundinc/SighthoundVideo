cmake_minimum_required(VERSION 3.2.2)




project(xnat)


if (WIN32)
    set(TARGET_NAME "Arden.aiXNAT")
    add_executable(${TARGET_NAME} xnat.c minidump.c)
    set(WINLIB iphlpapi.lib ws2_32.lib)
else()
    set(TARGET_NAME "xnat")
    add_library(${TARGET_NAME} SHARED xnat.c)
    target_compile_definitions(${TARGET_NAME} PUBLIC __XNAT_DYLIB)
endif()

target_compile_definitions(${TARGET_NAME} PUBLIC MINIUPNP_STATICLIB=1 NATPMP_STATICLIB=1)
target_include_directories(${TARGET_NAME} PRIVATE ${CONAN_INCLUDE_DIRS_MINIUPNPC} ${CONAN_INCLUDE_DIRS_LIBNATPMP})
target_link_directories(${TARGET_NAME} PRIVATE ${CONAN_LIB_DIRS_MINIUPNPC} ${CONAN_LIB_DIRS_LIBNATPMP})
target_link_libraries(${TARGET_NAME} ${CONAN_LIBS_MINIUPNPC} ${CONAN_LIBS_LIBNATPMP} ${WINLIB})

install(TARGETS ${TARGET_NAME}
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib)


