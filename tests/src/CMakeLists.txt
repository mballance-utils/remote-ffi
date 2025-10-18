cmake_minimum_required(VERSION 3.10)
project(test_rffi CXX)

add_executable(test_rffi test_rffi.cpp)
add_dependencies(test_rffi gtest_external)
target_include_directories(test_rffi PRIVATE
    ${CMAKE_SOURCE_DIR}/../src/include
    ${CMAKE_BINARY_DIR}/gtest-install/include
)
target_link_libraries(test_rffi
    rffi
    ${CMAKE_BINARY_DIR}/gtest-install/lib/libgtest.a
    ${CMAKE_BINARY_DIR}/gtest-install/lib/libgtest_main.a
    pthread
)

add_test(NAME test_rffi COMMAND test_rffi)
