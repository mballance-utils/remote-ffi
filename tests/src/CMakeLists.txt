cmake_minimum_required(VERSION 3.10)

add_executable(test_rffi test_rffi.cpp)
target_include_directories(test_rffi PRIVATE
    ${CMAKE_SOURCE_DIR}/src/include
    ${CMAKE_SOURCE_DIR}/packages/gtest/include
)
target_link_libraries(test_rffi
    rffi
    gtest
    gtest_main
    pthread
)

add_test(NAME test_rffi COMMAND test_rffi)
