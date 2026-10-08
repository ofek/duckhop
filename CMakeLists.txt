cmake_minimum_required(VERSION 3.14...3.29)

project(duckhop LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(src/include)
set(EXTENSION_SOURCES src/duckhop_extension.cpp)

build_static_extension(duckhop ${EXTENSION_SOURCES})
build_loadable_extension(duckhop "" ${EXTENSION_SOURCES})

install(
    TARGETS duckhop_extension
    EXPORT "${DUCKDB_EXPORT_SET}"
    LIBRARY DESTINATION "${INSTALL_LIB_DIR}"
    ARCHIVE DESTINATION "${INSTALL_LIB_DIR}"
)
