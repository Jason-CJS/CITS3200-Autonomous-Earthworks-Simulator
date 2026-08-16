cmake_minimum_required(VERSION 3.18)
cmake_policy(SET CMP0091 NEW)

project(AutonomousEarthworksSimulator LANGUAGES CXX)

option(AES_BUILD_TESTS "Build the headless Chrono acceptance test" ON)
option(AES_ENABLE_IRRLICHT "Build the demo with an interactive 3D window" OFF)
option(AES_ENABLE_SCM "Add SCM deformable terrain to the graphical excavator demo" OFF)

if(AES_ENABLE_SCM AND NOT AES_ENABLE_IRRLICHT)
    message(FATAL_ERROR "AES_ENABLE_SCM requires AES_ENABLE_IRRLICHT=ON")
endif()

if(AES_ENABLE_SCM)
    find_package(Chrono COMPONENTS Irrlicht Vehicle CONFIG REQUIRED)
elseif(AES_ENABLE_IRRLICHT)
    find_package(Chrono COMPONENTS Irrlicht CONFIG REQUIRED)
else()
    find_package(Chrono CONFIG REQUIRED)
endif()

set(AES_IRRLICHT_PLATFORM_LIBRARIES)
if(AES_ENABLE_IRRLICHT AND UNIX AND NOT APPLE)
    find_package(OpenGL REQUIRED)
    find_package(X11 REQUIRED)
    find_library(AES_XF86VM_LIBRARY NAMES Xxf86vm REQUIRED)
    list(APPEND AES_IRRLICHT_PLATFORM_LIBRARIES OpenGL::GL X11::X11 ${AES_XF86VM_LIBRARY})
endif()

add_library(aes_vehicles
    vehicles/common/DifferentialDriveFunctions.h
    vehicles/excavator/articulation/ExcavatorModel.cpp
)
target_include_directories(aes_vehicles PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(aes_vehicles PUBLIC cxx_std_17)
target_compile_definitions(aes_vehicles PRIVATE
    "AES_EXCAVATOR_ASSET_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/vehicles/excavator/model/assets/mathscavator9000\"")
target_link_libraries(aes_vehicles PUBLIC Chrono::Chrono_core)

add_executable(excavator_demo src/main.cpp)
target_link_libraries(excavator_demo PRIVATE aes_vehicles)

if(AES_ENABLE_SCM)
    add_library(aes_scm_demo src/SCMDemoTerrain.cpp)
    target_include_directories(aes_scm_demo PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
    target_compile_features(aes_scm_demo PUBLIC cxx_std_17)
    target_link_libraries(aes_scm_demo PUBLIC Chrono::Chrono_vehicle)

    target_compile_definitions(excavator_demo PRIVATE AES_ENABLE_SCM=1)
    target_link_libraries(excavator_demo PRIVATE aes_scm_demo)
endif()

if(AES_ENABLE_IRRLICHT)
    target_compile_definitions(excavator_demo PRIVATE
        AES_ENABLE_IRRLICHT=1
        "CHRONO_DATA_DIR=\"${CHRONO_DATA_DIR}\"")
    target_link_libraries(excavator_demo PRIVATE
        Chrono::Chrono_irrlicht ${AES_IRRLICHT_PLATFORM_LIBRARIES})
endif()

if(MSVC)
    set_target_properties(aes_vehicles excavator_demo PROPERTIES
        MSVC_RUNTIME_LIBRARY ${CHRONO_MSVC_RUNTIME_LIBRARY})
endif()

if(COMMAND add_CHRONO_DLLS_copy_command)
    add_CHRONO_DLLS_copy_command()
endif()

if(AES_BUILD_TESTS)
    enable_testing()
    add_executable(excavator_acceptance_test tests/excavator_acceptance_test.cpp)
    target_link_libraries(excavator_acceptance_test PRIVATE aes_vehicles)

    add_test(NAME excavator_loads_and_moves COMMAND excavator_acceptance_test)
    set(AES_TEST_NAMES excavator_loads_and_moves)

    if(AES_ENABLE_IRRLICHT)
        add_test(NAME excavator_graphics_smoke COMMAND excavator_demo --smoke-test)
        list(APPEND AES_TEST_NAMES excavator_graphics_smoke)
    endif()

    if(UNIX)
        set(AES_TEST_LIBRARY_PATH "$<TARGET_FILE_DIR:Chrono::Chrono_core>")
        if(AES_ENABLE_IRRLICHT)
            string(APPEND AES_TEST_LIBRARY_PATH ":$<TARGET_FILE_DIR:Irrlicht::Irrlicht>")
        endif()
        string(APPEND AES_TEST_LIBRARY_PATH ":$ENV{LD_LIBRARY_PATH}")
        set_tests_properties(${AES_TEST_NAMES} PROPERTIES
            ENVIRONMENT "LD_LIBRARY_PATH=${AES_TEST_LIBRARY_PATH}")
    endif()

    if(MSVC)
        set_target_properties(excavator_acceptance_test PROPERTIES
            MSVC_RUNTIME_LIBRARY ${CHRONO_MSVC_RUNTIME_LIBRARY})
    endif()
endif()
