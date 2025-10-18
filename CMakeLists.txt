cmake_minimum_required(VERSION 3.10)
project(remote_ffi C CXX)

# External packages
include(ExternalProject)
ExternalProject_Add(libffi_external
    SOURCE_DIR ${CMAKE_SOURCE_DIR}/packages/libffi
    CONFIGURE_COMMAND ${CMAKE_SOURCE_DIR}/packages/libffi/configure --prefix=${CMAKE_BINARY_DIR}/libffi-install
    BUILD_COMMAND make
    INSTALL_COMMAND make install
    BUILD_IN_SOURCE 1
)
add_subdirectory(packages/gtest)

# Library
add_subdirectory(src)
# Ensure rffi depends on libffi_external
add_dependencies(rffi libffi_external)

# Tests
enable_testing()
add_subdirectory(tests/src)
