cmake_minimum_required(VERSION 3.10)
project(rffi C)

add_library(rffi SHARED rffi.c cJSON.c)
target_include_directories(rffi PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_BINARY_DIR}/libffi-install/include
)

if(UNIX AND NOT APPLE)
    target_link_libraries(rffi PRIVATE dl)
endif()

# Link to the locally built libffi
if(APPLE)
    target_link_libraries(rffi PRIVATE
        ${CMAKE_BINARY_DIR}/libffi-install/lib/libffi.dylib
    )
else()
    target_link_libraries(rffi PRIVATE
        ${CMAKE_BINARY_DIR}/libffi-install/lib/libffi.so
    )
endif()

install(TARGETS rffi
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)

add_executable(test_target test_target.c)
